from __future__ import annotations

import sqlite3
from datetime import date, datetime
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"
DB_PATH = DATA_DIR / "work.db"


def today_iso() -> str:
    return date.today().isoformat()


def now_iso() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def _conn() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def init_db() -> None:
    con = _conn()
    cur = con.cursor()
    cur.executescript(
        """
        CREATE TABLE IF NOT EXISTS daily_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT UNIQUE NOT NULL,
            review TEXT DEFAULT '',
            done_items TEXT DEFAULT '',
            improvements TEXT DEFAULT '',
            unfinished TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            updated_at TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS todos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            priority TEXT DEFAULT 'medium',
            status TEXT DEFAULT 'pending',
            project TEXT DEFAULT '',
            due_date TEXT DEFAULT '',
            due_time TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            reminded_at TEXT DEFAULT '',
            created_at TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS improvements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            detail TEXT DEFAULT '',
            status TEXT DEFAULT 'open',
            source TEXT DEFAULT '',
            created_at TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            status TEXT DEFAULT 'active',
            progress INTEGER DEFAULT 0,
            current_task TEXT DEFAULT '',
            next_steps TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            updated_at TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        );
        """
    )
    con.commit()
    con.close()
    _seed_if_empty()


def get_settings() -> dict:
    con = _conn()
    rows = con.execute("SELECT key, value FROM settings").fetchall()
    con.close()
    return {r["key"]: r["value"] for r in rows}


def save_settings(payload: dict) -> dict:
    con = _conn()
    con.executemany(
        "INSERT INTO settings(key, value) VALUES(?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        list(payload.items()),
    )
    con.commit()
    con.close()
    return get_settings()


def public_settings() -> dict:
    s = get_settings()
    s["has_pushplus_token"] = bool(s.get("pushplus_token"))
    s["has_pushdeer_key"] = bool(s.get("pushdeer_key"))
    s["has_bark_key"] = bool(s.get("bark_key"))
    s["has_deepseek_key"] = bool(s.get("deepseek_key"))
    s.pop("pushplus_token", None)
    s.pop("pushdeer_key", None)
    s.pop("bark_key", None)
    s.pop("deepseek_key", None)
    return s


def _seed_if_empty() -> None:
    con = _conn()
    n = con.execute("SELECT COUNT(*) FROM todos").fetchone()[0]
    if n > 0:
        con.close()
        return
    today = today_iso()
    con.executemany(
        "INSERT INTO improvements(title, detail, status, source, created_at) VALUES(?,?,?,?,?)",
        [
            ("技能每轮只挂 7 本薄册，不灌整库", "前台 7 本省 token 薄册，其余走 skill-finder 先读 core.md 再查 catalog.md。", "open", "08-18 技能重构", now_iso()),
            ("ps1 脚本一律 UTF-8 带 BOM", "Windows 中文环境：无 BOM 会被 PowerShell 5.1 按 GBK 读成乱码。", "open", "08-18 喝水系统", now_iso()),
            ("token/隐私永不入库", "config 等含密文件 gitignore，泄露时用 git-filter-repo 重写历史 + force push。", "open", "08-18 隐私清理", now_iso()),
            ("慢操作本地化 + 显式反馈", "如「标为有用」从几十秒 fork 改为 ~40ms 本地标记，加徽章/筛选 + cache-busting。", "open", "08-18 日报优化", now_iso()),
            ("codex 技能预算靠削减加载量", "codex 元数据预算硬编码上下文 2%，只能禁插件/去重复/独立 junction 视图。", "open", "08-18 codex 修复", now_iso()),
        ],
    )
    con.executemany(
        "INSERT INTO projects(name, status, progress, current_task, next_steps, notes, updated_at) VALUES(?,?,?,?,?,?,?)",
        [
            ("技能库 global/skills", "active", 90, "Windows 已收敛 7 薄册 + skill-finder", "Mac 端历史清理 + 重跑 install-macos.sh；实测 skill-finder 一次完整调用", "唯一真源 = git 仓库 global-ai-skills", now_iso()),
            ("腾讯视频制作", "active", 70, "V1 成片完成，V2 隐晦表达补丁未产出", "补写 ao_collab/04_opencode_patch.md → 按补丁渲染 V2", "04_opencode_patch.md 昨天承诺写但实际没生成", now_iso()),
            ("github-star-digest 日报", "active", 85, "标为有用/接管/防重复已上", "重启网页 app 让 handoff 生效；观察每日 08:00 采集", "Token 已换 Classic repo", now_iso()),
            ("视频号运营", "active", 40, "申诉材料已备（200 字精简版）", "替换占位符后提交申诉；等待人工客服回复", "限流中，暂只发投资者教育内容", now_iso()),
        ],
    )
    todos = [
        ("Mac 端历史清理 + 双远端 force push", "high", "pending", "技能库", today, "08:00", "git fetch yj && git reset --hard yj/main && git push --force origin/yj main；push 前别跑 sync-skills.sh"),
        ("重启 opencode / Grok 让 7 薄册生效", "high", "pending", "技能库", today, "", "Windows 本地"),
        ("补写 ao_collab/04_opencode_patch.md", "medium", "pending", "腾讯视频制作", today, "", "读 tencent_video_build.ps1 + 03_final_script.txt，列删除直白夸赞最小改动"),
        ("按补丁渲染 V2（隐晦表达版）", "medium", "pending", "腾讯视频制作", today, "", "复用 08-18 制作管线"),
        ("重启 github-star-digest 网页 app", "low", "pending", "github-star-digest 日报", today, "", "让 handoff 接管机制生效"),
        ("提交视频号限流申诉", "low", "pending", "视频号运营", today, "", "200 字精简版，替换【】占位符"),
        ("WeChat 账户所有权验证回复", "low", "pending", "视频号运营", today, "", "填真实信息 + 附报错截图"),
    ]
    con.executemany(
        "INSERT INTO todos(title, priority, status, project, due_date, due_time, notes, created_at) VALUES(?,?,?,?,?,?,?,?)",
        [(t[0], t[1], t[2], t[3], t[4], t[5], t[6], now_iso()) for t in todos],
    )
    con.commit()
    con.close()


def upsert_log(row: dict) -> dict:
    con = _conn()
    con.execute(
        "INSERT INTO daily_logs(date, review, done_items, improvements, unfinished, notes, updated_at) "
        "VALUES(?,?,?,?,?,?,?) "
        "ON CONFLICT(date) DO UPDATE SET "
        "review=excluded.review, done_items=excluded.done_items, "
        "improvements=excluded.improvements, unfinished=excluded.unfinished, "
        "notes=excluded.notes, updated_at=excluded.updated_at",
        (
            row["date"],
            row.get("review", ""),
            row.get("done_items", ""),
            row.get("improvements", ""),
            row.get("unfinished", ""),
            row.get("notes", ""),
            now_iso(),
        ),
    )
    con.commit()
    con.close()
    return get_log(row["date"])


def get_log(log_date: str) -> dict:
    con = _conn()
    r = con.execute("SELECT * FROM daily_logs WHERE date=?", (log_date,)).fetchone()
    con.close()
    if r is None:
        return {"date": log_date, "review": "", "done_items": "", "improvements": "", "unfinished": "", "notes": ""}
    return dict(r)


def list_logs() -> list[dict]:
    con = _conn()
    rows = con.execute("SELECT date, updated_at, review FROM daily_logs ORDER BY date DESC").fetchall()
    con.close()
    return [dict(r) for r in rows]


def add_todo(row: dict) -> dict:
    con = _conn()
    cur = con.execute(
        "INSERT INTO todos(title, priority, status, project, due_date, due_time, notes, created_at) "
        "VALUES(?,?,?,?,?,?,?,?)",
        (
            row["title"],
            row.get("priority", "medium"),
            row.get("status", "pending"),
            row.get("project", ""),
            row.get("due_date", ""),
            row.get("due_time", ""),
            row.get("notes", ""),
            now_iso(),
        ),
    )
    con.commit()
    tid = cur.lastrowid
    con.close()
    return get_todo(tid)


def get_todo(tid: int) -> dict:
    con = _conn()
    r = con.execute("SELECT * FROM todos WHERE id=?", (tid,)).fetchone()
    con.close()
    return dict(r) if r else {}


def update_todo(tid: int, patch: dict) -> dict:
    con = _conn()
    fields = ["title", "priority", "status", "project", "due_date", "due_time", "notes", "reminded_at"]
    sets = [f"{f}=?" for f in fields if f in patch]
    if sets:
        con.execute(
            f"UPDATE todos SET {', '.join(sets)} WHERE id=?",
            [patch[f] for f in fields if f in patch] + [tid],
        )
    con.commit()
    con.close()
    return get_todo(tid)


def delete_todo(tid: int) -> None:
    con = _conn()
    con.execute("DELETE FROM todos WHERE id=?", (tid,))
    con.commit()
    con.close()


def list_todos(status: str = "", project: str = "", overdue_only: bool = False) -> list[dict]:
    con = _conn()
    q = "SELECT * FROM todos"
    conds = []
    args = []
    if status:
        conds.append("status=?")
        args.append(status)
    if project:
        conds.append("project=?")
        args.append(project)
    if overdue_only:
        conds.append("due_date<>'' AND due_date<=? AND status<>'done'")
        args.append(today_iso())
    if conds:
        q += " WHERE " + " AND ".join(conds)
    q += " ORDER BY CASE status WHEN 'done' THEN 1 ELSE 0 END, "
    q += "CASE priority WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END, due_date, id"
    rows = con.execute(q, args).fetchall()
    con.close()
    return [dict(r) for r in rows]


def add_improvement(row: dict) -> dict:
    con = _conn()
    cur = con.execute(
        "INSERT INTO improvements(title, detail, status, source, created_at) VALUES(?,?,?,?,?)",
        (
            row["title"],
            row.get("detail", ""),
            row.get("status", "open"),
            row.get("source", ""),
            now_iso(),
        ),
    )
    con.commit()
    con.close()
    return get_improvement(cur.lastrowid)


def get_improvement(iid: int) -> dict:
    con = _conn()
    r = con.execute("SELECT * FROM improvements WHERE id=?", (iid,)).fetchone()
    con.close()
    return dict(r) if r else {}


def update_improvement(iid: int, patch: dict) -> dict:
    con = _conn()
    fields = ["title", "detail", "status", "source"]
    sets = [f"{f}=?" for f in fields if f in patch]
    if sets:
        con.execute(
            f"UPDATE improvements SET {', '.join(sets)} WHERE id=?",
            [patch[f] for f in fields if f in patch] + [iid],
        )
    con.commit()
    con.close()
    return get_improvement(iid)


def delete_improvement(iid: int) -> None:
    con = _conn()
    con.execute("DELETE FROM improvements WHERE id=?", (iid,))
    con.commit()
    con.close()


def list_improvements(status: str = "") -> list[dict]:
    con = _conn()
    q = "SELECT * FROM improvements"
    if status:
        q += " WHERE status=?"
    q += " ORDER BY CASE status WHEN 'done' THEN 1 ELSE 0 END, id DESC"
    rows = con.execute(q, [status] if status else []).fetchall()
    con.close()
    return [dict(r) for r in rows]


def add_project(row: dict) -> dict:
    con = _conn()
    cur = con.execute(
        "INSERT INTO projects(name, status, progress, current_task, next_steps, notes, updated_at) "
        "VALUES(?,?,?,?,?,?,?)",
        (
            row["name"],
            row.get("status", "active"),
            int(row.get("progress", 0)),
            row.get("current_task", ""),
            row.get("next_steps", ""),
            row.get("notes", ""),
            now_iso(),
        ),
    )
    con.commit()
    con.close()
    return get_project(cur.lastrowid)


def get_project(pid: int) -> dict:
    con = _conn()
    r = con.execute("SELECT * FROM projects WHERE id=?", (pid,)).fetchone()
    con.close()
    return dict(r) if r else {}


def update_project(pid: int, patch: dict) -> dict:
    con = _conn()
    fields = ["name", "status", "progress", "current_task", "next_steps", "notes"]
    patch = dict(patch)
    if "progress" in patch:
        patch["progress"] = int(patch["progress"])
    patch["updated_at"] = now_iso()
    fields.append("updated_at")
    sets = [f"{f}=?" for f in fields if f in patch]
    if sets:
        con.execute(
            f"UPDATE projects SET {', '.join(sets)} WHERE id=?",
            [patch[f] for f in fields if f in patch] + [pid],
        )
    con.commit()
    con.close()
    return get_project(pid)


def delete_project(pid: int) -> None:
    con = _conn()
    con.execute("DELETE FROM projects WHERE id=?", (pid,))
    con.commit()
    con.close()


def list_projects(status: str = "") -> list[dict]:
    con = _conn()
    q = "SELECT * FROM projects"
    if status:
        q += " WHERE status=?"
    q += " ORDER BY CASE status WHEN 'active' THEN 0 ELSE 1 END, progress DESC, id"
    rows = con.execute(q, [status] if status else []).fetchall()
    con.close()
    return [dict(r) for r in rows]


def rollover(dry: bool = False) -> int:
    con = _conn()
    today = today_iso()
    rows = con.execute(
        "SELECT id, notes FROM todos WHERE status<>'done' AND due_date<>'' AND due_date<?",
        (today,),
    ).fetchall()
    count = len(rows)
    if not dry:
        for r in rows:
            notes = r["notes"] or ""
            if "昨日结转" not in notes:
                notes = (notes + "；" if notes else "") + "昨日结转"
            con.execute("UPDATE todos SET due_date=?, notes=? WHERE id=?", (today, notes, r["id"]))
        con.commit()
    con.close()
    return count


def carried_todos() -> list[dict]:
    return [t for t in list_todos() if t["status"] != "done" and "昨日结转" in (t["notes"] or "")]


def dashboard() -> dict:
    todos = list_todos()
    return {
        "today": today_iso(),
        "todo_counts": {
            "pending": sum(1 for t in todos if t["status"] == "pending"),
            "in_progress": sum(1 for t in todos if t["status"] == "in_progress"),
            "done": sum(1 for t in todos if t["status"] == "done"),
        },
        "overdue": sum(1 for t in todos if t["status"] != "done" and t["due_date"] and t["due_date"] <= today_iso()),
        "carried": len(carried_todos()),
        "improvements_open": sum(1 for i in list_improvements() if i["status"] == "open"),
        "projects_active": sum(1 for p in list_projects() if p["status"] == "active"),
        "today_todos": [t for t in todos if t["due_date"] == today_iso() and t["status"] != "done"],
        "today_log": get_log(today_iso()),
        "recent_logs": list_logs()[:5],
    }

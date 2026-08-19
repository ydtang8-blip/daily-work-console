from __future__ import annotations

import json
import os
import re
import glob
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import db

DEFAULT_DIRS = [
    r"C:\Users\43886\Documents\Default Project",
    r"C:\Users\43886\global\skills",
    r"C:\Users\43886\ao_collab",
    r"C:\Users\43886\finance-video-workstation",
    r"C:\Users\43886\github-star-digest",
    r"C:\Users\43886\tencent_video_ao",
    r"C:\Users\43886\screenshot-to-desktop",
    r"C:\Users\43886\memory-cleaner",
]

NOISE_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv", ".idea", "dist", "build", "bin", "obj", ".next", ".cache", "Temp"}
SKIP_EXT = {".pyc", ".log", ".tmp", ".swp", ".gitkeep"}

HOME = Path.home()
PS_READLINE_HISTORY = HOME / "AppData/Roaming/Microsoft/Windows/PowerShell/PSReadLine/ConsoleHost_history.txt"
CMD_HISTORY = HOME / "AppData/Roaming/Microsoft/Windows/Command Processor"  # placeholder, cmd 无持久历史


def _today_start() -> float:
    now = datetime.now()
    return datetime(now.year, now.month, now.day).timestamp()


def _fmt(ts: float) -> str:
    return datetime.fromtimestamp(ts).strftime("%H:%M")


def find_git_repos(roots: list[str]) -> list[str]:
    repos = set()
    for root in roots:
        root = Path(root)
        if not root.is_dir():
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            depth = len(Path(dirpath).relative_to(root).parts)
            if depth > 4:
                dirnames[:] = []
                continue
            if ".git" in dirnames:
                repos.add(dirpath)
                dirnames[:] = []
                continue
            dirnames[:] = [d for d in dirnames if d not in NOISE_DIRS]
    return sorted(repos)


def collect_git(dirs: list[str]) -> list[dict]:
    events = []
    since = datetime.now().strftime("%Y-%m-%d 00:00")
    until = datetime.now().strftime("%Y-%m-%d 23:59")
    for repo in find_git_repos(dirs):
        try:
            out = subprocess.run(
                ["git", "-C", repo, "log", f"--since={since}", f"--until={until}",
                 "--date=format:%H:%M", "--pretty=format:%ad|%s"],
                capture_output=True, text=True, timeout=20, encoding="utf-8", errors="replace",
            ).stdout.strip()
        except (subprocess.TimeoutExpired, OSError):
            continue
        if not out:
            continue
        name = Path(repo).name
        for line in out.splitlines():
            if "|" not in line:
                continue
            t, msg = line.split("|", 1)
            events.append({"time": t, "title": f"{name}: {msg.strip()[:80]}", "detail": repo})
    events.sort(key=lambda e: e.get("time", ""))
    return events


def collect_files(dirs: list[str]) -> list[dict]:
    events = []
    start = _today_start()
    for root in dirs:
        root = Path(root)
        if not root.is_dir():
            continue
        picked = []
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in NOISE_DIRS]
            for fn in filenames:
                if Path(fn).suffix.lower() in SKIP_EXT:
                    continue
                fp = os.path.join(dirpath, fn)
                try:
                    mtime = os.path.getmtime(fp)
                except OSError:
                    continue
                if mtime >= start:
                    rel = os.path.relpath(fp, root)
                    picked.append((mtime, rel, fp))
        picked.sort(reverse=True)
        for mtime, rel, fp in picked[:60]:
            events.append({"time": _fmt(mtime), "title": rel[:90], "detail": fp})
    events.sort(key=lambda e: e.get("time", ""))
    return events


def collect_terminal() -> list[dict]:
    events = []
    for path in [PS_READLINE_HISTORY]:
        if not path.exists():
            continue
        mtime = path.stat().st_mtime
        today = mtime >= _today_start()
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        lines = [l.strip() for l in lines if l.strip() and not l.strip().startswith("#")]
        for cmd in lines[-30:]:
            item = _chat_item(cmd)
            if item:
                events.append(item)
            else:
                events.append({
                    "time": _fmt(mtime) if today else "",
                    "title": cmd[:100],
                    "detail": "今天（PSReadLine 历史无精确时间戳）" if today else "较早",
                })
    return _dedup(events)


UUID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.I)
CODEX_SESSIONS = HOME / ".codex/sessions"
OPENCODE_DB = HOME / ".local/share/opencode/opencode.db"
GROK_SESSIONS = HOME / ".grok/sessions"
GROK_ACTIVE = HOME / ".grok/active_sessions.json"

_PII_PATTERNS = [
    (re.compile(r"(?<!\d)(1[3-9]\d)\d{4}(\d{4})(?!\d)"), r"\1****\2"),
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"), "***@***"),
    (re.compile(r"\b\d{17}[\dXx]\b"), "***身份证***"),
    (re.compile(r"\b\d{16,19}\b"), "***卡号***"),
    (re.compile(r"[¥￥$]\s?\d[\d,]*\.?\d*"), "***金额***"),
]


def _redact(text: str) -> str:
    for pat, rep in _PII_PATTERNS:
        text = pat.sub(rep, text)
    return text


def _chat_item(cmd: str) -> dict | None:
    low = cmd.lower()
    sid = ""
    m = UUID_RE.search(cmd)
    if m:
        sid = m.group(0)
    if "codex" in low:
        cid, summary = codex_channel(sid or None)
        title = "codex resume" if sid else "codex"
        key = ("codex", cid or sid or "bare")
    elif "opencode" in low:
        cid, summary = opencode_channel()
        title = "opencode"
        key = ("opencode", cid or "latest")
    elif "grok" in low:
        cid, summary = grok_channel()
        title = "grok"
        key = ("grok", cid or "latest")
    else:
        return None
    if summary and _is_sensitive(summary):
        return None
    if not summary:
        return {"time": "", "title": title, "detail": "（无会话记录）", "_key": key}
    detail = f"频道 {cid} · 内容：{_redact(summary)}" if cid else f"内容：{_redact(summary)}"
    return {"time": "", "title": title, "detail": detail, "_key": key}


def _dedup(events: list[dict]) -> list[dict]:
    final = []
    idx = {}
    for e in events:
        k = e.pop("_key", None)
        if not k:
            final.append(e)
            continue
        if k in idx:
            final[idx[k]] = e
        else:
            idx[k] = len(final)
            final.append(e)
    return final


def _sensitive_names() -> list[str]:
    raw = db.get_settings().get("sensitive_names", "")
    names = [n.strip() for n in raw.split(",") if n.strip()] if raw else ["家人"]
    return names


def _is_sensitive(text: str) -> bool:
    if not text:
        return False
    for name in _sensitive_names():
        if name and name in text:
            return True
    for pat, _ in _PII_PATTERNS:
        if pat.search(text):
            return True
    if re.search(r"(密码|password|身份证|银行卡|银行账户|验证码|私密|隐私)", text, re.I):
        return True
    return False


def codex_channel(session_id: str | None = None) -> tuple[str | None, str | None]:
    if session_id:
        pats = glob.glob(str(CODEX_SESSIONS / "**" / f"*{session_id}*"), recursive=True)
    else:
        pats = glob.glob(str(CODEX_SESSIONS / "**" / "rollout-*.jsonl"), recursive=True)
    if not pats:
        return None, None
    pats.sort(key=os.path.getmtime, reverse=True)
    fp = pats[0]
    m = UUID_RE.search(Path(fp).name)
    cid = m.group(0) if m else None
    first_user = None
    try:
        with open(fp, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if not line.strip():
                    continue
                try:
                    obj = json.loads(line)
                except ValueError:
                    continue
                pl = obj.get("payload")
                if not isinstance(pl, dict) or pl.get("role") != "user":
                    continue
                content = pl.get("content")
                if not isinstance(content, list):
                    continue
                text = " ".join(
                    c.get("text", "") for c in content
                    if isinstance(c, dict) and c.get("type") == "input_text" and c.get("text")
                ).strip()
                if text and "<environment_context>" not in text:
                    first_user = text
                    break
    except OSError:
        return cid, None
    if not first_user:
        return cid, None
    return cid, " ".join(first_user.split())[:80]


def opencode_channel() -> tuple[str | None, str | None]:
    if not OPENCODE_DB.exists():
        return None, None
    try:
        import sqlite3

        con = sqlite3.connect(str(OPENCODE_DB))
        con.row_factory = sqlite3.Row
        row = con.execute(
            "SELECT id, title FROM session WHERE title IS NOT NULL AND title<>'' ORDER BY time_updated DESC LIMIT 1"
        ).fetchone()
        con.close()
    except Exception:
        return None, None
    if not row:
        return None, None
    return row["id"], row["title"]


def grok_channel() -> tuple[str | None, str | None]:
    try:
        act = json.loads(GROK_ACTIVE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None, None
    if not isinstance(act, list):
        return None, None
    for a in act:
        sid = a.get("session_id")
        if not sid:
            continue
        for sp in glob.glob(str(GROK_SESSIONS / "**" / sid / "summary.json"), recursive=True):
            try:
                sm = json.load(open(sp, encoding="utf-8"))
            except (OSError, ValueError):
                continue
            title = sm.get("session_summary") or sm.get("title") or sm.get("summary") or ""
            if title:
                return sid, str(title).replace("<|eos|>", "").strip()[:80]
    return None, None


def collect() -> dict:
    settings = db.get_settings()
    raw = settings.get("activity_dirs", "")
    dirs = [d.strip() for d in raw.split(";") if d.strip()] if raw else DEFAULT_DIRS
    dirs = list(dict.fromkeys(dirs))
    events = {
        "git": collect_git(dirs),
        "files": collect_files(dirs),
        "terminal": collect_terminal(),
    }
    events["_dirs"] = dirs
    return events


def collect_and_store() -> dict:
    db.init_db()
    events = collect()
    db.save_activity(db.today_iso(), events)
    return {"date": db.today_iso(), "count": sum(len(v) for k, v in events.items() if k != "_dirs"), "events": events}


def summarize(events: dict) -> str:
    if not events:
        return ""
    lines = []
    git = events.get("git", [])
    files = events.get("files", [])
    term = events.get("terminal", [])
    if git:
        lines.append("今日 Git 提交：" + "；".join(e["title"] for e in git[:15]))
    if files:
        lines.append("今日改动的文件：" + "；".join(e["title"] for e in files[:15]))
    if term:
        lines.append("今日终端命令：" + "；".join(e["title"] for e in term[:15]))
    return "\n".join(lines)


def main() -> int:
    dry = "--dry-run" in sys.argv
    if dry:
        print(json.dumps(collect(), ensure_ascii=False, indent=2)[:3000])
        return 0
    if "--collect" in sys.argv or len(sys.argv) == 1:
        result = collect_and_store()
        print(json.dumps(result, ensure_ascii=False, indent=2)[:3000])
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
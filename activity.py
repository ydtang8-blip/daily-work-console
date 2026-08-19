from __future__ import annotations

import json
import os
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
        recent = lines[-30:]
        for cmd in recent:
            events.append({
                "time": _fmt(mtime) if today else "",
                "title": cmd[:100],
                "detail": ("今天（PSReadLine 历史无精确时间戳）" if today else "较早"),
            })
    return events


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
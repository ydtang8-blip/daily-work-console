from __future__ import annotations

import json
import sys
import urllib.parse
import urllib.request
from datetime import datetime

from db import get_log, get_settings, list_todos, today_iso, update_todo

PUSHPLUS_URL = "https://www.pushplus.plus/send"
PUSHDEER_URL = "https://api2.pushdeer.com/message/push"
BARK_URL = "https://api.day.app/push"


def send_pushplus(title: str, content: str, token: str) -> dict:
    body = json.dumps(
        {
            "token": token,
            "title": title,
            "content": content,
            "template": "html",
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        PUSHPLUS_URL,
        data=body,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def send_pushdeer(title: str, content: str, pushkey: str) -> dict:
    data = urllib.parse.urlencode(
        {"pushkey": pushkey, "text": title, "desp": content, "type": "markdown"}
    ).encode("utf-8")
    req = urllib.request.Request(
        PUSHDEER_URL, data=data, headers={"Content-Type": "application/x-www-form-urlencoded"}, method="POST"
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def send_bark(title: str, content: str, device_key: str) -> dict:
    body = json.dumps(
        {
            "device_key": device_key,
            "title": title,
            "body": content,
            "group": "工作台提醒",
            "sound": "critical",
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        BARK_URL, data=body, headers={"Content-Type": "application/json; charset=utf-8"}, method="POST"
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def dispatch(title: str, content: str, settings: dict) -> tuple[dict, str]:
    channel = settings.get("channel", "pushplus")
    if channel == "pushdeer":
        key = settings.get("pushdeer_key", "")
        if not key:
            return {"ok": False, "reason": "pushdeer_key 未配置"}, channel
        return send_pushdeer(title, content, key), channel
    if channel == "bark":
        key = settings.get("bark_key", "")
        if not key:
            return {"ok": False, "reason": "bark_key 未配置"}, channel
        return send_bark(title, content, key), channel
    token = settings.get("pushplus_token", "")
    if not token:
        return {"ok": False, "reason": "pushplus_token 未配置"}, channel
    return send_pushplus(title, content, token), channel


def _ok(result: dict, channel: str) -> bool:
    if channel == "pushplus":
        return result.get("code") == 200
    if channel == "pushdeer":
        if result.get("code") != 0:
            return False
        inner = result.get("content", {}).get("result")
        if isinstance(inner, list) and inner and isinstance(inner[0], str):
            try:
                return json.loads(inner[0]).get("success") == "ok"
            except (TypeError, ValueError):
                return False
        return isinstance(inner, list) and inner and inner[0] == "ok"
    if channel == "bark":
        return result.get("code") == 200
    return False


def due_todos() -> list[dict]:
    todos = list_todos()
    today = today_iso()
    return [
        t
        for t in todos
        if t["status"] != "done"
        and t["due_date"]
        and t["due_date"] <= today
        and (not t["reminded_at"] or not t["reminded_at"].startswith(today))
    ]


def build_content(todos: list[dict]) -> str:
    lines = []
    for t in todos:
        tag = {
            "high": "🔴",
            "medium": "🟠",
            "low": "⚪",
        }.get(t["priority"], "•")
        due = f"{t['due_date']}" + (f" {t['due_time']}" if t.get("due_time") else "")
        line = f"{tag} **{t['title']}**"
        if t.get("project"):
            line += f"（{t['project']}）"
        if due:
            line += f" 截止 {due}"
        lines.append(line)
    return "\n\n".join(lines)


def run(dry: bool = False) -> dict:
    settings = get_settings()
    hour = datetime.now().hour
    if hour < 8 or hour > 23:
        return {"ok": True, "sent": 0, "detail": "非推送时段(8-23点)"}
    todos = due_todos()
    if not todos:
        return {"ok": True, "sent": 0, "detail": "今日无到期待办"}
    title = settings.get("pushplus_title", "工作台提醒")
    result, channel = dispatch(title, build_content(todos), settings)
    if not result.get("ok") and result.get("reason"):
        return {"ok": False, "reason": result["reason"], "channel": channel}
    if _ok(result, channel) and not dry:
        for t in todos:
            update_todo(t["id"], {"reminded_at": today_iso()})
    return {"ok": True, "sent": len(todos), "channel": channel, "result": result, "todos": todos}


def morning_summary() -> dict:
    settings = get_settings()
    todos = list_todos()
    today = today_iso()
    due = [t for t in todos if t["status"] != "done" and t["due_date"] == today]
    overdue = [t for t in todos if t["status"] != "done" and t["due_date"] and t["due_date"] < today]
    if not due and not overdue:
        return {"ok": True, "sent": 0, "detail": "今日无待办"}
    blocks = []
    if due:
        blocks.append("**今日待办**\n\n" + build_content(due))
    if overdue:
        blocks.append("**已逾期（快去补）**\n\n" + build_content(overdue))
    result, channel = dispatch(settings.get("pushplus_title", "工作台提醒") + " · 今日待办", "\n\n---\n\n".join(blocks), settings)
    return {"ok": True, "sent": len(due), "channel": channel, "result": result}


def evening_nudge() -> dict:
    settings = get_settings()
    today = today_iso()
    log = get_log(today)
    if log:
        return {"ok": True, "sent": 0, "detail": "今日复盘已写"}
    content = "今天的复盘还没写，去工作台花 2 分钟记录：\n\n- 今天完成了什么\n- 想到哪些改进点\n- 哪些还没做完，明天继续"
    result, channel = dispatch(settings.get("pushplus_title", "工作台提醒") + " · 该写复盘了", content, settings)
    return {"ok": True, "sent": 1, "channel": channel, "result": result}


def main() -> int:
    dry = "--dry-run" in sys.argv
    if "--test" in sys.argv:
        settings = get_settings()
        result, channel = dispatch(
            settings.get("pushplus_title", "工作台提醒"),
            "测试消息：工作台提醒通道正常 ✅",
            settings,
        )
        print(json.dumps({"channel": channel, "result": result}, ensure_ascii=False))
        return 0 if _ok(result, channel) else 1
    if "--morning" in sys.argv:
        print(json.dumps(morning_summary(), ensure_ascii=False, indent=2))
        return 0
    if "--evening" in sys.argv:
        print(json.dumps(evening_nudge(), ensure_ascii=False, indent=2))
        return 0
    if "--check" in sys.argv:
        print(json.dumps(due_todos(), ensure_ascii=False, indent=2))
        return 0
    print(json.dumps(run(dry=dry), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
from __future__ import annotations

import json
import urllib.request

from db import get_settings

DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"
DEFAULT_MODEL = "deepseek-chat"

SYSTEM_PROMPT = (
    "你是个人效率复盘助手。根据用户提供的一天工作数据，写一份简洁、具体、可执行的每日复盘。"
    "要求：1) 用中文；2) 分四段：完成情况、问题与反思、明天最重要的一件事、一句话总结；"
    "3) 不吹捧、不编造数据、不写用户没做的事；4) 总长度不超过 350 字。"
)


def generate_review(done: list[str], unfinished: list[str], improvements: list[str], context: str = "") -> str:
    settings = get_settings()
    key = settings.get("deepseek_key", "")
    if not key:
        raise RuntimeError("deepseek_key 未配置，请在设置页填写 DeepSeek API Key")

    parts = []
    if context:
        parts.append(context)
    parts.append(f"【今日完成】\n" + ("\n".join(done) if done else "（无）"))
    parts.append(f"【未完成/遗留】\n" + ("\n".join(unfinished) if unfinished else "（无）"))
    parts.append(f"【改进点/反思】\n" + ("\n".join(improvements) if improvements else "（无）"))
    user_prompt = "\n\n".join(parts)

    body = json.dumps(
        {
            "model": DEFAULT_MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.7,
            "max_tokens": 800,
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        DEEPSEEK_URL,
        data=body,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"DeepSeek 接口错误 {e.code}: {detail}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"DeepSeek 网络错误: {e.reason}") from e

    try:
        return data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError(f"DeepSeek 返回异常: {json.dumps(data, ensure_ascii=False)[:300]}") from exc


def build_today_context() -> str:
    from db import get_log, list_projects, list_todos, today_iso
    import activity
    import db

    today = today_iso()
    todos = list_todos()
    today_todos = [t for t in todos if t["due_date"] == today]
    done_today = [t for t in todos if t["status"] == "done"]
    projects = list_projects()
    active = [p for p in projects if p["status"] == "active"]

    lines = [f"今天是 {today}。"]
    if today_todos:
        lines.append("今日待办：" + "；".join(f"{t['title']}({t['status']})" for t in today_todos))
    if done_today:
        lines.append("今天已完成：" + "；".join(t["title"] for t in done_today[:10]))
    if active:
        lines.append("进行中项目：" + "；".join(p["name"] for p in active))
    stored = db.get_activity(today)
    if stored and stored.get("events"):
        act_summary = activity.summarize(stored["events"])
        if act_summary:
            lines.append("【电脑活动采集】" + act_summary)
    log = get_log(today)
    if log and (log.get("review") or log.get("notes")):
        lines.append(f"今日已有草稿备注：{log.get('review') or log.get('notes')}")
    return "\n".join(lines)


def auto_draft() -> dict:
    from db import get_log, today_iso

    today = today_iso()
    log = get_log(today)
    done = [s for s in (log.get("done_items") or "").splitlines() if s.strip()] if log else []
    unfinished = [s for s in (log.get("unfinished") or "").splitlines() if s.strip()] if log else []
    improvements = [s for s in (log.get("improvements") or "").splitlines() if s.strip()] if log else []
    context = build_today_context()
    review = generate_review(done, unfinished, improvements, context)
    return {"review": review, "done_items": "\n".join(done), "unfinished": "\n".join(unfinished), "improvements": "\n".join(improvements)}


def main() -> int:
    import sys

    if "--test" in sys.argv:
        try:
            result = auto_draft()
            print(result["review"])
            return 0
        except RuntimeError as e:
            print(f"错误: {e}")
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
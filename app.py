from __future__ import annotations

import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import db
import deepseek
import reminder
import skills_index
import activity

BASE_DIR = Path(__file__).resolve().parent
WEB_DIR = BASE_DIR / "web"

db.init_db()
db.rollover()

app = FastAPI(title="每日工作台", docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=str(WEB_DIR / "static")), name="static")


@app.middleware("http")
async def no_cache(request: Request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    return response


class LogIn(BaseModel):
    date: str
    review: str = ""
    done_items: str = ""
    improvements: str = ""
    unfinished: str = ""
    notes: str = ""


class TodoIn(BaseModel):
    title: str
    priority: str = "medium"
    status: str = "pending"
    project: str = ""
    due_date: str = ""
    due_time: str = ""
    notes: str = ""


class ImprovementIn(BaseModel):
    title: str
    detail: str = ""
    status: str = "open"
    source: str = ""


class ProjectIn(BaseModel):
    name: str
    status: str = "active"
    progress: int = 0
    current_task: str = ""
    next_steps: str = ""
    notes: str = ""


class SettingsIn(BaseModel):
    channel: str | None = None
    pushplus_token: str | None = None
    pushplus_title: str | None = None
    pushdeer_key: str | None = None
    bark_key: str | None = None
    deepseek_key: str | None = None
    skills_path: str | None = None
    activity_dirs: str | None = None
    sensitive_names: str | None = None
    port: str | None = None


@app.get("/")
def index() -> FileResponse:
    return FileResponse(WEB_DIR / "templates" / "index.html")


@app.get("/api/health")
def api_health() -> dict:
    return {"ok": True, "today": db.today_iso()}


@app.get("/api/skill-content")
def api_skill_content(path: str) -> dict:
    root = Path(db.get_settings().get("skills_path") or skills_index.DEFAULT_SKILLS_PATH).expanduser()
    target = Path(path).resolve()
    try:
        target.relative_to(root.resolve())
    except ValueError as exc:
        raise HTTPException(400, "路径不在技能库内") from exc
    if not target.is_file() or target.name.lower() != "skill.md":
        raise HTTPException(400, "只能查看 SKILL.md 文件")
    return {"content": target.read_text(encoding="utf-8", errors="replace")[:20000]}


@app.get("/api/dashboard")
def api_dashboard() -> dict:
    return db.dashboard()


@app.get("/api/logs")
def api_logs() -> dict:
    return {"logs": db.list_logs()}


@app.get("/api/logs/{log_date}")
def api_log(log_date: str) -> dict:
    return db.get_log(log_date)


@app.post("/api/logs")
def api_save_log(body: LogIn) -> dict:
    return db.upsert_log(body.model_dump())


@app.get("/api/todos")
def api_todos(status: str = "", project: str = "", overdue_only: bool = False) -> dict:
    return {"todos": db.list_todos(status=status, project=project, overdue_only=overdue_only)}


@app.post("/api/todos")
def api_add_todo(body: TodoIn) -> dict:
    if not body.title.strip():
        raise HTTPException(400, "待办内容不能为空")
    return db.add_todo(body.model_dump())


@app.post("/api/todos/rollover")
def api_todos_rollover() -> dict:
    count = db.rollover()
    return {"ok": True, "rolled": count}


@app.post("/api/todos/from-project/{pid}")
def api_todo_from_project(pid: int) -> dict:
    project = db.get_project(pid)
    if not project:
        raise HTTPException(404, "项目不存在")
    steps = project.get("next_steps", "")
    if not steps.strip():
        raise HTTPException(400, "该项目没有下一步计划")
    todo = db.add_todo(
        {
            "title": steps.strip()[:100],
            "priority": "medium",
            "status": "pending",
            "project": project["name"],
            "due_date": db.today_iso(),
            "due_time": "",
            "notes": f"来自项目《{project['name']}》的下一步",
        }
    )
    return todo


@app.put("/api/todos/{tid}")
def api_update_todo(tid: int, body: TodoIn) -> dict:
    if not db.get_todo(tid):
        raise HTTPException(404, "待办不存在")
    return db.update_todo(tid, body.model_dump())


@app.post("/api/todos/{tid}/toggle")
def api_toggle_todo(tid: int) -> dict:
    todo = db.get_todo(tid)
    if not todo:
        raise HTTPException(404, "待办不存在")
    status = "pending" if todo["status"] == "done" else "done"
    return db.update_todo(tid, {"status": status})


@app.delete("/api/todos/{tid}")
def api_delete_todo(tid: int) -> dict:
    db.delete_todo(tid)
    return {"ok": True}


@app.get("/api/improvements")
def api_improvements(status: str = "") -> dict:
    return {"improvements": db.list_improvements(status=status)}


@app.post("/api/improvements")
def api_add_improvement(body: ImprovementIn) -> dict:
    if not body.title.strip():
        raise HTTPException(400, "改进点标题不能为空")
    return db.add_improvement(body.model_dump())


@app.put("/api/improvements/{iid}")
def api_update_improvement(iid: int, body: ImprovementIn) -> dict:
    if not db.get_improvement(iid):
        raise HTTPException(404, "改进点不存在")
    return db.update_improvement(iid, body.model_dump())


@app.post("/api/improvements/{iid}/toggle")
def api_toggle_improvement(iid: int) -> dict:
    item = db.get_improvement(iid)
    if not item:
        raise HTTPException(404, "改进点不存在")
    status = "open" if item["status"] == "done" else "done"
    return db.update_improvement(iid, {"status": status})


@app.delete("/api/improvements/{iid}")
def api_delete_improvement(iid: int) -> dict:
    db.delete_improvement(iid)
    return {"ok": True}


@app.get("/api/projects")
def api_projects(status: str = "") -> dict:
    return {"projects": db.list_projects(status=status)}


@app.post("/api/projects")
def api_add_project(body: ProjectIn) -> dict:
    if not body.name.strip():
        raise HTTPException(400, "项目名不能为空")
    return db.add_project(body.model_dump())


@app.put("/api/projects/{pid}")
def api_update_project(pid: int, body: ProjectIn) -> dict:
    if not db.get_project(pid):
        raise HTTPException(404, "项目不存在")
    return db.update_project(pid, body.model_dump())


@app.delete("/api/projects/{pid}")
def api_delete_project(pid: int) -> dict:
    db.delete_project(pid)
    return {"ok": True}


@app.get("/api/skills")
def api_skills(q: str = "") -> dict:
    path = db.get_settings().get("skills_path", "")
    return {
        "skills": skills_index.search(q=q, path=path),
        "counts": skills_index.counts(path=path),
    }


@app.get("/api/settings")
def api_settings() -> dict:
    return db.public_settings()


@app.post("/api/settings")
def api_save_settings(body: SettingsIn) -> dict:
    payload = body.model_dump(exclude_none=True)
    for key in ("pushplus_token", "pushdeer_key", "bark_key", "deepseek_key"):
        if payload.get(key) == "********":
            payload.pop(key)
    db.save_settings(payload)
    return db.public_settings()


@app.post("/api/reminders/test")
def api_reminder_test() -> dict:
    settings = db.get_settings()
    if not settings.get("channel") or settings.get("channel") == "pushplus":
        if not settings.get("pushplus_token"):
            raise HTTPException(400, "请先配置所选通道的凭证")
    result, channel = reminder.dispatch(
        settings.get("pushplus_title", "工作台提醒"),
        "测试消息：工作台提醒通道正常 ✅",
        settings,
    )
    if result.get("reason") or not reminder._ok(result, channel):
        raise HTTPException(502, f"推送失败：{result}")
    return {"ok": True, "channel": channel, "result": result}


@app.get("/api/reminders/due")
def api_reminders_due() -> dict:
    return {"todos": reminder.due_todos()}


@app.post("/api/reviews/ai")
def api_review_ai() -> dict:
    if not db.get_settings().get("deepseek_key"):
        raise HTTPException(400, "请先在设置页填写 DeepSeek API Key")
    try:
        result = deepseek.auto_draft()
    except RuntimeError as e:
        raise HTTPException(502, str(e)) from e
    return result


@app.post("/api/activity/collect")
def api_activity_collect() -> dict:
    try:
        return activity.collect_and_store()
    except Exception as e:
        raise HTTPException(500, f"采集失败：{e}") from e


@app.get("/api/activity")
def api_activity_list() -> dict:
    return {"days": db.list_activity()}


@app.get("/api/activity/{day}")
def api_activity_get(day: str) -> dict:
    return db.get_activity(day)


def main() -> None:
    import uvicorn

    port = int(db.get_settings().get("port") or 8789)
    uvicorn.run("app:app", host="127.0.0.1", port=port, reload=False)


if __name__ == "__main__":
    sys.exit(main() or 0)

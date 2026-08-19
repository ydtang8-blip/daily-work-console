# 每日工作台

本地网页工作台：管理 **每日复盘 / 待办 / 改进点 / 项目进度 / 技能库联动 / 微信提醒**。

## 启动

双击 `run.cmd`，或：

```powershell
cd "C:\Users\43886\Documents\Default Project\daily-work-console"
python app.py
```

浏览器打开 `http://127.0.0.1:8789`。

## 功能

| 页签 | 说明 |
| --- | --- |
| 首页 | 今日待办、逾期数、活跃项目、今日复盘、最近记录 |
| 待办 | 增删改、优先级、截止日期、按状态/逾期筛选，逾期可推送微信 |
| 复盘 | 按日期写复盘（总结/完成/改进点/遗留），改进点与遗留可一键转存 |
| 改进点 | 记录"思考到的改进"，落实后打勾 |
| 项目 | 每个项目的进度、当前任务、下一步 |
| 技能库 | 扫描 `C:\Users\43886\global\skills`，搜索/按位置筛（核心/顶层/图书馆），点击查看 SKILL.md |
| 设置 | PushPlus Token（微信提醒）、技能库路径、端口、测试推送 |

## 微信提醒（PushPlus）

1. 到 `https://www.pushplus.plus/` 用微信扫码登录，拿 token。
2. 网页「设置」里填 token → 保存 → 「发测试推送」确认微信能收到。
3. 安装定时任务（每 30 分钟检查一次到期待办，8:00–23:00 推送）：

```powershell
powershell -ExecutionPolicy Bypass -File "C:\Users\43886\Documents\Default Project\daily-work-console\install-reminder.ps1"
```

卸载：`install-reminder.ps1 -Uninstall`。

手动命令：

```powershell
python reminder.py --check   # 只看当前到期待办，不推送
python reminder.py           # 立即推送一次
python reminder.py --test    # 发一条测试消息
```

## 数据

全部存在本地 SQLite：`data/work.db`（token 不入库，放设置表里但 API 不回传明文；含密配置请勿推送到公开仓库）。

## 端口

默认 `8789`，可在「设置」里改，改完重启服务生效。
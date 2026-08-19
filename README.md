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
| 复盘 | 按日期写复盘（总结/完成/改进点/遗留），改进点与遗留可一键转存；「AI 生成复盘」用 DeepSeek 自动起草 |
| 改进点 | 记录"思考到的改进"，落实后打勾 |
| 项目 | 每个项目的进度、当前任务、下一步，下一步可一键转待办 |
| 技能库 | 扫描 `C:\Users\43886\global\skills`，搜索/按位置筛（核心/顶层/图书馆），点击查看 SKILL.md |
| 设置 | 提醒通道（PushDeer/Bark/PushPlus）、DeepSeek Key、技能库路径、端口、测试推送 |

## 提醒（手机弹窗：PushDeer / Bark / PushPlus）

在网页「设置」里选通道并填凭证：

- **PushDeer**（iPhone/安卓系统通知弹窗，推荐）：App Store 装 PushDeer，复制 PushKey（`PDU…`）
- **Bark**（仅 iPhone，可静音响铃）：装 Bark App，复制设备 Key
- **PushPlus**（微信服务号，不弹窗）：`https://www.pushplus.plus/` 扫码拿 token

保存后点「发测试推送」确认手机能收到。

安装定时任务（3 个）：

```powershell
powershell -ExecutionPolicy Bypass -File "C:\Users\43886\Documents\Default Project\daily-work-console\install-reminder.ps1"
```

- **WorkConsoleMorning** 每天 08:00 推送「今日待办 + 逾期」
- **WorkConsoleReminder** 每 30 分钟检查到期待办（8:00–23:00）
- **WorkConsoleEvening** 每天 21:00 提醒写复盘，配了 DeepSeek Key 则自动起草草稿一起推送

卸载：`install-reminder.ps1 -Uninstall`。

手动命令：

```powershell
python reminder.py --check     # 只看当前到期待办，不推送
python reminder.py --morning   # 推送今日待办 + 逾期
python reminder.py --test      # 发一条测试消息
```

## AI 写复盘（DeepSeek）

1. 「设置」填 DeepSeek API Key（`https://platform.deepseek.com` 创建，`sk-…`）
2. 「复盘」页点 **AI 生成复盘**：自动读取今日待办/已完成/项目状态，起草四段式复盘，可修改后保存
3. 21:00 晚间提醒也会带上 AI 草稿（未写复盘时）

## 数据

全部存在本地 SQLite：`data/work.db`（API Key / token 只存设置表，API 不回传明文，已加 `.gitignore` 排除）。

## 端口

默认 `8789`，可在「设置」里改，改完重启服务生效。
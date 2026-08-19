param(
    [switch]$Uninstall
)

$ErrorActionPreference = "Stop"
$Proj = "C:\Users\43886\Documents\Default Project\daily-work-console"
$Py = (Get-Command python).Source

if ($Uninstall) {
    foreach ($t in "WorkConsoleReminder", "WorkConsoleMorning", "WorkConsoleEvening", "WorkConsoleActivity") {
        Unregister-ScheduledTask -TaskName $t -Confirm:$false -ErrorAction SilentlyContinue
        Write-Output "已卸载 $t"
    }
    exit 0
}

$Reminder = New-ScheduledTaskAction -Execute $Py -Argument "`"$Proj\reminder.py`"" -WorkingDirectory $Proj
$Start = Get-Date "00:00"
$Trig30 = New-ScheduledTaskTrigger -Once -At $Start -RepetitionInterval (New-TimeSpan -Minutes 30) -RepetitionDuration (New-TimeSpan -Days 365)
$Settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 5)
Register-ScheduledTask -TaskName "WorkConsoleReminder" -Action $Reminder -Trigger $Trig30 -Settings $Settings -Force | Out-Null
Write-Output "已安装 WorkConsoleReminder（每 30 分钟检查一次到期待办，仅 8:00-23:00 推送）"

$Morning = New-ScheduledTaskAction -Execute $Py -Argument "`"$Proj\reminder.py`" --morning" -WorkingDirectory $Proj
$TrigMorning = New-ScheduledTaskTrigger -Daily -At 08:00
Register-ScheduledTask -TaskName "WorkConsoleMorning" -Action $Morning -Trigger $TrigMorning -Settings $Settings -Force | Out-Null
Write-Output "已安装 WorkConsoleMorning（每天 08:00 推送今日待办 + 逾期）"

$Evening = New-ScheduledTaskAction -Execute $Py -Argument "`"$Proj\reminder.py`" --evening" -WorkingDirectory $Proj
$TrigEvening = New-ScheduledTaskTrigger -Daily -At 21:00
Register-ScheduledTask -TaskName "WorkConsoleEvening" -Action $Evening -Trigger $TrigEvening -Settings $Settings -Force | Out-Null
Write-Output "已安装 WorkConsoleEvening（每天 21:00 提醒写复盘，已写则跳过）"

$Activity = New-ScheduledTaskAction -Execute $Py -Argument "`"$Proj\activity.py`" --collect" -WorkingDirectory $Proj
$TrigActivity = New-ScheduledTaskTrigger -Daily -At 20:30
Register-ScheduledTask -TaskName "WorkConsoleActivity" -Action $Activity -Trigger $TrigActivity -Settings $Settings -Force | Out-Null
Write-Output "已安装 WorkConsoleActivity（每天 20:30 采集今日电脑活动，供 AI 复盘引用）"

& $Py "`"$Proj\reminder.py`"" --check
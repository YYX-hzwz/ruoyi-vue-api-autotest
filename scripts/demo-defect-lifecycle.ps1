# 缺陷生命周期演示：同一套用例，在"缺陷存在"和"缺陷修复"两种状态下各跑一次
#
#   .\scripts\demo-defect-lifecycle.ps1
#
# 预期输出：
#   第一次（BUGS=true）  -> 144 passed, 3 xfailed
#   第二次（BUGS=false） -> 144 passed, 3 xpassed，并提示"请移除 xfail 标记"
#
# 这就是"缺陷被写成会红的用例，修复后转绿"的完整闭环，
# 比在报告里写一句"已发现 4 个缺陷"有说服力得多。

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$env:PYTHONIOENCODING = "utf-8"
$env:AUTOTEST_TARGET = "stub"

function Show-Result([string]$label, [string]$summaryPath) {
    if (-not (Test-Path $summaryPath)) { return }
    $data = Get-Content $summaryPath -Raw -Encoding UTF8 | ConvertFrom-Json
    Write-Host ""
    Write-Host "──── $label ────" -ForegroundColor Cyan
    $t = $data.totals
    Write-Host ("passed={0}  failed={1}  xfailed={2}  xpassed={3}" -f [int]$t.passed, [int]$t.failed, [int]$t.xfailed, [int]$t.xpassed)
    foreach ($d in $data.defects) {
        Write-Host ("  {0} [{1}] {2} -> {3}" -f $d.id, $d.severity, $d.title, $d.observed)
    }
}

Write-Host "======== 第 1 轮：缺陷存在 ========" -ForegroundColor Yellow
$env:AUTOTEST_STUB_REPRODUCE_BUGS = "true"
& py -m pytest -q
Copy-Item "reports/summary.json" "reports/summary-with-defects.json" -Force
Copy-Item "reports/report.html" "reports/report-with-defects.html" -Force
Show-Result "缺陷存在" "reports/summary-with-defects.json"

Write-Host "======== 第 2 轮：缺陷修复 ========" -ForegroundColor Yellow
$env:AUTOTEST_STUB_REPRODUCE_BUGS = "false"
& py -m pytest -q
Copy-Item "reports/summary.json" "reports/summary-fixed.json" -Force
Copy-Item "reports/report.html" "reports/report-fixed.html" -Force
Show-Result "缺陷修复" "reports/summary-fixed.json"

Write-Host ""
Write-Host "对比两份报告：" -ForegroundColor Green
Write-Host "  reports/report-with-defects.html  （3 条 xfail）"
Write-Host "  reports/report-fixed.html         （3 条 xpass）"

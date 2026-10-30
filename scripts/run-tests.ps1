# 一键跑用例（默认跑内置契约桩，不需要任何外部依赖）
#
#   .\scripts\run-tests.ps1                     # 全量
#   .\scripts\run-tests.ps1 -Marker contract    # 只跑契约测试
#   .\scripts\run-tests.ps1 -Fixed              # 模拟"缺陷已修复"，观察 xfail -> xpass
#   .\scripts\run-tests.ps1 -Args "-k","user"   # 透传任意 pytest 参数
#
# 说明：控制台编码统一为 UTF-8，避免 Windows GBK 下的中文乱码。

param(
    [ValidateSet("stub", "real")]
    [string]$Target = "stub",

    [switch]$Fixed,

    [string]$BaseUrl = "http://localhost:8080",

    [string]$Marker = "",

    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$PytestArgs
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$env:PYTHONIOENCODING = "utf-8"
$env:AUTOTEST_TARGET = $Target
$env:AUTOTEST_BASE_URL = $BaseUrl

if ($Fixed) {
    $env:AUTOTEST_STUB_REPRODUCE_BUGS = "false"
    Write-Host "[run-tests] 缺陷复现已关闭：预期 3 条缺陷用例从 xfail 变为 xpass" -ForegroundColor Yellow
}

$pytest = @("-m", "pytest")

if ($Target -eq "real") {
    Write-Host "[run-tests] 目标：真实后端 $BaseUrl" -ForegroundColor Cyan
}

$extra = @()
if ($Marker) { $extra += @("-m", $Marker) }
if ($PytestArgs) { $extra += $PytestArgs }

& py @pytest @extra
$code = $LASTEXITCODE

Write-Host ""
Write-Host "[run-tests] 退出码: $code" -ForegroundColor $(if ($code -eq 0) { "Green" } else { "Red" })
Write-Host "[run-tests] 报告: reports/report.html | reports/QUALITY.md | reports/summary.json"
exit $code

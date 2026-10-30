# 起真实 RuoYi 后端并跑全量用例
#
# 前置：
#   1. Docker Desktop 已启动
#   2. RuoYi-Vue 源码在 RUOYI_HOME（默认 ../../，即项目的上一级目录）
#
#   .\scripts\run-real.ps1              # 起依赖 + 后端，跑全量
#   .\scripts\run-real.ps1 -InfraOnly   # 只起 MySQL/Redis，后端用 IDE 单独跑
#   .\scripts\run-real.ps1 -Down        # 停止并清理数据卷

param(
    [switch]$InfraOnly,
    [switch]$Down,
    [string]$BaseUrl = "http://localhost:8080"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$compose = @("-f", "docker/docker-compose.yml")
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "[run-real] 已从 .env.example 生成 .env" -ForegroundColor Yellow
}

if ($Down) {
    docker compose @compose --profile backend down -v
    exit $LASTEXITCODE
}

if (-not $env:RUOYI_HOME) {
    $env:RUOYI_HOME = (Resolve-Path (Join-Path $root "..\..")).Path
}
Write-Host "[run-real] RUOYI_HOME=$env:RUOYI_HOME" -ForegroundColor Cyan

# 1) 起 MySQL + Redis + 建库导数据
docker compose @compose --env-file .env up -d mysql redis db-init
if ($LASTEXITCODE -ne 0) { throw "依赖服务启动失败" }

Write-Host "[run-real] 等待 db-init 完成..." -ForegroundColor Cyan
docker compose @compose --env-file .env logs -f db-init

if ($InfraOnly) {
    Write-Host "[run-real] 只起了依赖。请在 RuoYi 源码里用 IDE 或 mvn 启动后端：" -ForegroundColor Yellow
    Write-Host "           cd \$env:RUOYI_HOME; mvn -pl ruoyi-admin spring-boot:run"
    exit 0
}

# 2) 构建并启动后端
docker compose @compose --env-file .env --profile backend up -d --build ruoyi
if ($LASTEXITCODE -ne 0) { throw "后端构建/启动失败" }

# 3) 等健康检查
Write-Host "[run-real] 等待后端就绪（最长 180s）..." -ForegroundColor Cyan
$ready = $false
for ($i = 0; $i -lt 60; $i++) {
    try {
        $r = Invoke-WebRequest -Uri "$BaseUrl/captchaImage" -TimeoutSec 3 -UseBasicParsing
        if ($r.StatusCode -eq 200) { $ready = $true; break }
    } catch { Start-Sleep -Seconds 3 }
}
if (-not $ready) {
    docker compose @compose --env-file .env logs --no-color ruoyi
    throw "后端未就绪"
}

# 4) 跑用例
& "$PSScriptRoot\run-tests.ps1" -Target real -BaseUrl $BaseUrl
exit $LASTEXITCODE

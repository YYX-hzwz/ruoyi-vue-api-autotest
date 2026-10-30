# 把这次重构整理成 6 个有意义的提交（而不是一个 "update" 大提交）
#
# 为什么需要这个脚本：
#   招聘方会看 git log。一个 43 文件的 commit 说明不了工程习惯，
#   而"清理 -> 框架 -> 领域层 -> 桩 -> 用例 -> CI/文档"的演进过程本身就是作品的一部分。
#
# 使用前先把身份改成你自己的（当前仓库里还是占位符）：
#   git config user.name  "你的名字"
#   git config user.email "你的邮箱"
#
# 然后（在项目根目录）：
#   .\scripts\commit-history.ps1
#
# 只想看看会做什么，不实际提交：
#   .\scripts\commit-history.ps1 -DryRun

param(
    [switch]$DryRun,
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$name = (git config user.name) 2>$null
$email = (git config user.email) 2>$null
if (-not $Force -and ("$name" -match "你的名字" -or "$email" -match "你的邮箱")) {
    Write-Host "[commit] git 身份还是占位符：'$name <$email>'" -ForegroundColor Red
    Write-Host "         先执行：" -ForegroundColor Yellow
    Write-Host '           git config user.name  "你的名字"' -ForegroundColor Yellow
    Write-Host '           git config user.email "你的邮箱"' -ForegroundColor Yellow
    Write-Host "         确认要直接用当前身份提交，加 -Force" -ForegroundColor Yellow
    exit 1
}

$commits = @(
    @{
        message = "chore(repo): 清理仓库卫生并归档旧版用例`n`n- 补 .gitignore，移除入库的 __pycache__ 与 60KB report.html`n- 修正 pytest.ini（testpaths 指向不存在的 tests/）`n- 旧版 43 条用例移入 legacy/，保留为重构对照`n- 配置外置为 .env.example，不再硬编码地址与口令"
        paths   = @(".gitignore", ".env.example", "pytest.ini", "requirements.txt", "report.html", "__pycache__", "legacy", "docs/review-2026.md", "api_client.py", "config.py", "defects.md", "test_login.py", "test_user_api.py", "test_user_extended.py", "test_role_api.py", "test_common_api.py")
    },
    @{
        message = "feat(framework): 通用测试基础设施`n`n- settings: 环境变量配置，启动即校验，frozen dataclass`n- http: Session 复用 + 强制超时 + 幂等重试 + 401 自动重登`n- assertions: expect_ok/expect_perm_denied/eventually，失败带完整响应上下文`n- schema: 零依赖响应契约 DSL，返回全部错误而非第一个`n- trace/logger: 请求响应追踪与敏感信息脱敏"
        paths   = @("framework")
    },
    @{
        message = "feat(ruoyi): 被测系统领域层`n`n- API Object 封装 auth/user/role/system，只发请求不断言`n- schemas 把接口契约写成代码（活文档）`n- factories 生成唯一合法基线数据，杜绝固定数据撞唯一索引`n- constants 集中枚举/文案/权限标识，移除魔法值"
        paths   = @("ruoyi", "data")
    },
    @{
        message = "feat(stub): RuoYi 契约桩与缺陷开关`n`n- 对齐 RuoYi 3.9.x 的路径与信封（业务错误 HTTP 200 + code）`n- 缺陷开关驱动 xfail/xpass，用于演示缺陷生命周期`n- 明确标注「非被测系统」，仅用于离线与 CI 冒烟"
        paths   = @("stub")
    },
    @{
        message = "test: 148 条接口用例、权限矩阵与缺陷回归`n`n- 分五层：冒烟/功能/校验/权限/契约，另加缺陷回归与套件自检`n- 分页断言改为校验 total 与页大小关系，修掉假断言`n- 越权用例不再操作固定 ID，改用自建数据 + 语义断言`n- 3 个缺陷固化为 xfail，并与 defects/registry.json 双向绑定"
        paths   = @("tests", "conftest.py", "defects")
    },
    @{
        message = "ci: 流水线、环境编排、性能基线与文档`n`n- CI 双轮跑（缺陷存在/修复），上传 report/QUALITY/summary`n- docker compose 编排 MySQL/Redis/后端，SQL 初始化测试库`n- Locust 加业务断言、阶梯加压与 SLA 门禁`n- 补齐架构、测试方案、缺陷、真实环境与学习路线文档"
        paths   = @(".github", "docker", "scripts", "performance_test", "docs", "README.md")
    }
)

if ($DryRun) {
    Write-Host "[commit] DryRun：以下 6 个提交将被创建" -ForegroundColor Cyan
    $i = 1
    foreach ($c in $commits) {
        $title = ($c.message -split "`n")[0]
        Write-Host ("  {0}. {1}" -f $i, $title)
        Write-Host ("     涉及: {0}" -f ($c.paths -join ", ")) -ForegroundColor DarkGray
        $i++
    }
    exit 0
}

# 先清空暂存区，保证每个提交只包含自己那部分
git reset | Out-Null

$i = 0
foreach ($c in $commits) {
    $i++
    foreach ($path in $c.paths) {
        if (Test-Path $path) {
            git add -A -- $path
        } else {
            # 已删除的路径：仍然让 git 记录删除
            git rm -r --cached --ignore-unmatch --quiet -- $path 2>$null | Out-Null
        }
    }
    $staged = (git diff --cached --name-only | Measure-Object -Line).Lines
    if ($staged -eq 0) {
        Write-Host ("[commit] 第 {0} 个提交没有内容，跳过" -f $i) -ForegroundColor Yellow
        continue
    }
    git commit -m $c.message | Out-Null
    Write-Host ("[commit] {0}/6 完成（{1} 个文件）" -f $i, $staged) -ForegroundColor Green
}

# 兜底：把剩下的（未匹配到的）一起提交，避免遗漏
git add -A
$rest = (git diff --cached --name-only | Measure-Object -Line).Lines
if ($rest -gt 0) {
    git commit -m "chore: 收尾（补充遗漏文件）" | Out-Null
    Write-Host ("[commit] 收尾提交 {0} 个文件" -f $rest) -ForegroundColor Yellow
}

Write-Host ""
Write-Host "[commit] 完成，最近提交：" -ForegroundColor Cyan
git log --oneline -8

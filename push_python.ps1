# ============================================================
#  push_python.ps1
#  把 D:\Fish 项目里被改动过的 Python 源码上传到
#      https://github.com/ACM555/Fish-v1
#
#  用法：
#      pwsh -File D:\Fish\push_python.ps1 -Message "更新 test.py 的 PID 参数"
#      pwsh -File D:\Fish\push_python.ps1              # 自动生成提交信息
#
#  说明：只提交 .py 与仓库说明文件；游戏本体/引擎/日志由 .gitignore 排除。
# ============================================================
[CmdletBinding()]
param(
    [string]$Message = "",
    [string]$Remote = "https://github.com/ACM555/Fish-v1.git",
    [string]$Branch = "main",
    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'
$repoRoot = 'D:\Fish'
Set-Location -LiteralPath $repoRoot

# ---------- 1. 确保仓库已初始化并绑定远程 ----------
if (-not (Test-Path (Join-Path $repoRoot '.git'))) {
    Write-Host "[init] 初始化 git 仓库 ..." -ForegroundColor Cyan
    git init -b $Branch | Out-Null
    git branch -M $Branch
}

$existing = git remote 2>$null
if ($existing -notcontains 'origin') {
    Write-Host "[init] 添加远程 origin -> $Remote" -ForegroundColor Cyan
    git remote add origin $Remote
} else {
    $cur = (git remote get-url origin).Trim()
    if ($cur -ne $Remote) {
        Write-Host "[init] 修正 origin：$cur -> $Remote" -ForegroundColor Yellow
        git remote set-url origin $Remote
    }
}

# ---------- 2. 暂存 Python 源码 ----------
# pathspec '*.py' 会匹配任意层级；被 .gitignore 排除的引擎标准库不会被加入。
git add -- '*.py' '.gitignore' 'README.md' 'AGENTS.md' 'push_python.ps1' 'push_python.cmd'

$staged = @(git diff --cached --name-only)
if ($staged.Count -eq 0) {
    Write-Host "[skip] 没有任何 Python 改动需要上传。" -ForegroundColor Green
    exit 0
}

Write-Host ("[stage] 本次将上传 {0} 个文件：" -f $staged.Count) -ForegroundColor Cyan
$staged | ForEach-Object { "        $_" }

if (-not $Message) {
    $Message = "更新 Python 源码 {0}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
}

if ($DryRun) {
    Write-Host "[dryrun] 仅暂存，未提交未推送。" -ForegroundColor Yellow
    exit 0
}

# ---------- 3. 提交并推送 ----------
git commit -m $Message | Write-Host
if ($LASTEXITCODE -ne 0) { throw "git commit 失败（退出码 $LASTEXITCODE）" }

git push origin $Branch
if ($LASTEXITCODE -ne 0) {
    # 首次推送时目标分支可能还不存在，重试一次并建立跟踪
    Write-Host "[retry] push 失败，尝试 -u 建立上游跟踪 ..." -ForegroundColor Yellow
    git push -u origin $Branch
    if ($LASTEXITCODE -ne 0) { throw "git push 失败（退出码 $LASTEXITCODE），改动仍留在本地提交中" }
}

$head = (git rev-parse --short HEAD).Trim()
Write-Host ("[done] 已上传到 {0} (commit {1})" -f $Remote, $head) -ForegroundColor Green

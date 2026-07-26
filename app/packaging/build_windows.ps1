# =============================================================================
# PPT Master Agent SaaS — Windows 产物本地构建脚本
#
# 与 CI（.github/workflows/build-pptsaas.yml 的 windows job）完全一致的流程。
# **必须在 Windows（x86_64）上执行** —— PyInstaller 不能交叉编译。
#
# 前置：本机装好 Python 3.12（仅作构建宿主，最终产物不依赖它）。
# 在仓库根目录执行：
#   powershell -ExecutionPolicy Bypass -File app\packaging\build_windows.ps1
#
# 流程：
#   1. pip 安装全部依赖 + pyinstaller（宿主 python）
#   2. pyinstaller 读取 app/packaging/pptsaas.spec → dist\pptsaas\（onedir）
#   3. 下载 python-build-standalone（cpython-3.12 windows-amd64 install_only）
#      作为内嵌 Python 运行时，并往其中 pip 安装技能管线依赖
#   4. 组装 pkg\pptsaas\（app\ onedir + python\ 内嵌运行时 + start.bat +
#      .env.example），冒烟启动验证 HTTP 200 后压缩 dist\pptsaas-windows-x86_64.zip
# =============================================================================

$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $RepoRoot

Write-Host "==> [1/5] 安装打包依赖（pyinstaller + 运行依赖，宿主 python）"
python -m pip install --upgrade pip
python -m pip install pyinstaller
python -m pip install -r app\backend\requirements.txt -r skills\ppt-master\requirements.txt

Write-Host "==> [2/5] PyInstaller 构建 onedir 产物"
python -m PyInstaller app\packaging\pptsaas.spec `
    --distpath dist --workpath build --noconfirm

Write-Host "==> [3/5] 下载内嵌 Python（python-build-standalone）并安装技能依赖"
$rel = Invoke-RestMethod "https://api.github.com/repos/astral-sh/python-build-standalone/releases/latest"
$asset = $rel.assets | Where-Object {
  $_.name -match '^cpython-3\.12\..*-x86_64-pc-windows-msvc-install_only\.tar\.gz$'
} | Select-Object -First 1
if (-not $asset) { throw "未找到匹配的 python-build-standalone 资产" }
Write-Host "    下载 $($asset.name)"
Invoke-WebRequest $asset.browser_download_url -OutFile "$env:TEMP\pbs.tar.gz"
New-Item -ItemType Directory -Force pkg\pptsaas | Out-Null
tar -xzf "$env:TEMP\pbs.tar.gz" -C pkg\pptsaas   # 解出 pkg\pptsaas\python\python.exe
pkg\pptsaas\python\python.exe -m pip install --no-warn-script-location `
  -r skills\ppt-master\requirements.txt
pkg\pptsaas\python\python.exe -c "import pptx, fitz, PIL, requests, openpyxl"

Write-Host "==> [4/5] 组装包（onedir + 启动器 + .env 模板）并冒烟验证"
Copy-Item -Recurse dist\pptsaas pkg\pptsaas\app
@'
@echo off
setlocal
set "HERE=%~dp0"
set "PPTSAAS_PYTHON=%HERE%python\python.exe"
if not defined PPTSAAS_DATA_DIR set "PPTSAAS_DATA_DIR=%HERE%data"
if not exist "%PPTSAAS_DATA_DIR%" mkdir "%PPTSAAS_DATA_DIR%"
cd /d "%HERE%"
"%HERE%app\pptsaas.exe" %*
'@ -replace "`n", "`r`n" | Set-Content -NoNewline pkg\pptsaas\start.bat -Encoding ASCII
@'
# PPT Master Agent SaaS 配置（与 start.bat 同目录；不配 LLM key 为 mock 演示模式）
PPTSAAS_LLM_BASE_URL=https://api.deepseek.com/v1
PPTSAAS_LLM_API_KEY=
PPTSAAS_LLM_MODEL=deepseek-chat
# PEXELS_API_KEY=
# PPTSAAS_HOST=127.0.0.1
# PPTSAAS_PORT=8310
'@ -replace "`n", "`r`n" | Set-Content -NoNewline pkg\pptsaas\.env.example -Encoding UTF8

$env:PPTSAAS_PORT = "8399"
$env:PPTSAAS_HOST = "127.0.0.1"
$proc = Start-Process -FilePath "pkg\pptsaas\start.bat" -PassThru `
  -RedirectStandardOutput "$env:TEMP\pptsaas-out.log" `
  -RedirectStandardError "$env:TEMP\pptsaas-err.log"
$ok = $false
for ($i = 0; $i -lt 45; $i++) {
  try {
    $r = Invoke-WebRequest "http://127.0.0.1:8399/" -UseBasicParsing -TimeoutSec 5
    if ($r.StatusCode -eq 200) { $ok = $true; break }
  } catch { Start-Sleep 2 }
}
Get-Process pptsaas -ErrorAction SilentlyContinue | Stop-Process -Force
Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
if (-not $ok) {
  Get-Content "$env:TEMP\pptsaas-err.log" -Tail 30 -ErrorAction SilentlyContinue
  throw "冒烟验证失败：服务未返回 HTTP 200"
}
Write-Host "    冒烟验证通过（HTTP 200）"

Write-Host "==> [5/5] 压缩 dist\pptsaas-windows-x86_64.zip"
New-Item -ItemType Directory -Force dist | Out-Null
$ZipPath = "dist\pptsaas-windows-x86_64.zip"
if (Test-Path $ZipPath) { Remove-Item $ZipPath -Force }
Compress-Archive -Path pkg\pptsaas -DestinationPath $ZipPath

Write-Host ""
Write-Host "完成：$ZipPath"
Write-Host "使用：解压后把 .env.example 复制为 .env 填入 key，双击 start.bat（访问 http://localhost:8310）"
Write-Host "提示：首次启动如弹防火墙提示，仅本机使用选取消并在 .env 设 PPTSAAS_HOST=127.0.0.1"
Write-Host "      杀毒软件可能对内嵌 python\ 目录误报，需加白名单（见 docs/zh/saas/DEPLOYMENT.md）"

#!/usr/bin/env bash
# =============================================================================
# PPT Master Agent SaaS — Linux 产物本地构建脚本
#
# 与 CI（.github/workflows/build-pptsaas.yml 的 linux job）完全一致的流程：
# 一切构建都在 app/packaging/Dockerfile.linux-build 里完成，本脚本只是
# 封装 docker build + 冒烟验证。任意装了 Docker 的系统（含 macOS）都能跑，
# 不要求本机是 Linux，也不要求本机有 Python。
#
# 在仓库根目录执行：  bash app/packaging/build_linux.sh
#
# 产物（写入 dist/）：
#   pptsaas-linux-x86_64.tar.gz   解压即用：pptsaas.sh 启动器 + PyInstaller
#                                 onedir 后端 + 内嵌便携 Python 3.12 运行时
#   pptsaas-x86_64.AppImage       同内容 AppImage（appimagetool 可下载时）
#   SHA256SUMS.txt
#
# 无 FUSE 的环境运行 AppImage：  ./pptsaas-x86_64.AppImage --appimage-extract-and-run
# =============================================================================
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

echo "==> [1/2] docker build（pip 依赖 → PyInstaller onedir → 组装 + 内嵌 Python → tar.gz/AppImage）"
docker build -f app/packaging/Dockerfile.linux-build \
    --output type=local,dest=dist .

echo "==> [2/2] 冒烟验证（debian 干净容器内启动产物，断言 HTTP 200 + 注册 + 主题接口）"
docker run --rm -v "$PWD/dist:/dist" debian:bookworm-slim bash -c '
  set -euo pipefail
  apt-get update -qq && apt-get install -y -qq curl >/dev/null   # slim 镜像无 curl
  ! command -v python3 && echo "no system python: OK"
  mkdir /w && tar -xzf /dist/pptsaas-linux-x86_64.tar.gz -C /w
  cd /w/pptsaas
  ./python/bin/python3.12 -c "import pptx, fitz, PIL, requests, openpyxl"
  PPTSAAS_PORT=8399 PPTSAAS_HOST=127.0.0.1 PPTSAAS_NO_BROWSER=1 nohup ./pptsaas.sh > server.log 2>&1 &
  ok=""
  for i in $(seq 1 45); do
    if curl -fsS http://127.0.0.1:8399/ -o /dev/null 2>/dev/null; then ok=1; break; fi
    sleep 2
  done
  if [ -z "$ok" ]; then echo "SERVER FAILED TO START"; tail -30 server.log; exit 1; fi
  TOKEN=$(curl -fsS -X POST http://127.0.0.1:8399/api/auth/register \
    -H "Content-Type: application/json" \
    -d "{\"username\":\"smoke\",\"password\":\"smoke-pass-123\"}" | sed -n "s/.*\"token\":\"\([^\"]*\)\".*/\1/p")
  test -n "$TOKEN"
  curl -fsS http://127.0.0.1:8399/api/themes -H "Authorization: Bearer $TOKEN" | grep -q "style_md\|商务蓝"
  echo SMOKE_OK
'

echo
echo "完成。产物："
ls -lh dist/pptsaas-linux-x86_64.tar.gz dist/pptsaas-x86_64.AppImage 2>/dev/null || true
echo
echo "使用：tar -xzf dist/pptsaas-linux-x86_64.tar.gz && cd pptsaas"
echo "      cp .env.example .env  # 填入 PPTSAAS_LLM_API_KEY（不配则为 mock 演示模式）"
echo "      ./pptsaas.sh          # 启动后浏览器自动打开应用窗口（无浏览器环境请手动访问 http://localhost:8310）"

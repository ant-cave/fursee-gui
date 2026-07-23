#!/usr/bin/env bash
set -e

cd "$(dirname "$0")"

echo "=== Fursee Server ==="

if [ -f venv/bin/activate ]; then
    source venv/bin/activate
    echo "[OK] Python 虚拟环境已激活"
fi

python3 -c "import websockets" 2>/dev/null || pip install websockets --quiet

API_ONLY=false
PORT=8898

while [[ $# -gt 0 ]]; do
  case "$1" in
    --api-only) API_ONLY=true; shift ;;
    --port) PORT="$2"; shift 2 ;;
    --admin-token) export FURSEE_ADMIN_TOKEN="$2"; shift 2 ;;
    *) PORT="$1"; shift ;;
  esac
done

if [ "$API_ONLY" = false ]; then
    echo "[..] 正在构建前端..."
    cd fursee_ui
    npm install --silent
    npm run build --silent
    cd ..
    echo "[OK] 前端构建完成"
    export FURSEE_SERVE_FRONTEND=true
fi

echo "[..] 启动服务: http://0.0.0.0:${PORT}"
exec uvicorn fursee_api.main:app --host 0.0.0.0 --port "$PORT"

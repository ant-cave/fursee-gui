#!/usr/bin/env bash
set -e

cd "$(dirname "$0")"

echo "=== Fursee Server ==="

if [ -f venv/bin/activate ]; then
    source venv/bin/activate
    echo "[OK] Python 虚拟环境已激活"
fi

python3 -c "import websockets" 2>/dev/null || pip install websockets --quiet

echo "[..] 正在构建前端..."
cd fursee_ui
npm install --silent
npm run build --silent
cd ..
echo "[OK] 前端构建完成"

PORT=${1:-8898}
exec uvicorn fursee_api.main:app --host 0.0.0.0 --port "$PORT"

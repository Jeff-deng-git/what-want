#!/usr/bin/env bash
# Smoke: start backend, hit 5 core endpoints + 1 LLM end-to-end.
# Assumes DEEPSEEK_API_KEY is set in env. Set SKIP_LLM=1 to skip the LLM call.
set -e
API=${API:-http://localhost:8011}
PORT=${PORT:-8011}

cd "$(dirname "$0")/.."
echo "== start backend on :$PORT"
python3 -u run.py > /tmp/ww_backend.log 2>&1 &
BACK_PID=$!
trap "kill $BACK_PID 2>/dev/null || true" EXIT
sleep 2

echo "== /api/health"
curl -fsS $API/api/health
echo

echo "== /api/roles"
curl -fsS $API/api/roles | head -c 300
echo

echo "== /api/book/chapters"
curl -fsS $API/api/book/chapters | head -c 300
echo

echo "== /api/notes?chapter_id=ch04"
curl -fsS "$API/api/notes?chapter_id=ch04" | head -c 300
echo

echo "== /api/chapters/ch04/steps/step-1"
curl -fsS $API/api/chapters/ch04/steps/step-1 | head -c 300
echo

if [ "${SKIP_LLM:-0}" = "1" ]; then
  echo "== SKIP_LLM=1, skipping end-to-end LLM call"
  exit 0
fi

if [ -z "${DEEPSEEK_API_KEY:-}" ]; then
  echo "WARN: DEEPSEEK_API_KEY not set; skipping end-to-end LLM call (set it then re-run)"
  exit 0
fi

echo "== run step-1 with real LLM"
curl -fsS -X POST $API/api/chapters/ch04/steps/step-1/run \
  -H 'Content-Type: application/json' \
  -d @backend/test_step1.json | head -c 600
echo
echo "OK: smoke complete"

#!/bin/bash
pip3 install --break-system-packages pytest==8.3.4 pytest-json-ctrf==0.3.5 --quiet 2>/dev/null || true
mkdir -p /logs/verifier

# Check if ctrf plugin is available
CTRF_ARGS=""
if python3 -c "import pytest_ctrf" 2>/dev/null; then
    CTRF_ARGS="--ctrf /logs/verifier/ctrf.json"
fi

set +e
python3 -m pytest $CTRF_ARGS /tests/test_outputs.py -rA -v 2>&1 | tee /logs/verifier/test-stdout.txt
PYTEST_EXIT_CODE=${PIPESTATUS[0]}
set -e

if [ -f "/logs/verifier/ctrf.json" ]; then
    REWARD=$(python3 -c "
import json
with open('/logs/verifier/ctrf.json') as f:
    data = json.load(f)
summary = data.get('results', {}).get('summary', {})
total = summary.get('tests', 0)
passed = summary.get('passed', 0)
print(passed / total if total > 0 else 0.0)
" 2>/dev/null)
    echo "${REWARD:-0.0}" > /logs/verifier/reward.txt
else
    if [ $PYTEST_EXIT_CODE -eq 0 ]; then echo 1 > /logs/verifier/reward.txt; else echo 0 > /logs/verifier/reward.txt; fi
fi
exit 0

#!/bin/bash
cd "/mnt/c/Users/Duong Vinh/Vinh"
export PATH="$HOME/uvenv/bin:$PATH"
~/campus-venv/bin/python -B -m pytest -q -p no:cacheprovider --basetemp="/mnt/c/Users/Duong Vinh/Vinh/.pytest-tmp-linux-1" \
  tests/rag_v2 tests/api tests/architecture tests/operations tests/knowledge_platform tests/evals tests/contract tests/contracts tests/unit/retrieval tests/unit/agent tests/integration > "/mnt/c/Users/Duong Vinh/Vinh/evals/results/linux-port-20261115/pytest-linux.log" 2>&1
echo "exit=$?" >> "/mnt/c/Users/Duong Vinh/Vinh/evals/results/linux-port-20261115/pytest-linux.log"

#!/bin/bash
cd "/mnt/c/Users/Duong Vinh/Vinh"
export PATH="$HOME/uvenv/bin:$PATH"
~/campus-venv/bin/python -B -m pytest -q -p no:cacheprovider --basetemp="/mnt/c/Users/Duong Vinh/Vinh/.pytest-tmp-linux-2" $(cat evals/results/linux-port-20261115/rerun-files.txt | tr '\n' ' ') > "/mnt/c/Users/Duong Vinh/Vinh/evals/results/linux-port-20261115/pytest-linux-rerun.log" 2>&1
echo "exit=$?" >> "/mnt/c/Users/Duong Vinh/Vinh/evals/results/linux-port-20261115/pytest-linux-rerun.log"

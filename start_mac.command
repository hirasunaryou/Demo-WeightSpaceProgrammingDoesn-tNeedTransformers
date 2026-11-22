#!/bin/bash
cd "$(dirname "$0")" || exit 1
echo "========================================"
echo " WSP Live Lab / macOS"
echo " Weight-Space Programming"
echo " Python standard library / no venv"
echo "========================================"
if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3.8以上が必要です: https://www.python.org/downloads/"
  read -r -p "Enterで閉じます..."
  exit 1
fi
python3 launch.py "$@"
status=$?
if [ "$status" -ne 0 ]; then
  echo "エラー終了 (code=$status)"
  read -r -p "Enterで閉じます..."
fi
exit "$status"

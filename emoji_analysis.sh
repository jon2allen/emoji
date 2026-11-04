#!/usr/bin/env bash
# emoji_analysis.sh - Run emoji test suite and density analysis on the testbed
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "========================================================================"
echo " 1. Running Test Suite (pytest)"
echo "========================================================================"
if command -v uv >/dev/null 2>&1; then
    uv run --with pytest pytest -o console_output_style=count
elif command -v pytest >/dev/null 2>&1; then
    pytest -o console_output_style=count
elif python3 -m pytest --version >/dev/null 2>&1; then
    python3 -m pytest -o console_output_style=count
else
    echo "Warning: pytest not found via uv or python3; skipping unit tests." >&2
fi

echo ""
echo "========================================================================"
echo " 2. Running Emoji Density Analysis on Testbed"
echo "========================================================================"

if [ ! -d "testbed" ] || [ -z "$(ls -A testbed/*.txt 2>/dev/null)" ]; then
    echo "testbed/ directory missing or empty. Generating samples..."
    mkdir -p testbed
    ./detect_emoji.py --fix - < cat_story.txt > testbed/baseline.txt 2>/dev/null
    ./generate_testbed.py testbed/baseline.txt --density 5  > testbed/low_density.txt
    ./generate_testbed.py testbed/baseline.txt --density 20 > testbed/medium_density.txt
    ./generate_testbed.py testbed/baseline.txt --density 50 > testbed/high_density.txt
    ./generate_testbed.py testbed/baseline.txt --density 30 --category emoticons > testbed/emoticons_only.txt
fi

./detect_emoji.py --density --group-by all,category testbed/*.txt cat_story.txt

echo ""
echo "========================================================================"
echo " 3. Per-Emoji Breakdown (top 15, high-density sample + cat_story)"
echo "========================================================================"
./detect_emoji.py --density --group-by emoji --top 15 testbed/high_density.txt cat_story.txt

echo ""
echo "Analysis complete."

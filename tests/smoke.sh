#!/usr/bin/env bash
# Render everything without a printer. Fails loudly if any widget or example breaks.
set -euo pipefail
cd "$(dirname "$0")/.."
OUT="$(mktemp -d)"
T=bin/tearoff
for f in skills/tearoff/examples/newspaper-*.json; do $T newspaper --edition "$f" --out "$OUT/$(basename "$f" .json).png"; done
for f in skills/tearoff/examples/gig-*.json; do $T gig --edition "$f" --split --out "$OUT/$(basename "$f" .json).png"; done
for f in skills/tearoff/examples/week-ahead.json skills/tearoff/examples/meals-and-shopping.json; do $T strip --spec "$f" --out "$OUT/$(basename "$f" .json).png"; done
$T sampler --out "$OUT/sampler.png" 2>/dev/null
$T quick todo "Test" "one" "two" --out "$OUT/todo.png"
$T quick shop Milk Bananas "Tinned tomatoes" --out "$OUT/shop.png"
$T quick sudoku --level hard --seed 1 --out "$OUT/sudoku.png"
$T quick banner "OK" --out "$OUT/banner.png"
$T widgets > /dev/null
echo "smoke test passed: $(ls "$OUT" | wc -l) images in $OUT"

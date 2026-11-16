#!/usr/bin/env bash
# Copy the tearoff skill into an agent's skills folder.
#   ./install.sh hermes     -> ~/.hermes/skills/tearoff      (Hermes Agent)
#   ./install.sh claude     -> ~/.claude/skills/tearoff      (Claude Code)
# Re-run after pulling updates. Published installs can use
#   hermes skills install bennybuoy/tearoff/skills/tearoff
set -euo pipefail
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/skills/tearoff"
case "${1:-}" in
  hermes) DEST="${HERMES_HOME:-$HOME/.hermes}/skills/tearoff" ;;
  claude) DEST="$HOME/.claude/skills/tearoff" ;;
  *) echo "usage: install.sh hermes|claude"; exit 1 ;;
esac
mkdir -p "$DEST"
cp -r "$SRC"/SKILL.md "$SRC"/scripts "$SRC"/references "$SRC"/examples "$DEST"/
find "$DEST" -name __pycache__ -type d -prune -exec rm -rf {} +
echo "installed tearoff skill to $DEST"
echo "next: python3 $DEST/scripts/tearoff.py setup --printer <printer ip>   then   ... tearoff.py test"

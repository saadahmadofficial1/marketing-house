#!/usr/bin/env bash
# Fix pack — safe, config-only fixes for an AI-agent set-up (template).
# Backs up before every change. Skips (never guesses) if a file doesn't match expectations.
# Fixes that need judgement are applied separately, by an agent working from a reviewed checklist prompt.
# Placeholders: point the paths and commands below at your own agents, and change the keys
# and values in each step to match their configuration.
set -u
STAMP=$(date +%Y%m%d-%H%M%S)
AGENT_CFG="${AGENT_CFG:-$HOME/.agent-a/config.yaml}"          # agent A: YAML config holding its memory caps
AGENT_B_CLI="${AGENT_B_CLI:-agent-b}"                         # agent B: a CLI with a 'config set' command
AGENT_B_CFG="${AGENT_B_CFG:-$HOME/.agent-b/config.json}"     # agent B's config file (backed up first)
INDEX_SCRIPT="${INDEX_SCRIPT:-$HOME/notes/build_index.py}"   # rebuilds the shared notes index
ok(){ printf '✅ %s\n' "$*"; }
skip(){ printf '⚠️  SKIPPED: %s\n' "$*"; }

# 1. Agent A memory caps (shipped defaults 2200→8000, 1375→4000)
if [ -f "$AGENT_CFG" ]; then
  if grep -q '^  memory_char_limit: 2200$' "$AGENT_CFG" && grep -q '^  user_char_limit: 1375$' "$AGENT_CFG"; then
    cp "$AGENT_CFG" "$AGENT_CFG.bak-fixpack-$STAMP"
    # ponytail: exact-line replace, no YAML lib needed; config format is machine-written and stable
    python3 - "$AGENT_CFG" <<'EOF'
import sys
p = sys.argv[1]
s = open(p).read()
s = s.replace("  memory_char_limit: 2200\n", "  memory_char_limit: 8000\n", 1)
s = s.replace("  user_char_limit: 1375\n", "  user_char_limit: 4000\n", 1)
open(p, "w").write(s)
EOF
    grep -q 'memory_char_limit: 8000' "$AGENT_CFG" && ok "Agent A memory caps raised (backup: $AGENT_CFG.bak-fixpack-$STAMP)"
  else
    skip "Agent A caps not at expected defaults — edit memory_char_limit/user_char_limit manually"
  fi
else
  skip "no $AGENT_CFG on this machine"
fi

# 2. Agent B's primary model back to the intended one; the free model only as the last fallback
INTENDED_MODEL='"provider/intended-model"'
FALLBACKS='["provider/stronger-model","router/free-model"]'
if command -v "$AGENT_B_CLI" >/dev/null 2>&1; then
  cp "$AGENT_B_CFG" "$AGENT_B_CFG.bak-fixpack-$STAMP" 2>/dev/null || true
  if "$AGENT_B_CLI" config set agents.defaults.model.primary "$INTENDED_MODEL" --strict-json \
     && "$AGENT_B_CLI" config set agents.defaults.model.fallbacks "$FALLBACKS" --strict-json; then
    ok "Agent B primary model restored to $INTENDED_MODEL"
  else
    skip "$AGENT_B_CLI config set failed — set the primary model and fallbacks by hand"
  fi
else
  skip "$AGENT_B_CLI CLI not found"
fi

# 3. Rebuild the shared notes index (it had gone stale)
if [ -f "$INDEX_SCRIPT" ]; then
  python3 "$INDEX_SCRIPT" index && ok "shared notes index rebuilt"
else
  skip "$INDEX_SCRIPT not found"
fi

echo
echo "Done. Now restart both agents, then apply the remaining steps from the checklist prompt."

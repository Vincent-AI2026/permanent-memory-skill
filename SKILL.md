---
name: permanent-memory
description: "Permanent conversation memory system. Automatically saves sessions, supports keyword-triggered retrieval, and enforces confirmation to prevent loss of important dialogues."
emoji: "🧠"
metadata:
  openclaw:
    requires: { "bins": ["python3"] }
    version: "2025-02"
    priority: high
---

# Permanent Memory Skill

**Core Goal**: Allow agents to truly "remember" specific past conversations instead of losing details due to context window summarization or compaction.

## Trigger Conditions (Must Respond)

The skill **must** be invoked when any of the following keywords appear in the user's message:

- before / previously / last time / earlier / you said before / we talked about before
- remember / do you remember / you still remember
- deep recall / recall earlier / search past conversation

**Strongly recommended**: Even without exact keywords, proactively trigger if the user is clearly referring to a specific past interaction.

## Execution Flow (Recommended Order)

1. **Two-stage Search** (prefer `search2`)

   ```bash
   # For assistant (global access)
   ~/.openclaw/workspace-assistant/skills/permanent-memory/permanent-memory.sh search2 \
     "assistant" "${user_id}" "${user's current message}" "true"

   # For copaw / other agents (limited to own memory)
   ~/.openclaw/workspace-copaw/skills/permanent-memory/permanent-memory.sh search2 \
     "copaw" "${user_id}" "${user's current message}" "false"
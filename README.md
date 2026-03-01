
#### README.md

```markdown
# OpenClaw Permanent Memory Skill

A lightweight, structured **permanent conversation archive** system using SQLite + FTS5.

## Features

- Automatically saves full conversations on session switch (low risk of missing data)
- Two-stage retrieval: match natural-language summary first → fall back to full-text search
- Mandatory user confirmation before using memory (avoids wrong recall)
- `assistant` can search globally; other agents are restricted
- Extremely lightweight: pure SQLite, no extra services

## Storage Location

`~/.openclaw/memories.db`

### Core Tables

```sql
-- Main table
memories (
    id              TEXT PRIMARY KEY,           -- e.g. 20250228101122_assistant_ou_73e1
    agent_id        TEXT NOT NULL,
    user_id         TEXT NOT NULL,
    session_id      TEXT,
    summary         TEXT NOT NULL,              -- 128–256 char natural language summary
    conversation    TEXT NOT NULL,              -- JSON serialized message list
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
)

-- FTS5 index for fast summary search
memories_fts USING fts5(summary, content='memories', content_rowid='rowid')

-- Session state (for detecting switches)
memory_state (
    agent_id        TEXT PRIMARY KEY,
    last_session_id TEXT,
    last_user_id    TEXT,
    updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP
)
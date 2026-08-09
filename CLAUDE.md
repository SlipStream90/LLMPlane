# CLAUDE.md

## Agent usage

For complex, multi-step, or open-ended tasks (broad codebase exploration, multi-file refactors, research spanning several files/systems, or anything that would otherwise take many sequential tool calls), always spawn a subagent via the Agent tool rather than doing the work inline. Use the `Explore` agent type for read-only searches/investigation and `general-purpose` for multi-step implementation or research work. Reserve inline handling (direct Read/Grep/Glob/Edit) for small, targeted tasks — a single known file, a specific symbol lookup, or a one-line fix.

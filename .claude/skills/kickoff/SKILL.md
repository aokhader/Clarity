---
name: kickoff
description: Start this session as one of the team roles defined in .claude/agents. Run as /kickoff <role> at the start of a worker session.
argument-hint: <role>
disable-model-invocation: true
---

Start this session as the **$ARGUMENTS** role.

1. Read `.claude/agents/$ARGUMENTS.md`. If it does not exist, list the roles in `.claude/agents/`, say that `$ARGUMENTS` is not one of them, and stop.
2. Read `.claude/ownership.json` and note the paths this role owns and the shared files.
3. Read `CLAUDE.md`, `PLAN.md`, `STATUS.md` and `DECISIONS.md`. If `HANDOFF.md` exists and is for this role, read it too.
4. Reply in five lines at most: the role, the paths it owns, the first task you will take and when you expect to finish it, and what you need from other roles.
5. Fill in this role's row in `STATUS.md` (Now, Next, Blocked on, Updated with the local time), then start the first task.

For the rest of the session, follow the role file. Edit only the paths this role owns and its own row in STATUS.md. If the session was started without `KIT_ROLE`, the ownership hook cannot tell which role you are, so keep to your paths yourself. When you need a change in a path you do not own, write it under "Blocked on" in your row and tell the user which role owns it.

Before the session's context is cleared or the session ends, copy `HANDOFF.md.example` to `HANDOFF.md` and fill it in for this role.

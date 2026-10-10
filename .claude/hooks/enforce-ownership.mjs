#!/usr/bin/env node
// PreToolUse hook: stops a role from editing a file it does not own.
//
// The role comes from KIT_ROLE (set when a worker session is started from a
// shell) or from the hook input's agent_type (a subagent or teammate defined in
// .claude/agents). With neither, the session is the lead and may edit anything.
// A role missing from .claude/ownership.json, such as a built-in Explore agent,
// is not checked. Files outside the repository are not this hook's business.
//
// Exit 0 allows the edit. Exit 2 blocks it, and Claude Code shows stderr to the
// model so it can ask the owner instead. Unreadable input fails open, because a
// broken guard must not stop the whole team.

import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ignoreCase = process.platform === 'win32';

export function globToRegExp(glob) {
  let source = '';
  for (let i = 0; i < glob.length; i++) {
    const c = glob[i];
    if (c === '*' && glob[i + 1] === '*') {
      // "dir/**" matches everything under dir; "**/x" matches x at any depth.
      if (glob[i + 2] === '/') {
        source += '(?:.*/)?';
        i += 2;
      } else {
        source += '.*';
        i += 1;
      }
    } else if (c === '*') {
      source += '[^/]*';
    } else if (c === '?') {
      source += '[^/]';
    } else {
      source += c.replace(/[.+^${}()|[\]\\]/g, '\\$&');
    }
  }
  return new RegExp(`^${source}$`, ignoreCase ? 'i' : '');
}

// Path of `file` relative to the repository root with forward slashes, or null
// when it lies outside. An edit inside a worktree (.claude/worktrees/<name>/)
// is mapped back to the path it has in the main checkout.
export function repoRelative(file, root) {
  let target = file;
  if (process.platform === 'win32') {
    // Git Bash style /d/dir -> D:/dir
    target = target.replace(/^\/([a-zA-Z])\//, (_, drive) => `${drive.toUpperCase()}:/`);
  }
  const rel = path.relative(root, path.resolve(root, target)).split(path.sep).join('/');
  if (rel === '' || rel === '..' || rel.startsWith('../') || path.isAbsolute(rel)) return null;
  return rel.replace(/^\.claude\/worktrees\/[^/]+\//, '');
}

export function ownersOf(rel, ownership) {
  return Object.entries(ownership.roles ?? {})
    .filter(([, globs]) => globs.some((g) => globToRegExp(g).test(rel)))
    .map(([role]) => role);
}

export function decide({ role, file, root, ownership }) {
  if (!role || !file) return { allow: true };
  const roles = ownership.roles ?? {};
  if (!(role in roles)) return { allow: true };
  const rel = repoRelative(file, root);
  if (rel === null) return { allow: true };
  const allowed = [...(ownership.shared ?? []), ...roles[role]];
  if (allowed.some((g) => globToRegExp(g).test(rel))) return { allow: true };
  const owners = ownersOf(rel, ownership);
  const ownerText = owners.length
    ? `It belongs to ${owners.join(', ')}.`
    : "No role owns it, so it is the lead's.";
  return {
    allow: false,
    reason:
      `[ownership] ${role} may edit only ${allowed.join(', ')}. ${rel} is outside that. ${ownerText} ` +
      'Do not edit it: write what you need under "Blocked on" in your STATUS.md row and tell the user which role owns it.',
  };
}

function main() {
  const here = path.dirname(fileURLToPath(import.meta.url));
  const root = process.env.CLAUDE_PROJECT_DIR || path.resolve(here, '..', '..');
  let input;
  let ownership;
  try {
    input = JSON.parse(readFileSync(0, 'utf8') || '{}');
    ownership = JSON.parse(readFileSync(path.join(root, '.claude', 'ownership.json'), 'utf8'));
  } catch (error) {
    process.stderr.write(`[ownership] check skipped: ${error.message}\n`);
    process.exit(0);
  }
  const role = process.env.KIT_ROLE || input.agent_type || '';
  const file = input.tool_input?.file_path ?? input.tool_input?.notebook_path ?? '';
  const verdict = decide({ role, file, root, ownership });
  if (!verdict.allow) {
    process.stderr.write(`${verdict.reason}\n`);
    process.exit(2);
  }
  process.exit(0);
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) main();

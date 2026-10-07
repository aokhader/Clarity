// Nothing private is committed: no environment files, local databases, data
// folders, keys, session hand-offs or submission bundles, whether tracked now,
// sitting untracked but not ignored, or anywhere in history. And .env.example
// holds no value that looks like a real secret.
//
//   node --test tests/repo_hygiene.test.mjs
//
// KIT_FORBIDDEN adds one more regular expression for paths (for example the
// organisers' materials folder). If the project keeps code in a folder named
// data/, narrow that pattern below.

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { existsSync, readFileSync } from 'node:fs';
import path from 'node:path';

const FORBIDDEN = [
  [/(^|\/)\.env(\.(?!example$)[^/]*)?$/i, 'environment file'],
  [/\.(db|sqlite|sqlite3)$|\.db-(wal|shm|journal)$/i, 'local database'],
  [/(^|\/)data\//, 'data folder'],
  [/\.(pem|key|p12|pfx)$/i, 'private key'],
  [/(^|\/)HANDOFF\.md$/, 'session hand-off'],
  [/(^|\/)submissions\//, 'submission bundle'],
];
if (process.env.KIT_FORBIDDEN) FORBIDDEN.push([new RegExp(process.env.KIT_FORBIDDEN, 'i'), 'KIT_FORBIDDEN']);

const SECRET_VALUE = /(sk-[A-Za-z0-9_-]{20,}|sk_live_|gh[pousr]_[A-Za-z0-9]{30,}|xox[abpr]-|AKIA[0-9A-Z]{16}|PRIVATE KEY)/;
const LONG_TOKEN = /^[A-Za-z0-9+/_=.-]{32,}$/;

function git(args, cwd) {
  return execFileSync('git', args, { cwd, encoding: 'utf8', maxBuffer: 256 * 1024 * 1024 });
}

function repoRoot() {
  try {
    return git(['rev-parse', '--show-toplevel'], process.cwd()).trim();
  } catch {
    return null;
  }
}

function forbidden(paths) {
  return [...new Set(paths)].flatMap((p) => {
    const rule = FORBIDDEN.find(([pattern]) => pattern.test(p));
    return rule ? [`  ${p}  (${rule[1]})`] : [];
  });
}

const lines = (text) => text.split(/\r?\n/).filter(Boolean);
const root = repoRoot();
const notRepo = root ? false : 'not a git repository';

test('no forbidden file is tracked', { skip: notRepo }, () => {
  const found = forbidden(lines(git(['ls-files'], root)));
  assert.equal(found.length, 0, `Tracked files that must not be:\n${found.join('\n')}`);
});

test('no forbidden file sits untracked without being ignored', { skip: notRepo }, () => {
  const found = forbidden(lines(git(['ls-files', '--others', '--exclude-standard'], root)));
  assert.equal(found.length, 0, `Add these to .gitignore before someone commits them:\n${found.join('\n')}`);
});

test('no forbidden file was ever committed', { skip: notRepo }, () => {
  const found = forbidden(lines(git(['log', '--all', '--name-only', '--format='], root)));
  assert.equal(found.length, 0, `In history (deleting the file now does not remove it):\n${found.join('\n')}`);
});

test('.env.example holds no real-looking secret', { skip: notRepo }, (t) => {
  const file = path.join(root, '.env.example');
  if (!existsSync(file)) return t.skip('no .env.example');
  const suspicious = lines(readFileSync(file, 'utf8'))
    .filter((line) => !line.trimStart().startsWith('#') && line.includes('='))
    .map((line) => [line.slice(0, line.indexOf('=')).trim(), line.slice(line.indexOf('=') + 1).trim().replace(/^["']|["']$/g, '')])
    .filter(([, value]) => SECRET_VALUE.test(value) || LONG_TOKEN.test(value))
    .map(([key]) => `  ${key}`);
  assert.equal(suspicious.length, 0, `Values that look like real secrets:\n${suspicious.join('\n')}`);
});

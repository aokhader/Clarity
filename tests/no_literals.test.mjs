// No case data in the repository. The forbidden terms are derived at run time
// from the organisers' data export (gitignored; its path in KIT_EXPORT), so the
// terms never appear in the repository, and this file holds none of them.
//
//   KIT_EXPORT=<export.json or folder> node --test tests/no_literals.test.mjs
//
// Terms are the values of identifying fields (names, contacts, titles), dates in
// several spellings, distinctive amounts, and six-word runs of long free text.
// Tracked files, file names and commit messages are scanned, and hits are
// printed masked. Generic words that trip it go in tests/no_literals_allow.txt,
// one per line; never paste case data there.

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { existsSync, readFileSync, readdirSync, statSync } from 'node:fs';
import path from 'node:path';

const MIN_TERMS = Number(process.env.KIT_MIN_TERMS ?? 20);
const IDENTIFYING_KEY =
  /(name|first|last|middle|title|email|phone|address|street|city|zip|postal|birth|dob|employer|company|insurer|carrier|provider|client|contact|claim_?n(o|umber)|policy_?n(o|umber))/i;
const PERSON_NAME_KEY = /(first|last|middle|given|family|sur)_?name/i;
const AMOUNT_KEY = /(amount|total|balance|limit|price|cost|charge|paid|due|value|cents)/i;
const ISO_DATE = /\b(\d{4})-(\d{2})-(\d{2})\b/g;
const MONTHS = ['january', 'february', 'march', 'april', 'may', 'june', 'july', 'august', 'september', 'october', 'november', 'december'];
const SKIP_FILE =
  /(^|\/)(package-lock\.json|pnpm-lock\.yaml|yarn\.lock|uv\.lock|poetry\.lock|no_literals_allow\.txt)$|\.(png|jpe?g|gif|webp|ico|pdf|zip|woff2?|ttf|mp4|webm)$/i;

const normalize = (s) => s.trim().replace(/\s+/g, ' ').toLowerCase();
const edgeTrim = (w) => w.replace(/^[^\p{L}\p{N}]+|[^\p{L}\p{N}]+$/gu, '');

export function deriveTerms(data, { allow = new Set(), ignoreDates = new Set() } = {}) {
  const terms = new Set();
  const add = (t) => {
    const v = normalize(t);
    if (v.length >= 4 && !allow.has(v)) terms.add(v);
  };
  const walk = (node, key = '') => {
    if (Array.isArray(node)) return node.forEach((n) => walk(n, key));
    if (node && typeof node === 'object') return Object.entries(node).forEach(([k, v]) => walk(v, k));
    if (typeof node === 'number') {
      if (AMOUNT_KEY.test(key)) amountForms(node, key).forEach(add);
      return;
    }
    if (typeof node !== 'string') return;
    if (AMOUNT_KEY.test(key) && /^\$?[\d,]+(\.\d+)?$/.test(node.trim())) {
      amountForms(Number(node.replace(/[$,\s]/g, '')), key).forEach(add);
    } else if (IDENTIFYING_KEY.test(key)) {
      // A one-word value under a generic key ("name", "title") is usually a label,
      // such as a phone number's "Work" or a stage name, not an identity. One word
      // counts only under a person-name key, or when it carries a digit.
      const value = node.trim();
      if (/\s/.test(value) || PERSON_NAME_KEY.test(key) || /\d/.test(value)) add(value);
    }
    for (const [, y, m, d] of node.matchAll(ISO_DATE)) dateForms(y, m, d, ignoreDates).forEach(add);
    const words = node.split(/\s+/).filter(Boolean);
    if (words.length >= 12) {
      for (let i = 0; i + 6 <= words.length && i < 120; i += 6) add(words.slice(i, i + 6).join(' '));
    }
  };
  walk(data);
  return terms;
}

// A round amount (a multiple of 1,000) says nothing about a case; 12,345.67 does.
function amountForms(value, key) {
  const n = /cents/i.test(key) ? value / 100 : value;
  if (!Number.isFinite(n) || Math.abs(n) < 1000 || n % 1000 === 0) return [];
  const whole = Math.trunc(Math.abs(n));
  const forms = [String(whole), whole.toLocaleString('en-US')];
  if (!Number.isInteger(n)) {
    const cents = Math.abs(n).toFixed(2).split('.')[1];
    forms.push(`${whole}.${cents}`, `${whole.toLocaleString('en-US')}.${cents}`);
  }
  return forms;
}

function dateForms(y, m, d, ignoreDates) {
  const iso = `${y}-${m}-${d}`;
  const month = MONTHS[Number(m) - 1];
  if (ignoreDates.has(iso) || !month) return [];
  return [iso, `${Number(m)}/${Number(d)}/${y}`, `${m}/${d}/${y}`, `${month} ${Number(d)}, ${y}`];
}

export function scanTexts(items, terms) {
  // Index terms by their first word, so each line is checked only against the
  // terms that could start in it.
  const byFirstWord = new Map();
  for (const term of terms) {
    const first = edgeTrim(term.split(' ')[0]);
    if (!byFirstWord.has(first)) byFirstWord.set(first, []);
    byFirstWord.get(first).push(term);
  }
  const hits = [];
  for (const { where, text } of items) {
    text.split(/\r?\n/).forEach((line, i) => {
      const lower = normalize(line);
      const seen = new Set();
      for (const word of lower.split(' ')) {
        for (const term of byFirstWord.get(edgeTrim(word)) ?? []) {
          if (!seen.has(term) && lower.includes(term)) {
            seen.add(term);
            hits.push({ where: `${where}:${i + 1}`, term });
          }
        }
      }
    });
  }
  return hits;
}

export const mask = (term) => `${term.slice(0, 2)}${'*'.repeat(Math.max(term.length - 2, 2))} (${term.length} chars)`;

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

function loadExport(target) {
  if (statSync(target).isDirectory()) {
    return readdirSync(target).map((f) => loadExport(path.join(target, f)));
  }
  const text = readFileSync(target, 'utf8');
  return target.toLowerCase().endsWith('.json') ? JSON.parse(text) : { text };
}

function trackedTexts(root, exportPath) {
  const files = git(['ls-files', '-z'], root).split('\0').filter(Boolean);
  const exportAbs = path.resolve(exportPath);
  const items = [{ where: 'file names', text: files.join('\n') }];
  for (const f of files) {
    const abs = path.join(root, f);
    if (SKIP_FILE.test(f) || abs.startsWith(exportAbs) || !existsSync(abs)) continue;
    const stat = statSync(abs);
    if (!stat.isFile() || stat.size > 5_000_000) continue;
    const buf = readFileSync(abs);
    if (buf.includes(0)) continue;
    items.push({ where: f, text: buf.toString('utf8') });
  }
  return items;
}

function commitMessages(root) {
  return git(['log', '--all', '--format=%h%x00%B%x01'], root)
    .split('\x01')
    .map((entry) => entry.trim())
    .filter(Boolean)
    .map((entry) => {
      const [hash, message = ''] = entry.split('\0');
      return { where: `commit ${hash}`, text: message };
    });
}

function report(hits) {
  const lines = hits.slice(0, 30).map((h) => `  ${h.where}  ${mask(h.term)}`);
  const more = hits.length > 30 ? `\n  ...and ${hits.length - 30} more` : '';
  return `${hits.length} case term(s) found:\n${lines.join('\n')}${more}\nRemove them, or add a generic false positive to tests/no_literals_allow.txt.`;
}

const exportPath = process.env.KIT_EXPORT;
const root = repoRoot();
const needExport = !exportPath || !existsSync(exportPath) ? 'KIT_EXPORT not set to an existing export' : false;
const needRepo = needExport || (!root ? 'not a git repository' : false);

let cachedTerms;
function realTerms() {
  if (!cachedTerms) {
    const allowFile = root && path.join(root, 'tests', 'no_literals_allow.txt');
    const allow = new Set(
      allowFile && existsSync(allowFile)
        ? readFileSync(allowFile, 'utf8').split(/\r?\n/).map(normalize).filter(Boolean)
        : [],
    );
    // Dates the repository itself was worked on appear in its docs legitimately.
    const ignoreDates = new Set(root ? git(['log', '--all', '--format=%as'], root).split(/\s+/).filter(Boolean) : []);
    cachedTerms = deriveTerms(loadExport(exportPath), { allow, ignoreDates });
  }
  return cachedTerms;
}

test('a planted canary is caught and reported masked', () => {
  const invented = {
    client: { first_name: 'Zebulon', last_name: 'Quackenbush' },
    bills: [{ amount: 12345.67, service_date: '1999-04-03' }],
    notes: [{ body: 'The invented patient walked into an invented clinic on an invented morning and asked about invented things.' }],
  };
  const terms = deriveTerms(invented);
  const hits = scanTexts(
    [
      { where: 'planted.py', text: 'NAME = "Quackenbush"\nTOTAL = "$12,345.67"' },
      { where: 'planted.md', text: 'Seen on April 3, 1999.\nThe invented patient walked into an invented clinic, it says.' },
      { where: 'clean.md', text: 'Nothing to see here, 1,000 times over.' },
    ],
    terms,
  );
  const files = [...new Set(hits.map((h) => h.where.split(':')[0]))].sort();
  assert.deepEqual(files, ['planted.md', 'planted.py']);
  assert.ok(hits.length >= 4, `expected the name, the amount, the date and the phrase; got ${hits.length}`);
  assert.ok(hits.every((h) => !mask(h.term).includes(h.term)), 'a hit was printed unmasked');
});

test('the export yields enough terms to mean something', { skip: needExport }, () => {
  const count = realTerms().size;
  assert.ok(count >= MIN_TERMS, `only ${count} terms came from the export (minimum ${MIN_TERMS}); an empty or wrong export must not pass`);
});

test('no tracked file or file name contains case data', { skip: needRepo }, () => {
  const hits = scanTexts(trackedTexts(root, exportPath), realTerms());
  assert.equal(hits.length, 0, report(hits));
});

test('no commit message contains case data', { skip: needRepo }, () => {
  const hits = scanTexts(commitMessages(root), realTerms());
  assert.equal(hits.length, 0, report(hits));
});

// SPDX-FileCopyrightText: 2026 Mindstep Corporation
// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtempSync, mkdirSync, writeFileSync, rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {fileURLToPath} from 'node:url';
import {spawnSync} from 'node:child_process';
import {browserModules} from '../../scripts/browser-modules.mjs';

function fixture(t) {
  const root = mkdtempSync(join(tmpdir(), 'foreview-browser-tooling-'));
  t.after(() => rmSync(root, {recursive: true, force: true}));
  const assets = join(root, 'static');
  mkdirSync(join(assets, 'shared'), {recursive: true});
  return {root, assets, module: join(assets, 'shared', 'sample.mjs')};
}
function run(script, ...args) {
  return spawnSync(process.execPath, [fileURLToPath(new URL(`../../scripts/${script}`, import.meta.url)), ...args], {encoding: 'utf8'});
}

test('syntax gate checks nested modules without executing them and rejects invalid syntax', (t) => {
  const paths = fixture(t);
  writeFileSync(paths.module, 'throw new Error("Must not execute");');
  assert.equal(run('check-browser-syntax.mjs', paths.assets).status, 0);
  writeFileSync(paths.module, 'export const broken = ;');
  assert.notEqual(run('check-browser-syntax.mjs', paths.assets).status, 0);
});

test('coverage sentinel rejects missing, unexecuted and unexercised nested modules', (t) => {
  const paths = fixture(t);
  writeFileSync(paths.module, 'export const sample = () => 1;');
  const report = join(paths.root, 'report.json');
  for (const entry of [null, {s: {0: 0}}, {s: {0: 1}, fnMap: {0: {}}, f: {0: 0}}]) {
    writeFileSync(report, JSON.stringify(entry ? {[paths.module]: entry} : {}));
    assert.notEqual(run('check-browser-coverage.mjs', paths.assets, report).status, 0);
  }
  writeFileSync(report, JSON.stringify({[paths.module]: {s: {0: 1}, fnMap: {0: {}}, f: {0: 1}}}));
  assert.equal(run('check-browser-coverage.mjs', paths.assets, report).status, 0);
});

test('browser module discovery covers root and nested implementations, not unrelated assets', (t) => {
  const paths = fixture(t);
  writeFileSync(paths.module, '');
  const entry = join(paths.assets, 'entry.mjs');
  writeFileSync(entry, '');
  writeFileSync(join(paths.assets, 'csrf.js'), '');
  writeFileSync(join(paths.assets, 'style.css'), '');
  assert.deepEqual(browserModules(paths.assets), [entry, paths.module].sort());
});

test('browser gates reject an empty module selection', (t) => {
  const paths = fixture(t);
  assert.notEqual(run('check-browser-syntax.mjs', paths.assets).status, 0);
  const report = join(paths.root, 'report.json');
  writeFileSync(report, '{}');
  assert.notEqual(run('check-browser-coverage.mjs', paths.assets, report).status, 0);
});

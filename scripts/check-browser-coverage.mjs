// SPDX-FileCopyrightText: 2026 Mindstep Corporation
// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

import {readFileSync} from 'node:fs';
import {resolve, relative} from 'node:path';
import {browserModules} from './browser-modules.mjs';

// Coverage floors alone do not prove that moved files are still instrumented.
const root = resolve(process.argv[2] || 'static');
const report = JSON.parse(readFileSync(process.argv[3] || 'coverage/coverage-final.json', 'utf8'));
const coverage = new Map(Object.entries(report).map(([path, data]) => [resolve(path), data]));
const modules = browserModules(root);
if (!modules.length) throw new Error(`No browser modules found under ${root}`);
for (const path of modules) {
  const data = coverage.get(path);
  if (!data || !Object.values(data.s || {}).some((hits) => hits > 0)) {
    throw new Error(`Browser module missing executed coverage: ${relative(root, path)}`);
  }
  if (Object.keys(data.fnMap || {}).length && !Object.values(data.f || {}).some((hits) => hits > 0)) {
    throw new Error(`Browser module has no exercised function: ${relative(root, path)}`);
  }
}
console.log(`Verified executed coverage for ${modules.length} browser modules recursively.`);

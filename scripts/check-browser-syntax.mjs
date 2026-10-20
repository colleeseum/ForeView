// SPDX-FileCopyrightText: 2026 Mindstep Corporation
// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

import {resolve} from 'node:path';
import {spawnSync} from 'node:child_process';
import {browserModules} from './browser-modules.mjs';

// Optional root permits isolated regression checks without changing production assets.
const root = resolve(process.argv[2] || 'static');
const modules = browserModules(root);
if (!modules.length) throw new Error(`No browser modules found under ${root}`);
for (const path of modules) {
  const result = spawnSync(process.execPath, ['--check', path], {stdio: 'inherit'});
  if (result.error) throw result.error;
  if (result.status !== 0) process.exit(result.status || 1);
}
console.log(`Syntax checked ${modules.length} browser modules recursively.`);

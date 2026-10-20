// SPDX-FileCopyrightText: 2026 Mindstep Corporation
// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

import {readdirSync} from 'node:fs';
import {resolve} from 'node:path';

export function browserModules(directory) {
  return readdirSync(directory, {withFileTypes: true}).flatMap((entry) => {
    const path = resolve(directory, entry.name);
    if (entry.isDirectory()) return browserModules(path);
    return entry.isFile() && entry.name.endsWith('.mjs') ? [path] : [];
  }).sort();
}

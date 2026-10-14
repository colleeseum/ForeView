// SPDX-FileCopyrightText: 2026 Mindstep Corporation
// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import test from 'node:test';

test('declared Node minimum covers the locked browser acceptance dependency', () => {
  const manifest = JSON.parse(readFileSync(new URL('../../package.json', import.meta.url), 'utf8'));
  const lock = JSON.parse(readFileSync(new URL('../../package-lock.json', import.meta.url), 'utf8'));
  const minimum = (requirement) => {
    const match = /^>=(\d+)(?:\.(\d+))?(?:\.(\d+))?$/.exec(requirement);
    assert(match, `Expected an explicit minimum version: ${requirement}`);
    return match.slice(1).map((part) => Number(part || 0));
  };
  const meetsMinimum = (declared, required) => {
    const actual = minimum(declared);
    const needed = minimum(required);
    const difference = actual.findIndex((part, index) => part !== needed[index]);
    return difference === -1 || actual[difference] > needed[difference];
  };
  assert.equal(meetsMinimum('>=20', '>=20.1'), false);
  assert.equal(meetsMinimum('>=22', '>=20.1.1'), true);
  assert.equal(meetsMinimum('>=20.1', '>=20.1.1'), false);
  assert.equal(lock.packages[''].engines.node, manifest.engines.node);
  assert(meetsMinimum(manifest.engines.node, lock.packages['node_modules/@playwright/test'].engines.node));
});

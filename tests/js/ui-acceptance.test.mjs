// SPDX-FileCopyrightText: 2026 Mindstep Corporation
// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

import assert from 'node:assert/strict';
import test from 'node:test';
import {assertLayout, contrastRatio} from '../browser/acceptance.mjs';

test('acceptance contrast calculation handles equal, extreme, and shared Sage colors', () => {
  assert.equal(contrastRatio([255, 255, 255], [0, 0, 0]), 21);
  assert.equal(contrastRatio([0, 0, 0], [255, 255, 255]), 21);
  assert.equal(contrastRatio([82, 101, 91], [82, 101, 91]), 1);
  assert(contrastRatio([255, 255, 255], [50, 104, 88]) >= 4.5);
  assert(contrastRatio([113, 128, 120], [23, 34, 30]) < 4.5, 'Original sidebar pair remains a failing baseline');
});

test('acceptance rejects workspace overflow even when document and main fit', () => {
  const layout = {viewport: 640, document: 640, available: 640, content: 640,
    workspaceAvailable: 620, workspaceContent: 620, uncontainedTables: 0, regions: []};
  assert.doesNotThrow(() => assertLayout(layout, 'baseline'));
  assert.throws(() => assertLayout({...layout, workspaceContent: 2000}, 'wide child'), /workspace overflow/);
  assert.throws(() => assertLayout({...layout, uncontainedTables: 1}, 'table'), /every visible table/);
  assert.throws(() => assertLayout({...layout, regions: [{name: '', tabIndex: 0, overflow: 'auto'}]}, 'unnamed'), /accessible local scrolling/);
});

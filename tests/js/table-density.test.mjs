// SPDX-FileCopyrightText: 2026 Mindstep Corporation
// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

import assert from 'node:assert/strict';
import test from 'node:test';
import {JSDOM} from 'jsdom';
import {initializeTableDensity} from '../../static/shared/table-density.mjs';

function fixture() {
  const {window} = new JSDOM('<main><select><option value="standard">Standard</option><option value="compact">Compact</option></select></main>', {url: 'http://localhost'});
  return {window, select: window.document.querySelector('select'), root: window.document.querySelector('main')};
}

test('table density restores valid saved choices and saves both selections', () => {
  for (const saved of [null, 'invalid', 'standard', 'compact']) {
    const {window, select, root} = fixture();
    if (saved !== null) window.localStorage.setItem('density', saved);
    window.localStorage.setItem('other-workspace', 'untouched');
    initializeTableDensity(select, root, 'density');
    const expected = saved === 'compact' ? 'compact' : 'standard';
    assert.equal(select.value, expected);
    assert.equal(root.dataset.tableDensity, expected);
    for (const next of ['compact', 'standard']) {
      select.value = next;
      select.dispatchEvent(new window.Event('change'));
      assert.equal(root.dataset.tableDensity, next);
      assert.equal(window.localStorage.getItem('density'), next);
    }
    assert.equal(window.localStorage.getItem('other-workspace'), 'untouched');
    window.close();
  }
});

test('unavailable storage and failed writes do not prevent current-page changes', () => {
  for (const blockedRead of [true, false]) {
    const {window, select, root} = fixture();
    Object.defineProperty(window, 'localStorage', {get() {
      if (blockedRead) throw new window.DOMException('Denied', 'SecurityError');
      return {getItem: () => 'compact', setItem: () => {throw new Error('Quota exceeded');}};
    }});
    initializeTableDensity(select, root, 'density');
    assert.equal(select.value, blockedRead ? 'standard' : 'compact');
    select.value = 'compact';
    select.dispatchEvent(new window.Event('change'));
    assert.equal(root.dataset.tableDensity, 'compact');
    window.close();
  }
});

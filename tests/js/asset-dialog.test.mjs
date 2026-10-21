// SPDX-FileCopyrightText: 2026 Mindstep Corporation
// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

import assert from 'node:assert/strict';
import test from 'node:test';
import {JSDOM} from 'jsdom';
import {createAssetDialog} from '../../static/accounts/asset-dialog.mjs';
import {factualMoney} from '../../static/accounts/accounts-format.mjs';
import {configureTestLocalization} from './localization-fixture.mjs';

test('factual money distinguishes missing balances from zero in each language', () => {
  for (const locale of ['en-CA', 'fr-CA']) {
    configureTestLocalization(locale);
    assert.equal(factualMoney(null), locale === 'en-CA' ? 'Unavailable' : 'Indisponible');
    assert.match(factualMoney(0), /0[.,]00/);
  }
  configureTestLocalization();
});

test('asset dialog restores a replaced action or current category after data reload', () => {
  for (const replace of [false, true]) {
    const {window} = new JSDOM('<button class="view-tab active">Category</button><button data-edit-account="1">Edit</button><dialog hidden><input><button data-dialog-close>Cancel</button></dialog>');
    const document = window.document;
    const dialog = document.querySelector('dialog');
    dialog.showModal = () => {dialog.open = true; dialog.querySelector('input').focus();};
    dialog.close = () => {dialog.open = false; dialog.dispatchEvent(new window.Event('close'));};
    const controller = createAssetDialog(dialog);
    const original = document.querySelector('[data-edit-account]');
    original.focus();
    controller.open();
    assert(!dialog.hidden);
    dialog.dispatchEvent(new window.Event('close'));
    assert(!dialog.hidden, 'queued old close does not hide a reopened modal');
    if (replace) original.insertAdjacentHTML('afterend', '<button data-edit-account="2">Other</button><button data-edit-account="1">Edit new</button>');
    original.remove();
    controller.close();
    assert(dialog.hidden);
    assert.equal(document.activeElement.textContent, replace ? 'Edit new' : 'Category');
    window.close();
  }
});

test('asset dialog supports native dismissal and generic invokers', () => {
  const {window} = new JSDOM('<button id="open">Open</button><dialog hidden><select><option>A</option></select><button data-dialog-close>Cancel</button></dialog>');
  const document = window.document;
  const dialog = document.querySelector('dialog');
  dialog.showModal = () => {dialog.open = true;};
  dialog.close = () => {dialog.open = false; dialog.dispatchEvent(new window.Event('close'));};
  const controller = createAssetDialog(dialog);
  document.querySelector('#open').focus();
  controller.open();
  dialog.querySelector('button').click();
  assert(dialog.hidden);
  assert.equal(document.activeElement.id, 'open');
  window.close();
});

test('busy asset dialogs lock controls and dismissal until the request settles', () => {
  configureTestLocalization();
  const {window} = new JSDOM('<button id="open">Open</button><dialog hidden><input><input disabled><button type="submit">Save</button><button data-dialog-close>Cancel</button></dialog>');
  const document = window.document;
  const dialog = document.querySelector('dialog');
  dialog.showModal = () => {dialog.open = true; dialog.querySelector('input').focus();};
  dialog.close = () => {dialog.open = false; dialog.dispatchEvent(new window.Event('close'));};
  const controller = createAssetDialog(dialog);
  document.querySelector('#open').focus();
  controller.open();
  controller.setBusy(true);
  assert(controller.busy);
  assert.equal(dialog.getAttribute('aria-busy'), 'true');
  assert([...dialog.querySelectorAll('input, button')].every(node => node.disabled));
  controller.close();
  assert(dialog.open);
  const cancel = new window.Event('cancel', {cancelable: true});
  dialog.dispatchEvent(cancel);
  assert(cancel.defaultPrevented);
  controller.setBusy(false);
  assert.equal(dialog.querySelector('button[type="submit"]').textContent, 'Save');
  assert.equal(dialog.querySelector('input').disabled, false);
  assert.equal(dialog.querySelectorAll('input')[1].disabled, true);
  controller.close();
  assert.equal(document.activeElement.id, 'open');
  window.close();
});

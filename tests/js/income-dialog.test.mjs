// SPDX-FileCopyrightText: 2026 Mindstep Corporation
// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

import assert from 'node:assert/strict';
import test from 'node:test';
import {JSDOM} from 'jsdom';
import {createIncomeDialog} from '../../static/income/income-dialog.mjs';
import {configureTestLocalization} from './localization-fixture.mjs';

test('income dialogs preserve disabled fields, focus replacements and keep help in the modal', async () => {
  configureTestLocalization();
  const dom = new JSDOM('<button id="fallback">Add</button><button data-edit-year="2025">Edit</button><dialog hidden><input autofocus><input disabled><button data-help-article="facts">Help</button><button data-help-tooltip="amount">Amount</button><button>Save</button></dialog>');
  const {document} = dom.window;
  globalThis.document = document;
  const dialog = document.querySelector('dialog');
  dialog.showModal = () => {dialog.open = true;};
  dialog.close = () => {dialog.open = false; dialog.dispatchEvent(new dom.window.Event('close'));};
  const control = createIncomeDialog(dialog, document.querySelector('#fallback'));
  const trigger = document.querySelector('[data-edit-year]');
  trigger.focus();
  control.open();
  control.setBusy(true);
  control.setBusy(true);
  assert(control.busy);
  control.close();
  assert(dialog.open);
  const cancel = new dom.window.Event('cancel', {cancelable: true});
  dialog.dispatchEvent(cancel);
  assert(cancel.defaultPrevented);
  assert([...dialog.querySelectorAll('input, button')].every(node => node.disabled));
  control.setBusy(false);
  assert(document.querySelectorAll('input')[1].disabled);
  let failed = false;
  let missing = false;
  globalThis.fetch = async () => ({ok: !failed, json: async () => ({
    articles: missing ? [] : [{key: 'facts', title: 'Facts', summary: 'Summary', body: '<b>Original source</b>', field_languages: {body: 'fr-CA'}}],
    tooltips: [{key: 'amount', title: 'Amount', body: 'Value'}],
  })});
  const help = document.querySelector('[data-help-article]');
  const tick = () => new Promise(resolve => setTimeout(resolve, 0));
  help.click();
  await tick();
  const panel = dialog.querySelector('[data-inline-help]');
  assert.match(panel.textContent, /Original source/);
  assert.equal(panel.querySelector('b'), null);
  assert.equal(panel.querySelector('p:last-child').lang, 'fr-CA');
  document.querySelector('[data-help-tooltip]').click();
  await tick();
  assert.match(panel.textContent, /Value/);
  missing = true;
  help.click();
  await tick();
  assert.match(panel.textContent, /unavailable/i);
  failed = true;
  help.click();
  await tick();
  assert.match(panel.textContent, /unavailable/i);
  const replacement = trigger.cloneNode(true);
  trigger.replaceWith(replacement);
  control.close();
  assert(dialog.hidden);
  assert.equal(document.activeElement, replacement);
  document.querySelector('#fallback').focus();
  control.open();
  dialog.dispatchEvent(new dom.window.Event('close'));
  assert(!dialog.hidden, 'Stale close events must not hide an open dialog');
  control.close();
  assert.equal(document.activeElement.id, 'fallback');
  const retry = document.createElement('button');
  retry.id = 'income-retry';
  document.body.append(retry);
  control.open();
  document.querySelector('#fallback').disabled = true;
  control.close();
  assert.equal(document.activeElement, retry);
  dom.window.close();
});

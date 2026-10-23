// SPDX-FileCopyrightText: 2026 Mindstep Corporation
// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

import assert from 'node:assert/strict';
import test from 'node:test';
import {JSDOM} from 'jsdom';
import {configureTestLocalization} from './localization-fixture.mjs';

test('administration enhancement is idempotent, labelled and presentation-only', async () => {
  configureTestLocalization('fr-CA');
  const dom = new JSDOM(`<main class="fv-admin"><section><h2>Source rules</h2><table><thead><tr><th>Amount</th></tr></thead><tbody><tr><td>123.45</td></tr></tbody></table><details><summary>Sources</summary><a href="https://example.invalid/source">Original source</a></details></section><button type="submit">Save</button><input type="checkbox"><input type="hidden"><input type="date"><select></select><textarea></textarea><a class="view-action" href="/connect">Connect</a><table><caption>Existing caption</caption><thead><tr><th>Key</th></tr></thead></table></main>`);
  Object.assign(globalThis, {window: dom.window, document: dom.window.document, MutationObserver: dom.window.MutationObserver});
  globalThis.fetch = () => {throw new Error('Presentation must not request or mutate data');};
  const module = await import(`../../static/administration/administration.mjs?test=${Date.now()}`);
  const root = document.querySelector('main');
  module.enhanceAdministration(root);
  assert.equal(root.querySelectorAll('.fv-table-scroll').length, 2);
  assert.equal(root.querySelector('table').caption.textContent, 'Source rules');
  assert.equal(root.querySelectorAll('caption').length, 2);
  assert.equal(root.querySelector('.fv-table-scroll').getAttribute('aria-label'), 'Source rules');
  assert.equal(root.querySelector('.fv-table-scroll').tabIndex, 0);
  assert.equal(root.querySelectorAll('.fv-help').length, 2);
  assert(document.getElementById(root.querySelector('.fv-table-scroll').getAttribute('aria-describedby')));
  assert.equal(root.querySelector('th').scope, 'col');
  assert.equal(root.querySelector('details').parentElement.tagName, 'SECTION');
  assert.equal(root.querySelector('td').textContent, '123.45');
  assert(root.querySelector('[type="submit"]').classList.contains('fv-button--primary'));
  assert(!root.querySelector('[type="checkbox"]').classList.contains('fv-input'));
  assert(!root.querySelector('[type="hidden"]').classList.contains('fv-input'));
  root.insertAdjacentHTML('beforeend', '<button id="dynamic">Retry</button>');
  await new Promise(resolve => setTimeout(resolve, 0));
  assert(root.querySelector('#dynamic').classList.contains('fv-button'));
  dom.window.close();
  configureTestLocalization();
});

test('administration module does not opt unrelated pages in', async () => {
  const dom = new JSDOM('<main><button>Unchanged</button></main>');
  Object.assign(globalThis, {window: dom.window, document: dom.window.document});
  await import(`../../static/administration/administration.mjs?plain=${Date.now()}`);
  assert.equal(document.querySelector('button').className, '');
  dom.window.close();
});

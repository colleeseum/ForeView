// SPDX-FileCopyrightText: 2026 Mindstep Corporation
// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

import assert from 'node:assert/strict';
import {mkdir} from 'node:fs/promises';
import {chromium, expect} from '@playwright/test';
import {verifyNavigation} from './navigation.mjs';
import {verifyDashboard} from './dashboard.mjs';
import {verifyAssets} from './assets.mjs';
import {verifyTransactions} from './transactions.mjs';
import {verifyIncome} from './income.mjs';
import {verifyExpenses} from './expenses.mjs';
import {verifyEmployment} from './employment.mjs';
import {verifyAdministration} from './administration.mjs';
import {verifyHelp} from './help.mjs';
import {verifyAcceptance, verifyAcceptanceGuards} from './acceptance.mjs';
import {verifyTextSize} from './text-size.mjs';

const [baseURL, locale, output, taxPath, hydroPath, energirPath] = process.argv.slice(2);
assert.match(baseURL, /^http:\/\/127\.0\.0\.1:\d+$/);
const browser = await chromium.launch();
const page = await browser.newPage({viewport: {width: 1280, height: 1000}});
const errors = [];
page.on('pageerror', error => errors.push(error.message));
async function snapshot() {
  return page.evaluate(async () => {
    const urls = ['/api/dashboard', '/api/model/accounts', '/api/salary-projection?start_year=2026&end_year=2027'];
    return Promise.all(urls.map(async url => {
      const response = await fetch(url);
      if (!response.ok) throw new Error(`Read model failed: ${url}`);
      return response.json();
    }));
  });
}
async function goto(path) {
  const response = await page.goto(baseURL + path);
  assert(response.ok(), `Page failed: ${path}`);
  await page.waitForLoadState('networkidle');
}
try {
  await verifyAcceptanceGuards(page);
  await page.setViewportSize({width: 1280, height: 1000});
  await goto('/accounts');
  const original = await snapshot();
  const legacyFont = await page.locator('body').evaluate(node => getComputedStyle(node).fontFamily);
  await goto('/_design-system');
  await expect(page.locator('html')).toHaveAttribute('lang', locale);
  await expect(page.locator('html')).toHaveAttribute('dir', locale === 'ar-XB' ? 'rtl' : 'ltr');
  assert(!(await page.locator('body').innerText()).includes('⟦'), 'All fixture messages must resolve');
  assert.equal(await page.locator('body').evaluate(node => getComputedStyle(node).fontFamily), legacyFont, 'Opt-in CSS must not restyle body');
  assert.match(await page.locator('main.fv-ui').evaluate(node => getComputedStyle(node).fontFamily), /system-ui/);
  for (const button of await page.locator('.fv-ui .fv-button').all()) {
    if (!await button.isVisible()) continue;
    const box = await button.boundingBox();
    assert(box.height >= 44 && box.width >= 44, 'Primary controls meet project target');
  }
  const standard = await page.locator('#standard tbody tr').first().boundingBox();
  const compact = await page.locator('#compact tbody tr').first().boundingBox();
  assert(compact.height < standard.height);
  assert.equal(await page.locator('#compact table').evaluate(node => getComputedStyle(node).fontSize), '14px');
  assert.match(await page.locator('.fv-number').first().evaluate(node => getComputedStyle(node).fontVariantNumeric), /tabular-nums/);
  await expect(page.locator('[aria-busy="true"]')).toBeDisabled();
  await expect(page.locator('input[readonly]')).toHaveAttribute('readonly', '');
  await expect(page.locator('[aria-invalid="true"]')).toHaveAttribute('aria-describedby', 'field-error');

  // Verify actual rendered normal text, control boundaries, status pairs and focus.
  const colors = await page.locator('main.fv-ui').evaluate(node => {
    const style = getComputedStyle(node);
    return Object.fromEntries(['text', 'muted', 'surface', 'primary', 'primary-hover', 'danger', 'danger-hover', 'success', 'success-surface', 'warning', 'warning-surface', 'info', 'info-surface', 'danger-surface', 'focus', 'control-border', 'navigation'].map(key => [key, style.getPropertyValue(`--fv-${key}`).trim()]));
  });
  function luminance(hex) {
    const channels = hex.slice(1).match(/../g).map(channel => parseInt(channel, 16) / 255).map(value => value <= .04045 ? value / 12.92 : ((value + .055) / 1.055) ** 2.4);
    return channels[0] * .2126 + channels[1] * .7152 + channels[2] * .0722;
  }
  function contrast(fg, bg) {
    const values = [luminance(colors[fg]), luminance(colors[bg])].sort((a, b) => b - a);
    return (values[0] + .05) / (values[1] + .05);
  }
  for (const [fg, bg] of [['text', 'surface'], ['muted', 'surface'], ['surface', 'primary'], ['surface', 'primary-hover'], ['surface', 'danger'], ['surface', 'danger-hover'], ['success', 'success-surface'], ['warning', 'warning-surface'], ['info', 'info-surface'], ['danger', 'danger-surface'], ['primary', 'navigation']]) {
    assert(contrast(fg, bg) >= 4.5, `${fg}/${bg} text contrast`);
  }
  for (const fg of ['focus', 'control-border']) assert(contrast(fg, 'surface') >= 3, `${fg} contrast`);

  const quick = page.locator('#quick-help');
  await quick.focus();
  await expect(page.locator('#quick-tip')).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(page.locator('#quick-tip')).toBeHidden();
  await page.keyboard.press('Tab');
  assert.deepEqual(await page.locator('[data-help-article]').evaluate(node => {
    const style = getComputedStyle(node);
    return [style.outlineWidth, style.outlineStyle, style.outlineColor];
  }), ['3px', 'solid', 'rgb(49, 93, 168)']);
  await page.locator('[data-help-article]').click();
  await expect(page.locator('.help-drawer-backdrop')).toBeVisible();
  await expect(page.locator('.help-article h2')).not.toBeEmpty();
  assert(await page.locator('.help-drawer-backdrop').evaluate(node => {
    const box = node.getBoundingClientRect();
    return Math.abs(box.width - innerWidth) < 1 && Math.abs(box.height - innerHeight) < 1
      && getComputedStyle(node.querySelector('.help-drawer')).display === 'flex';
  }), 'Showcase loads the native help layout, not legacy div or user-agent dialog sizing');
  await page.keyboard.press('Escape');
  await page.locator('[data-open-help]').click();
  await expect(page.locator('#help-search')).toBeFocused();
  await page.keyboard.press('Escape');

  const dialog = page.locator('#preview-dialog');
  const trigger = page.locator('#open-dialog');
  await trigger.click();
  await expect(page.locator('#dialog-name')).toBeFocused();
  await page.locator('#preview').click();
  await expect(dialog).toBeVisible();
  assert.equal(await page.locator('#dialog-name').evaluate(node => node.validity.valueMissing), true);
  await page.locator('#dialog-name').focus();
  await page.keyboard.press('Shift+Tab');
  await expect(page.locator('#preview')).toBeFocused();
  await page.keyboard.press('Tab');
  await expect(page.locator('#dialog-name')).toBeFocused();
  await page.keyboard.press('Escape');
  await expect(dialog).toBeHidden();
  await expect(trigger).toBeFocused();
  await trigger.click();
  await page.locator('#dialog-name').fill('Synthetic preview');
  await page.locator('#preview').click();
  await expect(dialog).toBeHidden();
  await expect(trigger).toBeFocused();
  await expect(page.locator('#preview-status')).not.toBeEmpty();
  // Exercise the documented non-tabbable heading autofocus contract as well.
  await page.locator('#dialog-name').evaluate(node => node.removeAttribute('autofocus'));
  await page.locator('#dialog-title').evaluate(node => {node.tabIndex = -1; node.autofocus = true;});
  await trigger.click();
  await expect(page.locator('#dialog-title')).toBeFocused();
  await page.keyboard.press('Shift+Tab');
  await expect(page.locator('#preview')).toBeFocused();
  await page.keyboard.press('Tab');
  await expect(page.locator('#dialog-name')).toBeFocused();
  await page.keyboard.press('Escape');
  await expect(trigger).toBeFocused();
  await page.locator('#dialog-title').evaluate(node => {node.removeAttribute('autofocus'); node.removeAttribute('tabindex');});
  await page.locator('#dialog-name').evaluate(node => {node.autofocus = true;});
  await dialog.evaluate(node => node.insertAdjacentHTML('beforeend', '<fieldset id="radio-regression"><legend>Test choices</legend><label><input id="radio-first" type="radio" name="test-choice" checked> First</label><label><input id="radio-last" type="radio" name="test-choice"> Last</label></fieldset>'));
  await trigger.click();
  await page.locator('#radio-first').focus();
  await page.keyboard.press('Tab');
  await expect(page.locator('#dialog-name')).toBeFocused();
  await page.keyboard.press('Shift+Tab');
  await expect(page.locator('#radio-first')).toBeFocused();
  await page.keyboard.press('ArrowDown');
  await expect(page.locator('#radio-last')).toBeChecked();
  await page.keyboard.press('Tab');
  await expect(page.locator('#dialog-name')).toBeFocused();
  await page.keyboard.press('Escape');
  await expect(trigger).toBeFocused();
  await page.locator('#radio-regression').evaluate(node => node.remove());
  // A widget's consumed Tab must not be overridden by the dialog controller.
  await trigger.click();
  await page.locator('#preview').evaluate(node => {
    node._consumeTab = event => {if (event.key === 'Tab') event.preventDefault();};
    node.addEventListener('keydown', node._consumeTab);
  });
  await page.locator('#preview').focus();
  await page.keyboard.press('Tab');
  await expect(page.locator('#preview')).toBeFocused();
  await page.locator('#preview').evaluate(node => node.removeEventListener('keydown', node._consumeTab));
  await page.keyboard.press('Escape');
  // Test effective inherited disabling with a separate logical fallback.
  await page.evaluate(async () => {
    const {createDialog} = await import('/static/shared/dialog.mjs');
    const host = document.createElement('div');
    host.id = 'focus-regression';
    host.innerHTML = '<fieldset><button id="effective-trigger">Open</button></fieldset><button id="effective-fallback">Fallback</button><dialog><input autofocus><button data-dialog-close>Close</button></dialog>';
    document.querySelector('main').append(host);
    const modal = host.querySelector('dialog');
    const controller = createDialog(modal, {fallbackFocus: host.querySelector('#effective-fallback')});
    const opener = host.querySelector('#effective-trigger');
    opener.focus();
    controller.open(opener);
    host.querySelector('fieldset').disabled = true;
    controller.close();
    controller.destroy();
  });
  await expect(page.locator('#effective-fallback')).toBeFocused();
  await page.locator('#focus-regression').evaluate(node => node.remove());
  for (const state of ['hidden', 'inert', 'display', 'visibility', 'nonfocusable']) {
    await page.evaluate(async state => {
      const {createDialog} = await import('/static/shared/dialog.mjs');
      const host = document.createElement('div');
      host.id = 'unfocusable-regression';
      host.innerHTML = '<div id="invoker-wrapper"><button id="unfocusable-trigger">Open</button></div><button id="usable-fallback">Fallback</button><dialog><input autofocus></dialog>';
      if (state === 'nonfocusable') host.querySelector('#invoker-wrapper').innerHTML = '<span id="unfocusable-trigger" tabindex="0">Open</span>';
      document.querySelector('main').append(host);
      const controller = createDialog(host.querySelector('dialog'), {fallbackFocus: host.querySelector('#usable-fallback')});
      const opener = host.querySelector('#unfocusable-trigger');
      opener.focus();
      controller.open(opener);
      const wrapper = host.querySelector('#invoker-wrapper');
      if (state === 'hidden') wrapper.hidden = true;
      if (state === 'inert') wrapper.inert = true;
      if (state === 'display') wrapper.style.display = 'none';
      if (state === 'visibility') wrapper.style.visibility = 'hidden';
      if (state === 'nonfocusable') {
        opener.removeAttribute('tabindex');
      }
      controller.close();
      controller.destroy();
    }, state);
    await expect(page.locator('#usable-fallback')).toBeFocused();
    await page.locator('#unfocusable-regression').evaluate(node => node.remove());
  }
  await dialog.evaluate(node => node.insertAdjacentHTML('beforeend', '<button id="visibility-regression" style="visibility:hidden">Hidden</button>'));
  await trigger.click();
  await page.locator('#preview').focus();
  await page.keyboard.press('Tab');
  await expect(page.locator('#dialog-name')).toBeFocused();
  await page.keyboard.press('Escape');
  await page.locator('#visibility-regression').evaluate(node => node.remove());
  for (const state of ['', 'true', 'plaintext-only']) {
    await dialog.evaluate((node, state) => {
      const editor = document.createElement('div');
      editor.id = 'editable-regression';
      editor.setAttribute('contenteditable', state);
      editor.textContent = 'Synthetic editor';
      node.append(editor);
    }, state);
    await trigger.click();
    await page.locator('#preview').focus();
    await page.keyboard.press('Tab');
    await expect(page.locator('#editable-regression')).toBeFocused();
    await page.keyboard.press('Tab');
    await expect(page.locator('#dialog-name')).toBeFocused();
    await page.keyboard.press('Shift+Tab');
    await expect(page.locator('#editable-regression')).toBeFocused();
    await page.keyboard.press('Escape');
    await page.locator('#editable-regression').evaluate(node => node.remove());
  }
  assert.deepEqual(await snapshot(), original, 'Components never mutate financial records/results');

  await mkdir(output, {recursive: true});
  for (const width of [1280, 390, 320]) {
    await page.setViewportSize({width, height: 1000});
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth && document.querySelector('main').scrollWidth <= document.querySelector('main').clientWidth), 'No page or opted-in content overflow');
    await page.locator('#standard .fv-table-scroll').focus();
    assert.equal(await page.locator('#standard .fv-table-scroll').evaluate(node => getComputedStyle(node).overflowX), 'auto');
    if (width === 390) {
      await page.locator('#standard .fv-table-scroll').evaluate(node => {node.scrollLeft = document.documentElement.dir === 'rtl' ? -100 : 100;});
      assert.notEqual(await page.locator('#standard .fv-table-scroll').evaluate(node => node.scrollLeft), 0);
      await page.locator('#standard .fv-table-scroll').evaluate(node => {node.scrollLeft = 0;});
    }
    assert.deepEqual(errors, []);
    await page.screenshot({path: `${output}/${locale}-${width}.png`, fullPage: true});
    await trigger.click();
    await expect(dialog).toBeVisible();
    const box = await dialog.boundingBox();
    assert(box.x >= 0 && box.x + box.width <= width, 'Dialog fits narrow viewport');
    await page.screenshot({path: `${output}/${locale}-${width}-dialog.png`});
    await page.locator('#cancel-dialog').click();
    await expect(trigger).toBeFocused();
  }
  assert.deepEqual(errors, []);
  await verifyNavigation(page, baseURL, locale, output);
  await verifyDashboard(page, baseURL, locale, output);
  await verifyAssets(page, baseURL, locale, output);
  await verifyTransactions(page, baseURL, locale, output);
  await verifyIncome(page, baseURL, locale, output, taxPath);
  await verifyExpenses(page, baseURL, locale, output, hydroPath, energirPath);
  await verifyEmployment(page, baseURL, locale, output);
  await verifyAdministration(page, baseURL, locale, output);
  await verifyHelp(page, baseURL, locale, output);
  await verifyAcceptance(page, baseURL, locale, output);
  await verifyTextSize(page, baseURL, locale, output);
  assert.deepEqual(errors, []);
  console.log('SAGE_PRIMITIVES_PASSED');
} finally {
  await browser.close();
}

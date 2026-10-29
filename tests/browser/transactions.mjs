// SPDX-FileCopyrightText: 2026 Mindstep Corporation
// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

import assert from 'node:assert/strict';
import {expect} from '@playwright/test';

export async function verifyTransactions(page, baseURL, locale, output) {
  async function api(url, method = 'GET', payload) {
    return page.evaluate(async ({url, method, payload}) => {
      const response = await fetch(url, {method, headers: {
        'Content-Type': 'application/json',
        'X-CSRF-Token': document.querySelector('meta[name="csrf-token"]').content,
      }, ...(payload === undefined ? {} : {body: JSON.stringify(payload)})});
      if (!response.ok) throw new Error(`Synthetic API ${url}: ${response.status} ${await response.text()}`);
      return response.json();
    }, {url, method, payload});
  }
  async function goto(query = '') {
    await page.goto(`${baseURL}/transactions${query}`);
    await expect(page.locator('#transactions-table-content')).toHaveAttribute('aria-busy', 'false');
    await page.waitForLoadState('networkidle');
    await expect(page.locator('#transactions-error')).toBeHidden();
    await page.locator('.fv-navigation').evaluate(node => {node.open = false;});
    assert(!(await page.locator('main').innerText()).includes('⟦'));
  }
  await goto();
  const help = page.locator('[data-help-article="transaction-import"]');
  await expect(help).toHaveAttribute('data-icon-action', 'help');
  const headerHelp = page.locator('.full-help-button');
  const appearance = locator => locator.evaluate(node => {
    const icon = node.querySelector('.fv-icon');
    const buttonStyle = getComputedStyle(node);
    const iconStyle = getComputedStyle(icon);
    return [buttonStyle.color, buttonStyle.borderRadius, buttonStyle.width, buttonStyle.height,
      iconStyle.maskImage, iconStyle.width, iconStyle.height, getComputedStyle(icon, '::before').content];
  });
  assert.equal((await appearance(help)).at(-1), '"?"', 'Help uses the approved plain question mark');
  assert.deepEqual(await appearance(help), await appearance(headerHelp), 'Header and contextual Help use the same glyph, color, shape and size');
  await help.click();
  await expect(page.locator('.help-drawer-backdrop')).toBeVisible();
  await page.locator('.help-drawer-close').click();
  await expect(help).toBeFocused();
  const original = await api('/api/model/transactions?account_type=non_registered');
  for (const width of [1280, 390, 320]) {
    await page.setViewportSize({width, height: 1000});
    await goto();
    await page.locator('#transaction-density').selectOption('standard');
    const cells = await page.locator('#transactions-table-content tbody').innerText();
    const row = page.locator('#transactions-table-content tbody tr').first();
    const standard = await row.boundingBox();
    await page.locator('#transaction-density').selectOption('compact');
    assert((await row.boundingBox()).height < standard.height);
    assert.equal(await page.locator('#transactions-table-content tbody').innerText(), cells);
    await expect(page.locator('#transactions-table-content table')).toHaveCSS('font-size', '14px');
    const region = page.locator('#transactions-table-content');
    await region.focus();
    await expect(region).toBeFocused();
    await expect(region).toHaveCSS('outline-width', '3px');
    if (width < 900) {
      await region.evaluate(node => {node.scrollLeft = document.documentElement.dir === 'rtl' ? -200 : 200;});
      assert.notEqual(await region.evaluate(node => node.scrollLeft), 0);
      await region.evaluate(node => {node.scrollLeft = 0;});
    }
    assert(await page.locator('.page-content').evaluate(node => node.scrollWidth <= node.clientWidth));
    await page.screenshot({path: `${output}/${locale}-${width}-transactions.png`, fullPage: true});
    const trigger = page.locator('#open-import-button');
    await trigger.click();
    const dialog = page.locator('#import-dialog');
    await expect(page.locator('#transaction-account')).toBeFocused();
    await expect(page.locator('#import-submit-button')).toBeDisabled();
    await page.locator('#import-inline-help').click();
    await expect(page.locator('#import-instructions')).toHaveAttribute('open', '');
    const box = await dialog.boundingBox();
    assert(box.x >= 0 && box.x + box.width <= width);
    for (const selector of ['#close-import-dialog', '#import-inline-help']) {
      const action = page.locator(selector);
      const target = await action.boundingBox();
      assert(target.width >= 44 && target.height >= 44);
      assert.equal((await action.innerText()).trim(), '');
      await expect(action.locator('[aria-hidden="true"]')).toHaveCount(1);
      await action.focus();
      const tooltip = dialog.locator('[role="tooltip"]');
      await expect(tooltip).toBeVisible();
      await expect(tooltip).toHaveText(await action.getAttribute('aria-label'));
      await page.keyboard.press('Escape');
      await expect(tooltip).toHaveCount(0);
      await expect(dialog).toBeVisible();
      await expect(action).toBeFocused();
    }
    await page.locator('#close-import-dialog').focus();
    // Moving focus back creates a new tooltip; dismiss it before testing focus wrap.
    await page.keyboard.press('Escape');
    await page.keyboard.press('Shift+Tab');
    assert(await dialog.evaluate(node => node.contains(document.activeElement)));
    await page.screenshot({path: `${output}/${locale}-${width}-transaction-import.png`});
    await page.keyboard.press('Escape');
    await expect(dialog).toBeHidden();
    await expect(trigger).toBeFocused();
  }
  await goto();
  await expect(page.locator('#transaction-density')).toHaveValue('compact');
  assert.deepEqual(await api('/api/model/transactions?account_type=non_registered'), original, 'Density and dialogs never change facts or semantic ordering');

  const {people} = await api('/api/model/people');
  const {id} = await api('/api/model/accounts', 'POST', {
    category: 'non_registered', account_number: `UX03F-${locale}`, institution: 'Generic CSV', name: `UX03F ${locale}`,
    owners: [{person_id: people[0].id, share: 1}],
  });
  await goto(`?type=non_registered&account_id=${id}`);
  await expect(page.locator('#transaction-account-filter')).toHaveValue(String(id));
  await expect(page.locator('#open-reconcile-button')).toBeEnabled();
  const files = [
    {name: `january-${locale}.csv`, mimeType: 'text/csv', buffer: Buffer.from(`Date,Description,Amount,Balance\n2026-01-10,Synthetic January ${locale},100,100\n`)},
    {name: `february-${locale}.csv`, mimeType: 'text/csv', buffer: Buffer.from(`Date,Description,Amount,Balance\n2026-02-10,Synthetic February ${locale},25,125\n`)},
  ];
  async function selectFiles(selected) {
    await page.locator('#open-import-button').click();
    await page.locator('#transaction-import-form input[type="file"]').first().setInputFiles(selected);
    for (const file of selected) await expect(page.locator('#import-file-review')).toContainText(file.name);
  }
  let release;
  const hold = new Promise(resolve => {release = resolve;});
  let importRequests = 0;
  const delay = async route => {importRequests++; await hold; await route.continue();};
  await page.route('**/api/model/transactions/import', delay);
  await selectFiles(files);
  await page.locator('#import-submit-button').click();
  await expect(page.locator('#transaction-import-form')).toHaveAttribute('aria-busy', 'true');
  await expect(page.locator('#import-submit-button')).toBeDisabled();
  await expect(page.locator('#close-import-dialog')).toBeDisabled();
  await expect(page.locator('#import-inline-help')).toBeDisabled();
  assert.equal(await page.locator('#import-inline-help').evaluate(node => getComputedStyle(node).color),
    await page.locator('#close-import-dialog').evaluate(node => getComputedStyle(node).color), 'Disabled Help retains the shared disabled color');
  await page.locator('#transaction-import-form').evaluate(node => node.dispatchEvent(new Event('submit', {bubbles: true, cancelable: true})));
  await page.keyboard.press('Escape');
  await expect(page.locator('#import-dialog')).toBeVisible();
  release();
  await expect(page.locator('#import-dialog')).toBeHidden();
  assert.equal(importRequests, 1, 'Busy submit must not send another import');
  await page.unroute('**/api/model/transactions/import', delay);
  await expect(page.locator('#open-import-button')).toBeFocused();
  const imported = await api(`/api/model/transactions?account_id=${id}`);
  assert.equal(imported.transactions.length, 2);
  assert.deepEqual(imported.transactions.map(row => row.description), [`Synthetic February ${locale}`, `Synthetic January ${locale}`]);
  await selectFiles(files);
  await page.locator('#import-submit-button').click();
  await expect(page.locator('#import-dialog')).toBeHidden();
  assert.deepEqual(await api(`/api/model/transactions?account_id=${id}`), imported, 'Reimport does not duplicate transactions or alter balances');
  await expect(page.locator('#toast')).toContainText('2');

  await page.locator('#open-reconcile-button').click();
  await page.locator('#reconcile-date').fill('2026-02-10');
  await page.locator('#reconcile-amount').fill('125.00');
  await page.locator('#reconcile-submit-button').click();
  await expect(page.locator('#reconcile-dialog')).toBeHidden();
  await expect(page.locator('#open-reconcile-button')).toBeFocused();
  const late = {name: `late-${locale}.csv`, mimeType: 'text/csv', buffer: Buffer.from(`Date,Description,Amount,Balance\n2026-01-20,Synthetic late evidence ${locale},-10,90\n`)};
  await selectFiles([late]);
  await page.locator('#import-submit-button').click();
  await expect(page.locator('#import-confirm-dialog')).toBeVisible();
  await expect(page.locator('#import-confirm-cancel')).toBeFocused();
  await page.screenshot({path: `${output}/${locale}-transaction-confirm.png`});
  await page.keyboard.press('Escape');
  await expect(page.locator('#import-confirm-dialog')).toBeHidden();
  await expect(page.locator('#import-submit-button')).toBeEnabled();
  await expect(page.locator('#import-file-review')).toContainText(late.name);
  assert.deepEqual(await api(`/api/model/transactions?account_id=${id}`), imported);
  await page.locator('#import-submit-button').click();
  await page.locator('#import-confirm-continue').click();
  await expect(page.locator('#import-dialog')).toBeHidden();
  assert.equal((await api(`/api/model/transactions?account_id=${id}`)).transactions.length, 3);
  assert.equal((await api(`/api/model/accounts/${id}/reconciliation`)).needs_review, true);

  await selectFiles([{name: 'invalid.csv', mimeType: 'text/csv', buffer: Buffer.from('not,csv,headers\n1,2,3\n')}]);
  await page.locator('#import-submit-button').click();
  await expect(page.locator('#import-result')).toHaveAttribute('role', 'alert');
  await expect(page.locator('#import-submit-button')).toBeEnabled();
  await expect(page.locator('#import-file-review')).toContainText('invalid.csv');
  await page.keyboard.press('Escape');
  await expect(page.locator('#import-dialog')).toBeHidden();
  const failure = route => route.fulfill({status: 503, json: {error: 'Synthetic failure'}});
  await page.route('**/api/model/transactions?*', failure);
  await page.locator('#transaction-account-filter').selectOption('');
  await expect(page.locator('#transactions-error')).toBeVisible();
  await expect(page.locator('#transactions-table-content')).toHaveAttribute('aria-busy', 'false');
  await page.unroute('**/api/model/transactions?*', failure);
  await page.locator('#transactions-retry').click();
  await expect(page.locator('#transactions-error')).toBeHidden();
  await expect(page.locator('#transactions-table-content')).toHaveAttribute('aria-busy', 'false');
  await page.locator('[data-type="tfsa"]').click();
  await expect(page.locator('[data-type="tfsa"]')).toHaveAttribute('aria-pressed', 'true');
  await expect(page).toHaveURL(/type=tfsa/);
  await page.locator('[data-type="non_registered"]').click();
  await page.locator('#transaction-account-filter').selectOption(String(id));
  await expect(page.locator('#transactions-table-content')).toContainText('Synthetic late evidence');
}

// SPDX-FileCopyrightText: 2026 Mindstep Corporation
// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {chromium, expect} from '@playwright/test';

const [baseURL, hydroPath, csvPath, taxPath] = process.argv.slice(2);
assert.match(baseURL, /^http:\/\/127\.0\.0\.1:\d+$/);
const browser = await chromium.launch();
const context = await browser.newContext({viewport: {width: 1280, height: 900}});
const page = await context.newPage();
const errors = [];
page.on('pageerror', (error) => errors.push(error.message));
page.on('dialog', (dialog) => dialog.accept());
async function goto(path) {
  await page.goto(baseURL + path);
  await page.waitForLoadState('networkidle');
}
async function api(url, method = 'GET', payload = undefined) {
  return page.evaluate(async ({url, method, payload}) => {
    const response = await fetch(url, {method, headers: {
      'Content-Type': 'application/json',
      'X-CSRF-Token': document.querySelector('meta[name="csrf-token"]')?.content || document.querySelector('input[name="csrf_token"]')?.value || '',
    }, ...(payload === undefined ? {} : {body: JSON.stringify(payload)})});
    return {status: response.status, data: await response.json()};
  }, {url, method, payload});
}
async function language(code) {
  await goto('/application-settings');
  await page.locator('#locale').selectOption(code);
  await Promise.all([page.waitForNavigation(), page.locator('form[action="/application-settings/language"] button[type="submit"]').click()]);
  await expect(page.locator('html')).toHaveAttribute('lang', code);
}
async function snapshot() {
  const accounts = await api('/api/model/accounts');
  const projection = await api('/api/salary-projection?start_year=2026&end_year=2027');
  assert.equal(accounts.status, 200);
  assert.equal(projection.status, 200);
  assert(projection.data.people.some((person) => person.projection.length > 0), 'Synthetic projection must calculate actual rows');
  return {accounts: accounts.data, computed: projection.data.people.map((person) => ({id: person.id, projection: person.projection}))};
}
try {
  await language('en-CA');
  await goto('/');
  const original = await snapshot();
  for (const code of ['en-CA', 'fr-CA']) {
    await language(code);
    await goto('/salary-projection');
    await expect(page.locator('#salary-table')).not.toBeEmpty();
    assert.deepEqual(await snapshot(), original, 'Locale changes must not alter computed or factual values');
  }

  for (const [index, code] of ['en-CA', 'fr-CA'].entries()) {
    await language(code);
    await goto('/setup');
    const personName = `Original English person ${code}`;
    await page.locator('#person-form [name="name"]').fill(personName);
    await page.locator('#person-form [name="birth_date"]').fill('1970-01-01');
    await page.locator('#person-form button[type="submit"]').click();
    await expect(page.locator('#people-list')).toContainText(personName);

    await goto('/accounts');
    await page.locator('[data-add-account-type="non_registered"]').click();
    await page.locator('#account-dialog-form [name="account_number"]').fill(`BROWSER-${index}`);
    await page.locator('#account-dialog-form [name="institution"]').fill('Original Bank');
    await page.locator('#account-dialog-form [name="name"]').fill(`Original English account ${code}`);
    await page.locator('#dialog-owner-fields [data-owner-id]').first().check();
    await page.locator('#account-dialog-form [name="balance_amount"]').fill('1234.56');
    await page.locator('#account-dialog-form button[type="submit"]').click();
    await expect(page.locator('#account-dialog')).toBeHidden();
    const account = (await api('/api/model/accounts')).data.accounts.find((item) => item.account_number === `BROWSER-${index}`);
    assert(account, 'Account must persist');
    await page.locator(`[data-edit-account="${account.id}"]`).click();
    await page.locator('#account-dialog-form [name="name"]').fill(`Edited English account ${code}`);
    await page.locator('#account-dialog-form button[type="submit"]').click();
    await expect(page.locator('#account-dialog')).toBeHidden();
    const invalidAccount = await api('/api/model/accounts', 'POST', {category: 'non_registered', account_number: 'INVALID', owners: []});
    assert.equal(invalidAccount.status, 400);
    assert.equal(invalidAccount.data.error_language, code);

    await goto('/income');
    await expect(page.locator('#income-tabs button').first()).toBeVisible();
    await page.locator('#income-import').click();
    await page.locator('#income-import-file').setInputFiles(taxPath);
    await page.locator('#income-import-preview').click();
    await expect(page.locator('#income-dialog-backdrop')).toBeVisible();
    await expect(page.locator('#income-dialog-backdrop')).toContainText('Alex Example');
    await expect(page.locator('#income-form [name="employment_income"]')).toHaveValue('123456.78');
    await page.locator('#income-form button[type="submit"]').click();
    await expect(page.locator('#income-dialog-backdrop')).toBeHidden();
    await page.locator('#income-add').click();
    await page.locator('#income-form [name="tax_year"]').fill(String(2028 + index));
    await page.locator('#income-form [name="province_of_residence"]').selectOption('QC');
    await page.locator('#income-form [name="employment_income"]').fill('100000');
    await page.locator('#income-form button[type="submit"]').click();
    await expect(page.locator('#income-dialog-backdrop')).toBeHidden();
    await expect(page.locator('#income-summary')).toContainText('100');

    await goto('/expenses');
    await page.locator('#expense-categories').click();
    await page.locator('#category-add').click();
    const categoryName = `Original English category ${code}`;
    await page.locator('#category-editor-form [name="name"]').fill(categoryName);
    await page.locator('#category-editor-save').click();
    await page.waitForLoadState('networkidle');
    await expect(page.locator('#category-dialog-backdrop')).toBeVisible();
    await expect(page.locator('#category-dialog-backdrop')).toContainText(categoryName);
    await page.locator('#category-dialog-close').click();
    await page.locator('#expense-add').click();
    const expenseForm = page.locator('#expense-dialog-backdrop form');
    await expenseForm.locator('[name="name"]').fill(`Original English spending ${code}`);
    await expenseForm.locator('[name="category_id"]').selectOption({label: `${categoryName} (${code === 'en-CA' ? 'Required' : 'Obligatoire'})`});
    await expenseForm.locator('[name="amount"]').fill('88.25');
    await expenseForm.locator('[name="period_start"]').fill('2026-03-01');
    await expenseForm.locator('[name="period_end"]').fill('2026-03-31');
    await expenseForm.locator('button[type="submit"]').click();
    await page.waitForLoadState('networkidle');
    await expect(page.locator('#expense-dialog-backdrop')).toBeHidden();
    const records = (await api('/api/expenses?year=2026')).data;
    assert(records.some((item) => item.name === `Original English spending ${code}` && item.amount === '88.25'));

    await page.locator('#expense-import').click();
    await page.locator('#expense-import-file').setInputFiles(hydroPath);
    await page.locator('#import-preview-btn').click();
    await expect(page.locator('#import-confirm')).toBeVisible();
    await page.locator('#import-confirm').click();
    await page.waitForLoadState('networkidle');
    await expect(page.locator('#expense-import-dialog-backdrop')).toBeHidden();
    await expect(page).toHaveURL(/year=2026/);
    const imported = (await api('/api/expenses?year=2026')).data.filter((item) => item.source_kind === 'imported');
    assert(imported.some((item) => item.amount === '31.00' && item.period_start === '2026-01-01'));

    await goto(`/transactions?account_id=${account.id}&type=non_registered`);
    await page.locator('#open-import-button').click();
    await page.locator('#transaction-account').selectOption(String(account.id));
    await page.locator('#transaction-import-form input[type="file"]').first().setInputFiles({
      name: `synthetic-bank-${code}.csv`, mimeType: 'text/csv',
      buffer: Buffer.from(readFileSync(csvPath, 'utf8').replace('2027-07-01', `2027-07-0${index + 1}`)),
    });
    await page.locator('#import-submit-button').click();
    await expect(page.locator('#import-dialog')).toBeHidden();
    await expect(page.locator('#transactions-table-content')).toContainText('Original English bank evidence');
    assert(!(await page.locator('body').innerText()).includes('⟦'), `Missing translation on ${code} workflow`);
  }

  // Fresh browser context proves persisted selection is server-owned, not a browser cache.
  const restartedContext = await browser.newContext();
  const restarted = await restartedContext.newPage();
  await restarted.goto(baseURL + '/about');
  await expect(restarted.locator('html')).toHaveAttribute('lang', 'fr-CA');
  await restartedContext.close();
  await language('ar-XB');
  await goto('/expenses');
  await expect(page.locator('html')).toHaveAttribute('dir', 'rtl');
  await page.locator('.full-help-button').click();
  await expect(page.locator('.help-drawer-backdrop')).toBeVisible();
  await expect(page.locator('#help-search')).toBeFocused();
  const drawer = await page.locator('.help-drawer').boundingBox();
  assert(drawer && drawer.x < 2, 'RTL drawer must anchor at the left inline end');
  await page.keyboard.press('Shift+Tab');
  assert(await page.locator('.help-drawer').evaluate((element) => element.contains(document.activeElement)), 'Focus must stay in help');
  await page.keyboard.press('Escape');
  await expect(page.locator('.help-drawer-backdrop')).toBeHidden();
  await expect(page.locator('.full-help-button')).toBeFocused();
  await page.locator('#expense-add').click();
  const close = await page.locator('#expense-dialog-close').boundingBox();
  const modal = await page.locator('#expense-dialog-backdrop').boundingBox();
  assert(close && modal && close.x < modal.x + modal.width / 2, 'RTL close control must mirror to inline end');
  await page.keyboard.press('Escape');
  await expect(page.locator('#expense-dialog-backdrop')).toBeHidden();
  await page.setViewportSize({width: 390, height: 844});
  await goto('/income');
  assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), 'Mobile layout must fit viewport');
  await goto('/disclaimer');
  await expect(page.locator('.legal-document')).toHaveAttribute('lang', 'en-CA');
  await expect(page.locator('.legal-document')).toHaveAttribute('dir', 'ltr');
  assert.deepEqual(errors, [], 'No unexpected browser JavaScript exceptions');
  console.log('BROWSER_ACCEPTANCE_PASSED');
} finally {
  await context.close();
  await browser.close();
}

// SPDX-FileCopyrightText: 2026 Mindstep Corporation
// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {expect} from '@playwright/test';

export async function verifyExpenses(page, baseURL, locale, output, hydroPath, energirPath, montrealPath, montrealFrenchPath) {
  const legacyModule = route => route.fulfill({contentType: 'text/javascript', body: 'throw new Error("Legacy Expense module requested");'});
  await page.route('**/expenses/expenses.mjs?v=20261006-1', legacyModule);
  async function api() {
    return page.evaluate(async () => {
      const response = await fetch('/api/expenses');
      if (!response.ok) throw new Error('Synthetic expense read failed');
      return response.json();
    });
  }
  async function goto() {
    await page.goto(`${baseURL}/expenses?year=2026`);
    await page.waitForLoadState('networkidle');
    await page.locator('.fv-navigation').evaluate(node => {node.open = false;});
    assert(!(await page.locator('main').innerText()).includes('⟦'));
  }
  await goto();
  const original = await api();
  const originalTotals = await page.locator('.expense-summary-grid').allTextContents();
  for (const width of [1280, 390, 320]) {
    await page.setViewportSize({width, height: 1000});
    await goto();
    const details = page.locator('.expense-record-details');
    await details.evaluate(node => {node.open = true;});
    const region = details.locator('.fv-table-scroll');
    await region.focus();
    await expect(region).toHaveCSS('outline-width', '3px');
    assert(await page.locator('.page-content').evaluate(node => node.scrollWidth <= node.clientWidth));
    await page.screenshot({path: `${output}/${locale}-${width}-expenses.png`, fullPage: true});
    await page.locator('#expense-categories').click();
    await expect(page.locator('#category-dialog-backdrop')).toHaveJSProperty('open', true);
    await page.locator('#category-add').click();
    const editor = page.locator('#category-editor-backdrop');
    await expect(editor.locator('[name="name"]')).toBeFocused();
    await page.locator('#category-editor-close').focus();
    await page.keyboard.press('Shift+Tab');
    assert(await editor.evaluate(node => node.contains(document.activeElement)));
    await page.keyboard.press('Escape');
    await expect(editor).toBeHidden();
    await expect(page.locator('#category-dialog-backdrop')).toHaveJSProperty('open', true);
    await page.keyboard.press('Escape');
    await expect(page.locator('#expense-categories')).toBeFocused();
  }
  assert.deepEqual(await api(), original, 'Dialog and layout changes never modify factual periods or amounts');
  assert.deepEqual(await page.locator('.expense-summary-grid').allTextContents(), originalTotals, 'Seasonal estimate displays and unavailable/review states remain unchanged');

  const name = `UX03H ${locale}`;
  await page.locator('#expense-categories').click();
  await page.locator('#category-add').click();
  await page.locator('#category-editor-form [name="name"]').fill('   ');
  await page.locator('#category-editor-save').click();
  await expect(page.locator('#category-editor-backdrop [data-form-message]')).toHaveAttribute('role', 'alert');
  await expect(page.locator('#category-editor-form [name="name"]')).toHaveValue('   ');
  await page.locator('#category-editor-form [name="name"]').fill(name);
  await page.locator('#category-editor-save').click();
  await expect(page.locator('#category-dialog-backdrop')).toHaveJSProperty('open', true);
  await expect(page.locator('#category-dialog-backdrop [role="status"]')).toBeVisible();
  const categoryRow = page.locator('#category-dialog-backdrop tbody tr').filter({hasText: name});
  await expect(categoryRow).toBeVisible();
  await categoryRow.locator('[data-category-edit]').click();
  await page.locator('#category-editor-form [name="name"]').fill(`${name} edited`);
  await page.locator('#category-editor-save').click();
  await expect(page.locator('#category-dialog-backdrop')).toHaveJSProperty('open', true);
  await expect(page.locator('#category-dialog-backdrop')).toContainText(`${name} edited`);
  await page.keyboard.press('Escape');
  await page.locator('#expense-add').click();
  const form = page.locator('#expense-dialog-backdrop form');
  await form.locator('[name="name"]').fill(`Irregular evidence ${locale}`);
  const categoryId = await form.locator('[name="category_id"] option').evaluateAll((nodes, label) => nodes.find(node => node.textContent.startsWith(label)).value, `${name} edited`);
  await form.locator('[name="category_id"]').selectOption(categoryId);
  await form.locator('[name="amount"]').fill('77.13');
  await form.locator('[name="period_start"]').fill('2025-12-19');
  await form.locator('[name="period_end"]').fill('2026-02-07');
  await form.locator('[name="period_kind"]').selectOption('recurring_statement');
  await form.locator('button[type="submit"]').click();
  await expect(page.locator('#expense-dialog-backdrop')).toBeHidden();
  const manual = (await api()).find(item => item.name === `Irregular evidence ${locale}`);
  assert.equal(manual.amount, '77.13');
  assert.equal(manual.period_start, '2025-12-19');
  assert.equal(manual.period_end, '2026-02-07');
  await page.locator('.expense-record-details').evaluate(node => {node.open = true;});
  await page.evaluate(async id => {
    const response = await fetch(`/api/expenses/categories/${id}`, {method: 'PUT',
      headers: {'Content-Type': 'application/json', 'X-CSRF-Token': document.querySelector('meta[name="csrf-token"]').content},
      body: JSON.stringify({name: `Reclassified historical category ${id}`, classification: 'discretionary', active: false})});
    if (!response.ok) throw new Error('Synthetic category reclassification failed');
  }, categoryId);
  await goto();
  await page.locator('.expense-record-details').evaluate(node => {node.open = true;});
  await page.locator('.expense-record-details tbody tr').filter({hasText: manual.name}).locator('[data-expense-edit]').click();
  await expect(form.locator('[name="category_id"]')).toHaveValue(String(categoryId));
  await expect(form.locator('[name="period_start"]')).toHaveValue('2025-12-19');
  await form.locator('[name="name"]').fill(`Edited irregular evidence ${locale}`);
  await form.locator('button[type="submit"]').click();
  await expect(page.locator('#expense-dialog-backdrop')).toBeHidden();
  const edited = (await api()).find(item => item.id === manual.id);
  assert.equal(edited.name, `Edited irregular evidence ${locale}`);
  for (const field of ['amount', 'period_start', 'period_end', 'period_kind', 'source_kind', 'association_kind', 'association_id', 'category_id', 'category_name', 'classification']) assert.equal(edited[field], manual[field]);
  // The following import phase creates new evidence, which requires an active category.
  await page.evaluate(async id => {
    const response = await fetch(`/api/expenses/categories/${id}`, {method: 'PUT',
      headers: {'Content-Type': 'application/json', 'X-CSRF-Token': document.querySelector('meta[name="csrf-token"]').content},
      body: JSON.stringify({name: `Reclassified historical category ${id}`, classification: 'discretionary', active: true})});
    if (!response.ok) throw new Error('Synthetic category reactivation failed');
  }, categoryId);
  await goto();

  const buffer = await readFile(hydroPath);
  const files = ['first', 'duplicate'].map(part => ({name: `hydro-${locale}-${part}.pdf`, mimeType: 'application/pdf', buffer}));
  await page.locator('#expense-import').click();
  await expect(page.locator('#import-preview-btn')).toBeDisabled();
  await page.locator('#expense-import-dialog-backdrop [data-help-article]').first().click();
  await expect(page.locator('[data-import-help] strong')).toBeVisible();
  await page.locator('#expense-import-file').setInputFiles(files);
  for (const file of files) await expect(page.locator('#expense-file-review')).toContainText(file.name);
  let release;
  const hold = new Promise(resolve => {release = resolve;});
  let previews = 0;
  const delay = async route => {previews++; await hold; await route.continue();};
  await page.route('**/api/expenses/import/preview', delay);
  await page.locator('#import-preview-btn').click();
  await expect(page.locator('#expense-import-dialog-backdrop')).toHaveAttribute('aria-busy', 'true');
  await expect(page.locator('#expense-import-close')).toBeDisabled();
  await page.locator('#import-preview-btn').evaluate(node => node.dispatchEvent(new Event('click', {bubbles: true})));
  await page.keyboard.press('Escape');
  await expect(page.locator('#expense-import-dialog-backdrop')).toBeVisible();
  release();
  await expect(page.locator('#import-step-preview')).toBeVisible();
  assert.equal(previews, 1);
  await page.unroute('**/api/expenses/import/preview', delay);
  for (let index = 0; index < 2; index++) {
    await expect(page.locator('#import-confirm')).toBeEnabled();
    await page.locator('#import-name').fill(`Hydro identity ${locale}`);
    await page.locator('#import-category').selectOption(categoryId);
    await page.locator('#import-confirm').click();
    if (index === 0) await expect(page.locator('#expense-import-queue-status')).toContainText(files[1].name);
  }
  await expect(page.locator('#expense-import-dialog-backdrop')).toBeHidden();
  const imports = (await api()).filter(item => item.category_id === Number(categoryId) && item.source_kind === 'imported');
  assert.equal(imports.length, 2);
  assert(imports.every(item => item.amount === '31.00' && item.period_start === '2026-01-01' && item.period_end === '2026-01-31'));
  assert(imports.every(item => item.overlap_status === 'potential'), 'Repeated source bytes still require overlap review');
  const rows = page.locator('.expense-record-details tbody tr').filter({hasText: `Hydro identity ${locale}`});
  await expect(rows).toHaveCount(2);
  await rows.first().locator('input[name="note"]').fill('Synthetic duplicate excluded');
  await rows.first().locator('button[value="false"]').click();
  const remaining = page.locator('.expense-record-details tbody tr').filter({hasText: `Hydro identity ${locale}`}).filter({has: page.locator('input[name="note"]')});
  await remaining.locator('input[name="note"]').fill('Synthetic reviewed source included');
  await remaining.locator('button[value="true"]').click();
  const resolved = (await api()).filter(item => imports.some(record => record.id === item.id));
  assert.deepEqual(resolved.map(item => item.overlap_status).sort(), ['resolved_exclude', 'resolved_include']);
  await page.locator('#expense-import').click();
  await page.locator('#expense-import-dialog-backdrop [data-help-article="expense-source-energir"]').click();
  await expect(page.locator('[data-import-help] strong')).toContainText('Énergir');
  await page.locator('#expense-import-file').setInputFiles(energirPath);
  await page.locator('#import-preview-btn').click();
  await expect(page.locator('#import-step-preview')).toBeVisible();
  await expect(page.locator('#import-provider-key')).toHaveValue('energir');
  await expect(page.locator('#import-provider')).toHaveAttribute('lang', locale === 'en-CA' ? 'en-CA' : 'fr-CA');
  await expect(page.locator('#import-name')).toHaveValue('Énergir');
  await page.locator('#import-name').fill(`Synthetic gas ${locale}`);
  await page.locator('#import-category').selectOption(categoryId);
  await page.screenshot({path: `${output}/${locale}-energir-preview.png`, fullPage: true});
  await page.locator('#import-confirm').click();
  await expect(page.locator('#expense-import-dialog-backdrop')).toBeHidden();
  const gas = (await api()).filter(item => item.name === `Synthetic gas ${locale}`);
  assert.equal(gas.length, 1);
  assert.equal(gas[0].parser_name, 'energir');
  assert.equal(gas[0].amount, '114.98');
  assert.equal(gas[0].period_start, '2025-12-15');
  assert.equal(gas[0].period_end, '2026-01-14');
  const beforeTaxPreview = await api();
  await page.locator('#expense-import').click();
  await page.locator('#expense-import-dialog-backdrop [data-help-article="expense-source-montreal-tax"]').click();
  await expect(page.locator('[data-import-help] strong')).toContainText('Montréal');
  await page.locator('#expense-import-file').setInputFiles(montrealPath);
  await page.locator('#import-preview-btn').click();
  await expect(page.locator('#import-step-preview')).toBeVisible();
  await expect(page.locator('#import-provider-key')).toHaveValue('montreal-tax');
  await expect(page.locator('#import-provider')).toHaveAttribute('lang', locale === 'en-CA' ? 'en-CA' : 'fr-CA');
  await expect(page.locator('#import-name')).toHaveValue('Montréal municipal property tax · 123 Example Street · 000001-00');
  assert.deepEqual(await api(), beforeTaxPreview, 'Tax preview never persists expense evidence');
  await page.locator('#import-name').fill(`Synthetic municipal tax ${locale}`);
  await page.locator('#import-category').selectOption(categoryId);
  const property = await page.locator('#import-association option[value^="real_estate:"]').first().getAttribute('value');
  assert(property, 'Synthetic runtime supplies a property association');
  await page.locator('#import-association').selectOption(property);
  await page.locator('#import-confirm').click();
  await expect(page.locator('#expense-import-dialog-backdrop')).toBeHidden();
  const tax = (await api()).filter(item => item.name === `Synthetic municipal tax ${locale}`);
  assert.equal(tax.length, 1);
  assert.equal(tax[0].amount, '4000.03');
  assert.equal(tax[0].period_start, '2026-01-01');
  assert.equal(tax[0].period_end, '2026-12-31');
  assert.equal(tax[0].period_kind, 'annual_or_one_time');
  assert.equal(tax[0].association_kind, 'real_estate');
  assert.equal(tax[0].association_id, Number(property.split(':')[1]));
  assert.equal(tax[0].parser_name, 'montreal-tax');
  const beforeFrenchTaxPreview = await api();
  await page.locator('#expense-import').click();
  await page.locator('#expense-import-file').setInputFiles(montrealFrenchPath);
  await page.locator('#import-preview-btn').click();
  await expect(page.locator('#import-step-preview')).toBeVisible();
  await expect(page.locator('#import-name')).toHaveValue('Montréal municipal property tax · 123 Example Street · 000001-00');
  assert.deepEqual(await api(), beforeFrenchTaxPreview, 'French source preview is read-only');
  await page.locator('#import-name').fill(`Synthetic municipal tax ${locale}`);
  await page.locator('#import-category').selectOption(categoryId);
  await page.locator('#import-association').selectOption(property);
  await page.locator('#import-confirm').click();
  await expect(page.locator('#expense-import-dialog-backdrop')).toBeHidden();
  const languageCopies = (await api()).filter(item => item.name === `Synthetic municipal tax ${locale}`);
  assert.equal(languageCopies.length, 2);
  assert(languageCopies.every(item => item.amount === '4000.03' && item.period_kind === 'annual_or_one_time'));
  assert(languageCopies.every(item => item.overlap_status === 'potential'), 'Language copies require explicit overlap review');
  await page.locator('#expense-import').click();
  await page.locator('#expense-import-file').setInputFiles({name: 'invalid.pdf', mimeType: 'application/pdf', buffer: Buffer.from('Synthetic invalid PDF')});
  await page.locator('#import-preview-btn').click();
  await expect(page.locator('#expense-import-message')).toBeVisible();
  await expect(page.locator('#import-preview-btn')).toBeEnabled();
  await page.keyboard.press('Escape');
  await expect(page.locator('#expense-import')).toBeFocused();
  if (locale === 'ar-XB') {
    const categories = await page.locator('[data-category-edit]').evaluateAll(nodes => nodes.map(node => ({
      id: node.dataset.action.split('/').at(-1), name: node.dataset.name, classification: node.dataset.classification,
    })));
    await page.evaluate(async categories => {
      for (const category of categories) {
        const response = await fetch(`/api/expenses/categories/${category.id}`, {method: 'PUT',
          headers: {'Content-Type': 'application/json', 'X-CSRF-Token': document.querySelector('meta[name="csrf-token"]').content},
          body: JSON.stringify({...category, active: false})});
        if (!response.ok) throw new Error('Synthetic category archive failed');
      }
    }, categories);
    await goto();
    await page.locator('#expense-add').click();
    await expect(form).toBeHidden();
    await page.keyboard.press('Escape');
    await page.locator('.expense-record-details').evaluate(node => {node.open = true;});
    await page.locator('.expense-record-details tbody tr').filter({hasText: edited.name}).locator('[data-expense-edit]').click();
    await expect(form).toBeVisible();
    await expect(form.locator('[name="category_id"]')).toHaveValue(String(categoryId));
    await form.locator('[name="period_start"]').fill('2027-01-19');
    await form.locator('[name="period_end"]').fill('2027-02-07');
    await form.locator('button[type="submit"]').click();
    await expect(page).toHaveURL(/year=2027/);
    await page.locator('.expense-record-details').evaluate(node => {node.open = true;});
    await expect(page.locator('.expense-record-details tbody tr').filter({hasText: edited.name})).toBeVisible();
    await goto();
    await page.locator('#expense-import').click();
    await expect(page.locator('#expense-import-form')).toHaveCount(0);
    await expect(page.locator('#import-open-categories')).toBeVisible();
    await page.locator('#import-open-categories').click();
    await expect(page.locator('#category-editor-backdrop')).toHaveJSProperty('open', true);
    await page.locator('#category-editor-form [name="name"]').fill('Synthetic onboarding');
    await page.locator('#category-editor-save').click();
    await expect(page.locator('#category-dialog-backdrop')).toHaveJSProperty('open', true);
    await expect(page.locator('#category-dialog-backdrop')).toContainText('Synthetic onboarding');
    await page.keyboard.press('Escape');
  }
  const noModule = route => route.fulfill({contentType: 'text/javascript', body: ''});
  await page.route('**/expenses/expenses.mjs?*', noModule);
  await page.goto(`${baseURL}/expenses?year=2026&dialog=categories&message=Synthetic%20fallback%20confirmation`);
  await expect(page.locator('#category-dialog-backdrop')).toBeVisible();
  await expect(page.locator('#category-dialog-backdrop [role="status"]')).toHaveText('Synthetic fallback confirmation');
  await page.unroute('**/expenses/expenses.mjs?*', noModule);
  await page.unroute('**/expenses/expenses.mjs?v=20261006-1', legacyModule);
}

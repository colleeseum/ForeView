// SPDX-FileCopyrightText: 2026 Mindstep Corporation
// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

import assert from 'node:assert/strict';
import {expect} from '@playwright/test';

export async function verifyIncome(page, baseURL, locale, output, taxPath) {
  // A returning browser may still have these pre-native-dialog modules cached.
  // Reject their URLs so the full workflow proves both changed modules are versioned.
  const legacyModule = route => route.fulfill({contentType: 'text/javascript', body: 'throw new Error("Stale Income module URL requested");'});
  await page.route('**/income/income.mjs?v=20261003-1', legacyModule);
  await page.route('**/income/income-corrections.mjs', legacyModule);
  async function api(url, method = 'GET', payload) {
    return page.evaluate(async ({url, method, payload}) => {
      const response = await fetch(url, {method, headers: {'Content-Type': 'application/json',
        'X-CSRF-Token': document.querySelector('meta[name="csrf-token"]').content},
      ...(payload === undefined ? {} : {body: JSON.stringify(payload)})});
      if (!response.ok) throw new Error(`Synthetic income request: ${response.status} ${await response.text()}`);
      return response.json();
    }, {url, method, payload});
  }
  async function goto() {
    await page.goto(`${baseURL}/income`);
    await page.waitForLoadState('networkidle');
    await expect(page.locator('#income-add')).toBeEnabled();
    await page.locator('.fv-navigation').evaluate(node => {node.open = false;});
    assert(!(await page.locator('main').innerText()).includes('⟦'));
  }
  await goto();
  const {people} = await api('/api/model/people');
  const id = people[0].id;
  const original = await api(`/api/income?person_id=${id}`);
  for (const width of [1280, 390, 320]) {
    await page.setViewportSize({width, height: 1000});
    await goto();
    const cardActions = await page.locator('.income-summary-value').evaluateAll(cards => cards.map(card => {
      const button = card.querySelector('[data-icon-action]');
      const cardBox = card.getBoundingClientRect();
      const actionBox = button.getBoundingClientRect();
      const style = getComputedStyle(card);
      const rtl = style.direction === 'rtl';
      const inlineGap = rtl ? actionBox.left - cardBox.left : cardBox.right - actionBox.right;
      const border = parseFloat(rtl ? style.borderLeftWidth : style.borderRightWidth);
      return {bottom: actionBox.bottom, expectedBottom: cardBox.bottom - parseFloat(style.paddingBottom) - parseFloat(style.borderBottomWidth),
        inlineGap, expectedGap: parseFloat(style.paddingInlineEnd) + border,
        color: getComputedStyle(button).color, iconColor: getComputedStyle(button.querySelector('.fv-icon')).color};
    }));
    for (const placement of cardActions) {
      assert(Math.abs(placement.bottom - placement.expectedBottom) < 2, 'Card action aligns at the bottom');
      assert(Math.abs(placement.inlineGap - placement.expectedGap) < 2, 'Card action aligns at the logical end');
      assert.equal(placement.color, placement.iconColor, 'Glyph inherits the shared action color');
    }
    const active = page.locator('#income-tabs [aria-pressed="true"]');
    await expect(active).toHaveCSS('background-color', 'rgb(50, 104, 88)');
    await page.locator('.income-source-details > summary').click();
    await expect(page.locator('#income-history [data-edit-year]').first()).toBeVisible();
    const region = page.locator('#income-history .fv-table-scroll');
    await region.focus();
    await expect(region).toBeFocused();
    await expect(region).toHaveCSS('outline-width', '3px');
    assert(await page.locator('.page-content').evaluate(node => node.scrollWidth <= node.clientWidth));
    await page.screenshot({path: `${output}/${locale}-${width}-income.png`, fullPage: true});
    await page.locator('#income-add').click();
    const editor = page.locator('#income-dialog-backdrop');
    await expect(editor).toHaveJSProperty('open', true);
    await expect(editor.locator('[name="tax_year"]')).toBeFocused();
    const box = await editor.boundingBox();
    assert(box.x >= 0 && box.x + box.width <= width);
    const close = page.locator('#income-dialog-close');
    await expect(close).toHaveAttribute('data-icon-action', 'close');
    await close.focus();
    const tip = editor.locator('[role="tooltip"]');
    await expect(tip).toBeVisible();
    await expect(tip).toHaveText(await close.getAttribute('aria-label'));
    await page.keyboard.press('Escape');
    await expect(tip).toHaveCount(0);
    await expect(editor).toBeVisible();
    await page.keyboard.press('Shift+Tab');
    assert(await editor.evaluate(node => node.contains(document.activeElement)));
    await page.keyboard.press('Escape');
    await expect(editor).toBeHidden();
    await expect(page.locator('#income-add')).toBeFocused();
  }
  assert.deepEqual(await api(`/api/income?person_id=${id}`), original, 'Presentation never changes income facts');
  await page.locator('#income-import').click();
  await expect(page.locator('#income-import-preview')).toBeDisabled();
  await page.locator('#ufile-dialog-backdrop [data-help-article]').first().click();
  await expect(page.locator('#ufile-dialog-backdrop [data-inline-help] strong')).toBeVisible();
  await page.locator('#income-import-file').setInputFiles(taxPath);
  await page.locator('#income-import-preview').click();
  await expect(page.locator('#income-dialog-backdrop')).toBeVisible();
  await expect(page.locator('#income-editor-person')).toContainText('Alex Example');
  await expect(page.locator('#income-form [name="employment_income"]')).toHaveValue('123456.78');
  assert.deepEqual(await api(`/api/income?person_id=${id}`), original, 'PDF preview must not persist facts');
  await page.locator('#income-form button[type="submit"]').click();
  await expect(page.locator('#income-dialog-backdrop')).toBeHidden();
  assert((await api(`/api/income?person_id=${id}`)).records.some(record => record.year === 2024 && record.employment_income === '123456.78'));

  const year = 2031 + ['en-CA', 'fr-CA', 'ar-XB'].indexOf(locale);
  await page.locator('#income-add').click();
  await page.locator('#income-form [name="tax_year"]').fill(String(year));
  await page.locator('#income-form [name="province_of_residence"]').selectOption('QC');
  await page.locator('#income-form [name="employment_income"]').fill('100000');
  await page.locator('#income-form [name="source"]').selectOption('Manual');
  await page.locator('#income-form button[type="submit"]').click();
  await expect(page.locator('#income-dialog-backdrop')).toBeHidden();
  const underlying = await api(`/api/income?person_id=${id}`);
  const action = page.locator('[data-correct-concept="employment_income"]');
  await expect(action).toHaveAttribute('data-icon-action', 'edit');
  await expect(action).toHaveAttribute('aria-label', new RegExp(String(year)));
  const dimensions = await action.boundingBox();
  assert(dimensions.width >= 44 && dimensions.height >= 44);
  await action.click();
  const correction = page.locator('#income-correction-backdrop');
  await expect(correction).toHaveAttribute('aria-busy', 'false');
  await page.locator('#income-correction-form [name="correct_amount"]').fill('105000');
  await page.locator('#income-correction-form [name="reason"]').fill('Synthetic payroll evidence');
  await page.locator('#income-correction-save').click();
  await expect(correction).toBeHidden();
  await expect(action).toBeFocused();
  await expect(action).toHaveAttribute('data-icon-action', 'view');
  let data = await api(`/api/income?person_id=${id}`);
  assert.equal(data.corrections.find(item => item.concept === 'employment_income').revision_number, 1);
  assert.deepEqual(data.records, underlying.records, 'Correction never rewrites the annual source');
  await api(`/api/income/people/${id}/years/${year}`, 'PUT', {
    employment_income: '110000', province_of_residence: 'QC', source: 'Manual',
  });
  await goto();
  await action.click();
  await expect(correction).toHaveAttribute('aria-busy', 'false');
  await expect(page.locator('#income-correction-status')).toBeVisible();
  await expect(page.locator('#income-correction-confirm')).toBeVisible();
  await page.screenshot({path: `${output}/${locale}-income-review.png`});
  await page.locator('#income-correction-confirm').click();
  await expect(correction).toBeHidden();
  await action.click();
  await expect(correction).toHaveAttribute('aria-busy', 'false');
  await expect(page.locator('#income-correction-confirm')).toBeHidden();
  await page.locator('#income-correction-remove').click();
  await expect(correction).toBeHidden();
  data = await api(`/api/income?person_id=${id}`);
  assert.equal(data.corrections.length, 0);
  assert.equal(data.snapshot.values.find(value => value.concept === 'employment_income').amount, '110000.00');
  await action.click();
  await expect(correction).toHaveAttribute('aria-busy', 'false');
  await page.locator('#income-correction-form [name="correct_amount"]').fill('106000');
  await page.locator('#income-correction-form [name="reason"]').fill('Synthetic reactivation');
  await page.locator('#income-correction-save').click();
  await expect(correction).toBeHidden();
  const history = await api(`/api/income/corrections/person/${id}/year/${year}/employment_income`);
  assert.deepEqual(history.corrections.map(item => item.revision_kind), ['create', 'confirm', 'remove', 'create']);
  await page.locator('[data-income-snapshot-year]').selectOption('2024');
  await expect(page.locator('#income-summary')).toContainText('2024');
  await page.locator('.income-source-details > summary').click();
  await expect(page.locator('[data-edit-year="2024"]')).toBeVisible();
  await page.locator('[data-edit-year="2024"]').click();
  await expect(page.locator('#income-form [name="tax_year"]')).toBeDisabled();
  await page.keyboard.press('Escape');
  await page.unroute('**/income/income.mjs?v=20261003-1', legacyModule);
  await page.unroute('**/income/income-corrections.mjs', legacyModule);
}

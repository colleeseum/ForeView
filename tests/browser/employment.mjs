// SPDX-FileCopyrightText: 2026 Mindstep Corporation
// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

import assert from 'node:assert/strict';
import {expect} from '@playwright/test';

export async function verifyEmployment(page, baseURL, locale, output) {
  async function read(id = '') {
    return page.evaluate(async id => {
      const response = await fetch(`/api/salary-projection?start_year=2026&end_year=2027${id ? `&scenario_id=${id}` : ''}`);
      assertResponse(response);
      return response.json();
      function assertResponse(response) {if (!response.ok) throw new Error('Synthetic projection read failed');}
    }, id);
  }
  const rows = model => model.people.map(person => ({id: person.id, actuals: person.actuals, projection: person.projection}));
  await page.goto(`${baseURL}/salary-projection`);
  await expect(page.locator('#salary-tabs button')).not.toHaveCount(0);
  await page.waitForFunction(() => document.querySelector('main').getAttribute('aria-busy') === 'false');
  const original = await read();
  const personId = original.people.find(person => person.projection.some(row => row.year === 2027)).id;
  await page.locator(`#salary-tabs [data-person-key="${personId}"]`).click();
  await expect(page.locator('[name="default_raise"]')).toHaveValue(String(Number(original.people.find(person => person.id === personId).settings.default_raise) * 100));
  for (const width of [1280, 390, 320]) {
    await page.setViewportSize({width, height: 1000});
    await page.locator('.fv-navigation').evaluate(node => {node.open = false;});
    await expect(page.locator('.projection-disclaimer a')).toHaveAttribute('href', '/disclaimer');
    assert((await page.locator('.salary-toolbar label').first().boundingBox()).height < 120, 'Scenario control must not stretch into a tall empty mobile panel');
    assert(await page.locator('.page-content').evaluate(node => node.scrollWidth <= node.clientWidth));
    const region = page.locator('#salary-table .fv-table-scroll');
    await region.focus();
    await expect(region).toHaveCSS('outline-width', '3px');
    assert((await page.locator('.salary-year-input').first().boundingBox()).width >= 150, 'Editable amounts must not collapse or truncate ordinary values');
    await page.screenshot({path: `${output}/${locale}-${width}-employment.png`, fullPage: true});
    await page.locator('#salary-save-as').click();
    const dialog = page.locator('#salary-save-as-backdrop');
    await expect(dialog).toHaveJSProperty('open', true);
    await expect(dialog.locator('[name="name"]')).toBeFocused();
    const close = page.locator('#salary-save-as-close');
    await expect(close).toHaveAttribute('data-icon-action', 'close');
    await close.focus();
    const tooltip = dialog.locator('[role="tooltip"]');
    await expect(tooltip).toHaveText(await close.getAttribute('aria-label'));
    await page.keyboard.press('Escape');
    await expect(tooltip).toHaveCount(0);
    await expect(dialog).toBeVisible();
    await page.keyboard.press('Shift+Tab');
    assert(await dialog.evaluate(node => node.contains(document.activeElement)));
    await page.keyboard.press('Escape');
    await expect(page.locator('#salary-save-as')).toBeFocused();
  }
  assert.deepEqual(rows(await read()), rows(original), 'Presentation and modal navigation preserve calculated and factual values');
  await page.locator('#salary-save-as').click();
  const name = `UX03I ${locale}`;
  await page.locator('#salary-save-as-form [name="name"]').fill(name);
  const cloneRequest = page.waitForRequest(request => request.url().endsWith('/clone'));
  await page.locator('#salary-save-as-form [type="submit"]').click();
  const clonePayload = (await cloneRequest).postDataJSON();
  assert.equal(clonePayload.settings, undefined, 'An unchanged clone must not resubmit or round saved assumptions');
  await expect(page.locator('#salary-save-as-backdrop')).toBeHidden();
  await expect(page.locator('#salary-message')).toContainText(name);
  const scenario = await page.locator('#salary-scenario').inputValue();
  assert.notEqual(Number(scenario), original.selected_scenario_id);
  assert.deepEqual(rows(await read(scenario)), rows(original), 'Cloning unchanged inputs preserves every annual amount');
  await page.locator(`#salary-tabs [data-person-key="${personId}"]`).click();
  await page.locator('[name="default_raise"]').fill('3');
  await page.locator('[name="retirement_date"]').fill('2027-07-01');
  await expect(page.locator('#salary-expense-form input').first()).toBeDisabled();
  await page.locator('#salary-save').click();
  await expect(page.locator('#salary-save')).toBeDisabled();
  await page.waitForFunction(() => document.querySelector('main').getAttribute('aria-busy') === 'false');
  const saved = (await read(scenario)).people.find(person => person.id === personId);
  assert.equal(saved.settings.retirement_date, '2027-07-01');
  assert.equal(saved.settings.default_raise, '0.03');
  assert(Number(saved.projection.find(row => row.year === 2027).gross_income) < Number(saved.projection.find(row => row.year === 2027).annual_salary_rate), 'Retirement year is prorated by the existing service');
  const salary = page.locator('.salary-year-input[data-year="2027"][data-field="salary"]');
  await salary.fill('123456.78');
  await page.locator('#salary-save').click();
  await expect(page.locator('.salary-use-default[data-year="2027"][data-field="salary"]')).toBeVisible();
  assert.equal((await read(scenario)).people.find(person => person.id === personId).overrides.find(item => item.year === 2027).salary, '123456.78');
  const reset = page.locator('.salary-use-default[data-year="2027"][data-field="salary"]');
  await expect(reset).toHaveAttribute('data-icon-action', 'reset');
  assert.equal((await reset.innerText()).trim(), '');
  const resetBox = await reset.boundingBox();
  assert(resetBox.width >= 44 && resetBox.height >= 44);
  await reset.focus();
  await expect(page.locator('.fv-icon-tooltip')).toHaveText(await reset.getAttribute('aria-label'));
  await page.keyboard.press('Escape');
  await expect(page.locator('.fv-icon-tooltip')).toHaveCount(0);
  await expect(reset).toBeFocused();
  await reset.click();
  await page.locator('#salary-save').click();
  await expect(page.locator('.salary-use-default[data-year="2027"][data-field="salary"]')).toHaveCount(0);
  await page.locator('[data-person-key="household"]').click();
  await expect(page.locator('#salary-setup')).toBeHidden();
  await page.locator('#salary-expense-form [name="required_annual_amount"]').fill('45678.90');
  await page.locator('#salary-expense-save').click();
  await page.waitForFunction(() => document.querySelector('main').getAttribute('aria-busy') === 'false');
  assert.equal((await read(scenario)).expense_plan.required_annual_amount, '45678.90');
  assert.deepEqual(rows(await read(original.selected_scenario_id)), rows(original), 'Draft and spending saves never mutate the original scenario');
  const fail = route => route.fulfill({status: 503, contentType: 'application/json', body: JSON.stringify({error: 'Synthetic unavailable projection'})});
  await page.route('**/api/salary-projection?*', fail);
  await page.locator('#salary-view').click();
  await expect(page.locator('#salary-message')).toHaveAttribute('role', 'alert');
  await expect(page.locator('#salary-table table')).toHaveCount(0);
  await page.unroute('**/api/salary-projection?*', fail);
  await page.locator('#salary-message button').click();
  await expect(page.locator('#salary-table table')).toBeVisible();
  assert(!(await page.locator('main').innerText()).includes('⟦'));
}

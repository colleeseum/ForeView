// SPDX-FileCopyrightText: 2026 Mindstep Corporation
// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

import assert from 'node:assert/strict';
import {expect} from '@playwright/test';

export async function verifyAssets(page, baseURL, locale, output) {
  async function read(path) {
    return page.evaluate(async path => {
      const response = await fetch(path);
      if (!response.ok) throw new Error(`Synthetic read failed: ${path}`);
      return response.json();
    }, path);
  }
  async function goto(tab = 'non_registered') {
    const response = await page.goto(`${baseURL}/accounts?tab=${tab}`);
    assert(response.ok());
    await expect(page.locator('#accounts-table-content')).toHaveAttribute('aria-busy', 'false');
    await page.waitForLoadState('networkidle');
    assert(!(await page.locator('main').innerText()).includes('⟦'), 'Asset labels resolve in the selected locale');
    await page.locator('.fv-navigation').evaluate(node => {node.open = false;});
  }
  async function checkIconTooltip(action) {
    await action.focus();
    const tip = page.locator('.fv-icon-tooltip');
    await expect(tip).toBeVisible();
    await expect(tip).toHaveText(await action.getAttribute('aria-label'));
    await page.keyboard.press('Escape');
    await expect(tip).toHaveCount(0);
    await expect(action).toBeFocused();
  }
  async function dismissAndCheck(id, trigger) {
    const modal = page.locator(id);
    await expect(modal).toBeVisible();
    assert(await modal.evaluate(node => node.contains(document.activeElement)));
    const first = modal.locator('button').first();
    await first.focus();
    await page.keyboard.press('Shift+Tab');
    assert(await modal.evaluate(node => node.contains(document.activeElement)), 'Reverse Tab stays modal');
    await page.keyboard.press('Escape');
    await expect(modal).toBeHidden();
    await expect(trigger).toBeFocused();
  }
  async function saveWithRefreshFailure(form, dialog) {
    let release;
    const hold = new Promise(resolve => {release = resolve;});
    let writes = 0;
    const path = dialog === '#real-estate-dialog' ? '**/api/model/real-estate' : '**/api/model/accounts';
    const delay = async route => {
      if (route.request().method() !== 'POST') return route.continue();
      writes++;
      await hold;
      await route.continue();
    };
    await page.route(path, delay);
    const failure = route => route.fulfill({status: 503, json: {error: 'Synthetic refresh unavailable', error_language: 'en-CA'}});
    await page.route('**/api/model/holdings', failure, {times: 1});
    await form.locator('button[type="submit"]').click();
    await expect(page.locator(dialog)).toHaveAttribute('aria-busy', 'true');
    for (const field of await form.locator('input, select, button').all()) await expect(field).toBeDisabled();
    await form.evaluate(node => node.dispatchEvent(new Event('submit', {bubbles: true, cancelable: true})));
    await page.keyboard.press('Escape');
    await expect(page.locator(dialog)).toBeVisible();
    release();
    await expect(page.locator(dialog)).toBeHidden();
    assert.equal(writes, 1, 'A busy editor must not submit the same create twice');
    await page.unroute(path, delay);
    await expect(page.locator('#assets-message')).toBeVisible();
    await expect(page.locator('#accounts-table-content')).toHaveAttribute('role', 'alert');
    await expect(page.locator('[data-add-account-type], [data-add-subaccount], [data-add-real-estate]')).toHaveCount(0);
    const retryWrites = [];
    const record = request => {if (['POST', 'PUT'].includes(request.method())) retryWrites.push(request.url());};
    page.on('request', record);
    await page.locator('#retry-assets').click();
    await expect(page.locator('#accounts-table-content')).toHaveAttribute('aria-busy', 'false');
    await expect(page.locator('#accounts-table-content')).not.toHaveAttribute('role', 'alert');
    page.off('request', record);
    assert.deepEqual(retryWrites, [], 'Retry reloads reads only, never the committed mutation');
  }
  await goto();
  const original = await read('/api/model/accounts');
  for (const source of ['people', 'accounts', 'holdings', 'real-estate']) {
    await page.route(`**/api/model/${source}`, route => route.fulfill({status: 503, json: {error: 'Synthetic initial load failure'}}), {times: 1});
    await page.goto(`${baseURL}/accounts`);
    await expect(page.locator('#accounts-table-content')).toHaveAttribute('role', 'alert');
    for (const tab of ['tfsa', 'real_estate', 'non_registered']) {
      await page.locator(`[data-view="${tab}"]`).click();
      await expect(page.locator('#accounts-table-content')).toHaveAttribute('role', 'alert');
      await expect(page.locator('[data-add-account-type], [data-add-real-estate]')).toHaveCount(0);
    }
    await page.locator('#retry-assets').click();
    await expect(page.locator('#accounts-table-content')).toHaveAttribute('aria-busy', 'false');
    await expect(page.locator('[data-add-account-type]')).toBeVisible();
  }
  for (const width of [1280, 390, 320]) {
    await page.setViewportSize({width, height: 1000});
    await goto();
    const defaultTab = page.locator('[data-view="non_registered"]');
    const rrspTab = page.locator('[data-view="rrsp"]');
    for (const selected of [defaultTab, rrspTab, defaultTab]) {
      await selected.click();
      await selected.hover();
      await expect(selected).toHaveAttribute('aria-pressed', 'true');
      await expect(selected).toHaveCSS('color', 'rgb(255, 255, 255)');
      await expect(selected).toHaveCSS('background-color', 'rgb(50, 104, 88)');
      await expect(selected).toHaveCSS('border-bottom-width', '3px');
      const inactive = selected === defaultTab ? rrspTab : defaultTab;
      await expect(inactive).toHaveAttribute('aria-pressed', 'false');
      await expect(inactive).toHaveCSS('background-color', 'rgba(0, 0, 0, 0)');
    }
    const edit = page.locator('[data-edit-account]').first();
    await edit.click();
    await expect(page.locator('#account-dialog-form button[type="submit"]')).toBeDisabled();
    const box = await page.locator('#account-dialog').boundingBox();
    assert(box.x >= 0 && box.x + box.width <= width);
    await page.screenshot({path: `${output}/${locale}-${width}-account-dialog.png`});
    await dismissAndCheck('#account-dialog', edit);
    await checkIconTooltip(edit);
    await page.locator('#asset-density').selectOption('standard');
    const header = page.locator('.table-card thead th').first();
    const total = page.locator('.table-card tfoot th').first();
    await expect(header).toHaveCSS('background-color', 'rgb(50, 104, 88)');
    await expect(header).toHaveCSS('color', 'rgb(255, 255, 255)');
    await expect(total).toHaveCSS('background-color', 'rgb(228, 238, 231)');
    await expect(total).toHaveCSS('color', 'rgb(32, 49, 44)');
    await expect(total).toHaveCSS('border-top-width', '3px');
    const standard = await page.locator('.table-card tbody tr').first().boundingBox();
    await page.locator('#asset-density').selectOption('compact');
    const compact = await page.locator('.table-card tbody tr').first().boundingBox();
    assert(compact.height < standard.height);
    for (const action of await page.locator('.fv-icon-action').all()) {
      const target = await action.boundingBox();
      assert(target.height >= 44 && target.width >= 44);
      assert.equal((await action.innerText()).trim(), '');
      assert((await action.getAttribute('aria-label')).trim());
      await expect(action.locator('.fv-icon')).toHaveAttribute('aria-hidden', 'true');
      assert(await action.locator('.fv-icon').evaluate(node => parseFloat(getComputedStyle(node).width) >= 20));
    }
    const region = page.locator('.table-card').first();
    await region.focus();
    await expect(region).toBeFocused();
    if (width < 900) {
      await region.evaluate(node => {node.scrollLeft = document.documentElement.dir === 'rtl' ? -200 : 200;});
      assert.notEqual(await region.evaluate(node => node.scrollLeft), 0);
      await region.evaluate(node => {node.scrollLeft = 0;});
    }
    assert(await page.locator('.page-content').evaluate(node => node.scrollWidth <= node.clientWidth));
    await page.screenshot({path: `${output}/${locale}-${width}-assets.png`, fullPage: true});
    const addGic = page.locator('[data-add-subaccount]').first();
    await addGic.click();
    const parent = page.locator('#subaccount-parent');
    const reference = page.locator('#subaccount-dialog-form [name="account_number"]');
    const name = page.locator('#subaccount-dialog-form [name="name"]');
    const parentBox = await parent.boundingBox();
    const referenceBox = await reference.boundingBox();
    const nameBox = await name.boundingBox();
    assert(parentBox.y + parentBox.height <= referenceBox.y, 'Parent has a full-width row above reference/name');
    if (width === 1280) {
      assert(Math.abs(referenceBox.y - nameBox.y) < 2, 'Reference and Name share the next row');
      assert(parentBox.width > referenceBox.width * 1.8);
    }
    await expect(page.locator('#subaccount-parent-description')).toHaveText(await parent.locator('option:checked').textContent());
    const options = await parent.locator('option').count();
    if (options > 1) {
      await parent.selectOption({index: options - 1});
      await expect(page.locator('#subaccount-parent-description')).toHaveText(await parent.locator('option:checked').textContent());
    }
    await page.screenshot({path: `${output}/${locale}-${width}-gic-dialog.png`});
    await dismissAndCheck('#subaccount-dialog', addGic);
    await page.locator('[data-view="tfsa"]').click();
    const branch = page.locator('.tree-branch').first();
    if (await branch.count()) {
      assert.equal(await branch.evaluate(node => getComputedStyle(node).color), 'rgb(50, 104, 88)');
      assert.equal(await branch.locator('xpath=ancestor::td').evaluate(node => getComputedStyle(node).borderInlineStartColor), 'rgb(216, 226, 218)');
    }
    await page.locator('[data-view="real_estate"]').click();
    const editProperty = page.locator('[data-edit-real-estate]').first();
    await editProperty.click();
    await expect(page.locator('#real-estate-dialog-form button[type="submit"]')).toBeDisabled();
    await dismissAndCheck('#real-estate-dialog', editProperty);
  }
  assert.deepEqual(await read('/api/model/accounts'), original, 'Visual checks never change factual read model');
  await page.reload();
  await expect(page.locator('#asset-density')).toHaveValue('compact');
  await expect(page.locator('.fv-assets')).toHaveAttribute('data-table-density', 'compact');
  await page.locator('#asset-density').selectOption('standard');
  await page.reload();
  await expect(page.locator('#asset-density')).toHaveValue('standard');
  await expect(page.locator('.fv-assets')).toHaveAttribute('data-table-density', 'standard');
  await page.setViewportSize({width: 1280, height: 1000});
  await goto();
  await page.locator('[data-add-account-type="non_registered"]').click();
  const form = page.locator('#account-dialog-form');
  await form.locator('[name="name"]').fill('Synthetic invalid draft');
  await form.locator('button[type="submit"]').click();
  await expect(page.locator('#account-dialog')).toBeVisible();
  assert.equal(await form.evaluate(node => node.checkValidity()), false);
  await form.locator('[name="account_number"]').fill(`UX03E-${locale}`);
  await form.locator('[name="institution"]').fill('Synthetic long institution name for responsive assets');
  await form.locator('[name="name"]').fill(`Synthetic account ${locale}`);
  await form.locator('[name="balance_date"]').fill('2026-10-21');
  await form.locator('[name="balance_amount"]').fill('1000.25');
  await form.locator('[name="interest_rate"]').fill('2.50');
  await page.locator('#dialog-owner-fields [data-owner-id]').first().check();
  await saveWithRefreshFailure(form, '#account-dialog');
  await expect(page.locator('#account-dialog')).toBeHidden();
  await expect(page.locator('#assets-message')).toBeVisible();
  let account = (await read('/api/model/accounts')).accounts.find(item => item.account_number === `UX03E-${locale}`);
  assert.equal(Number(account.latest_amount), 1000.25);
  assert.equal(Number(account.interest_rate), .025);
  const edit = page.locator(`[data-edit-account="${account.id}"]`);
  await edit.click();
  await form.locator('[name="name"]').fill(`Edited account ${locale}`);
  await page.route(`**/api/model/accounts/${account.id}`, route => route.fulfill({status: 400, contentType: 'application/json', body: JSON.stringify({error: 'Synthetic validation failure'})}), {times: 1});
  await form.locator('button[type="submit"]').click();
  await expect(page.locator('#account-dialog-message')).toContainText('Synthetic validation failure');
  await expect(form.locator('[name="name"]')).toHaveValue(`Edited account ${locale}`);
  await expect(form.locator('[name="balance_amount"]')).toHaveValue('1000.25');
  await form.locator('button[type="submit"]').click();
  await expect(page.locator('#account-dialog')).toBeHidden();
  await expect(page.locator(`[data-edit-account="${account.id}"]`)).toBeFocused();
  account = (await read('/api/model/accounts')).accounts.find(item => item.id === account.id);
  assert.equal(Number(account.latest_amount), 1000.25);
  assert.equal(account.name, `Edited account ${locale}`);

  await page.locator(`[data-add-subaccount="${account.id}"]`).click();
  const gicForm = page.locator('#subaccount-dialog-form');
  await gicForm.locator('[name="account_number"]').fill(`GIC-${locale}`);
  await gicForm.locator('[name="name"]').fill(`Synthetic GIC ${locale}`);
  await gicForm.locator('[name="start_date"]').fill('2026-10-21');
  await gicForm.locator('[name="maturity_date"]').fill('2027-10-21');
  await gicForm.locator('[name="principal"]').fill('200.00');
  await gicForm.locator('[name="balance_amount"]').fill('200.00');
  await gicForm.locator('[name="interest_rate"]').fill('3.00');
  await saveWithRefreshFailure(gicForm, '#subaccount-dialog');
  await expect(page.locator('#subaccount-dialog')).toBeHidden();
  const gic = (await read('/api/model/accounts')).accounts.find(item => item.account_number === `GIC-${locale}`);
  assert.equal(gic.parent_account_id, account.id);
  assert.equal(Number(gic.principal), 200);
  await page.locator(`[data-edit-account="${gic.id}"]`).click();
  await gicForm.locator('[name="name"]').fill(`Edited GIC ${locale}`);
  await gicForm.locator('button[type="submit"]').click();
  await expect(page.locator('#subaccount-dialog')).toBeHidden();
  assert.equal((await read('/api/model/accounts')).accounts.find(item => item.id === gic.id).name, `Edited GIC ${locale}`);

  await page.locator('[data-view="real_estate"]').click();
  await page.locator('[data-add-real-estate]').click();
  const property = page.locator('#real-estate-dialog-form');
  await property.locator('[name="name"]').fill(`Synthetic property ${locale}`);
  await property.locator('[name="estimated_value"]').fill('123456.78');
  await property.locator('[name="valuation_date"]').fill('2026-10-21');
  await property.locator('[name="acb"]').fill('100000.00');
  const checks = page.locator('#real-estate-owner-fields [data-owner-id]');
  await checks.nth(0).check();
  await checks.nth(1).check();
  const shares = page.locator('#real-estate-owner-fields [data-owner-share]');
  await shares.nth(0).fill('40');
  await expect(property.locator('button[type="submit"]')).toBeDisabled();
  await shares.nth(1).fill('60');
  await saveWithRefreshFailure(property, '#real-estate-dialog');
  await expect(page.locator('#real-estate-dialog')).toBeHidden();
  const asset = (await read('/api/model/real-estate')).assets.find(item => item.name === `Synthetic property ${locale}`);
  assert.equal(Number(asset.estimated_value), 123456.78);
  assert.deepEqual(asset.owners.map(owner => Number(owner.share)).sort(), [.4, .6]);
  await page.locator(`[data-edit-real-estate="${asset.id}"]`).click();
  await property.locator('[name="name"]').fill(`Edited property ${locale}`);
  await property.locator('button[type="submit"]').click();
  await expect(page.locator('#real-estate-dialog')).toBeHidden();
  await expect(page.locator(`[data-edit-real-estate="${asset.id}"]`)).toBeFocused();
  const updated = (await read('/api/model/real-estate')).assets.find(item => item.id === asset.id);
  assert.equal(updated.name, `Edited property ${locale}`);
  assert.equal(Number(updated.estimated_value), 123456.78);
  assert.deepEqual(updated.owners, asset.owners);
}

// SPDX-FileCopyrightText: 2026 Mindstep Corporation
// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

import assert from 'node:assert/strict';
import {expect} from '@playwright/test';
import {assertCloseVisible, assertLayout, measureLayout, dismissHelpWithEscape} from './acceptance.mjs';

export async function verifyTextSize(page, baseURL, locale, output) {
  const paths = ['/', '/accounts', '/transactions', '/income', '/expenses', '/salary-projection',
    '/setup', '/connections', '/settings', '/application-settings', '/about', '/disclaimer'];
  async function goto(path) {
    await page.goto(baseURL + path);
    await page.waitForLoadState('networkidle');
  }
  async function select(size) {
    await goto('/application-settings');
    await page.locator('#text-size').selectOption(size);
    await page.locator('#text-size').focus();
    await page.keyboard.press('Tab');
    const save = page.locator('form[action="/application-settings/text-size"] button');
    await expect(save).toBeFocused();
    await Promise.all([page.waitForNavigation(), page.keyboard.press('Enter')]);
    await expect(page.locator('[aria-labelledby="appearance-heading"] [role="status"]')).toContainText(locale === 'en-CA' ? 'Text size saved.' : 'Taille du texte enregistrée.');
  }
  const snapshot = () => page.evaluate(async () => Promise.all([
    '/api/dashboard', '/api/model/accounts', '/api/model/transactions?account_type=non_registered',
    '/api/salary-projection?start_year=2026&end_year=2027',
  ].map(async url => {
    const response = await fetch(url);
    if (!response.ok) throw new Error('Synthetic text-size read failed');
    return response.json();
  })));
  await goto('/accounts');
  const originalSize = await page.locator('html').getAttribute('data-text-size');
  const before = await snapshot();
  const density = await page.locator('#asset-density').inputValue();
  await page.locator('#asset-density').selectOption('compact');
  try {
    for (const [size, scale] of [['small', 1], ['normal', 1.125], ['large', 1.25]]) {
      await select(size);
      await page.reload();
      await expect(page.locator('#text-size')).toHaveValue(size);
      for (const path of paths) {
        await page.setViewportSize({width: 320, height: 800});
        await goto(path);
        await expect(page.locator('html')).toHaveAttribute('data-text-size', size);
        await expect(page.locator('html')).toHaveAttribute('lang', locale);
        assert(!(await page.locator('main').innerText()).includes('⟦'));
        assert.equal(await page.locator('html').evaluate(node => parseFloat(getComputedStyle(node).fontSize)), 16 * scale);
        assert.equal(await page.locator('main > header h1').evaluate(node => parseFloat(getComputedStyle(node).fontSize)), 28 * scale);
        assert.equal(await page.locator('.side-menu-heading').first().evaluate(node => parseFloat(getComputedStyle(node).fontSize)), 12 * scale);
        assertLayout(await page.evaluate(measureLayout), `${size} ${path}`);
        for (const node of await page.locator('.full-help-button, .fv-button:visible, .fv-navigation a:visible').all()) {
          const box = await node.boundingBox();
          assert(box.width >= 43.9 && box.height >= 43.9, 'Small text retains control hit targets');
        }
        if (path === '/accounts') {
          await expect(page.locator('#asset-density')).toHaveValue('compact');
          await page.locator('.fv-navigation').evaluate(node => {node.open = false;});
          const trigger = page.locator('[data-add-account-type]').first();
          await trigger.click();
          const dialog = page.locator('#account-dialog');
          await expect(dialog).toBeVisible();
          assert.equal(await dialog.evaluate(node => parseFloat(getComputedStyle(node).fontSize)), 16 * scale);
          const bounds = await dialog.boundingBox();
          assert(bounds.x >= 0 && bounds.x + bounds.width <= 321);
          await page.keyboard.press('Escape');
          await expect(trigger).toBeFocused();
        }
      }
      await goto('/application-settings');
      await page.setViewportSize({width: 320, height: 450});
      const opener = page.locator('.full-help-button');
      await opener.click();
      await expect(page.locator('#help-search')).toBeFocused();
      assert.equal(await page.locator('.help-drawer').evaluate(node => parseFloat(getComputedStyle(node).fontSize)), 16 * scale);
      await assertCloseVisible(page);
      await dismissHelpWithEscape(page);
      await expect(opener).toBeFocused();
      // Text-only resize, not a claim of native browser-chrome zoom automation.
      await page.locator('html').evaluate((node, scale) => {node.style.fontSize = `${200 * scale}%`;}, scale);
      assertLayout(await page.evaluate(measureLayout), `${size}: 200% text resize`);
      await page.locator('html').evaluate(node => {node.style.fontSize = '';});
      await page.setViewportSize({width: 320, height: 800});
      await page.locator('.fv-navigation').evaluate(node => {node.open = false;});
      await page.locator('#text-size').focus();
      await page.screenshot({path: `${output}/${locale}-320-text-size-${size}.png`, fullPage: true});
      await page.setViewportSize({width: 800, height: 900});
      assert.equal(await page.locator('main > header h1').evaluate(node => parseFloat(getComputedStyle(node).fontSize)), 32 * scale, 'Responsive heading scales between its rem bounds');
      await page.setViewportSize({width: 1280, height: 900});
      assertLayout(await page.evaluate(measureLayout), `${size}: desktop settings`);
      // Language writes must not reset appearance; restore the test locale.
      for (const language of [locale === 'en-CA' ? 'fr-CA' : 'en-CA', locale]) {
        await page.locator('#locale').selectOption(language);
        await Promise.all([page.waitForNavigation(), page.locator('form[action="/application-settings/language"] button').click()]);
        await expect(page.locator('html')).toHaveAttribute('lang', language);
        await expect(page.locator('html')).toHaveAttribute('data-text-size', size);
        await expect(page.locator('#text-size')).toHaveValue(size);
      }
    }
    assert.deepEqual(await snapshot(), before, 'Text size never changes financial read models');
  } finally {
    await select(originalSize);
    await goto('/accounts');
    await page.locator('#asset-density').selectOption(density);
  }
}

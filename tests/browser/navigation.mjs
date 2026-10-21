// SPDX-FileCopyrightText: 2026 Mindstep Corporation
// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

import assert from 'node:assert/strict';
import {expect} from '@playwright/test';

export async function verifyNavigation(page, baseURL, locale, output) {
  await page.goto(baseURL + '/');
  await page.waitForLoadState('networkidle');
  const destinations = await page.locator('.fv-navigation a').evaluateAll(links => links.map(link => link.getAttribute('href')));
  assert.equal(destinations.length, 11);
  assert.equal(new Set(destinations).size, 11);
  for (const href of destinations) {
    const response = await page.goto(baseURL + href);
    assert(response.ok(), `Navigation destination failed: ${href}`);
    await page.waitForLoadState('networkidle');
    await expect(page.locator('.fv-navigation [aria-current="page"]')).toHaveAttribute('href', href);
    await expect(page.locator('.full-help-button')).toBeVisible();
    const toggle = page.locator('.fv-navigation-toggle');
    await toggle.focus();
    await page.keyboard.press('Enter');
    await expect(page.locator('.fv-navigation')).not.toHaveAttribute('open');
    await expect(page.locator('.fv-navigation a').first()).toBeHidden();
    await page.keyboard.press('Space');
    await expect(page.locator('.fv-navigation')).toHaveAttribute('open', '');
    await page.keyboard.press('Tab');
    await expect(page.locator('.fv-navigation a').first()).toBeFocused();
    for (let i = 1; i < destinations.length; i++) await page.keyboard.press('Tab');
    await expect(page.locator('.fv-navigation a').last()).toBeFocused();
    await page.keyboard.press('Tab');
    assert(!await page.locator('.fv-navigation').evaluate(node => node.contains(document.activeElement)), 'Navigation must not trap focus');
  }
  await page.goto(baseURL + '/transactions?type=non_registered');
  await page.reload();
  await expect(page).toHaveURL(/\/transactions\?type=non_registered$/);
  await expect(page.locator('.fv-navigation a[aria-current="page"]')).toHaveAttribute('href', '/transactions');
  await page.goto(baseURL + '/disclaimer');
  await expect(page.locator('.fv-navigation [aria-current="page"]')).toHaveCount(0);
  await expect(page.locator('.fv-navigation a[href="/about"]')).toHaveClass('section-active');
  await page.locator('.fv-navigation a[href="/about"]').click();
  await expect(page.locator('.fv-navigation [aria-current="page"]')).toHaveAttribute('href', '/about');
  for (const width of [1280, 800, 390, 320]) {
    await page.setViewportSize({width, height: 900});
    await page.goto(baseURL + '/income');
    await page.waitForLoadState('networkidle');
    const navigation = page.locator('.fv-navigation');
    await expect(navigation).toHaveAttribute('dir', locale === 'ar-XB' ? 'rtl' : 'ltr');
    const box = await navigation.boundingBox();
    assert(box.x >= 0 && box.x + box.width <= width);
    const overflow = await page.evaluate(() => ({
      viewport: innerWidth, document: document.documentElement.scrollWidth,
      shell: document.querySelector('.page-shell').scrollWidth,
      available: document.querySelector('.page-shell').clientWidth,
      wide: [...document.querySelectorAll('.page-shell *')].filter(node => node.getBoundingClientRect().right > innerWidth).map(node => node.className).slice(0, 8),
    }));
    assert(overflow.document <= width && overflow.shell <= overflow.available, JSON.stringify(overflow));
    if (width === 1280) assert(box.width >= 220, 'Desktop sidebar is wider');
    for (const link of await navigation.locator('a').all()) {
      assert((await link.boundingBox()).height >= 44);
    }
    await page.screenshot({path: `${output}/${locale}-${width}-navigation.png`});
    await navigation.locator('summary').focus();
    await page.keyboard.press('Enter');
    await expect(navigation.locator('a').first()).toBeHidden();
    await expect(navigation.locator('summary')).toBeFocused();
    await page.screenshot({path: `${output}/${locale}-${width}-navigation-collapsed.png`});
    await page.keyboard.press('Enter');
    await expect(navigation.locator('a').last()).toBeVisible();
  }
  await page.setViewportSize({width: 1280, height: 1000});
}

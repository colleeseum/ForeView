// SPDX-FileCopyrightText: 2026 Mindstep Corporation
// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

import assert from 'node:assert/strict';
import {expect} from '@playwright/test';

export async function verifyDashboard(page, baseURL, locale, output) {
  await page.goto(baseURL + '/');
  await page.waitForLoadState('networkidle');
  const original = await page.evaluate(async () => (await fetch('/api/dashboard')).json());
  for (const width of [1280, 390, 320]) {
    await page.setViewportSize({width, height: 1000});
    // Native menu is a separate shell feature; collapse it to inspect the dashboard.
    await page.locator('.fv-navigation').evaluate(node => {node.open = false;});
    await expect(page.locator('#dashboard-metrics .summary-pill')).toHaveCount(7);
    await expect(page.locator('#dashboard-metrics')).toHaveAttribute('aria-busy', 'false');
    for (const node of await page.locator('#dashboard-metrics .summary-pill').all()) {
      assert(await node.evaluate(element => element.scrollWidth <= element.clientWidth), 'Metric content must fit card');
    }
    assert(await page.locator('.page-content').evaluate(node => node.scrollWidth <= node.clientWidth), 'No dashboard-wide scroll');
    assert(!(await page.locator('.page-content').innerText()).includes('⟦'));
    await page.screenshot({path: `${output}/${locale}-${width}-dashboard.png`, fullPage: true});
  }
  assert.deepEqual(await page.evaluate(async () => (await fetch('/api/dashboard')).json()), original);
  const unavailable = locale === 'en-CA' ? 'Unavailable' : 'Indisponible';
  let release;
  const gate = new Promise(resolve => {release = resolve;});
  await page.route('**/api/dashboard', async route => {
    await gate;
    await route.fulfill({status: 503, contentType: 'application/json', body: JSON.stringify({error: 'Synthetic dashboard failure'})});
  });
  await page.goto(baseURL + '/');
  await expect(page.locator('#dashboard-metrics')).toHaveAttribute('aria-busy', 'true');
  await expect(page.locator('#dashboard-metrics [role="status"]')).toBeVisible();
  release();
  await expect(page.locator('#dashboard-metrics [role="alert"]')).toContainText('Synthetic dashboard failure');
  for (const suffix of ['categories', 'liquidity', 'maturities', 'transactions']) {
    await expect(page.locator(`#dashboard-${suffix}`)).toHaveText(unavailable);
    await expect(page.locator(`#dashboard-${suffix}`)).toHaveAttribute('aria-busy', 'false');
  }
  await page.unroute('**/api/dashboard');
  await page.route('**/api/dashboard', async route => route.fulfill({contentType: 'application/json', body: JSON.stringify({
    ...original, gross_assets: null, immovable_value: 0, categories: [], maturities: [], recent_transactions: [],
  })}));
  await page.reload();
  await expect(page.locator('#dashboard-metrics strong').first()).toHaveText(unavailable);
  await expect(page.locator('#dashboard-metrics strong').nth(1)).toContainText(/0[.,]00/);
  await expect(page.locator('#dashboard-categories .dashboard-empty')).toBeVisible();
  await expect(page.locator('#dashboard-maturities .dashboard-empty')).toBeVisible();
  await expect(page.locator('#dashboard-transactions .dashboard-empty')).toBeVisible();
  await page.unroute('**/api/dashboard');
  await page.setViewportSize({width: 1280, height: 1000});
}

// SPDX-FileCopyrightText: 2026 Mindstep Corporation
// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

import assert from 'node:assert/strict';
import {expect} from '@playwright/test';

export async function verifyAdministration(page, baseURL, locale, output) {
  async function goto(path) {
    await page.goto(baseURL + path);
    await page.waitForLoadState('networkidle');
    await page.locator('.fv-navigation').evaluate(node => {node.open = false;});
    assert(!(await page.locator('main').innerText()).includes('⟦'));
  }
  async function snapshot() {
    return page.evaluate(async () => {
      const urls = ['/api/model/accounts', '/api/salary-projection?start_year=2026&end_year=2027'];
      return Promise.all(urls.map(async url => {
        const response = await fetch(url);
        if (!response.ok) throw new Error('Synthetic administration invariant read failed');
        return response.json();
      }));
    });
  }
  await goto('/setup');
  const original = await snapshot();
  const field = page.locator('[data-birth-date]').first();
  const originalDate = await field.inputValue();
  const id = await field.getAttribute('data-birth-date');
  const replacement = originalDate.endsWith('-01') ? '1975-04-02' : '1975-04-01';
  await field.fill(replacement);
  await page.locator(`[data-save-person="${id}"]`).click();
  await expect(field).toHaveValue(replacement);
  await expect(page.locator('#setup-message')).not.toBeEmpty();
  const people = await page.evaluate(async () => (await (await fetch('/api/model/people')).json()).people);
  assert.equal(people.find(person => String(person.id) === id).birth_date, replacement);
  await field.fill(originalDate);
  await page.locator(`[data-save-person="${id}"]`).click();
  await expect(field).toHaveAttribute('data-original-date', originalDate);
  for (const panel of ['accounts', 'balances', 'scenario', 'people']) {
    const button = page.locator(`[data-tab="${panel}-panel"]`);
    await button.click();
    await expect(button).toHaveAttribute('aria-pressed', 'true');
    await expect(page.locator(`#${panel}-panel`)).toBeVisible();
  }

  let offline = true;
  let posts = 0;
  const discovery = route => route.fulfill({json: {institutions: [
    {key: 'synthetic-live', display_name: 'Synthetic connected provider', connection: {status_path: '/api/ux03j/status', sync_path: '/api/ux03j/sync', connect_path: '/synthetic-connect'}},
    {key: 'synthetic-offline', display_name: 'Synthetic unavailable provider', connection: {status_path: '/api/ux03j/offline'}},
  ]}});
  const status = route => route.fulfill({json: {configured_connections: ['Saved synthetic login'], authorizations: [{name: 'Saved synthetic login', access_expires_at: '2026-12-01T12:00:00Z', last_sync_at: null}]}});
  const unavailable = route => route.fulfill(offline ? {status: 503, json: {error: 'Private upstream detail must not be shown'}} : {json: {configured_connections: []}});
  const sync = route => {posts++; return route.fulfill({status: 503, json: {errors: [{error: 'Synthetic safe sync failure', error_language: 'en-CA'}], results: []}});};
  await page.route('**/api/institutions', discovery);
  await page.route('**/api/ux03j/status', status);
  await page.route('**/api/ux03j/offline', unavailable);
  await page.route('**/api/ux03j/sync', sync);
  await goto('/connections');
  await expect(page.locator('.connection-card')).toHaveCount(2);
  assert.equal(posts, 0, 'Opening Connections is read-only');
  assert(!(await page.locator('main').innerText()).includes('Private upstream'));
  await expect(page.locator('.connection-actions a')).toHaveAttribute('href', '/synthetic-connect?connection=Saved%20synthetic%20login');
  await page.locator('.sync-connection').click();
  await expect(page.locator('.connection-notice.error')).toContainText('Synthetic safe sync failure');
  await expect(page.locator('.sync-connection')).toBeEnabled();
  assert.equal(posts, 1);
  offline = false;
  await page.locator('[data-reload-connections]').click();
  await expect(page.locator('[data-reload-connections]')).toHaveCount(0);
  await expect(page.locator('.sync-connection')).toBeFocused();
  assert.equal(posts, 1, 'Retry only re-reads status');
  offline = true;

  const pages = [['people', '/setup'], ['connections', '/connections'], ['rules', '/settings?jurisdiction=CA&year=2025'], ['settings', '/application-settings'], ['about', '/about'], ['disclaimer', '/disclaimer']];
  for (const [name, path] of pages) {
    await goto(path);
    for (const width of [1280, 390, 320]) {
      await page.setViewportSize({width, height: 1000});
      assert(await page.locator('.page-content').evaluate(node => node.scrollWidth <= node.clientWidth), `${name} contains overflow at ${width}px`);
      for (const table of await page.locator('.fv-table-scroll').all()) {
        await table.focus();
        await expect(table).toHaveCSS('outline-width', '3px');
        await expect(table).toHaveAttribute('aria-label', /.+/);
      }
      const first = page.locator('.page-content input:not([type="hidden"]), .page-content select, .page-content button, .page-content a[href]').first();
      if (await first.count() && await first.isVisible()) {
        await first.focus();
        await expect(first).toBeFocused();
      }
      await page.screenshot({path: `${output}/${locale}-${width}-admin-${name}.png`, fullPage: true});
    }
    if (name === 'rules') {
      const federal = page.locator('.public-rule-tabs a[href="/settings?jurisdiction=CA"]');
      const quebec = page.locator('.public-rule-tabs a[href="/settings?jurisdiction=CA-QC"]');
      const bc = page.locator('.public-rule-tabs a[href="/settings?jurisdiction=CA-BC"]');
      await expect(federal).toHaveText(locale === 'en-CA' ? 'Federal' : 'Fédéral');
      await expect(quebec).toHaveText(locale === 'en-CA' ? 'Quebec' : 'Québec');
      await expect(bc).toHaveText(locale === 'en-CA' ? 'British Columbia' : 'Colombie-Britannique');
      await page.locator('.public-rule-tabs').screenshot({path: `${output}/${locale}-jurisdiction-labels.png`});
      const approval = page.locator('form[action$="/approve"]').first();
      if (await approval.count()) {
        const hash = await approval.locator('[name="content_hash"]').inputValue();
        assert.match(hash, /^[0-9a-f]{64}$/);
        await approval.locator('button').click();
        await expect(page.locator('.approval-badge.approved')).toBeVisible();
        await expect(page.locator('.public-rule-heading code')).toHaveText(hash);
      }
      await page.locator('.public-rule-card details').last().locator('summary').click();
      const source = page.locator('.public-rule-card details[open] a').first();
      await expect(source).toBeVisible();
      await expect(source).toHaveAttribute('href', /^https:\/\//);
      await page.locator('.public-rule-tabs a[href*="CA-QC"]').click();
      await expect(page.locator('.public-rule-tabs [aria-current="page"]')).toHaveAttribute('href', /CA-QC/);
    }
    if (name === 'settings') {
      await page.locator('#locale').selectOption(locale);
      await Promise.all([page.waitForNavigation(), page.locator('form[action="/application-settings/language"] button[type="submit"]').click()]);
      await expect(page.locator('html')).toHaveAttribute('lang', locale);
    }
    if (name === 'about') {
      const institutions = page.locator('[aria-labelledby="institution-modules-heading"] tbody tr');
      assert(await institutions.count() > 0, 'Institution references are populated');
      for (const row of await institutions.all()) {
        await expect(row.locator('td').first()).toHaveAttribute('lang', /.+/);
        await expect(row.locator('td').first()).not.toBeEmpty();
        await expect(row.locator('td').nth(1)).not.toBeEmpty();
      }
      await page.locator('[aria-labelledby="institution-modules-heading"]').screenshot({path: `${output}/${locale}-institution-labels.png`});
      await expect(page.locator('a[href="mailto:info@mindstep.ca"]')).toBeVisible();
      await expect(page.locator('.legal-summary a[href="/disclaimer"]')).toBeVisible();
      assert((await page.locator('.legal-summary').innerText()).includes('PolyForm Noncommercial'));
    }
    if (name === 'disclaimer') {
      await expect(page.locator('.legal-document')).toHaveAttribute('lang', 'en-CA');
      await expect(page.locator('.legal-document')).toHaveAttribute('dir', 'ltr');
      assert((await page.locator('.legal-document').innerText()).includes('informational, planning, and modelling'));
    }
  }
  assert.deepEqual(await snapshot(), original, 'Administration presentation and restored edits preserve financial values');
  await page.unroute('**/api/institutions', discovery);
  await page.unroute('**/api/ux03j/status', status);
  await page.unroute('**/api/ux03j/offline', unavailable);
  await page.unroute('**/api/ux03j/sync', sync);
}

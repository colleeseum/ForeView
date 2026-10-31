// SPDX-FileCopyrightText: 2026 Mindstep Corporation
// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

import assert from 'node:assert/strict';
import {expect} from '@playwright/test';

export async function verifyHelp(page, baseURL, locale, output) {
  await page.goto(baseURL + '/expenses');
  await page.waitForLoadState('networkidle');
  const snapshot = () => page.evaluate(async () => Promise.all([
    '/api/model/accounts', '/api/salary-projection?start_year=2026&end_year=2027',
  ].map(async url => {
    const response = await fetch(url);
    if (!response.ok) throw new Error('Synthetic help invariant read failed');
    return response.json();
  })));
  const original = await snapshot();
  const catalog = await page.evaluate(async () => (await (await fetch('/api/help')).json()));
  const modal = page.locator('dialog.help-drawer-backdrop');
  const search = page.locator('#help-search');
  const title = page.locator('.help-article h2');
  const opener = page.locator('.full-help-button');
  await expect(opener).toHaveAttribute('data-icon-action', 'help');
  const expense = catalog.articles.find(article => article.key === 'expenses');
  await opener.click();
  await expect(modal).toBeVisible();
  assert(await modal.evaluate(node => node.matches(':modal')), 'Help uses the native modal top layer');
  await expect(search).toBeFocused();
  const close = modal.locator('.help-drawer-close');
  await expect(close).toHaveAttribute('data-icon-action', 'close');
  await close.focus();
  await expect(modal.locator('.fv-icon-tooltip')).toHaveText(await close.getAttribute('aria-label'));
  const closeSize = await close.boundingBox();
  assert(closeSize.width >= 44 && closeSize.height >= 44);
  await page.keyboard.press('Escape');
  await expect(modal.locator('.fv-icon-tooltip')).toHaveCount(0);
  await expect(modal).toBeVisible();
  await search.focus();
  await expect(title).toHaveText(expense.title);
  await expect(page.locator('[aria-current="true"][data-help-result]')).toHaveAttribute('data-help-result', 'expenses');
  const selected = page.locator('[data-help-result="expenses"]');
  assert(await selected.evaluate(node => {
    let branch = node.closest('details');
    while (branch) {if (!branch.open) return false; branch = branch.parentElement.closest('details');}
    return true;
  }));
  await search.fill('no-such-help-ux03k');
  await expect(page.locator('[data-help-result]')).toHaveCount(0);
  await expect(page.locator('.help-status')).not.toBeEmpty();
  await expect(page.locator('.help-article-body')).not.toBeEmpty();
  await search.fill('');
  const firstTopic = page.locator('[data-help-result]').first();
  await expect(firstTopic).toBeVisible();
  await firstTopic.click();
  await expect(page.locator('.help-article')).toBeFocused();
  await page.keyboard.press('Tab');
  await expect(page.locator('.help-drawer-close')).toBeFocused();
  await page.keyboard.press('Shift+Tab');
  await expect(page.locator('.help-article')).toBeFocused();
  await page.keyboard.press('Escape');
  await expect(modal).toBeHidden();
  await expect(opener).toBeFocused();

  // The expense title button opens the generic topic in the main help surface.
  await page.locator('#expense-import').click();
  const importDialog = page.locator('#expense-import-dialog-backdrop');
  const providerButton = importDialog.locator('[data-help-article="expense-import"]');
  const providerKey = 'expense-import';
  const provider = catalog.articles.find(article => article.key === providerKey);
  await providerButton.click();
  await expect(modal).toBeVisible();
  await expect(page.locator('.help-article-body')).toHaveText(provider.body);
  await expect(page.locator('.help-article-body')).toHaveAttribute('lang', provider.field_languages?.body || provider.language || catalog.language);
  await page.keyboard.press('Escape');
  await expect(modal).toBeHidden();
  await expect(importDialog).toBeVisible();
  await expect(providerButton).toBeFocused();
  await page.keyboard.press('Escape');
  await expect(importDialog).toBeHidden();

  for (const width of [1280, 390, 320]) {
    await page.setViewportSize({width, height: 1000});
    await opener.click();
    await page.evaluate(key => window.openContextHelp(key), providerKey);
    await expect(title).toHaveText(provider.title);
    await expect(page.locator('.help-article-body')).toHaveText(provider.body);
    await expect(page.locator('.help-article-body')).toHaveAttribute('lang', provider.field_languages?.body || provider.language || catalog.language);
    await expect(page.locator(`[data-help-result="${providerKey}"]`)).toHaveAttribute('aria-current', 'true');
    const searchTerm = provider.title.split(/\s+/)[0];
    await search.fill(searchTerm);
    await expect(page.locator(`[data-help-result="${providerKey}"] small`)).not.toBeEmpty();
    await search.fill('');
    assert(await modal.evaluate(node => {
      const panel = node.querySelector('.help-drawer');
      const rect = panel.getBoundingClientRect();
      return rect.left >= 0 && rect.right <= innerWidth + 1 && panel.scrollWidth <= panel.clientWidth + 1;
    }), 'Long help content fits the viewport');
    assert(!(await modal.innerText()).includes('⟦'));
    await page.locator('.help-article').focus();
    const closeBox = await page.locator('.help-drawer-close').boundingBox();
    assert(closeBox.y >= 0 && closeBox.y + closeBox.height <= 1000, 'Close remains reachable while reading long articles');
    await page.screenshot({path: `${output}/${locale}-${width}-help-provider.png`});
    // Keep the pointer off Close while checking keyboard-only dismissal.
    await page.locator('.help-article').hover();
    await page.keyboard.press('Tab');
    await expect(page.locator('.help-drawer-close')).toBeFocused();
    await page.keyboard.press('Shift+Tab');
    await expect(page.locator('.help-article')).toBeFocused();
    await expect(modal.locator('.fv-icon-tooltip')).toHaveCount(0);
    await page.keyboard.press('Escape');
    await expect(opener).toBeFocused();
  }

  // Unmapped pages retain the rendered category-order default, not Connections.
  await page.goto(baseURL + '/about');
  await page.waitForLoadState('networkidle');
  await page.locator('.full-help-button').click();
  await expect(page.locator('[data-help-result]').first()).toHaveAttribute('aria-current', 'true');
  await page.keyboard.press('Escape');

  // Help stacks above an existing native dialog and returns to its invoker.
  await page.evaluate(() => {
    const dialog = document.createElement('dialog');
    dialog.id = 'help-underlying';
    dialog.innerHTML = '<button data-help-article="expenses">Synthetic contextual help</button>';
    document.body.append(dialog);
    dialog.showModal();
  });
  const underlying = page.locator('#help-underlying');
  await underlying.locator('button').click();
  await expect(modal).toBeVisible();
  await expect(search).toBeFocused();
  await page.keyboard.press('Escape');
  await expect(modal).toBeHidden();
  await expect(underlying).toBeVisible();
  await expect(underlying.locator('button')).toBeFocused();
  await underlying.evaluate(node => {node.close(); node.remove();});

  // A short reference is described on focus, fits a narrow viewport, and dismisses.
  await page.evaluate(() => {
    const button = document.createElement('button');
    button.id = 'help-tooltip-fixture';
    button.dataset.helpTooltip = 'salary-rate';
    button.textContent = 'Synthetic quick reference';
    document.querySelector('main').append(button);
  });
  const quick = page.locator('#help-tooltip-fixture');
  await quick.scrollIntoViewIfNeeded();
  await quick.focus();
  const tooltip = page.locator('#help-quick-reference');
  await expect(tooltip).toBeVisible();
  await expect(quick).toHaveAttribute('aria-describedby', 'help-quick-reference');
  await page.evaluate(() => document.dispatchEvent(new Event('scroll')));
  await expect(tooltip).toBeVisible();
  assert(await tooltip.evaluate(node => {
    const box = node.getBoundingClientRect();
    return box.left >= 0 && box.right <= innerWidth && box.top >= 0 && box.bottom <= innerHeight;
  }));
  await page.screenshot({path: `${output}/${locale}-320-help-tooltip.png`});
  await expect(tooltip).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(tooltip).toBeHidden();
  assert.equal(await quick.getAttribute('aria-describedby'), null);
  await quick.evaluate(node => node.remove());
  assert.deepEqual(await snapshot(), original, 'Help does not change financial records or results');
}

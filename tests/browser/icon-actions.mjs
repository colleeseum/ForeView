// SPDX-FileCopyrightText: 2026 Mindstep Corporation
// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

import assert from 'node:assert/strict';
import {expect} from '@playwright/test';

export async function verifyIconActions(page, output, locale) {
  const section = page.locator('#icon-action-reference');
  for (const button of await section.locator('[data-reference-action]').all()) {
    assert((await button.getAttribute('aria-label')).trim());
    assert.equal((await button.innerText()).trim(), '');
    await expect(button.locator('.fv-icon')).toHaveAttribute('aria-hidden', 'true');
    assert(await button.locator('.fv-icon').evaluate(node => getComputedStyle(node).maskImage.includes('.svg')));
    const action = await button.getAttribute('data-icon-action');
    assert(await page.evaluate(async action => (await fetch(`/static/shared/icons/${action}.svg`)).ok, action));
  }
  await expect(section.locator('#icon-disabled')).toBeDisabled();
  await expect(section.locator('#icon-busy')).toBeDisabled();
  await expect(section.locator('#icon-busy')).toHaveAttribute('aria-busy', 'true');
  const edit = section.locator('#icon-edit');
  for (const width of [1280, 320]) {
    await page.setViewportSize({width, height: 1000});
    for (const scale of ['100%', '125%']) {
      await page.locator('html').evaluate((node, size) => {node.style.fontSize = size;}, scale);
      for (const button of await section.locator('.fv-icon-action').all()) {
        const box = await button.boundingBox();
        assert(box.width >= 44 && box.height >= 44);
      }
      await edit.focus();
      const tip = page.locator('.fv-icon-tooltip');
      await expect(tip).toBeVisible();
      await expect(tip).toHaveText(await edit.getAttribute('aria-label'));
      const box = await tip.boundingBox();
      assert(box.x >= 0 && box.x + box.width <= width);
      await page.keyboard.press('Escape');
      await expect(tip).toHaveCount(0);
      await expect(edit).toBeFocused();
      await page.keyboard.press('Tab');
      await expect(section.locator('#icon-delete')).toBeFocused();
      await expect(tip).toBeVisible();
      await page.screenshot({path: `${output}/${locale}-${width}-${scale.replace('%', '')}-icon-actions.png`, fullPage: true});
      await page.keyboard.press('Escape');
    }
  }
  await page.locator('html').evaluate(node => {node.style.fontSize = '';});
  await page.setViewportSize({width: 1280, height: 1000});
  await page.evaluate(() => document.activeElement.blur());
  await edit.hover();
  const hoverTip = page.locator('.fv-icon-tooltip');
  await expect(hoverTip).toBeVisible();
  const hoverBox = await hoverTip.boundingBox();
  await page.mouse.move(hoverBox.x + hoverBox.width / 2, hoverBox.y + 4, {steps: 10});
  await expect(hoverTip).toBeVisible();
  await page.mouse.move(0, 0);
  await expect(hoverTip).toHaveCount(0);
  await edit.hover();
  await edit.focus();
  await page.evaluate(() => document.activeElement.blur());
  await expect(page.locator('.fv-icon-tooltip')).toBeVisible();
  await page.mouse.move(0, 0);
  await expect(page.locator('.fv-icon-tooltip')).toHaveCount(0);
  const originalLabel = await edit.getAttribute('aria-label');
  await page.setViewportSize({width: 320, height: 480});
  await edit.evaluate(node => node.setAttribute('aria-label', 'Long synthetic record name '.repeat(250)));
  await edit.focus();
  const tallTip = page.locator('.fv-icon-tooltip');
  await expect(tallTip).toBeVisible();
  const bounds = await tallTip.boundingBox();
  assert(bounds.x >= 0 && bounds.x + bounds.width <= 320);
  assert(bounds.y >= 0 && bounds.y + bounds.height <= 480);
  assert(await tallTip.evaluate(node => node.scrollHeight > node.clientHeight));
  await page.keyboard.press('PageDown');
  assert(await tallTip.evaluate(node => node.scrollTop > 0));
  await expect(edit).toBeFocused();
  await page.keyboard.press('Escape');
  await expect(tallTip).toHaveCount(0);
  await edit.evaluate((node, label) => node.setAttribute('aria-label', label), originalLabel);
  await page.setViewportSize({width: 1280, height: 1000});
  await section.locator('#icon-dynamic').focus();
  await expect(page.locator('.fv-icon-tooltip')).toBeVisible();
  await page.keyboard.press('Escape');
  await section.locator('#icon-dynamic').evaluate(node => {node.disabled = true;});
}

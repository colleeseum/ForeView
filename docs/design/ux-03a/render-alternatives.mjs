// SPDX-FileCopyrightText: 2026 Mindstep Corporation
// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

// Render static, code-native design concepts. No application or financial engine is loaded.
import assert from 'node:assert/strict';
import {mkdir, writeFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import {chromium} from '@playwright/test';

const output = fileURLToPath(new URL('./concepts/', import.meta.url));
await mkdir(output, {recursive: true});
const browser = await chromium.launch();
const page = await browser.newPage({viewport: {width: 1440, height: 1100}, deviceScaleFactor: 1});
const errors = [];
const results = [];
page.on('pageerror', error => errors.push(error.message));
try {
  await page.goto(new URL('./alternatives.html', import.meta.url).href);
  for (const direction of ['sage', 'analyst']) {
    await page.locator('#direction').selectOption(direction);
    for (const screen of ['overview', 'account', 'form', 'retirement', 'comparison']) {
      await page.locator('#screen').selectOption(screen);
      assert.match(await page.locator('.review-note').innerText(), /NON-FUNCTIONAL/);
      await page.mouse.move(0, 0);
      await page.screenshot({path: output + `${direction}-desktop-${screen}.png`, fullPage: true});
      results.push({direction, size: 'desktop', screen});
    }
    await page.setViewportSize({width: 390, height: 844});
    for (const screen of ['overview', 'account', 'form']) {
      await page.locator('#screen').selectOption(screen);
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth > innerWidth);
      assert.equal(overflow, false, `${direction}/${screen}: page-wide overflow`);
      await page.screenshot({path: output + `${direction}-mobile-${screen}.png`, fullPage: true});
      results.push({direction, size: 'mobile', screen});
    }
    await page.setViewportSize({width: 1440, height: 1100});
    await page.locator('#screen').selectOption('overview');
    await page.locator('[data-density]').click();
    assert.equal(await page.locator('table').getAttribute('class'), 'compact');
    await page.locator('[data-density]').click();
    await page.locator('[data-screen="account"]').first().click();
    assert.equal(await page.locator('#screen').inputValue(), 'account');
  }
  assert.deepEqual(errors, []);
  await writeFile(output + 'checks.json', JSON.stringify({captures: results, pageErrors: errors, mobileOverflow: false, prototypeControls: 'passed'}, null, 2) + '\n');
  console.log(`CONCEPT_CHECKS_PASSED: ${results.length} captures`);
} finally {
  await browser.close();
}

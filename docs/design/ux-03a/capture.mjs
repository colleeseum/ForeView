// SPDX-FileCopyrightText: 2026 Mindstep Corporation
// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

// Audit-only runner. Supply disposable localhost synthetic and empty runtimes, never prod.
import assert from 'node:assert/strict';
import {mkdir, writeFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import {resolve} from 'node:path';
import {chromium} from '@playwright/test';

const [baseURL, emptyURL, outputDirectory] = process.argv.slice(2);
for (const url of [baseURL, emptyURL]) assert.match(url || '', /^http:\/\/127\.0\.0\.1:\d+$/);
const output = (outputDirectory ? resolve(outputDirectory) : fileURLToPath(new URL('./baseline/', import.meta.url))) + '/';
await mkdir(output, {recursive: true});
const browser = await chromium.launch();
const report = {viewports: {desktop: {width: 1440, height: 1000}, mobile: {width: 390, height: 844}}, captures: [], errors: [], checks: {}};
const context = await browser.newContext({viewport: report.viewports.desktop, deviceScaleFactor: 1});
const page = await context.newPage();
page.on('pageerror', error => report.errors.push(error.message));
async function goto(path, url = baseURL) {
  const response = await page.goto(url + path);
  assert.equal(response.status(), 200, path);
  await page.waitForLoadState('networkidle');
  assert.deepEqual(report.errors, [], 'Browser exceptions invalidate the capture');
}
async function language(code, url = baseURL) {
  await goto('/application-settings', url);
  await page.locator('#locale').selectOption(code);
  await Promise.all([page.waitForNavigation(), page.locator('form button[type="submit"]').click()]);
  assert.equal(await page.locator('html').getAttribute('lang'), code);
}
async function capture(name, note = 'Current application, synthetic data; viewport capture, not full-page.') {
  await page.screenshot({path: output + name + '.png', animations: 'disabled'});
  const measurements = await page.evaluate(() => {
    const css = getComputedStyle(document.body);
    const rect = node => {
      const r = node.getBoundingClientRect();
      return {width: Math.round(r.width), height: Math.round(r.height)};
    };
    const visible = node => node.getClientRects().length && getComputedStyle(node).visibility !== 'hidden';
    return {
      lang: document.documentElement.lang, dir: document.documentElement.dir,
      viewport: {width: innerWidth, height: innerHeight},
      documentWidth: document.documentElement.scrollWidth,
      bodyFont: css.fontFamily,
      visibleControls: [...document.querySelectorAll('button,input,select')].filter(visible).slice(0, 80).map(node => ({
        tag: node.tagName, id: node.id, ...rect(node), fontSize: getComputedStyle(node).fontSize,
        disabled: node.disabled, label: (node.getAttribute('aria-label') || node.textContent || '').trim().slice(0, 70),
      })),
      tables: [...document.querySelectorAll('table')].filter(visible).map(node => ({...rect(node), scrollWidth: node.scrollWidth})),
    };
  });
  report.captures.push({name, note, ...measurements});
}
async function facts() {
  return page.evaluate(async () => {
    const paths = ['/api/dashboard', '/api/model/accounts', '/api/salary-projection?start_year=2026&end_year=2027'];
    return Promise.all(paths.map(async path => {
      const response = await fetch(path);
      if (!response.ok) throw new Error(path);
      return response.json();
    }));
  });
}
try {
  for (const url of [baseURL, emptyURL]) {
    const response = await context.request.get(url + '/');
    assert.equal(response.headers()['x-foreview-audit-synthetic'], '1', 'Refusing an unmarked server. Use this review\'s disposable serve.py, never prod/dev.');
  }
  await goto('/');
  const before = await facts();
  for (const locale of ['en-CA', 'fr-CA']) {
    await language(locale);
    for (const [size, viewport] of Object.entries(report.viewports)) {
      await page.setViewportSize(viewport);
      for (const [name, path] of [['dashboard','/'], ['assets','/accounts'], ['transactions','/transactions'], ['income','/income'], ['expenses','/expenses'], ['employment','/salary-projection']]) {
        await goto(path);
        await capture(`${locale}-${size}-${name}`);
        if (name === 'assets') {
          await page.locator('[data-edit-account]').first().click();
          await page.locator('#account-dialog').waitFor({state: 'visible'});
          await capture(`${locale}-${size}-account-details`);
          await page.locator('#cancel-account-dialog').click();
        }
        if (name === 'income') {
          await page.locator('#income-import').click();
          await capture(`${locale}-${size}-import-disabled`);
          report.checks[`${locale}-${size}-importRequiresFile`] = await page.locator('#income-import-preview').isDisabled();
        }
      }
    }
  }
  await page.setViewportSize(report.viewports.desktop);
  await language('en-CA');
  for (const [name, path] of [['people','/setup'], ['connections','/connections'], ['rules','/settings'], ['settings','/application-settings'], ['about','/about'], ['disclaimer','/disclaimer']]) {
    await goto(path);
    await capture(`en-CA-desktop-${name}`);
  }
  await goto('/accounts');
  const trigger = page.locator('[data-add-account-type="non_registered"]');
  await trigger.click();
  report.checks.accountFocusEnters = await page.locator('#account-dialog').evaluate(node => node.contains(document.activeElement));
  await page.locator('#account-dialog-form [name="name"]').fill('Synthetic unsaved draft');
  await page.locator('#account-dialog-form button[type="submit"]').click();
  report.checks.invalidFormBlocked = await page.locator('#account-dialog-form').evaluate(form => !form.checkValidity());
  await capture('en-CA-desktop-invalid-form', 'Synthetic incomplete account form; native constraint validation, no save.');
  await page.keyboard.press('Escape');
  report.checks.accountEscapeCloses = await page.locator('#account-dialog').isHidden();
  report.checks.accountFocusReturned = await trigger.evaluate(node => document.activeElement === node);
  await trigger.click();
  await page.locator('#close-account-dialog').focus();
  await page.keyboard.press('Shift+Tab');
  report.checks.accountReverseTabContained = await page.locator('#account-dialog').evaluate(node => node.contains(document.activeElement));
  await page.keyboard.press('Escape');
  await goto('/expenses');
  await page.locator('.full-help-button').click();
  await page.locator('.help-drawer').waitFor({state: 'visible'});
  await capture('en-CA-desktop-contextual-help');
  await page.keyboard.press('Escape');
  report.checks.helpEscapeCloses = await page.locator('.help-drawer').isHidden();
  await language('ar-XB');
  await goto('/income');
  await capture('synthetic-RTL-desktop-income', 'Registered synthetic RTL locale using French fallback, not an Arabic translation.');
  report.checks.rtlDirection = await page.locator('html').getAttribute('dir');
  await page.setViewportSize(report.viewports.mobile);
  await goto('/accounts');
  await capture('synthetic-RTL-mobile-assets', 'Registered synthetic RTL locale using French fallback, not an Arabic translation.');
  await language('en-CA');
  await page.setViewportSize(report.viewports.desktop);
  await page.route('**/api/dashboard', route => route.fulfill({status: 503, contentType: 'application/json', body: '{"error":"Synthetic unavailable service"}'}));
  await goto('/');
  await capture('fixture-dashboard-error', 'Deliberately injected HTTP 503 in the browser only; not an observed server failure.');
  await page.unroute('**/api/dashboard');
  let release;
  const held = new Promise(resolve => { release = resolve; });
  await page.route('**/api/dashboard', async route => { await held; await route.continue(); });
  await page.goto(baseURL + '/', {waitUntil: 'domcontentloaded'});
  await page.waitForTimeout(150);
  await capture('fixture-dashboard-loading', 'Dashboard request deliberately paused in the browser; not a performance measurement.');
  release();
  await page.waitForLoadState('networkidle');
  await page.unroute('**/api/dashboard');
  assert.deepEqual(await facts(), before, 'Audit must not change financial facts or computed values');
  report.checks.financialReadModelsUnchanged = true;
  await language('en-CA', emptyURL);
  await goto('/income', emptyURL);
  await capture('empty-runtime-income', 'Separate initialized runtime with no people or financial records.');
  assert.deepEqual(report.errors, [], 'Browser exceptions invalidate the capture');
  await writeFile(output + 'measurements.json', JSON.stringify(report, null, 2) + '\n');
  console.log(JSON.stringify({captures: report.captures.length, checks: report.checks, errors: report.errors}));
} finally {
  await browser.close();
}

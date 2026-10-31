// SPDX-FileCopyrightText: 2026 Mindstep Corporation
// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

import assert from 'node:assert/strict';
import {writeFile} from 'node:fs/promises';
import {expect} from '@playwright/test';

export function contrastRatio(foreground, background) {
  function luminance(rgb) {
    const linear = rgb.map(value => value / 255).map(value => value <= .04045 ? value / 12.92 : ((value + .055) / 1.055) ** 2.4);
    return linear[0] * .2126 + linear[1] * .7152 + linear[2] * .0722;
  }
  const values = [luminance(foreground), luminance(background)].sort((a, b) => b - a);
  return (values[0] + .05) / (values[1] + .05);
}

// Runs in the browser. Composite each subtree before its parent's opacity,
// preserving CSS group opacity rather than multiplying foreground alpha alone.
export function renderedColors(node) {
  const channels = value => (value.match(/[\d.]+/g) || []).map(Number);
  const over = (front, back) => {
    const alpha = front[3] + back[3] * (1 - front[3]);
    return [...front.slice(0, 3).map((value, index) => alpha
      ? (value * front[3] + back[index] * back[3] * (1 - front[3])) / alpha : 0), alpha];
  };
  let foreground = channels(getComputedStyle(node).color);
  foreground[3] ??= 1;
  let background = [0, 0, 0, 0];
  for (let current = node; current; current = current.parentElement) {
    const style = getComputedStyle(current);
    const color = channels(style.backgroundColor);
    color[3] ??= 1;
    foreground = over(foreground, color);
    background = over(background, color);
    foreground[3] *= Number(style.opacity);
    background[3] *= Number(style.opacity);
  }
  return {foreground: over(foreground, [255, 255, 255, 1]).slice(0, 3),
    background: over(background, [255, 255, 255, 1]).slice(0, 3)};
}

export function measureLayout() {
  const main = document.querySelector('main');
  const workspace = main.querySelector('.page-content') || main;
  const regions = [...main.querySelectorAll('.fv-table-scroll, [role="region"][tabindex="0"]')]
    .filter(node => node.getClientRects().length);
  const tables = [...main.querySelectorAll('table')].filter(node => node.getClientRects().length);
  return {viewport: innerWidth, document: document.documentElement.scrollWidth,
    available: main.clientWidth, content: main.scrollWidth,
    workspaceAvailable: workspace.clientWidth, workspaceContent: workspace.scrollWidth,
    uncontainedTables: tables.filter(table => !regions.some(region => region.contains(table))).length,
    regions: regions.map(node => ({
      name: node.getAttribute('aria-label') || (node.getAttribute('aria-labelledby') || '').split(/\s+/).map(id => document.getElementById(id)?.textContent || '').join(' ').trim(),
      tabIndex: node.tabIndex, overflow: getComputedStyle(node).overflowX,
    }))};
}

export function assertLayout(result, context) {
  assert(result.document <= result.viewport + 1 && result.content <= result.available + 1
    && result.workspaceContent <= result.workspaceAvailable + 1,
  `${context}: page/workspace overflow ${JSON.stringify(result)}`);
  assert.equal(result.uncontainedTables, 0, `${context}: every visible table has a scroll region`);
  for (const region of result.regions) assert(region.name && region.tabIndex === 0 && ['auto', 'scroll'].includes(region.overflow), `${context}: accessible local scrolling`);
}

export async function assertCloseVisible(page, timeout = 5000) {
  const close = page.locator('.help-drawer-close');
  await expect(close).toBeVisible({timeout});
  await expect(close).toBeInViewport({timeout});
}

export async function dismissHelpWithEscape(page) {
  const modal = page.locator('dialog.help-drawer-backdrop');
  const tooltip = modal.locator('.fv-icon-tooltip');
  if (await tooltip.count()) {
    await page.keyboard.press('Escape');
    await expect(tooltip).toHaveCount(0);
    await expect(modal).toBeVisible();
  }
  await page.keyboard.press('Escape');
  await expect(modal).toBeHidden();
}

export async function verifyAcceptanceGuards(page) {
  await page.setViewportSize({width: 640, height: 450});
  await page.setContent(`<main><div class="page-content" style="overflow-x:auto">
    <div id="wide">Synthetic content</div>
    <div class="fv-table-scroll" role="region" tabindex="0" aria-label="Synthetic table" style="overflow-x:auto">
      <table><tr><td>Evidence</td></tr></table>
    </div></div><button class="help-drawer-close">Close</button>
    <div id="group" style="background:white"><span id="sample" style="color:black">Text</span></div></main>`);
  assertLayout(await page.evaluate(measureLayout), 'baseline');
  await assertCloseVisible(page);
  await page.locator('.help-drawer-close').evaluate(node => {node.style.visibility = 'hidden';});
  await expect(page.locator('.help-drawer-close')).toBeInViewport();
  await assert.rejects(() => assertCloseVisible(page, 100), /toBeVisible/);
  await page.locator('#wide').evaluate(node => {node.style.width = '2000px';});
  const overflow = await page.evaluate(measureLayout);
  assert(overflow.document <= overflow.viewport + 1 && overflow.content <= overflow.available + 1);
  assert.throws(() => assertLayout(overflow, 'injected'), /workspace overflow/);
  await page.locator('#wide').evaluate(node => {node.style.width = '';});
  await page.locator('.fv-table-scroll').evaluate(node => {
    node.className = ''; node.removeAttribute('role'); node.removeAttribute('tabindex');
  });
  const uncontained = await page.evaluate(measureLayout);
  assert.throws(() => assertLayout(uncontained, 'injected'), /every visible table/);
  for (const [target, property, value] of [
    ['#sample', 'color', 'rgba(0, 0, 0, .2)'],
    ['#sample', 'opacity', '.2'], ['#group', 'opacity', '.2'],
  ]) {
    await page.locator(target).evaluate((node, {property, value}) => {node.style[property] = value;}, {property, value});
    const colors = await page.locator('#sample').evaluate(renderedColors);
    assert(colors.foreground.every(channel => Math.abs(channel - 204) < .01));
    assert.deepEqual(colors.background, [255, 255, 255]);
    assert(contrastRatio(colors.foreground, colors.background) < 4.5, `${target} ${property}: faded text fails`);
    await page.locator(target).evaluate((node, property) => {node.style[property] = '';}, property);
  }
}

// Approved A matrix, plus a half-width CSS viewport reflow check. The latter
// does not claim to automate browser-chrome zoom or assistive technology.
const viewports = [
  {width: 1440, height: 1000}, {width: 1280, height: 900},
  {width: 390, height: 844}, {width: 320, height: 800},
  {width: 640, height: 450},
];
const pages = [
  ['dashboard', '/'], ['assets', '/accounts'], ['transactions', '/transactions'],
  ['income', '/income'], ['expenses', '/expenses'], ['employment', '/salary-projection'],
  ['people', '/setup'], ['connections', '/connections'], ['rules', '/settings'],
  ['settings', '/application-settings'], ['about', '/about'], ['disclaimer', '/disclaimer'],
];

export async function verifyAcceptance(page, baseURL, locale, output) {
  async function snapshot() {
    return page.evaluate(async () => Promise.all([
      '/api/dashboard', '/api/model/accounts', '/api/model/transactions?account_type=non_registered',
      '/api/salary-projection?start_year=2026&end_year=2027',
    ].map(async url => {
      const response = await fetch(url);
      if (!response.ok) throw new Error(`Acceptance read failed: ${url}`);
      return response.json();
    })));
  }
  await page.goto(baseURL + '/');
  await page.waitForLoadState('networkidle');
  const original = await snapshot();
  const writes = [];
  const recordWrite = request => {if (!['GET', 'HEAD', 'OPTIONS'].includes(request.method())) writes.push(request.url());};
  page.on('request', recordWrite);
  const measurements = [];
  try {
    for (const [key, path] of pages) {
      const response = await page.goto(baseURL + path);
      assert(response.ok(), path);
      await page.waitForLoadState('networkidle');
      await expect(page.locator('html')).toHaveAttribute('lang', locale);
      await expect(page.locator('main')).toHaveClass(/fv-ui/);
      assert(!(await page.locator('main').innerText()).includes('⟦'), `${key}: resolved messages`);
      if (key === 'income') await page.locator('.income-source-details').evaluate(node => {node.open = true;});
      for (const viewport of viewports) {
        await page.setViewportSize(viewport);
        const result = await page.evaluate(measureLayout);
        const controls = await page.evaluate(() => {
          const main = document.querySelector('main');
          const controls = [...main.querySelectorAll('.fv-button, .full-help-button')]
            .filter(node => node.getClientRects().length);
          return controls.map(node => {const box = node.getBoundingClientRect(); return {width: box.width, height: box.height};});
        });
        assertLayout(result, `${key} ${locale} ${viewport.width}`);
        for (const control of controls) assert(control.width >= 43.9 && control.height >= 43.9, `${key}: primary control target`);
        const pairs = [];
        for (const node of await page.locator('main h1, main .side-menu-heading, main .fv-button--primary:not(:disabled), main .fv-table thead th').all()) {
          if (await node.isVisible()) pairs.push(await node.evaluate(renderedColors));
        }
        assert(pairs.length > 0, `${key}: contrast samples exist`);
        const ratios = pairs.map(pair => contrastRatio(pair.foreground, pair.background));
        assert(ratios.every(ratio => ratio >= 4.5), `${key}: sampled text contrast ${Math.min(...ratios)}`);
        // Open full help at every approved viewport, including short screens.
        const trigger = page.locator('.full-help-button');
        await trigger.click();
        const modal = page.locator('dialog.help-drawer-backdrop');
        await expect(page.locator('#help-search')).toBeFocused();
        assert(await modal.evaluate(node => node.matches(':modal')));
        await assertCloseVisible(page);
        await dismissHelpWithEscape(page);
        await expect(trigger).toBeFocused();
        const image = `${locale}-${viewport.width}x${viewport.height}-${key}-acceptance.png`;
        if (viewport.width !== 640) {
          // Keep the expanded navigation assertions above, but show financial
          // content in narrow review captures rather than only the long menu.
          if (viewport.width < 720) await page.locator('.fv-navigation').evaluate(node => {node.open = false;});
          await page.screenshot({path: `${output}/${image}`});
          if (viewport.width < 720) await page.locator('.fv-navigation').evaluate(node => {node.open = true;});
        }
        measurements.push({page: key, path, ...viewport, controls: controls.length,
          scrollRegions: result.regions.length, contrastSamples: ratios.length, minimumContrast: Math.min(...ratios),
          screenshot: viewport.width === 640 ? null : image,
          screenshotNavigationCollapsed: viewport.width < 720 && viewport.width !== 640});
      }
    }
    // Browser-only evidence exercises values that normal fixture balances may
    // not contain. Keep original source language and never write these facts.
    const stress = {...original[0], gross_assets: 123456789012.34,
      immovable_value: -1234.56, invested_value: 0, gic_value: null,
      recent_transactions: [{transaction_date: '2026-01-25',
        description: 'Synthetic source evidence with a deliberately long description. '.repeat(12),
        description_language: 'en-CA', amount: -1234.56,
        institution: 'Synthetic institution', account_number: 'SYNTHETIC'}]};
    const dashboardFixture = route => route.fulfill({json: stress});
    await page.route('**/api/dashboard', dashboardFixture);
    try {
      await page.setViewportSize({width: 320, height: 800});
      await page.goto(baseURL + '/');
      await page.waitForLoadState('networkidle');
      const expected = await page.evaluate(locale => {
        const money = new Intl.NumberFormat(locale, {style: 'currency', currency: 'CAD', minimumFractionDigits: 2, maximumFractionDigits: 2});
        return {large: money.format('123456789012.34'), negative: money.format('-1234.56'), zero: money.format('0'),
          date: new Intl.DateTimeFormat(locale, {year: 'numeric', month: 'short', day: 'numeric', timeZone: 'UTC'}).format(new Date('2026-01-25T00:00:00Z'))};
      }, locale);
      const amounts = page.locator('#dashboard-metrics strong');
      await expect(amounts.nth(0)).toHaveText(expected.large);
      await expect(amounts.nth(1)).toHaveText(expected.negative);
      await expect(amounts.nth(2)).toHaveText(expected.zero);
      await expect(amounts.nth(3)).toHaveText(locale === 'en-CA' ? 'Unavailable' : 'Indisponible');
      await expect(page.locator('#dashboard-transactions tbody td').first()).toHaveText(expected.date);
      await expect(page.locator('#dashboard-transactions [lang="en-CA"]')).toContainText('Synthetic source evidence');
      await page.locator('.fv-navigation').evaluate(node => {node.open = false;});
      for (const card of await page.locator('#dashboard-metrics .summary-pill').all()) assert(await card.evaluate(node => node.scrollWidth <= node.clientWidth), 'Large/signed/missing amounts fit their cards');
      await page.screenshot({path: `${output}/${locale}-320-dashboard-stress.png`});
      await page.evaluate(() => {document.documentElement.style.fontSize = '200%';});
      assertLayout(await page.evaluate(measureLayout), 'Dashboard supports 200% text reflow');
      await page.screenshot({path: `${output}/${locale}-320-dashboard-text-resize.png`});
    } finally {
      await page.unroute('**/api/dashboard', dashboardFixture);
      await page.evaluate(() => {document.documentElement.style.fontSize = '';});
    }
    assert.deepEqual(await snapshot(), original, 'The acceptance tour preserves factual and calculated read models');
    assert.deepEqual(writes, [], 'The acceptance tour makes no mutation requests');
    await writeFile(`${output}/${locale}-acceptance.json`, JSON.stringify({locale, viewports, checks: measurements,
      dashboardStress: {largeNegativeZeroMissing: true, localizedMoneyDate: true, sourceLanguage: true, textResizePercent: 200},
      readModelsUnchanged: true, mutationRequests: 0}, null, 2));
  } finally {page.off('request', recordWrite);}
}

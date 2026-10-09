// SPDX-FileCopyrightText: 2026 Mindstep Corporation
// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
import test from 'node:test';
import assert from 'node:assert/strict';

async function translator(config) {
  globalThis.document = {querySelector: () => ({textContent: JSON.stringify(config)})};
  return import(`../../static/i18n.mjs?case=${Math.random()}`);
}

test('browser localization selects French, interpolates values and falls back', async () => {
  const {t, locale} = await translator({
    locale: 'fr-FR', fallbacks: ['fr-CA', 'en-CA'],
    catalogs: {
      'fr-FR': {sample: {}},
      'fr-CA': {sample: {hello: 'Bonjour {name}'}},
      'en-CA': {sample: {hello: 'Hello {name}', fallback: 'English fallback'}},
    },
  });
  assert.equal(locale, 'fr-FR');
  assert.equal(t('sample.hello', {name: 'Marie'}), 'Bonjour Marie');
  assert.equal(t('sample.fallback'), 'English fallback');
  assert.equal(t('sample.hello'), '⟦browser.sample.hello⟧');
  assert.equal(t('sample.missing'), '⟦browser.sample.missing⟧');
});

test('browser localization rejects unsupported brace syntax and falls back', async () => {
  const {t} = await translator({
    locale: 'fr-FR', fallbacks: ['fr-CA', 'en-CA'],
    catalogs: {
      'fr-FR': {sample: {
        amount: 'Montant {amount:.2f}',
        braces: 'Utilisez {{name}}',
      }},
      'fr-CA': {sample: {amount: 'Montant {amount}'}},
      'en-CA': {sample: {braces: 'Use the name field'}},
    },
  });
  assert.equal(t('sample.amount', {amount: '12,50'}), 'Montant 12,50');
  assert.equal(t('sample.braces', {name: 'value'}), 'Use the name field');
});

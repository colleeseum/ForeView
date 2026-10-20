// SPDX-FileCopyrightText: 2026 Mindstep Corporation
// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

import assert from 'node:assert/strict';
import test from 'node:test';
import {configureTestLocalization} from './localization-fixture.mjs';
import {money} from '../../static/accounts/accounts-format.mjs';
import {accountTypes} from '../../static/shared/account-types.mjs';
import {formatMoneyCents} from '../../static/shared/locale-format.mjs';

test('moved account modules share canonical localization and account-type state', async () => {
  globalThis.window = {location: {search: ''}};
  const {assetGroups} = await import('../../static/accounts/accounts-state.mjs');
  const canonical = await import('../../static/shared/i18n.mjs');
  const fromFeature = await import('../../static/accounts/../shared/i18n.mjs');
  assert.strictEqual(fromFeature, canonical);
  assert.strictEqual(assetGroups, accountTypes);
  for (const locale of ['en-CA', 'fr-CA']) {
    configureTestLocalization(locale);
    assert.equal(fromFeature.locale, locale);
    assert.equal(money(1234.56), formatMoneyCents(123456, {locale}));
  }
});

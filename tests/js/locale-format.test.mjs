// SPDX-FileCopyrightText: 2026 Mindstep Corporation
// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
import test from 'node:test';
import assert from 'node:assert/strict';
import {formatDate, formatNumber, formatMoneyCents, formatPercent, pluralCategory, plural} from '../../static/locale-format.mjs';

test('Canadian dates use locale-specific ordering without timezone drift', () => {
  assert.match(formatDate('2026-01-09', {locale: 'en-CA'}), /2026/);
  assert.match(formatDate('2026-01-09', {locale: 'fr-CA'}), /2026/);
  assert.notEqual(formatDate('2026-01-09', {locale: 'en-CA'}), formatDate('2026-01-09', {locale: 'fr-CA'}));
  assert.throws(() => formatDate('0000-01-01'), RangeError);
  assert.throws(() => formatDate('2026-02-30'), RangeError);
  assert.match(formatDate('0099-01-01', {locale: 'en-CA'}), /99/);
  assert.throws(() => formatDate('0099-02-29'), RangeError);
  assert.equal(
    formatDate('2026-01-09', {locale: 'en-CA', timeZone: 'America/Toronto'}),
    formatDate('2026-01-09', {locale: 'en-CA'}),
  );
  assert.match(formatDate('2026-01-09', {locale: 'en-CA', dateStyle: 'full'}), /2026/);
  assert.throws(() => formatDate('2026-01-09', {locale: 'en-CA', timeStyle: 'short'}), TypeError);
  assert.throws(() => formatDate('2026-01-09', {locale: 'en-CA', hour: 'numeric'}), TypeError);
  assert.throws(() => formatDate('2026-01-09', {locale: 'en-CA', timeZoneName: 'long'}), TypeError);
});
test('currency uses exact cent inputs and locale-specific separators', () => {
  const en = formatMoneyCents(123456, {locale: 'en-CA'});
  const fr = formatMoneyCents(123456, {locale: 'fr-CA'});
  assert.match(en, /1,234\.56/);
  assert.match(fr, /1\s?234,56|1\u00a0234,56|1\u202f234,56/);
  assert.notEqual(en, fr);
  assert.match(formatMoneyCents(1, {locale: 'en-CA'}), /0\.01/);
  assert.match(formatMoneyCents(-1, {locale: 'fr-CA'}), /0,01/);
  assert.throws(() => formatMoneyCents(1.5), TypeError);
  assert.match(formatMoneyCents(9007199254740901n, {locale: 'en-CA'}), /90,071,992,547,409\.01/);
  assert.match(formatMoneyCents(-9007199254740901n, {locale: 'fr-CA'}), /90.*409,01/);
  assert.match(formatMoneyCents(BigInt(Number.MAX_SAFE_INTEGER), {locale: 'en-CA'}), /90,071,992,547,409\.91/);
  assert.throws(() => formatMoneyCents(123n, {locale: 'en-CA', currency: 'USD'}), RangeError);
  assert.throws(() => formatMoneyCents(123n, {locale: 'en-CA', currency: 'BTC'}), RangeError);
  assert.throws(() => formatMoneyCents(123n, {locale: 'en-CA', currency: 'XDR'}), RangeError);
  assert.throws(() => formatMoneyCents(123n, {locale: 'en-CA', currency: 'ZZZ'}), RangeError);
  assert.throws(() => formatMoneyCents(123n, {locale: 'en-CA', currency: 'JPY'}), RangeError);
  assert.match(formatMoneyCents(123n, {locale: 'en-CA', currencyDisplay: 'code'}), /CAD/);
  for (const options of [
    {maximumSignificantDigits: 2},
    {roundingIncrement: 5},
    {style: 'percent'},
    {notation: 'compact'},
    {maximumFractionDigits: 0},
    {signDisplay: 'never'},
  ]) {
    assert.throws(() => formatMoneyCents(123n, {locale: 'en-CA', ...options}), TypeError);
  }
});
test('numbers and percentages have deterministic rounding boundaries', () => {
  assert.equal(formatNumber(1.234, {locale: 'en-CA', maximumFractionDigits: 2}), '1.23');
  assert.equal(formatNumber(1.235, {locale: 'en-CA', maximumFractionDigits: 2}), '1.24');
  assert.match(formatPercent(0.125, {locale: 'fr-CA', maximumFractionDigits: 1}), /12,5/);
  assert.match(formatPercent(0.125, {locale: 'en-CA', maximumFractionDigits: 1}), /12\.5/);
  assert.match(formatPercent(0.125, {locale: 'en-CA', style: 'percent'}), /12\.5%/);
  assert.throws(() => formatPercent(0.125, {locale: 'en-CA', style: 'decimal'}), TypeError);
  assert.throws(() => formatPercent(0.125, {locale: 'en-CA', style: 'currency', currency: 'CAD'}), TypeError);
  for (const signDisplay of ['never', 'exceptZero', 'negative']) {
    assert.throws(() => formatPercent(-0.001, {locale: 'en-CA', maximumFractionDigits: 0, signDisplay}), TypeError);
  }
  assert.match(formatPercent(-0.001, {locale: 'en-CA', maximumFractionDigits: 0, signDisplay: 'auto'}), /^-0%$/);
  assert.match(formatPercent(-0.001, {locale: 'en-CA', maximumFractionDigits: 0, signDisplay: 'always'}), /^-0%$/);
  assert.match(formatPercent(0.126, {locale: 'en-CA', minimumFractionDigits: 3}), /12\.600%/);
  assert.match(formatPercent(0.126, {locale: 'en-CA', roundingIncrement: 5}), /15%/);
  assert.match(formatPercent(0.126, {locale: 'en-CA', minimumSignificantDigits: 4}), /12\.60%/);
});
test('plural rules support locale categories and other fallback', () => {
  assert.equal(pluralCategory(1, {locale: 'en-CA'}), 'one');
  assert.equal(pluralCategory(2, {locale: 'en-CA'}), 'other');
  assert.equal(plural(1, {one: '{count} account', other: '{count} accounts'}, {locale: 'en-CA'}), '1 account');
  assert.equal(plural(2, {one: '{count} compte', other: '{count} comptes'}, {locale: 'fr-CA'}), '2 comptes');
  assert.equal(plural(0, {other: '{count} comptes'}, {locale: 'fr-CA'}), '0 comptes');
  assert.throws(() => plural(1, {one: 'one'}, {locale: 'en-CA'}), TypeError);
  assert.throws(() => plural(1, {one: 'one', other: 42}, {locale: 'en-CA'}), TypeError);
  assert.equal(plural(1, Object.assign(Object.create({one: 'inherited'}), {other: 'fallback'}), {locale: 'en-CA'}), 'fallback');
  assert.throws(() => plural(2, Object.create({other: '{count} inherited'}), {locale: 'en-CA'}), TypeError);
});

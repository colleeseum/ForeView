// SPDX-FileCopyrightText: 2026 Mindstep Corporation
// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
// Presentation only. Never use formatted output as input to calculations or storage.
import {locale as selectedLocale} from './i18n.mjs';

const MONEY_PRESENTATION_OPTIONS = new Set([
  'currencyDisplay',
  'currencySign',
  'localeMatcher',
  'numberingSystem',
  'useGrouping',
]);
const DATE_TIME_OPTIONS = [
  'dayPeriod',
  'fractionalSecondDigits',
  'hour',
  'hour12',
  'hourCycle',
  'minute',
  'second',
  'timeStyle',
  'timeZoneName',
];
const PERCENT_PRECISION_OPTIONS = [
  'maximumFractionDigits',
  'maximumSignificantDigits',
  'minimumFractionDigits',
  'minimumSignificantDigits',
  'roundingIncrement',
];
const SUPPORTED_CURRENCIES = new Set(['CAD']);

function language(locale) {
  return locale ?? selectedLocale;
}
function finite(value) {
  if (typeof value !== 'number' || !Number.isFinite(value)) throw new TypeError('Expected a finite number');
  return value;
}
function isoDate(value) {
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value)) throw new TypeError('Expected YYYY-MM-DD');
  const [year, month, day] = value.split('-').map(Number);
  if (year === 0) throw new RangeError('Invalid calendar date');
  // Date.UTC treats years 0..99 as 1900..1999; set the full year explicitly.
  const date = new Date(0);
  date.setUTCHours(0, 0, 0, 0);
  date.setUTCFullYear(year, month - 1, day);
  if (date.getUTCFullYear() !== year || date.getUTCMonth() !== month - 1 || date.getUTCDate() !== day) throw new RangeError('Invalid calendar date');
  return date;
}
// Canonical API dates sort by calendar date; malformed legacy evidence sorts first.
export function calendarDateSortKey(value) {
  try {
    isoDate(value);
    return [1, value];
  } catch (error) {
    if (error instanceof TypeError || error instanceof RangeError) return [0, String(value ?? '')];
    throw error;
  }
}
function moneyPresentationOptions(options) {
  for (const option of Object.keys(options)) {
    if (!MONEY_PRESENTATION_OPTIONS.has(option)) {
      throw new TypeError(`Unsupported money formatting option: ${option}`);
    }
  }
  return options;
}
export function formatDate(value, {locale, ...options} = {}) {
  const timeOption = DATE_TIME_OPTIONS.find((option) => options[option] !== undefined);
  if (timeOption !== undefined) {
    throw new TypeError(`Date-only formatting does not accept ${timeOption}`);
  }
  const defaults = options.dateStyle === undefined
    ? {year: 'numeric', month: 'short', day: 'numeric'}
    : {};
  return new Intl.DateTimeFormat(language(locale), {
    ...defaults,
    ...options,
    timeZone: 'UTC',
  }).format(isoDate(value));
}
export function formatNumber(value, {locale, ...options} = {}) {
  return new Intl.NumberFormat(language(locale), options).format(finite(value));
}
// Amounts are authoritative integer cents. BigInt avoids precision loss in cent arithmetic.
export function formatMoneyCents(cents, {locale, currency = 'CAD', ...options} = {}) {
  if (typeof cents !== 'bigint' && (!Number.isSafeInteger(cents))) throw new TypeError('Expected safe integer cents or bigint');
  const presentationOptions = moneyPresentationOptions(options);
  const currencyRules = new Intl.NumberFormat('en', {style: 'currency', currency}).resolvedOptions();
  if (
    !SUPPORTED_CURRENCIES.has(currencyRules.currency)
    || currencyRules.minimumFractionDigits !== 2
    || currencyRules.maximumFractionDigits !== 2
  ) {
    throw new RangeError('Currency must use cents as its standard minor unit');
  }
  const amount = BigInt(cents);
  const sign = amount < 0n ? '-' : '';
  const abs = amount < 0n ? -amount : amount;
  // ECMA-402 NumberFormat accepts decimal strings without first converting to
  // binary floating point. This preserves cents even for large bigint values.
  const decimal = `${sign}${abs / 100n}.${String(abs % 100n).padStart(2, '0')}`;
  return new Intl.NumberFormat(language(locale), {
    style: 'currency',
    currency,
    ...presentationOptions,
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(decimal);
}
// Percentages take ratios (0.125 => 12.5%), not already-scaled percent points.
export function formatPercent(ratio, {locale, style, ...options} = {}) {
  if (style !== undefined && style !== 'percent') {
    throw new TypeError('Percentage formatting style cannot be overridden');
  }
  if (options.signDisplay !== undefined && !['auto', 'always'].includes(options.signDisplay)) {
    throw new TypeError('Percentage sign display must preserve rounded negative values');
  }
  const hasPrecisionOption = PERCENT_PRECISION_OPTIONS.some(
    (option) => options[option] !== undefined,
  );
  return new Intl.NumberFormat(language(locale), {
    ...(hasPrecisionOption ? {} : {maximumFractionDigits: 2}),
    ...options,
    style: 'percent',
  }).format(finite(ratio));
}
export function pluralCategory(count, {locale, type = 'cardinal'} = {}) {
  return new Intl.PluralRules(language(locale), {type}).select(finite(count));
}
export function plural(count, forms, {locale, type = 'cardinal'} = {}) {
  const category = pluralCategory(count, {locale, type});
  if (forms === null || typeof forms !== 'object' || !Object.hasOwn(forms, 'other') || typeof forms.other !== 'string') throw new TypeError('Plural forms must provide an other fallback');
  const form = Object.hasOwn(forms, category) ? forms[category] : forms.other;
  if (typeof form !== 'string') throw new TypeError('Plural form must be a string');
  return form.replace(/\{count\}/g, formatNumber(count, {locale}));
}

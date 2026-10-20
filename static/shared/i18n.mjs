// SPDX-FileCopyrightText: 2026 Mindstep Corporation
// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
// Browser localization: same fallback order and visible missing-key policy as Python.
// Browser messages support simple {name} placeholders only. Other brace syntax makes a
// translation unrenderable so lookup can continue through the configured fallback chain.
const state = typeof document === 'undefined' ? null : document.querySelector('#browser-localization');
let config = state ? JSON.parse(state.textContent) : {locale: 'en-CA', fallbacks: [], catalogs: {}};
const lookup = (locale, key) => key.split('.').reduce((value, part) => value && typeof value === 'object' ? value[part] : undefined, config.catalogs[locale]);
const placeholderPattern = /\{([A-Za-z_][A-Za-z0-9_]*)\}/g;

export let locale = config.locale;

export function configureLocalization(nextConfig) {
  config = nextConfig;
  locale = config.locale;
}

export function t(key, values = {}) {
  const fallbacks = Array.isArray(config.fallbacks) ? config.fallbacks : [config.fallback];
  for (const candidate of [config.locale, ...fallbacks]) {
    const message = lookup(candidate, key);
    if (typeof message !== 'string') continue;
    const fields = [...message.matchAll(placeholderPattern)].map((match) => match[1]);
    const textWithoutPlaceholders = message.replace(placeholderPattern, '');
    if (textWithoutPlaceholders.includes('{') || textWithoutPlaceholders.includes('}')) continue;
    if (fields.some((field) => !Object.hasOwn(values, field))) continue;
    return message.replace(placeholderPattern, (_, field) => String(values[field]));
  }
  return `⟦browser.${key}⟧`;
}

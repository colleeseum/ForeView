// SPDX-FileCopyrightText: 2026 Mindstep Corporation
// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

const HTML_ENTITIES = Object.freeze({
  '&': '&amp;',
  '<': '&lt;',
  '>': '&gt;',
  '"': '&quot;',
  "'": '&#39;',
});

export function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, (character) => HTML_ENTITIES[character]);
}

export function languageSpan(value, language = 'en-CA') {
  return `<span lang="${escapeHtml(language)}">${escapeHtml(value)}</span>`;
}

export function sourceTextSpan(value, language = '') {
  return languageSpan(value, language);
}

export function htmlWithLanguageSpans(formatMessage, spans) {
  const replacements = Object.entries(spans).map(([name, span], index) => {
    const token = `__FOREVIEW_LANGUAGE_SPAN_${index}__`;
    const specification = typeof span === 'object' ? span : {value: span};
    return {name, token, ...specification};
  });
  const values = Object.fromEntries(replacements.map(({name, token}) => [name, token]));
  let html = escapeHtml(formatMessage(values));
  for (const {token, value, language = 'en-CA'} of replacements) {
    html = html.replaceAll(escapeHtml(token), languageSpan(value, language));
  }
  return html;
}

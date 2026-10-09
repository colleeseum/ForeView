// SPDX-FileCopyrightText: 2026 Mindstep Corporation
// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

import {t, locale} from './i18n.mjs';

async function jsonResponse(response) {
  const data = await response.json();
  if (!response.ok) {
    const error = new Error(data.error || t('accounts.request_failed', {status: response.status}));
    error.language = data.error ? 'en-CA' : locale;
    throw error;
  }
  return data;
}

export async function loadAssetData() {
  const [accountData, holdingData, realEstateData] = await Promise.all([
    fetch('/api/model/accounts').then(jsonResponse),
    fetch('/api/model/holdings').then(jsonResponse),
    fetch('/api/model/real-estate').then(jsonResponse),
  ]);
  return {
    accounts: accountData.accounts,
    categoryTotals: accountData.category_totals,
    holdings: holdingData.holdings,
    realEstateAssets: realEstateData.assets,
  };
}

export async function loadPeople() {
  return (await fetch('/api/model/people').then(jsonResponse)).people;
}

export function saveJson(url, method, payload) {
  return fetch(url, {
    method,
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(payload),
  }).then(jsonResponse);
}

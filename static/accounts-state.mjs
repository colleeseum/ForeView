// SPDX-FileCopyrightText: 2026 Mindstep Corporation
// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

import {accountTypes} from './account-types.mjs';

export const assetGroups = accountTypes;

const requestedView = new URLSearchParams(window.location.search).get('tab');
const validViews = new Set([...assetGroups, 'real_estate']);

export const assetState = {
  accounts: [],
  categoryTotals: [],
  holdings: [],
  people: [],
  realEstateAssets: [],
  view: validViews.has(requestedView) ? requestedView : 'non_registered',
};

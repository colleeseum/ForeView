// SPDX-FileCopyrightText: 2026 Mindstep Corporation
// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

import {t} from './i18n.mjs';

export const accountTypes = Object.freeze(['non_registered', 'tfsa', 'rrsp', 'resp']);

export function accountTypeLabel(type, fallback = '') {
  return accountTypes.includes(type) ? t(`accounts.types.${type}`) : fallback || type || '';
}

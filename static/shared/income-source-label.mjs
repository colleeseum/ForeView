// SPDX-FileCopyrightText: 2026 Mindstep Corporation
// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

import {t} from './i18n.mjs';

const localizedIncomeSources = new Map([['Manual', 'manual']]);

export function incomeSourceLabel(source) {
  const key = localizedIncomeSources.get(source);
  return key ? t(`income.source_labels.${key}`) : source || '';
}

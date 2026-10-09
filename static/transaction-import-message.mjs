// SPDX-FileCopyrightText: 2026 Mindstep Corporation
// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

import {t, locale} from './i18n.mjs';

export function importMessage(data) {
  const reconciliation = (data.results || []).find((item) => item.reconciliation_status);
  if (reconciliation) {
    if (reconciliation.reconciliation_status === 'reconciled') {
      const count = reconciliation.csv_transaction_count;
      return t(
        Number(count) === 1 ? 'transaction_import.reconciled' : 'transaction_import.reconciled_plural',
        {count},
      );
    }
    if (reconciliation.reconciliation_status === 'no_matching_transactions') {
      return t('transaction_import.no_matches');
    }
    return t('transaction_import.difference', {
      amount: Number(reconciliation.difference || 0).toLocaleString(locale, {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      }),
    });
  }
  const tfsa = (data.results || []).filter((item) => item.document_type === 'statement' || item.document_type === 'maturity_notice');
  if (tfsa.length) {
    const interestRows = tfsa.reduce((sum, item) => sum + Number(item.imported || 0), 0);
    const gics = tfsa.reduce((sum, item) => sum + Number(item.gics || 0), 0);
    return t('transaction_import.tfsa', {
      interest: t(interestRows === 1 ? 'transaction_import.interest_entry' : 'transaction_import.interest_entries', {count: interestRows}),
      gics: t(gics === 1 ? 'transaction_import.gic_record' : 'transaction_import.gic_records', {count: gics}),
    });
  }
  return t('transaction_import.complete', {
    transactions: t(data.imported === 1 ? 'transaction_import.transaction' : 'transaction_import.transactions', {count: data.imported}),
    files: t(data.files === 1 ? 'transaction_import.file' : 'transaction_import.files', {count: data.files}),
  });
}

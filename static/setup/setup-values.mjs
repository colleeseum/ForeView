// SPDX-FileCopyrightText: 2026 Mindstep Corporation
// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

export function editableAccountValues(account) {
  return {
    institution: account.institution ?? '',
    name: account.name ?? '',
    account_number: account.account_number ?? '',
  };
}

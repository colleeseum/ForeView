// SPDX-FileCopyrightText: 2026 Mindstep Corporation
// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

const securityInstitutions = new Set(['questrade', 'sunlife', 'sun life', 'manulife']);

export function money(value, blankForNull = false) {
  if (blankForNull && value == null) return '';
  return Number(value || 0).toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

export function isSecurityAccount(account) {
  const institution = String(account?.institution || '').trim().toLowerCase();
  return account?.asset_kind !== 'gic' && securityInstitutions.has(institution);
}

export function ownerDetails(account) {
  if (!account.owner_details) return [];
  return account.owner_details.split(',').map((item) => {
    const [personId, share] = item.split(':');
    return {person_id: Number(personId), share: Number(share)};
  });
}

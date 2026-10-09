// SPDX-FileCopyrightText: 2026 Mindstep Corporation
// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

export function formSignature(form, additionalParts = []) {
  const fields = [...form.elements]
    .filter((field) => field.name)
    .map((field) => `${field.name}:${field.type === 'checkbox' ? field.checked : field.value}`);
  return [...fields, ...additionalParts].join('|');
}

export function showError(target, error) {
  target.textContent = error instanceof Error ? error.message : String(error);
  target.classList.add('error');
  target.lang = error?.language || 'en-CA';
}

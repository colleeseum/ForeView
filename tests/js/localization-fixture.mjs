// SPDX-FileCopyrightText: 2026 Mindstep Corporation
// SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

import {readFileSync} from 'node:fs';

import {configureLocalization} from '../../static/i18n.mjs';

const catalogs = {
  'en-CA': JSON.parse(readFileSync(new URL('../../localization/en-CA/browser.json', import.meta.url))),
  'fr-CA': JSON.parse(readFileSync(new URL('../../localization/fr-CA/browser.json', import.meta.url))),
};

export function configureTestLocalization(locale = 'en-CA') {
  configureLocalization({locale, fallbacks: locale === 'en-CA' ? [] : ['en-CA'], catalogs});
}

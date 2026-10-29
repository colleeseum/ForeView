# Localization architecture

ForeView-owned interface text is localized through the registry and catalogs under `localization/`.
Imported evidence, identifiers, source wording, hashes, and normalized authoritative values are not
translated.

A locale is registered in `localization/registry.json` with a BCP-47-style code, native display
name, text direction, and optional fallback. Feature code uses semantic translation keys such as
`core.nav.assets`; it must not branch on English, French, or another locale. A new language is
therefore added by registration metadata and catalogs rather than workflow changes.

Catalogs are namespaced JSON files under `localization/<locale>/`. Missing translations follow the
registered fallback and ultimately the default locale. A key missing from the complete fallback
chain is rendered visibly as `⟦namespace.key⟧`, so incomplete controls cannot silently disappear.

The selected locale is a local runtime preference stored in `locale.json` beside the runtime
database. It is intentionally not part of household financial facts. The explicit user preference
wins on subsequent page loads and application restarts.

Templates receive `t`, `current_locale`, `locale_direction`, and `supported_locales` from the
Flask composition root. Pages set HTML `lang` and `dir` from locale metadata. This keeps the
contract open to right-to-left locales even though English and French are the initial catalogs.

Shared navigation, server-rendered pages, primary browser workflows and core help use the
catalog contract. Subsequent feature work must keep ForeView-owned strings, including browser
module messages, in the same contract. Locale-aware date, number, currency, percentage, and
plural formatting belongs in the localization layer; formatting must never mutate stored financial
values or calculation behavior.

Core production locales should have complete core catalogs. Provider/module catalogs may fall back
explicitly, but missing keys should be test-visible. Independently contributed modules should expose
their translations through this same namespace/catalog contract rather than adding language-specific
conditionals.

## HTTP errors and provider workflow presentation

Explicit request validations use stable codes in `localization/*/errors.json`. The HTTP adapter
returns the existing `error` message plus `error_code` and `error_language`, resolved through the
declared fallback chain. Browser request adapters honor that language marker. Diagnostics without
the marker retain their original text and the existing English diagnostic convention. Domain and
repository exceptions are not translated by matching their English text. Owned account, ownership,
income, expense, real-estate, projection and document validation guards attach explicit codes at
their validation boundary. Required request fields and numeric/date conversions also attach codes
without changing their accepted values or the non-HTTP diagnostic contract.
Factual-correction validation now attaches locale-independent codes and interpolation values to
`ValueError`-compatible exceptions. Diagnostic text remains available to non-HTTP callers; the
routes translate typed validation, missing-field, conflict and not-found errors while retaining
their existing HTTP statuses. English/French integration coverage exercises create, edit,
confirmation, removal and stale-write rejection, including unchanged underlying factual records
and original correction reasons. External or uncoded technical diagnostics are not silently
classified by their text.
Expense repository rules attach typed codes while preserving `ValueError`/`LookupError`
compatibility and diagnostic text. JSON and redirected form failures share localized error data
and resolved-language metadata. Required-field errors are attached where request fields are read,
not inferred from arbitrary parser `KeyError`s. Registry detection failures are localized;
built-in tax, pension and Hydro-Québec parser guards use localized errors, while external parser
diagnostics retain their original text. Bilingual expense workflow tests cover
categories, manual records, overlaps, rejected requests and unsupported documents, including
unchanged database bytes after failures and unchanged user-entered evidence/audit notes.

Provider workflow labels reuse the optional per-provider translations and per-field resolver used
by help. Import-help buttons resolve `display_name` and mark the resolved language. Discovery APIs
expose a separate `presentation` object, including `field_languages`, while preserving original
identity, source labels, help text and parser provenance. Providers may translate `display_name`
and `help_text` independently; blank or absent fields fall back without hiding the button. Imported
evidence and preview provenance continue to use the original values, not this presentation object.
For tax and pension help articles, translated `help_text` supplies the full-help body
unless the provider explicitly supplies `body`. Institution `HelpTopic` fields retain their
existing title/body contract. The transaction import dialog resolves those topics independently
and preserves their language-marked content when reopened, rather than flattening them into a
single default-language paragraph. Built-in document-source guidance and institution import-topic
instructions have French translations; untranslated contributed fields retain explicit fallback.

## Validation and acceptance boundary

Production English/French catalogs are checked for matching keys, nonblank string messages and
matching placeholders. Literal template/browser translation references and explicit owned Python
validation codes must resolve in production catalogs. Provider
help is tested for per-field fallback and resolved-language metadata; extension providers are not
required to translate every field before their controls can remain usable.

Locale-navigation integration tests exercise the persisted preference, primary page metadata,
fallback catalogs and unchanged account, dashboard and import-history API values and database
bytes. A synthetic `ar-XB` locale exercises RTL registration and French/English fallback without
feature-specific language branches. Browser DOM tests cover RTL dashboard text, unchanged source
evidence and direction-neutral positioning rules. Shared layout uses logical inline properties so
spacing, alignment, close controls and help positioning follow the document direction.

`tests/test_browser_workflows.py` additionally launches real headless Chromium against a temporary
synthetic Flask runtime. It is included in normal pytest and `make qa`, not an optional manual
gate. Development setup requires Node.js 20 or newer, `npm ci` and `npm run browser-install`
(both included in `make install-dev`). Playwright and Chromium are development-only dependencies; neither is needed
to run ForeView. All PDFs, CSVs and household records in this test are synthetic and disposable.

| Acceptance area | Automated evidence |
| --- | --- |
| English/French interactions | Browser creation/editing of accounts, household setup, T1 PDF preview/save, manual income, expense categories/records, Hydro PDF and bank CSV imports; API validation and correction lifecycle integration tests |
| Preference persistence | Navigation, a fresh browser page, and reconstructed localization service tests |
| Facts and calculations | Exact account and calculated salary-row equality across locale changes; source names, descriptions, amounts and canonical dates preserved through imports |
| Additional/RTL locales | Synthetic registration and fallback; rendered drawer and close-control placement, keyboard focus containment/restoration, Escape, mobile overflow and mixed-language legal text |
| Core completeness | Catalog key/placeholder parity, nonblank values, literal browser/template references and owned validation-code coverage |
| Provider extension contract | Per-field fallback and language metadata, translated help/import labels, unchanged provider identity and original evidence |

The browser gate covers representative primary workflows in Chromium. It does not certify every
browser, assistive technology or possible contributed locale. Operational integrity failures,
third-party exception text, proper names and source evidence remain original diagnostics, not
messages translated by matching arbitrary English strings. Independently mounted HTTP blueprints
without a localization service retain their original default diagnostics.

Proper names, identifiers, imported wording and the authoritative financial disclaimer are not
translation omissions. The full disclaimer retains explicit English language and LTR metadata.

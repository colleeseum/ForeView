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

Initial implementation localizes the shared navigation, language settings workflow, and summary
shell. Subsequent feature work should move remaining ForeView-owned strings, including browser
module messages, into the same contract. Locale-aware date, number, currency, percentage, and
plural formatting belongs in the localization layer; formatting must never mutate stored financial
values or calculation behavior.

Core production locales should have complete core catalogs. Provider/module catalogs may fall back
explicitly, but missing keys should be test-visible. Independently contributed modules should expose
their translations through this same namespace/catalog contract rather than adding language-specific
conditionals.

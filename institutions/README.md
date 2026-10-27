# Institutions

Each financial institution is one module in this directory: a single file or a
package. The application discovers every module here at startup, so adding an
institution needs no change anywhere else.

## Contract

A module must define `provider()` returning an `InstitutionProvider`
(`institution_support/institution_provider.py`):

| Field | Purpose |
|---|---|
| `key`, `display_name`, `aliases` | Identity. Names are matched ignoring case, spaces, and punctuation. |
| `importers` | `DocumentImporter` entries, one per supported document format. |
| `connection` | Optional `ConnectionCapability` for a live connection such as OAuth. Its `create_provider(runtime)` builds the runtime adapter (see `institution_support/connection_provider.py`) from the database and configuration, and `routes` is a Flask blueprint the application registers. |
| `help_topics` | User-facing help; topics keyed `imports` appear on the import help page. |
| `holds_securities` | `True` when accounts hold securities, so uninvested cash is flagged on the dashboard. |
| `statement_sources` | Raw-row source tags whose rows carry the balance printed on the statement. |
| `csv_parser` | Optional parser for institution-specific CSV layouts. Return `None` when a file should fall back to the generic Date/Amount parser. |
| `balance_excluded_sources` | Raw-row source tags excluded from balance reconstruction unless the account balance is known to include them. |
| `balance_including_snapshot_sources` | Snapshot labels proving that excluded rows are included in the account balance. |
| `transaction_repair` | Optional startup repair for rows written by a superseded institution parser. |

Each `HelpTopic` declares a stable key, title, and body. Optional hierarchy metadata consists of
`category` (defaults to `imports`), `parent_topic`, numeric `order`, and `owning_page`. Connection
guides should declare `category="connections"`; statement guides belong to `imports`. The shared
help adapter preserves this metadata, puts unknown categories under `application`, and combines
provider articles with core and document-source help. The browser uses category ancestry for
expansion and search paths, and `order` for article ordering. `parent_topic` is retained metadata,
not a separate article-nesting UI.

A `DocumentImporter` (`institution_support/document_importer.py`) declares:

- `detects(content) -> bool`: recognizes the document from its raw bytes;
- `importer(connection, account_id, filename, content)`: stores it;
- `account_number(content, filename)` and `account_type` (optional): let an import
  find or create its account automatically when the user chooses auto-detect;
- `name`, `document_type`, `help_text`: shown to the user.

Modules load in name order, and the first importer whose `detects` returns true
handles the document. Modules whose names start with `_` are skipped.

## Layout used by the existing institutions

```text
institutions/<name>/
    __init__.py            provider() declaration
    parser.py              detects and normalizes documents; never writes to SQLite
    import_service.py      stores parsed rows through repositories
    document_importers.py  wires the parser and PDF reader to the import service
    raw_sources.py         persisted source tags; never change existing values
```

Import services should reuse `ingestion/` for shared steps: `pdf_page_texts` to
read a PDF, `StatementRowWriter` to store raw rows and transactions with
deduplication, and the helpers in `ingestion/statement_import.py`. Database access
goes through `repositories/`; an institution module must not run SQL itself.

Generic Date/Amount CSV is an application import format rather than an institution.
An institution-specific CSV parser belongs to that institution and may fall back to
the generic parser when its own layout is not detected.

## Localized provider presentation (UX-02D)

Provider identity, parser detection, persisted source labels and original document
text are **not translated**. Providers can optionally declare `translations`
mapping registered locale codes to field dictionaries. The same optional
contract exists on `InstitutionProvider`, `HelpTopic`,
`IncomeSourceProvider`, `TaxNoticeProvider`,
`PublicPensionSourceProvider` and `ExpenseSourceProvider`.
The optional field is appended to each dataclass contract to preserve existing
positional constructor calls.

For help, the shared adapter resolves `title`, `summary` and `body`
independently through `LocalizationService.fallback_chain`. A missing field
falls back to a supported locale (normally `en-CA`), never to an empty
control or a missing-key marker. The API returns `field_languages` so the
browser can mark mixed-language text correctly. The app's core help
navigation, tooltips and explanatory articles live in
`localization/<locale>/help.json`; providers own their wording.
Core articles, category titles and tooltips use the same per-field fallback
chain. Empty or invalid fields do not suppress a usable fallback. Language
metadata describes the resolved field, not merely the selected UI locale.

Example:

```python
HelpTopic(
    key="connection",
    title="Connection guide",
    body="Authorize this login, then synchronize.",
    category="connections",
    translations={
        "fr-CA": {
            "title": "Guide de connexion",
            "body": "Autorisez cet identifiant, puis synchronisez.",
        },
    },
)
```

To add a language, register it in `localization/registry.json` with an
explicit supported fallback and supply the module's optional translations.
The shared adapter does not require language- or provider-specific branches.
The provider is expected to translate every user-facing label, action and
import instruction it owns; incomplete locales are supported for staged
adoption, but should be reported in provider QA. Document source strings,
transaction descriptions and provenance remain in their original language.

The help API, document import guidance, provider discovery presentation and About income,
tax-notice, public-pension, expense and institution module labels consume this contract through
shared presentation adapters. About institution names carry the resolved language and preserve
the original brand when no usable display-name translation exists. Identity and original evidence remain
separate from the localized display fields. Contributed translations can be incomplete and use
the declared per-field fallback; external diagnostics are not translated by matching their text.

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

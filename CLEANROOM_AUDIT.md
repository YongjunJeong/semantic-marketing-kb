# Public-content audit

Reviewed 2026-09-18. Scope: the complete local project, including hidden files, source, tests, documentation, synthetic fixtures, installation artifacts, and generated outputs. This is a content and dependency review, not a certification of authorship or a comparison against an external private corpus. Independent clean-room authorship and synthetic origin are supplied by the owner.

## Findings and remediation

| Category | Finding and disposition |
| --- | --- |
| Real company names / private identifiers | The previous audit's search example itself listed real company names and internal-looking identifiers. Removed that example and unnecessary references to other systems; the identifiers are not repeated here. |
| Customer names and metrics | Fixtures use only fictional `RetailCo` / `TravelCo` and invented percentages. Retained as synthetic evidence and explicitly labelled in README and dataset notes. No real customer data was identified. |
| Canonical descriptions | Names were already scrubbed from main text but remained in aliases; aliases and generated slugs now use the same neutralization. Provenance source IDs intentionally remain. |
| Personal / server paths | Local environment executables and package metadata contained machine-specific paths. The old environment and generated artifacts were removed from the release tree; source and docs contain no literal machine-specific absolute paths. Runtime `Path.resolve()` is path discovery, not a stored server path. |
| Credentials | No credential values, private keys, or populated environment files identified by text inspection and pattern checks. Tokenization helper names are not credentials. |
| URLs | Fixture URLs are all on `example.com`. The only non-fixture public URL in release documentation is the MIT reference at the Open Source Initiative. No private URL identified. |
| HTML / caches / databases | No raw HTML, SQLite, or Chroma database identified. Existing virtual environment, bytecode, pytest cache, editable-install metadata, and stale build snapshots were removed from the release tree. `.gitignore` excludes regenerated artifacts. |
| Prompts / imports | No extraction prompt or cross-repository import identified. Imports are Python standard library, this package, NumPy, PyYAML, pytest, and the optional sentence-transformers backend. |
| Overstated guarantees | Corrected signature-ranking and embedding comments, incomplete merge provenance, and the placeholder split implementation. Documentation now distinguishes an in-memory append-only history from overwritable CLI snapshots. |
| Evaluation | Reran the current 20 explicitly labelled synthetic pairs. No historical result is presented as an independent benchmark. |

## Data boundary

26 records: 25 campaign sources, one operational record. Two fictional vendors; customer values are `RetailCo`, `TravelCo`, or null. Source URLs are never fetched by the default demo. The dataset includes a duplicate publication, cross-vendor equivalents, mechanism variants, and distinct audiences.

Source fixtures and the 52-value taxonomy were reconstructed from the supplied normalized snapshot during the initial inventory. Existing tests and LICENSE became visible on a later inventory and were then reviewed. This audit makes no claim to have recovered the exact original labels or the larger vocabulary mentioned by the previous audit. Current labels, vocabulary, and reconstruction scope are documented in `examples/README.md`.

## Verification

- Full file inventory, including hidden files, and review of all project text.
- Pattern scans for credentials, literal absolute paths, private/local URLs, HTML, database and cache artifacts; findings reviewed rather than treating keyword matches as leaks.
- Parsed every JSONL record; validated fixture vendor/customer allowlists and URL hosts.
- Reviewed Python import roots; no local dependency outside the project.
- Clean editable install, dependency consistency check, 20 passing tests, clean pyflakes output, package/submodule import smoke, and CLI build/search/explain/demo checks.
- Owner-confirmed license: Copyright (c) 2026 Yongjun Jeong. MIT covers the code, documentation, and synthetic fixtures unless otherwise noted; the MIT grant and disclaimer are unchanged.

The default hashing demo runs offline after installation. Optional sentence-transformers may download a model and was not installed or validated. Third-party dependency internals are not part of this project's public source audit.

No Git repository was initialized, no commit or remote was created, and nothing was pushed or published. A future change needs a fresh audit; automated patterns cannot establish independent authorship or recognize every possible confidential term.

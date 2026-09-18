# Portfolio release review

The project is technically prepared for owner review and a later GitHub release. No Git initialization, commit, remote, push, or publication was performed. The owner has confirmed the copyright attribution and MIT coverage of the code, documentation, and synthetic fixtures unless otherwise noted.

## Project summary

An offline reference implementation of vendor-neutral marketing knowledge modeling, structural entity resolution, provenance, and contextual retrieval. Twenty-six fictional source records produce 12 canonical patterns and 25 evidence links. Eight patterns combine evidence from two fictional vendors. There is no LLM extraction or answer generation.

## Files changed or added

| Files | Result |
| --- | --- |
| `README.md` | Problem/solution, Mermaid architecture, design choices, runnable commands, three actual demos, synthetic metrics, explicit limitations |
| `docs/architecture.md` | Record boundaries, taxonomy, exact classifier/scoring behavior, split API example, storage tradeoffs |
| `examples/README.md` | Synthetic origin, reconstruction scope, label counts and limits |
| `examples/source_cases.jsonl`, `taxonomy/axes.yaml` | Restored raw fixtures from normalized local output; 10 axes / 52 observed values, channel groups aligned with existing tests |
| `examples/labelled_pairs.jsonl`, `examples/queries.jsonl` | Explicit current labels with rationales and three reproducible queries |
| `examples/canonical_usecases.jsonl` | Refreshed 12-record canonical snapshot, neutralized aliases and complete merge references |
| `.gitignore`, `pyproject.toml` | Release exclusions, editable install and CLI entry point, runtime/dev extras, existing license reference |
| `src/semantic_marketing_kb/canonicalize.py` | Avoid empty/case-folded URI identity; validate unique IDs and evaluation labels; retain all cluster merge references; rebuild real splits and evidence without mutating the old result; neutralize aliases/slugs |
| `src/semantic_marketing_kb/retrieve.py` | Validate result limits, avoid unknown-group adjacency, preserve relevance order when all similarities are negative |
| `src/semantic_marketing_kb/embed.py`, `models.py`, `normalize.py` | Correct comments about dependencies, IDs, aliases, signatures, optional embedding behavior, and quadratic candidate scaling |
| `tests/test_canonicalize.py`, `tests/test_reference.py` | Update existing split check; add seven regression/integration checks |
| `CLEANROOM_AUDIT.md`, `PORTFOLIO_RELEASE_REVIEW.md` | Current public audit and this review |

Existing retrieval/taxonomy tests were retained. The MIT grant and disclaimer were retained; copyright attribution was updated as explicitly confirmed by the owner. The first inventory exposed only source and generated artifacts; additional original documents and tests became visible later. Fixtures and labels prepared during that interval are documented as reconstructed/current, not silently attributed to an original benchmark.

## Risks found and removed

The previous audit contained unnecessary actual company names and private-looking identifiers in its scan example. Removed them without repeating them in public documentation. Local environment and install artifacts carried machine-specific paths; removed these artifacts from the release tree and excluded future copies. No credential, private URL, raw HTML, database, actual customer metric, extraction prompt, or external repository import was identified in the final project text.

Canonical aliases retained fictional names despite the separation claim; now neutralized. Provenance omitted a merge after its cluster root changed; now complete. The former split function only retired a record; it now creates children, reassigns evidence, and preserves the original result. Documentation does not claim persistent event replay or all-pairs cluster validation.

## Validation results

Validation environment: macOS arm64, Python 3.14.6, NumPy 2.5.3, PyYAML 6.0.3, pytest 9.1.1, pyflakes 3.4.0. Declared Python minimum is 3.10; other interpreters were not tested. The optional sentence-transformers backend was not tested.

| Check | Result |
| --- | --- |
| Fresh virtual environment and `python -m pip install -e .` | Pass |
| `python -m pip install -e '.[dev]'` | Pass |
| `python -m pip check` | Pass |
| `python -m pytest -q` | 20 passed (13 existing checks plus 7 added) |
| `python -m pyflakes src tests` | Clean |
| Import package and every submodule | Pass |
| CLI help, build, three searches, explain, demo | Pass |
| Architecture split example | Pass |
| JSONL parsing, local Markdown links, fixture identity/URL checks | Pass |

The release tree excludes environments and generated build files. Running the README commands regenerates them. Editable checkout installation is the supported distribution; wheel-only fixture packaging is not configured.

## Demo and evaluation

- Cart recovery: four sources / two vendors; discount voucher and browse/booking cases remain separate. Search ranks the discount voucher first and the general cart reminder second.
- Birthday offer: three sources / two vendors. In-app context increases the birthday score from 1.0 to 1.1, moves Win-back Campaign above the email-only voucher, and retains that voucher.
- Back-in-stock: two sources / two vendors. Price-drop Alert is classified as a variant and remains separate.
- Total: 12 patterns, 25 links, 14 merge log entries (one duplicate is recognized by two rules), 21 variant recommendations, four review recommendations.
- Current synthetic benchmark: 20 pairs (13 same-pattern / 4 variant / 3 different), zero false merges, zero false splits, precision 1.0, recall 1.0, weighted error 0.0.

This is a small, curated benchmark with explicit mechanism keys, not a held-out estimate. Pair evaluation only measures merged/separate membership. The hashing baseline supports the demonstrated resolution experiment; it does not demonstrate production-grade dense retrieval. No threshold tuning or large feature addition was undertaken for a better-looking score.

## README message

Heterogeneous terminology can share one knowledge model while source evidence stays separate. Embeddings propose pairs; deterministic identity and structural classification decide merges. False merges deserve a higher cost. Context reranks instead of hard-filtering. Provenance and reversible decisions make the result inspectable. These claims are bounded by the actual synthetic demo and documented storage/algorithm limitations.

## Suggested GitHub metadata

**Repository name:** `semantic-marketing-kb`

**Description:** A vendor-neutral knowledge layer for canonicalizing and retrieving marketing use cases with provenance-aware entity resolution.

**Topics (10):** `entity-resolution`, `knowledge-engineering`, `domain-modeling`, `semantic-search`, `information-retrieval`, `canonicalization`, `data-provenance`, `taxonomy`, `martech`, `python`.

These describe the implemented knowledge and retrieval layer without implying an LLM application or a graph database.

## License status

The MIT LICENSE retains the standard permission, attribution-retention, and warranty-disclaimer structure. The owner confirmed `Copyright (c) 2026 Yongjun Jeong` and the same MIT scope for code, documentation, and synthetic fixtures unless otherwise noted. The [OSI MIT text](https://opensource.org/license/mit) permits modification and redistribution while retaining the copyright and permission notice.

License status: owner-confirmed. Attribution and fixture coverage follow the owner's explicit release instruction. Dependencies retain their own licenses.

## Owner checks before publication

1. Review the explicitly rewritten pair labels and reconstructed 52-value taxonomy; do not present them as the exact historical benchmark/vocabulary.
2. Approve the README, documented limitations, and suggested repository metadata.
3. Request Git initialization and publication separately when ready. The current task stops before those actions.

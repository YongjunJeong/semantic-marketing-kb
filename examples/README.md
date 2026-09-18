# Synthetic fixtures

All records are fictional. `vendor_a` and `vendor_b` represent different publishing styles; `RetailCo` and `TravelCo` are generic fictional customers. URLs use `example.com` and are identifiers, not pages to fetch. Dates and percentage outcomes are invented and demonstrate evidence fields only.

- `source_cases.jsonl`: 26 pre-extracted records: 25 campaign sources and one excluded operational document. One campaign source is a duplicate publication. Text, tags, and mechanism keys are curated inputs, not extraction results.
- `labelled_pairs.jsonl`: 20 manually specified pairs with rationales: 13 same-pattern, 4 variant, 3 different. The evaluator measures merged versus separate membership, not the accuracy of all three labels.
- `queries.jsonl`: three illustrative queries, optional taxonomy context, and expected top-three families. These are smoke checks, not a held-out retrieval benchmark.
- `canonical_usecases.jsonl`: refreshed canonical snapshot from the default hashing run. Reproduce with `smkb build`; the full evidence and merge-log files are generated in `build/`. Snapshot log references require those companion files for inspection.

During release preparation, source records were recovered from the local normalized synthetic snapshot by removing derived normalization and hashes. Taxonomy IDs and aliases were reconstructed from its raw-to-normalized mappings (52 observed values). Channel grouping was reconciled with the existing taxonomy tests. No additional vocabulary coverage is claimed.

The pair file was rewritten explicitly from the described mechanisms; it is not claimed to be the original historical benchmark. Its rationales are inspectable. The perfect score on these curated pairs does not estimate performance on new data or prove absence of false merges outside the labelled set.

The owner has confirmed independent authorship and synthetic origin. Unless otherwise noted, all synthetic fixtures are covered by the same [MIT License](../LICENSE) as the code and documentation. Copyright (c) 2026 Yongjun Jeong.

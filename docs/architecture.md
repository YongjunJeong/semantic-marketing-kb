# Architecture

**English** | [한국어](architecture.ko.md) | [Overview](../README.md)

The pipeline separates three questions: what a source says, which reusable pattern
it describes, and which pattern helps a query. Inputs are prestructured synthetic
records. Crawling, LLM extraction and answer generation are outside the implementation.

## Records and provenance

| Record | Responsibility |
|---|---|
| `SourceCase` | Preserve source ID/URI/native ID/content hash, type, title, summary, mechanism/key, tags, normalized axes and source-specific outcomes |
| `CanonicalUseCase` | Reusable neutral description, union of member axes, primary objective/metric, counts, aliases, status and provenance |
| `EvidenceLink` | Link canonical ID to source ID with relation, method, fixed confidence and timestamp |
| `MergeLogEntry` | Record create/merge/recommend/split operations with input/output IDs, rule, optional scores and notes |

Canonical provenance contains source IDs, representative source and all merge
references within the final cluster, including intermediate union-find roots.
Representative text prefers the first pattern-library source by ID, otherwise the
first source. It is deterministic selection, not generated synthesis. Neutralized
aliases are stored but not searched. Evidence counts include duplicate publications,
not independent observations. Link confidence 1.0/0.8 is a fixed default for merged/
seed links, not a calibrated probability. Outcome values stay with evidence.

## Taxonomy and normalization

[`axes.yaml`](../taxonomy/axes.yaml) defines ten axes and 52 values: industry,
journey_stage, objective, metric, segment, channel, format, trigger, capability and
complexity. Existing IDs, normalized labels and aliases resolve values; unknown
labels remain `unmapped` and appear in coverage results. The first objective and
metric become primary values. A stored signature is diagnostic, not a merge/ranking
feature. Normalization mutates the supplied source objects in memory.

Channel groups are explicit: push/in-app → app, email/SMS → messaging, web → web.
This demo taxonomy is not an industry-wide ontology.

## Canonicalization

1. Reject duplicate source IDs. Use normalized campaign records; operational
   records remain in normalized output but do not receive canonical links.
2. Apply document identity rules: nonempty trimmed URI (case-sensitive), vendor +
   native ID, or content hash. These bypass structural checks and assume trusted
   identifiers. The hash covers supplied text/tags/outcomes, not a crawled page.
3. Encode title, summary and mechanism with normalized hashing vectors. Full cosine
   search proposes up to eight neighbors per source, deduplicates pairs and marks
   mutual neighbors. Cosine proposes candidates; it does not decide identity.
4. Calculate weighted Jaccard: objective 2, trigger 2, segment 1.5, channel 1,
   format 1, journey_stage 0.5. Axes empty on both sides leave the denominator.
5. Process candidates by descending structural score using these ordered rules.

| Condition | Decision |
|---|---|
| Known abandonment segments conflict | `variant` at structural ≥0.25, otherwise `different`; never merge |
| Primary objectives match, triggers overlap, structural ≥0.45 and either a shared nonempty mechanism key or title Jaccard ≥0.5 plus mechanism Jaccard ≥0.3 | `same_pattern`; union |
| Objectives match, triggers overlap and structural ≥0.25 | `variant`; recommendation |
| Mutual neighbors and structural ≥0.25 | `review_required`; recommendation |
| Otherwise | `different`; exclude |

Union-find can join transitive groups without testing every member pair. Identifier
rules can merge structurally conflicting annotations. Segment conflicts cover a
small explicit set, not arbitrary contradictions. Canonical neutrality checks are
deterministic name/number checks, not general factuality/privacy enforcement.

Evaluation validates relation labels/source references and measures final cluster
membership with `3 × false_merges + false_splits`. The weight describes a policy:
false merges mix evidence for different interventions, whereas false splits leave
separate reviewable records. It does not optimize thresholds or classify variants.

## Reversing a merge

`split()` is a Python API, not a CLI command. It requires normalized sources and a
nonempty, disjoint partition covering all members. It returns a new result with an
inactive parent, rebuilt children, reassigned evidence and an appended split event.
The original snapshot and prior events are unchanged.

```python
from semantic_marketing_kb.canonicalize import canonicalize, split
from semantic_marketing_kb.cli import EXAMPLES, load_sources
from semantic_marketing_kb.embed import HashingEmbedder
from semantic_marketing_kb.normalize import normalize_all
from semantic_marketing_kb.taxonomy import Taxonomy

sources = normalize_all(load_sources(EXAMPLES / "source_cases.jsonl"), Taxonomy())
result = canonicalize(sources, HashingEmbedder())
cart = next(u for u in result.usecases if u.id == "uc:abandoned-basket-recovery")
ids = cart.provenance["built_from"]
revised = split(result, cart.id, [ids[:2], ids[2:]],
                sources=sources, note="Illustrative manual partition")
assert revised.merge_log[-1].op == "split"
assert all(link.usecase_id != cart.id for link in revised.links)
assert cart.status == "active"  # original snapshot unchanged
```

This is an illustrative manual partition, not a correction to the demo labels.
Children retain prior provenance plus the split reference. Recommendations remain
historical observations rather than a recomputed queue. A later full build does
not replay manual splits: explicitly save a separate snapshot to retain decisions.
JSONL CLI builds overwrite output; append-only entries within a result do not
provide persistent transactional event storage.

## Retrieval

Active canonical titles, summaries and mechanisms form the index. Query cosine
search selects at most `4 × top_k` candidates. Taxonomy aliases resolve context;
soft boosts rerank results, and the default family cap permits at most two results
per objective/trigger family. `--no-family-cap` removes that cap.

```text
score = cosine / scale
      + channel boost (exact 0.10, adjacent 0.05, other 0)
      + industry match 0.06 + objective match 0.06 + journey-stage match 0.03
scale = highest candidate cosine when positive, otherwise 1.0
```

Scores are query-relative, may be negative or exceed one, and are not probabilities.
Unknown channel groups do not imply adjacency. Context does not reject candidates,
but finite candidate retrieval and family limits still exclude records. `exact`
means channel overlap, not semantic identity or measured query relevance.

Up to three evidence records accompany results. Matching industry, customer-story
records and recorded outcomes have priority; vendor diversity is selected before
remaining slots are filled. Outcomes remain source-specific. The birthday example
reranks lower results with in-app context; the cart query ranks a discount variant
above the generic reminder. Pair evaluation does not validate search ranking.

## Why no graph database

For 26 sources and 12 patterns, JSONL, keyed dictionaries, NumPy search and in-memory
union-find keep decisions reproducible without a service. Evidence retrieval is
an ID join; there is no multi-hop graph query. Candidate matrices require quadratic
space and retrieval scans all active patterns. Approximate indexing is a future
option when corpus size warrants it. Concurrent edits, transaction guarantees and
persistent decision replay would warrant storage work. A graph database should
follow a relationship-traversal requirement, not the presence of linked records.

Future experiments should validate model constraints and held-out entity/retrieval
labels using independent public or synthetic inputs. No private enterprise model,
customer information or unapproved source material belongs in this dataset.

from pathlib import Path

from semantic_marketing_kb.canonicalize import canonicalize
from semantic_marketing_kb.embed import HashingEmbedder
from semantic_marketing_kb.models import SourceCase, read_jsonl
from semantic_marketing_kb.normalize import normalize_all
from semantic_marketing_kb.retrieve import Context, Index
from semantic_marketing_kb.taxonomy import Taxonomy

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


def _index():
    t = Taxonomy()
    cases = normalize_all([SourceCase.from_dict(d) for d in read_jsonl(EXAMPLES / "source_cases.jsonl")], t)
    result = canonicalize(cases, HashingEmbedder())
    return Index(result.usecases, result.links, cases, HashingEmbedder(), t)


def test_example_queries_hit_expected_family_in_top3():
    idx = _index()
    misses = []
    for q in read_jsonl(EXAMPLES / "queries.jsonl"):
        hits = idx.search(q["query"], Context(**q.get("context", {})), top_k=3)
        if q["expect_family"] not in {h["family"] for h in hits}:
            misses.append((q["query"], [h["family"] for h in hits]))
    assert not misses, misses


def test_context_reranks_but_does_not_filter():
    idx = _index()
    # a web-only context should still return email/push plays (demoted to "other", not removed)
    hits = idx.search("remind shoppers about items left in their cart", Context(channels=["web"]), top_k=5, family_cap=0)
    tiers = {h["id"]: h["tier"] for h in hits}
    assert tiers and all(t in ("exact", "adjacent", "other") for t in tiers.values())
    assert any(t == "other" for t in tiers.values())


def test_evidence_carries_vendor_and_outcomes_but_canonical_does_not():
    idx = _index()
    hit = idx.search("remind shoppers about items left in their cart", Context(industry="retail"), top_k=1)[0]
    assert "%" not in hit["summary"] and "vendor" not in hit["summary"].lower()
    assert hit["evidence"] and any(e["outcomes"] for e in hit["evidence"]) and {e["vendor"] for e in hit["evidence"]} >= {"vendor_a", "vendor_b"}


def test_family_cap_limits_near_duplicates():
    idx = _index()
    hits = idx.search("abandonment reminder", Context(), top_k=6, family_cap=1)
    fams = [h["family"] for h in hits]
    assert len(fams) == len(set(fams))

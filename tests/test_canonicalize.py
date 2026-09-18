from pathlib import Path

from semantic_marketing_kb.canonicalize import PairFeatures, canonicalize, evaluate, identity_pairs, split
from semantic_marketing_kb.embed import HashingEmbedder
from semantic_marketing_kb.models import SourceCase, read_jsonl
from semantic_marketing_kb.normalize import normalize_all
from semantic_marketing_kb.taxonomy import Taxonomy

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


def _cases():
    return normalize_all([SourceCase.from_dict(d) for d in read_jsonl(EXAMPLES / "source_cases.jsonl")], Taxonomy())


def _feat(**kw):
    base = dict(a="x", b="y", cosine=0.9, structural=0.9, title_sim=0.9, mechanism_sim=0.9, same_mechanism_key=True, same_objective=True, trigger_overlap=True, segment_conflict=False, mutual_neighbours=True)
    base.update(kw)
    return PairFeatures(**base)


def test_identity_rules_merge_duplicates_only():
    pairs = identity_pairs(_cases())
    assert ("src:vendor_a:a1c0de000001", "src:vendor_a:a1c0de000002", "same_native_id") in pairs
    assert all(r in ("same_uri", "same_native_id", "same_content_hash") for _, _, r in pairs)


def test_cosine_alone_never_decides():
    # very high cosine but no structural agreement → not same
    assert _feat(cosine=0.99, same_objective=False, trigger_overlap=False, structural=0.1, same_mechanism_key=False, title_sim=0.1, mechanism_sim=0.1).decision() == "different"
    # low cosine but full structural agreement → same (cosine only proposed the pair)
    assert _feat(cosine=0.2).decision() == "same_pattern"


def test_false_merge_guards():
    # same trigger and objective, different mechanism, weak title overlap → variant, not merged
    assert _feat(same_mechanism_key=False, title_sim=0.2, mechanism_sim=0.2).decision() == "variant"
    # audience conflict (cart vs browse abandoner) blocks same_pattern even with high structure
    assert _feat(segment_conflict=True).decision() == "variant"


def test_end_to_end_merges_and_recommendations():
    result = canonicalize(_cases(), HashingEmbedder())
    member = {l.source_id: l.usecase_id for l in result.links}
    # same play across vendors is merged
    assert member["src:vendor_a:a1c0de000001"] == member["src:vendor_b:b2d1ef000001"] == member["src:vendor_b:b2d1ef000002"]
    # incentive variant stays separate and is recorded as a recommendation
    assert member["src:vendor_a:a1c0de000001"] != member["src:vendor_b:b2d1ef000003"]
    assert any({r["a"], r["b"]} == {"src:vendor_a:a1c0de000001", "src:vendor_b:b2d1ef000003"} and r["decision"] == "variant" for r in result.recommendations)
    # cart vs browse vs booking abandonment are three canonical records
    assert len({member["src:vendor_a:a1c0de000001"], member["src:vendor_a:a1c0de000003"], member["src:vendor_b:b2d1ef000006"]}) == 3
    # operational document never reaches layer 2
    assert "src:vendor_b:b2d1ef000016" not in member
    assert 8 <= len(result.usecases) <= 15
    ev = evaluate(result, read_jsonl(EXAMPLES / "labelled_pairs.jsonl"))
    assert ev["false_merges"] == 0 and ev["recall"] == 1.0


def test_merge_log_is_append_only_and_reversible():
    result = canonicalize(_cases(), HashingEmbedder())
    n = len(result.merge_log)
    ids = [e.id for e in result.merge_log]
    assert ids == sorted(ids) and len(set(ids)) == n
    uc = next(u for u in result.usecases if u.evidence_count > 1)
    after = split(result, uc.id, [[uc.provenance["built_from"][0]], uc.provenance["built_from"][1:]], sources=_cases())
    assert len(after.merge_log) == n + 1 and after.merge_log[-1].op == "split" and after.merge_log[:n] == result.merge_log[:n]
    assert uc.status == "active"
    assert next(u for u in after.usecases if u.id == uc.id).status.startswith("split_into:")


def test_layer2_text_is_neutral():
    result = canonicalize(_cases(), HashingEmbedder())
    for u in result.usecases:
        text = f"{u.title} {u.summary} {u.mechanism}".lower()
        assert "retailco" not in text and "travelco" not in text and "vendor" not in text and "%" not in text, u.id

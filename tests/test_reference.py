"""Small offline checks for the reference pipeline and its safety boundaries."""
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from semantic_marketing_kb.canonicalize import canonicalize, evaluate, identity_pairs, pair_features, split
from semantic_marketing_kb.cli import build, load_index, load_sources
from semantic_marketing_kb.embed import HashingEmbedder
from semantic_marketing_kb.models import read_jsonl
from semantic_marketing_kb.normalize import normalize_all
from semantic_marketing_kb.retrieve import Context, Index
from semantic_marketing_kb.taxonomy import Taxonomy

ROOT = Path(__file__).resolve().parents[1]


def dataset():
    return normalize_all(load_sources(ROOT / 'examples/source_cases.jsonl'), Taxonomy())


def test_demo_and_provenance(tmp_path):
    summary = build(ROOT / 'examples/source_cases.jsonl', tmp_path)
    assert (summary['sources'], summary['canonical'], summary['links']) == (26, 12, 25)
    assert summary['evaluation'] == dict(pairs=20, precision=1.0, recall=1.0, false_merges=0, false_splits=0, weighted_error=0.0)
    assert summary['needs_neutralization'] == []
    usecases = read_jsonl(tmp_path / 'canonical_usecases.jsonl')
    logs = read_jsonl(tmp_path / 'merge_log.jsonl')
    for uc in usecases:
        members = set(uc['provenance']['built_from'])
        expected = {e['id'] for e in logs if e['op'] == 'merge' and set(e['inputs']) <= members}
        assert expected <= set(uc['provenance']['merge_log_refs'])
        assert not any(name in str([uc['title'], uc['summary'], uc['mechanism'], uc['aliases']]).lower() for name in ['retailco', 'travelco', 'vendor_a', 'vendor_b'])
    counts = {u['id']: u['evidence_count'] for u in usecases}
    assert counts['uc:abandoned-basket-recovery'] == 4
    assert counts['uc:birthday-offer'] == 3
    assert counts['uc:back-in-stock-alert'] == 2
    idx = load_index(tmp_path)
    assert idx.search('birthday offer')[0]['id'] == 'uc:birthday-offer'
    assert idx.search('back in stock alert')[0]['id'] == 'uc:back-in-stock-alert'


def test_structural_identity_and_variant():
    cases = dataset()
    cart, story, voucher = cases[0], cases[2], cases[4]
    assert pair_features(cart, story, 0.0, False).decision() == 'same_pattern'
    assert pair_features(cart, voucher, 1.0, True).decision() == 'variant'
    stock = next(c for c in cases if c.title == 'Back-in-stock Alert')
    price = next(c for c in cases if c.title == 'Price-drop Alert')
    assert pair_features(stock, price, 1.0, True).decision() == 'variant'


def test_identity_missing_and_case_sensitive_uri():
    c = dataset()[0]
    other = replace(c, id='other', native_id=None, content_hash='distinct')
    c = replace(c, native_id=None, uri='')
    assert identity_pairs([c, replace(other, uri='')]) == []
    assert identity_pairs([replace(c, uri='https://example.com/Case'), replace(other, uri='https://example.com/case')]) == []
    assert identity_pairs([replace(c, uri='https://example.com/case'), replace(other, uri='https://example.com/case')])[0][2] == 'same_uri'


def test_split_rebuilds_links_and_preserves_history():
    cases = dataset()
    result = canonicalize(cases, HashingEmbedder())
    uc = next(u for u in result.usecases if u.id == 'uc:abandoned-basket-recovery')
    ids = uc.provenance['built_from']
    before = [e.to_dict() for e in result.merge_log]
    revised = split(result, uc.id, [ids[:2], ids[2:]], sources=cases)
    assert [e.to_dict() for e in revised.merge_log[:-1]] == before
    assert uc.status == 'active'
    children = revised.merge_log[-1].output
    assert len(children) == 2 and len(set(children)) == 2
    assert all(link.usecase_id != uc.id for link in revised.links)
    assert len(revised.links) == len(result.links)
    assert {link.usecase_id for link in revised.links if link.source_id in ids} == set(children)
    assert sum(u.evidence_count for u in revised.usecases if u.id in children) == 4
    idx = Index(revised.usecases, revised.links, cases, HashingEmbedder(), Taxonomy())
    assert uc.id not in {u.id for u in idx.usecases}
    for invalid in [[ids], [ids[:1], ids[:1]], [ids[:1], []], [ids[:1], ['unknown']]]:
        with pytest.raises(ValueError):
            split(result, uc.id, invalid, sources=cases)
    assert [e.to_dict() for e in result.merge_log] == before


def test_soft_context_keeps_candidates():
    cases = dataset()
    result = canonicalize(cases, HashingEmbedder())
    idx = Index(result.usecases, result.links, cases, HashingEmbedder(), Taxonomy())
    base = idx.search('birthday offer', top_k=12, family_cap=0)
    ctx = idx.search('birthday offer', Context(channels=['in-app']), top_k=12, family_cap=0)
    assert {h['id'] for h in base} == {h['id'] for h in ctx}
    assert ctx[0]['score'] == pytest.approx(base[0]['score'] + .1)
    assert any(h['tier'] == 'other' for h in ctx)
    assert any(h['tier'] == 'adjacent' for h in ctx)
    with pytest.raises(ValueError):
        idx.search('cart', top_k=0)
    # Negative cosine must not reverse relevance when all candidates are negative.
    idx.vectors = -np.outer(np.arange(1, len(idx.usecases) + 1), idx.embedder.encode(['birthday offer'])[0])
    hits = idx.search('birthday offer', top_k=12, family_cap=0)
    assert all(h['similarity'] < 0 for h in hits)
    assert all(hits[i]['similarity'] >= hits[i+1]['similarity'] for i in range(len(hits)-1))


def test_taxonomy_and_determinism():
    t = Taxonomy()
    assert t.resolve('objective', 'basket recovery') == t.resolve('objective', 'recover cart')
    assert t.resolve_many('channel', ['email', 'email', 'unlisted']) == (['ch:email'], ['unlisted'])
    assert all(not c.normalized['unmapped'] for c in dataset())
    e = HashingEmbedder()
    assert np.array_equal(e.encode(['cart']), e.encode(['cart']))


def test_invalid_ids_and_evaluation_labels():
    cases = dataset()
    with pytest.raises(ValueError):
        canonicalize([cases[0], cases[0]], HashingEmbedder())
    result = canonicalize(cases, HashingEmbedder())
    for p in [dict(a='missing', b=cases[0].id, relation='different'), dict(a=cases[0].id, b=cases[1].id, relation='typo')]:
        with pytest.raises(ValueError):
            evaluate(result, [p])

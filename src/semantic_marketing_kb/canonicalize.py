"""Canonicalization = entity resolution over normalized SourceCases.

Principles implemented here
- Identity rules are deterministic and few (same URI, same vendor+native id, same content hash). They are the only automatic merges
  that need no structural agreement.
- Embedding kNN proposes candidate pairs. It never decides identity.
- A pair is `same_pattern` only when the structured signals agree: primary objective, trigger overlap, no audience conflict,
  and either an identical mechanism key or agreeing title AND mechanism text.
  variant and review_required are recorded as recommendations; different candidates are discarded.
- False merges are treated as three times as costly as false splits (see evaluate()). Thresholds below are synthetic defaults
  chosen to be explainable, not tuned on any real corpus.
- The merge log is append-only. A merge is reversed by a `split` entry, never by editing history.
"""
from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, replace
from itertools import combinations

from .embed import Embedder, knn
from .models import CanonicalUseCase, EvidenceLink, MergeLogEntry, SourceCase
from .taxonomy import norm

STRUCT_AXES = ("objective", "trigger", "channel", "segment", "format", "journey_stage")
STRUCT_WEIGHTS = {"objective": 2.0, "trigger": 2.0, "segment": 1.5, "channel": 1.0, "format": 1.0, "journey_stage": 0.5}
CANDIDATE_K = 8   # neighbours per record; small corpora need a wider net so variants get *classified*, not just missed
CONFLICTING_SEGMENTS = {"seg:cart_abandoner", "seg:browse_abandoner", "seg:booking_abandoner"}
DEFAULTS = {"struct_same": 0.45, "struct_variant": 0.25, "title_same": 0.5, "mechanism_same": 0.3}
BANNED_IN_CANONICAL = ("vendor a", "vendor b", "retailco", "travelco")   # demo vendors/customers must not leak into layer 2 text


# ---------------------------------------------------------------- similarity signals

def _tokens(s: str) -> set[str]:
    return set(norm(s).split())


def token_jaccard(a: str, b: str) -> float:
    ta, tb = _tokens(a), _tokens(b)
    return len(ta & tb) / len(ta | tb) if ta | tb else 0.0


def structural_similarity(a: SourceCase, b: SourceCase) -> float:
    """Weighted Jaccard over taxonomy axes. Axes carry different weight: objective and trigger say what the play *is*."""
    num = den = 0.0
    for axis in STRUCT_AXES:
        sa, sb = set(a.normalized["axes"].get(axis, [])), set(b.normalized["axes"].get(axis, []))
        if not sa and not sb:
            continue
        w = STRUCT_WEIGHTS[axis]
        num += w * len(sa & sb) / len(sa | sb)
        den += w
    return num / den if den else 0.0


@dataclass
class PairFeatures:
    a: str
    b: str
    cosine: float
    structural: float
    title_sim: float
    mechanism_sim: float
    same_mechanism_key: bool
    same_objective: bool
    trigger_overlap: bool
    segment_conflict: bool
    mutual_neighbours: bool

    def decision(self, t: dict = DEFAULTS) -> str:
        """Classifier. Note what is absent: no cosine threshold. Cosine put the pair on the table; it does not decide."""
        agree = self.same_objective and self.trigger_overlap
        if self.segment_conflict:
            return "variant" if self.structural >= t["struct_variant"] else "different"
        if agree and self.structural >= t["struct_same"] and (self.same_mechanism_key or (self.title_sim >= t["title_same"] and self.mechanism_sim >= t["mechanism_same"])):
            return "same_pattern"
        if agree and self.structural >= t["struct_variant"]:
            return "variant"
        if self.mutual_neighbours and self.structural >= t["struct_variant"]:
            return "review_required"
        return "different"

    def scores(self) -> dict:
        return {"cosine": round(self.cosine, 3), "structural": round(self.structural, 3), "title_sim": round(self.title_sim, 3), "mechanism_sim": round(self.mechanism_sim, 3),
                "same_mechanism_key": self.same_mechanism_key, "same_objective": self.same_objective, "trigger_overlap": self.trigger_overlap, "segment_conflict": self.segment_conflict}


def pair_features(a: SourceCase, b: SourceCase, cosine: float, mutual: bool) -> PairFeatures:
    na, nb = a.normalized["axes"], b.normalized["axes"]
    sa, sb = set(na.get("segment", [])) & CONFLICTING_SEGMENTS, set(nb.get("segment", [])) & CONFLICTING_SEGMENTS
    return PairFeatures(a=a.id, b=b.id, cosine=cosine, structural=structural_similarity(a, b), title_sim=token_jaccard(a.title, b.title),
                        mechanism_sim=token_jaccard(a.mechanism, b.mechanism), same_mechanism_key=norm(a.mechanism_key) == norm(b.mechanism_key) and bool(a.mechanism_key),
                        same_objective=bool(na.get("objective")) and na.get("objective", [None])[:1] == nb.get("objective", [None])[:1],
                        trigger_overlap=bool(set(na.get("trigger", [])) & set(nb.get("trigger", []))), segment_conflict=bool(sa) and bool(sb) and not (sa & sb),
                        mutual_neighbours=mutual)


# ---------------------------------------------------------------- identity rules (deterministic, automatic)

def identity_pairs(cases: list[SourceCase]) -> list[tuple[str, str, str]]:
    """(a, b, rule). Only facts that make two records the *same document* — never similarity."""
    pairs = []
    groups = {"same_uri": defaultdict(list), "same_native_id": defaultdict(list), "same_content_hash": defaultdict(list)}
    for c in cases:
        if c.uri.strip():
            groups["same_uri"][c.uri.strip()].append(c.id)
        if c.native_id:
            groups["same_native_id"][(c.vendor, c.native_id)].append(c.id)
        if c.content_hash:
            groups["same_content_hash"][c.content_hash].append(c.id)
    for rule, g in groups.items():
        for ids in g.values():
            for x, y in combinations(sorted(ids), 2):
                pairs.append((x, y, rule))
    return pairs


class UnionFind:
    def __init__(self, ids):
        self.parent = {i: i for i in ids}

    def find(self, x):
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[rb] = ra

    def clusters(self) -> dict[str, list[str]]:
        out = defaultdict(list)
        for i in self.parent:
            out[self.find(i)].append(i)
        return dict(out)


# ---------------------------------------------------------------- canonical record construction

def slugify(s: str) -> str:
    return re.sub(r"-{2,}", "-", re.sub(r"[^a-z0-9]+", "-", s.lower())).strip("-")


def neutralize_text(text: str, names: list[str]) -> str:
    """Deterministic scrub used when the representative text comes from a customer story: named parties become 'the brand'.
    In a production extractor the neutral title/summary is produced at extraction time; this is the safety net."""
    out = text
    for n in sorted(set(names), key=len, reverse=True):
        if n:
            out = re.sub(re.escape(n), "the brand", out, flags=re.I)
    return out[:1].upper() + out[1:] if out else out


def neutrality_check(text: str) -> list[str]:
    low = text.lower()
    hits = [t for t in BANNED_IN_CANONICAL if t in low]
    hits += re.findall(r"[+\-]?\d+(?:\.\d+)?\s?(?:%|x\b)", low)   # outcome figures belong to evidence, not to the pattern
    return hits


def build_canonical(members: list[SourceCase], log_refs: list[str], used_slugs: set[str]) -> CanonicalUseCase:
    rep = sorted(members, key=lambda c: (c.source_type != "pattern_library", c.id))[0]   # prefer a pattern description as representative text
    axes = {}
    for axis in rep.normalized["axes"]:
        seen = []
        for m in members:
            for v in m.normalized["axes"].get(axis, []):
                if v not in seen:
                    seen.append(v)
        axes[axis] = seen
    names = [m.customer for m in members if m.customer] + [name for m in members for name in (m.vendor, m.vendor.replace("_", " "))]
    base = slugify(neutralize_text(rep.title, names))
    slug, n = base, 2
    while slug in used_slugs:
        slug, n = f"{base}-{n}", n + 1
    used_slugs.add(slug)
    primary_obj = rep.normalized["primary_objective"] or (axes["objective"][0] if axes["objective"] else None)
    family = f"{(primary_obj or 'obj:none').split(':')[1]}-{(axes['trigger'][0] if axes['trigger'] else 'trg:none').split(':')[1]}"
    title, summary, mechanism = (neutralize_text(x, names) for x in (rep.title, rep.summary, rep.mechanism))
    text_issues = neutrality_check(title + " " + summary + " " + mechanism)
    return CanonicalUseCase(id=f"uc:{slug}", family=family, title=title, summary=summary, mechanism=mechanism, axes=axes,
                            primary_objective=primary_obj, primary_metric=rep.normalized["primary_metric"], evidence_count=len(members),
                            vendor_count=len({m.vendor for m in members}), story_count=sum(1 for m in members if m.source_type == "customer_story"),
                            provenance={"built_from": [m.id for m in members], "merge_log_refs": log_refs, "representative": rep.id, "neutrality_issues": text_issues},
                            status="active" if not text_issues else "needs_neutralization", aliases=sorted({neutralize_text(m.title, names) for m in members} - {title}))


# ---------------------------------------------------------------- pipeline

@dataclass
class CanonResult:
    usecases: list[CanonicalUseCase]
    links: list[EvidenceLink]
    merge_log: list[MergeLogEntry]
    recommendations: list[dict]          # candidate pairs that were NOT merged, with decision + scores


def canonicalize(cases: list[SourceCase], embedder: Embedder, thresholds: dict = DEFAULTS, k: int = CANDIDATE_K) -> CanonResult:
    if len({c.id for c in cases}) != len(cases):
        raise ValueError("source IDs must be unique")
    campaign = [c for c in cases if c.is_campaign and c.normalized]
    by_id = {c.id: c for c in campaign}
    log: list[MergeLogEntry] = []

    def add(op, inputs, output, rule, decision=None, scores=None, note=None) -> str:
        e = MergeLogEntry(id=f"ml:{len(log) + 1:06d}", op=op, inputs=inputs, output=output, rule=rule, decision=decision, scores=scores, note=note)
        log.append(e)
        return e.id

    uf = UnionFind([c.id for c in campaign])
    # 1. identity rules → automatic merges
    for a, b, rule in identity_pairs(campaign):
        uf.union(a, b)
        add("merge", [a, b], uf.find(a), rule)
    # 2. embedding kNN → candidate pairs (proposals only)
    vectors = embedder.encode([f"{c.title}. {c.summary} {c.mechanism}" for c in campaign])
    neighbours = knn(vectors, k) if len(campaign) > 1 else [[] for _ in campaign]
    neighbour_sets = [{j for j, _ in nb} for nb in neighbours]
    seen = set()
    features: list[PairFeatures] = []
    for i, nb in enumerate(neighbours):
        for j, cos in nb:
            key = tuple(sorted((i, j)))
            if key in seen:
                continue
            seen.add(key)
            features.append(pair_features(campaign[key[0]], campaign[key[1]], cos, mutual=(j in neighbour_sets[i] and i in neighbour_sets[j])))
    # 3. structural decision → same_pattern merges; everything else is a recommendation
    recommendations = []
    for f in sorted(features, key=lambda f: -f.structural):
        decision = f.decision(thresholds)
        if uf.find(f.a) == uf.find(f.b):
            continue
        if decision == "same_pattern":
            uf.union(f.a, f.b)
            add("merge", [f.a, f.b], uf.find(f.a), "structural:same_pattern", decision, f.scores())
        elif decision != "different":
            ref = add("recommend", [f.a, f.b], None, "structural", decision, f.scores())
            recommendations.append({"a": f.a, "b": f.b, "decision": decision, "merge_log_ref": ref, **f.scores()})
    # 4. canonical records + evidence links
    usecases, links, used = [], [], set()
    for root, ids in sorted(uf.clusters().items()):
        members = [by_id[i] for i in sorted(ids)]
        refs = [e.id for e in log if e.op == "merge" and set(e.inputs) <= set(ids)]
        uc = build_canonical(members, refs, used)
        refs.insert(0, add("create", sorted(ids), uc.id, "cluster" if len(ids) > 1 else "singleton"))
        uc.provenance["merge_log_refs"] = refs
        usecases.append(uc)
        for m in members:
            rule = next((e.rule for e in log if e.op == "merge" and m.id in e.inputs), "seed")
            links.append(EvidenceLink(usecase_id=uc.id, source_id=m.id, relation="implements" if m.source_type == "customer_story" else "describes_pattern",
                                      method=rule, confidence=1.0 if rule != "seed" else 0.8))
    return CanonResult(usecases, links, log, recommendations)


def split(result: CanonResult, usecase_id: str, into: list[list[str]], note: str = "manual split", *, sources: list[SourceCase]) -> CanonResult:
    """Reverse a merge: append a split entry and rebuild the affected canonical records. History is never edited."""
    uc = next(u for u in result.usecases if u.id == usecase_id)
    members = uc.provenance["built_from"]
    flat = [sid for group in into for sid in group]
    if uc.status.startswith("split_into:") or len(into) < 2 or any(not group for group in into) or len(flat) != len(set(flat)) or set(flat) != set(members):
        raise ValueError("split must partition an unsplit record into nonempty, disjoint groups covering every source")
    by_id = {s.id: s for s in sources}
    if any(sid not in by_id or not by_id[sid].normalized for sid in flat):
        raise ValueError("normalized source records are required for every split member")
    log = list(result.merge_log)
    ref = f"ml:{len(log) + 1:06d}"
    used = {u.id.removeprefix("uc:") for u in result.usecases}
    children = [build_canonical([by_id[sid] for sid in sorted(group)], [*uc.provenance["merge_log_refs"], ref], used) for group in into]
    outputs = [child.id for child in children]
    log.append(MergeLogEntry(id=ref, op="split", inputs=[usecase_id], output=outputs, rule="human", note=note))
    usecases = [replace(u, status=f"split_into:{','.join(outputs)}") if u.id == usecase_id else u for u in result.usecases] + children
    assignment = {sid: child.id for child in children for sid in child.provenance["built_from"]}
    links = [replace(link, usecase_id=assignment[link.source_id], method="human:split") if link.usecase_id == usecase_id else link for link in result.links]
    return CanonResult(usecases, links, log, list(result.recommendations))


# ---------------------------------------------------------------- evaluation against labelled pairs

def evaluate(result: CanonResult, labelled_pairs: list[dict], false_merge_weight: float = 3.0) -> dict:
    """labelled_pairs: [{"a", "b", "relation": same_pattern|variant|different}]. A merge is what the pipeline actually did."""
    member_of = {l.source_id: l.usecase_id for l in result.links}
    tp = fm = fs = 0
    for p in labelled_pairs:
        if p["relation"] not in {"same_pattern", "variant", "different"} or p["a"] not in member_of or p["b"] not in member_of:
            raise ValueError("evaluation pairs must reference linked sources and a supported relation")
        merged = member_of.get(p["a"]) is not None and member_of.get(p["a"]) == member_of.get(p["b"])
        if p["relation"] == "same_pattern":
            tp += merged
            fs += not merged
        elif merged:
            fm += 1
    n_same = sum(1 for p in labelled_pairs if p["relation"] == "same_pattern")
    return {"pairs": len(labelled_pairs), "precision": round(tp / (tp + fm), 3) if tp + fm else None, "recall": round(tp / n_same, 3) if n_same else None,
            "false_merges": fm, "false_splits": fs, "weighted_error": false_merge_weight * fm + fs}

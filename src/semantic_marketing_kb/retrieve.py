"""Retrieval: dense candidates → taxonomy-aware soft reranking → family diversity → evidence attachment.

Context (industry, channels, objective, stage) *reranks*; it does not filter. A play on a neighbouring channel is demoted, not removed,
because the evidence for a channel problem often lives on another channel (e.g. web-push opt-in is fixed with an in-app prompt).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .embed import Embedder
from .models import CanonicalUseCase, EvidenceLink, SourceCase
from .taxonomy import Taxonomy

TIER_BOOST = {"exact": 0.10, "adjacent": 0.05, "other": 0.0}
CONTEXT_BOOST = {"industry": 0.06, "objective": 0.06, "journey_stage": 0.03}
FAMILY_CAP = 2


@dataclass
class Context:
    industry: str | None = None
    channels: list[str] = field(default_factory=list)
    objective: str | None = None
    journey_stage: str | None = None

    def resolved(self, t: Taxonomy) -> "Context":
        r = lambda axis, v: (t.resolve(axis, v) or v) if v else v  # noqa: E731
        return Context(industry=r("industry", self.industry), channels=[r("channel", c) for c in self.channels], objective=r("objective", self.objective), journey_stage=r("journey_stage", self.journey_stage))


class Index:
    """In-memory index over canonical records. Small on purpose: the reference implementation shows the *shape* of retrieval."""

    def __init__(self, usecases: list[CanonicalUseCase], links: list[EvidenceLink], sources: list[SourceCase], embedder: Embedder, taxonomy: Taxonomy):
        self.usecases = [u for u in usecases if u.status == "active"]
        self.embedder, self.t = embedder, taxonomy
        self.vectors = embedder.encode([f"{u.title}. {u.summary} {u.mechanism}" for u in self.usecases]) if self.usecases else np.zeros((0, 1))
        self.sources = {s.id: s for s in sources}
        self.links: dict[str, list[EvidenceLink]] = {}
        for l in links:
            self.links.setdefault(l.usecase_id, []).append(l)

    def tier(self, u: CanonicalUseCase, ctx: Context) -> str:
        chans = set(u.axes.get("channel", []))
        active = set(ctx.channels)
        if not active or not chans:
            return "other"
        if chans & active:
            return "exact"
        groups = {self.t.group(c) for c in active} - {None}
        return "adjacent" if any(self.t.group(c) in groups for c in chans) else "other"

    def boosts(self, u: CanonicalUseCase, ctx: Context) -> dict:
        b = {}
        if ctx.industry and ctx.industry in u.axes.get("industry", []):
            b["industry"] = CONTEXT_BOOST["industry"]
        if ctx.objective and ctx.objective in u.axes.get("objective", []):
            b["objective"] = CONTEXT_BOOST["objective"]
        if ctx.journey_stage and ctx.journey_stage in u.axes.get("journey_stage", []):
            b["journey_stage"] = CONTEXT_BOOST["journey_stage"]
        return b

    def evidence(self, u: CanonicalUseCase, ctx: Context, n: int = 3) -> list[dict]:
        rows = []
        for l in self.links.get(u.id, []):
            s = self.sources[l.source_id]
            rows.append({"source_id": s.id, "vendor": s.vendor, "source_type": s.source_type, "customer": s.customer, "title": s.title, "uri": s.uri,
                         "outcomes": s.outcomes, "published_at": s.published_at, "relation": l.relation, "method": l.method,
                         "_rank": (0 if ctx.industry and ctx.industry in s.normalized["axes"].get("industry", []) else 1, 0 if s.source_type == "customer_story" else 1, 0 if s.outcomes else 1)})
        rows.sort(key=lambda r: r["_rank"])
        out, vendors = [], set()
        for r in rows:                       # one per vendor first, then fill
            if r["vendor"] not in vendors:
                out.append(r)
                vendors.add(r["vendor"])
        for r in rows:
            if len(out) >= n:
                break
            if r not in out:
                out.append(r)
        for r in out:
            r.pop("_rank", None)
        return out[:n]

    def search(self, query: str, ctx: Context | None = None, top_k: int = 5, family_cap: int = FAMILY_CAP, include_evidence: bool = True) -> list[dict]:
        if top_k < 1 or family_cap < 0:
            raise ValueError("top_k must be positive and family_cap must be nonnegative")
        ctx = (ctx or Context()).resolved(self.t)
        if not self.usecases:
            return []
        q = self.embedder.encode([query])[0]
        sims = self.vectors @ q
        order = np.argsort(-sims)[: top_k * 4]
        top = float(sims[order[0]]) if sims[order[0]] > 0 else 1.0
        scored = []
        for i in order:
            u = self.usecases[int(i)]
            tier = self.tier(u, ctx)
            b = self.boosts(u, ctx)
            score = float(sims[i]) / top + TIER_BOOST[tier] + sum(b.values())
            scored.append((score, float(sims[i]), tier, b, u))
        scored.sort(key=lambda x: -x[0])
        out, per_family = [], {}
        for score, sim, tier, b, u in scored:
            if family_cap and per_family.get(u.family, 0) >= family_cap:
                continue
            per_family[u.family] = per_family.get(u.family, 0) + 1
            hit = {"id": u.id, "title": u.title, "family": u.family, "summary": u.summary, "mechanism": u.mechanism, "axes": u.axes, "score": round(score, 4),
                   "similarity": round(sim, 4), "tier": tier, "boosts": b, "evidence_count": u.evidence_count, "vendor_count": u.vendor_count}
            if include_evidence:
                hit["evidence"] = self.evidence(u, ctx)
            out.append(hit)
            if len(out) >= top_k:
                break
        return out

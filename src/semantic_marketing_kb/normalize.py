"""Normalization: raw vendor labels → taxonomy ids, plus a deterministic signature used as a *weak* identity hint.

The signature (primary objective | triggers | mechanism_key) is deliberately NOT an identity rule: two of its parts come from an
extraction step that may be model-generated. It is stored for inspection; this implementation does not use it for ranking or merging.
"""
from __future__ import annotations

from .models import SourceCase
from .taxonomy import AXES, Taxonomy


def normalize(case: SourceCase, taxonomy: Taxonomy) -> SourceCase:
    axes, unmapped = {}, {}
    for axis in AXES:
        ids, missing = taxonomy.resolve_many(axis, case.tags.get(axis, []))
        axes[axis] = ids
        if missing:
            unmapped[axis] = missing
    primary_objective = axes["objective"][0] if axes["objective"] else None
    signature = f"{primary_objective}|{','.join(sorted(axes['trigger']))}|{case.mechanism_key.strip().lower()}" if case.is_campaign and case.mechanism_key else None
    case.normalized = {"axes": axes, "unmapped": unmapped, "primary_objective": primary_objective,
                       "primary_metric": axes["metric"][0] if axes["metric"] else None, "signature": signature, "taxonomy_version": taxonomy.version}
    return case


def normalize_all(cases: list[SourceCase], taxonomy: Taxonomy) -> list[SourceCase]:
    return [normalize(c, taxonomy) for c in cases]

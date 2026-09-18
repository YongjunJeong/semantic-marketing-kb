"""Record types. Plain dataclasses with JSON round-trip; no ORM, no hidden state."""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def content_hash(*parts: Any) -> str:
    return "sha256:" + hashlib.sha256(json.dumps(parts, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:24]


@dataclass
class SourceCase:
    """Layer 1. One source document = one record. Vendor and customer names are kept here on purpose."""

    id: str                              # caller-supplied stable ID; demo uses src:<vendor>:<12 hex>
    vendor: str                          # publisher of the document
    source_type: str                     # pattern_library | customer_story | playbook
    uri: str                             # where it came from (synthetic URIs in the demo)
    title: str
    summary: str                         # neutral one-line description of the play (as extracted from the source)
    mechanism: str                       # neutral description of how it works
    mechanism_key: str                   # short slug naming the core mechanism, e.g. "timed-reminder-after-cart-add"
    is_campaign: bool = True             # False for operational/analytics documents; those never reach layer 2
    native_id: str | None = None
    customer: str | None = None          # customer named in a story (stays in layer 1)
    tags: dict[str, list[str]] = field(default_factory=dict)      # raw vendor labels per axis, before normalization
    outcomes: list[dict] = field(default_factory=list)            # [{"value": "+18%", "label": "checkout completion"}]
    published_at: str | None = None
    content_hash: str = ""
    normalized: dict | None = None       # filled by normalize(): {"axes": {axis: [ids]}, "unmapped": {axis: [labels]}, "signature": str}

    def __post_init__(self) -> None:
        if not self.content_hash:
            self.content_hash = content_hash(self.title, self.summary, self.mechanism, self.tags, self.outcomes)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "SourceCase":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class CanonicalUseCase:
    """Layer 2. One marketing pattern, described without vendor, product or customer names and without outcome figures."""

    id: str                              # uc:<slug>
    family: str                          # coarse grouping for diversity, e.g. "abandonment-recovery"
    title: str
    summary: str
    mechanism: str
    axes: dict[str, list[str]]           # taxonomy ids per axis (union over member sources)
    primary_objective: str | None
    primary_metric: str | None
    evidence_count: int
    vendor_count: int
    story_count: int
    provenance: dict                     # {"built_from": [src ids], "merge_log_refs": [ml ids], "representative": src id}
    status: str = "active"
    aliases: list[str] = field(default_factory=list)   # neutralized source titles; not used in retrieval

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "CanonicalUseCase":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class EvidenceLink:
    """Layer 2 → layer 1. The only path by which vendor/customer/outcome facts reach a search result."""

    usecase_id: str
    source_id: str
    relation: str                        # describes_pattern | implements
    method: str                          # identity rule name, "same_pattern", or "seed"
    confidence: float
    added_at: str = field(default_factory=now_iso)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class MergeLogEntry:
    """Append-only. Every create/merge/recommend is written; a merge is undone by a later split entry, never by deletion."""

    id: str                              # ml:000001
    op: str                              # create | merge | recommend | split
    inputs: list[str]
    output: str | list[str] | None
    rule: str                            # which rule or classifier branch produced it
    decision: str | None = None          # same_pattern | variant | different | review_required
    scores: dict | None = None
    note: str | None = None
    at: str = field(default_factory=now_iso)

    def to_dict(self) -> dict:
        return asdict(self)


def read_jsonl(path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def write_jsonl(rows: list[dict], path) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

"""Taxonomy loader and label resolver.

Resolution is deterministic (id → exact, else normalized alias/label match). Unknown labels are returned separately, never silently
dropped: a vocabulary that hides its gaps cannot be improved.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

DEFAULT_PATH = Path(__file__).resolve().parents[2] / "taxonomy" / "axes.yaml"
AXES = ["industry", "journey_stage", "objective", "metric", "segment", "channel", "format", "trigger", "capability", "complexity"]


def norm(label: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", (label or "").lower())).strip()


@dataclass
class Axis:
    name: str
    prefix: str
    values: dict[str, dict]      # id → entry
    index: dict[str, str]        # normalized label/alias/id-tail → id

    def label(self, id_: str) -> str:
        return self.values.get(id_, {}).get("label", id_)

    def ids(self) -> list[str]:
        return list(self.values)


class Taxonomy:
    def __init__(self, path: Path | str = DEFAULT_PATH):
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        self.version = data.get("version", 0)
        self.axes: dict[str, Axis] = {}
        for name, spec in data["axes"].items():
            values, index = {}, {}
            for entry in spec["values"]:
                values[entry["id"]] = entry
                keys = [entry["id"], entry["id"].split(":", 1)[1].replace("_", " "), entry.get("label", "")] + list(entry.get("aliases", []))
                for k in keys:
                    index.setdefault(norm(k), entry["id"])
            self.axes[name] = Axis(name, spec["prefix"], values, index)

    def resolve(self, axis: str, label: str) -> str | None:
        a = self.axes[axis]
        if label in a.values:
            return label
        return a.index.get(norm(label))

    def resolve_many(self, axis: str, labels: list[str]) -> tuple[list[str], list[str]]:
        """(resolved ids in order, unmapped labels). Duplicates removed, unknowns preserved."""
        ids, unmapped = [], []
        for label in labels or []:
            r = self.resolve(axis, label)
            if r and r not in ids:
                ids.append(r)
            elif not r and label not in unmapped:
                unmapped.append(label)
        return ids, unmapped

    def group(self, channel_id: str) -> str | None:
        return self.axes["channel"].values.get(channel_id, {}).get("group")

    def coverage(self, records: list[dict]) -> dict:
        """How much of the raw vocabulary the taxonomy covers, per axis. Input: normalized SourceCase dicts."""
        out = {}
        for axis in AXES:
            mapped = sum(len((r.get("normalized") or {}).get("axes", {}).get(axis, [])) for r in records)
            unmapped = [u for r in records for u in (r.get("normalized") or {}).get("unmapped", {}).get(axis, [])]
            out[axis] = {"mapped": mapped, "unmapped": len(unmapped), "unmapped_labels": sorted(set(unmapped))}
        return out

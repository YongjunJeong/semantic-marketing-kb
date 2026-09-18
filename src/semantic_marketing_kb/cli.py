"""smkb — build the demo KB from synthetic sources, search it, explain a canonical record, run the end-to-end demo."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .canonicalize import canonicalize, evaluate
from .embed import get_embedder
from .models import CanonicalUseCase, EvidenceLink, SourceCase, read_jsonl, write_jsonl
from .normalize import normalize_all
from .retrieve import Context, Index
from .taxonomy import Taxonomy

ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = ROOT / "examples"


def load_sources(path: Path) -> list[SourceCase]:
    return [SourceCase.from_dict(d) for d in read_jsonl(path)]


def build(sources_path: Path, out: Path, embedder_kind: str = "hashing", taxonomy_path: Path | None = None) -> dict:
    t = Taxonomy(taxonomy_path) if taxonomy_path else Taxonomy()
    cases = normalize_all(load_sources(sources_path), t)
    result = canonicalize(cases, get_embedder(embedder_kind))
    out.mkdir(parents=True, exist_ok=True)
    write_jsonl([c.to_dict() for c in cases], out / "source_cases.normalized.jsonl")
    write_jsonl([u.to_dict() for u in result.usecases], out / "canonical_usecases.jsonl")
    write_jsonl([l.to_dict() for l in result.links], out / "evidence_links.jsonl")
    write_jsonl([e.to_dict() for e in result.merge_log], out / "merge_log.jsonl")
    write_jsonl(result.recommendations, out / "recommendations.jsonl")
    summary = {"sources": len(cases), "campaign_sources": sum(1 for c in cases if c.is_campaign), "canonical": len(result.usecases),
               "multi_source": sum(1 for u in result.usecases if u.evidence_count > 1), "cross_vendor": sum(1 for u in result.usecases if u.vendor_count > 1),
               "links": len(result.links), "merges": sum(1 for e in result.merge_log if e.op == "merge"),
               "recommendations": {d: sum(1 for r in result.recommendations if r["decision"] == d) for d in ("variant", "review_required")},
               "needs_neutralization": [u.id for u in result.usecases if u.status != "active"], "coverage": t.coverage([c.to_dict() for c in cases])}
    labelled = EXAMPLES / "labelled_pairs.jsonl"
    if sources_path.resolve() == (EXAMPLES / "source_cases.jsonl").resolve() and labelled.exists():
        summary["evaluation"] = evaluate(result, read_jsonl(labelled))
    (out / "build_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    return summary


def load_index(build_dir: Path, embedder_kind: str = "hashing") -> Index:
    t = Taxonomy()
    usecases = [CanonicalUseCase.from_dict(d) for d in read_jsonl(build_dir / "canonical_usecases.jsonl")]
    links = [EvidenceLink(**d) for d in read_jsonl(build_dir / "evidence_links.jsonl")]
    sources = [SourceCase.from_dict(d) for d in read_jsonl(build_dir / "source_cases.normalized.jsonl")]
    return Index(usecases, links, sources, get_embedder(embedder_kind), t)


def render(hit: dict) -> str:
    ax = hit["axes"]
    lines = [f"[{hit['tier']}] {hit['title']}  score={hit['score']} sim={hit['similarity']} ({hit['id']})", f"   {hit['summary']}",
             f"   channels={[c[3:] for c in ax.get('channel', [])]} triggers={[t[4:] for t in ax.get('trigger', [])]} objective={(ax.get('objective') or [''])[0]} sources={hit['evidence_count']}/{hit['vendor_count']} vendors"]
    for e in hit.get("evidence", []):
        oc = "; ".join(f"{o['value']} {o['label']}" for o in e.get("outcomes", [])[:2])
        lines.append(f"   - {e['vendor']} {e['source_type']}{' · ' + e['customer'] if e.get('customer') else ''}: {e['title']}{' — ' + oc if oc else ''}  <{e['uri']}>")
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="smkb")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build", help="normalize + canonicalize sources into a build directory")
    b.add_argument("--sources", type=Path, default=EXAMPLES / "source_cases.jsonl")
    b.add_argument("--out", type=Path, default=ROOT / "build")
    b.add_argument("--embedder", default="hashing", choices=["hashing", "st"])
    s = sub.add_parser("search", help="search canonical use cases with optional context")
    s.add_argument("query")
    s.add_argument("--build", type=Path, default=ROOT / "build")
    s.add_argument("--industry")
    s.add_argument("--channels", help="comma separated, e.g. email,push")
    s.add_argument("--objective")
    s.add_argument("--stage")
    s.add_argument("--k", type=int, default=5)
    s.add_argument("--no-family-cap", action="store_true")
    s.add_argument("--json", action="store_true")
    s.add_argument("--embedder", default="hashing", choices=["hashing", "st"])
    e = sub.add_parser("explain", help="show a canonical record with its merge history and evidence")
    e.add_argument("id")
    e.add_argument("--build", type=Path, default=ROOT / "build")
    d = sub.add_parser("demo", help="build from examples/, run examples/queries.jsonl, print results")
    d.add_argument("--out", type=Path, default=ROOT / "build")
    args = ap.parse_args(argv)

    if args.cmd == "build":
        print(json.dumps(build(args.sources, args.out, args.embedder), ensure_ascii=False, indent=1))
    elif args.cmd == "search":
        idx = load_index(args.build, args.embedder)
        ctx = Context(industry=args.industry, channels=[c.strip() for c in args.channels.split(",")] if args.channels else [], objective=args.objective, journey_stage=args.stage)
        hits = idx.search(args.query, ctx, top_k=args.k, family_cap=0 if args.no_family_cap else 2)
        print(json.dumps(hits, ensure_ascii=False, indent=1) if args.json else "\n".join(render(h) for h in hits))
    elif args.cmd == "explain":
        ucs = {d["id"]: d for d in read_jsonl(args.build / "canonical_usecases.jsonl")}
        u = ucs.get(args.id)
        if not u:
            print("not found", file=sys.stderr)
            return 1
        log = {e["id"]: e for e in read_jsonl(args.build / "merge_log.jsonl")}
        links = [l for l in read_jsonl(args.build / "evidence_links.jsonl") if l["usecase_id"] == args.id]
        print(json.dumps({"usecase": u, "merge_history": [log[r] for r in u["provenance"]["merge_log_refs"] if r in log], "evidence_links": links}, ensure_ascii=False, indent=1))
    elif args.cmd == "demo":
        summary = build(EXAMPLES / "source_cases.jsonl", args.out)
        print(f"built: {summary['sources']} sources → {summary['canonical']} canonical ({summary['multi_source']} multi-source, {summary['cross_vendor']} cross-vendor), "
              f"{summary['merges']} merges, recommendations {summary['recommendations']}, evaluation {summary.get('evaluation')}")
        idx = load_index(args.out)
        for q in read_jsonl(EXAMPLES / "queries.jsonl"):
            ctx = Context(**q.get("context", {}))
            hits = idx.search(q["query"], ctx, top_k=3)
            print(f"\n### {q['query']}  {q.get('context', {})}")
            for h in hits:
                print(render(h))
    return 0


if __name__ == "__main__":
    sys.exit(main())

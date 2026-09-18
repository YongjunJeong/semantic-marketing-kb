"""semantic-marketing-kb — reference implementation.

Three layers: SourceCase (evidence, provenance kept) → CanonicalUseCase (vendor-neutral pattern) → EvidenceLink (which sources back which pattern).
Embeddings generate candidates; identity is decided by structural signals; every merge is logged and reversible.
"""

__version__ = "0.1.0"

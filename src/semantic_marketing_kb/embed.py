"""Embedders. The default is a deterministic hashing embedder so the whole demo runs offline with no model download;
a sentence-transformers backend can be plugged in for real corpora. Either way, embeddings only *propose* neighbours.
"""
from __future__ import annotations

import hashlib
import re
from typing import Protocol

import numpy as np


class Embedder(Protocol):
    name: str
    def encode(self, texts: list[str]) -> np.ndarray: ...


def _tokens(text: str) -> list[str]:
    words = re.findall(r"[a-z0-9]+", text.lower())
    grams = []
    for w in words:
        padded = f"#{w}#"
        grams += [padded[i:i + 3] for i in range(len(padded) - 2)]
    return words + grams


class HashingEmbedder:
    """Word + character-trigram hashing into a fixed-size vector, L2 normalised. Deterministic; uses NumPy."""

    name = "hashing-512"

    def __init__(self, dim: int = 512):
        self.dim = dim

    def encode(self, texts: list[str]) -> np.ndarray:
        out = np.zeros((len(texts), self.dim), dtype=np.float32)
        for i, t in enumerate(texts):
            for tok in _tokens(t):
                h = hashlib.blake2b(tok.encode("utf-8"), digest_size=8).digest()
                idx = int.from_bytes(h[:4], "little") % self.dim
                sign = 1.0 if h[4] & 1 else -1.0
                out[i, idx] += sign
            n = np.linalg.norm(out[i])
            if n:
                out[i] /= n
        return out


class SentenceTransformerEmbedder:
    """Optional experimental backend; uses a passage prefix for all texts, including queries."""

    name = "sentence-transformers"

    def __init__(self, model_name: str = "intfloat/multilingual-e5-small", prefix: str = "passage: "):
        from sentence_transformers import SentenceTransformer  # lazy import
        self.model = SentenceTransformer(model_name, device="cpu")
        self.prefix = prefix

    def encode(self, texts: list[str]) -> np.ndarray:
        return np.asarray(self.model.encode([self.prefix + t for t in texts], normalize_embeddings=True))


def get_embedder(kind: str = "hashing") -> Embedder:
    if kind == "hashing":
        return HashingEmbedder()
    if kind == "st":
        return SentenceTransformerEmbedder()
    raise ValueError(f"unknown embedder: {kind}")


def knn(vectors: np.ndarray, k: int) -> list[list[tuple[int, float]]]:
    """For each row, the k nearest other rows as (index, cosine)."""
    # ponytail: quadratic similarity matrix; use an approximate index when the corpus outgrows memory.
    sims = vectors @ vectors.T
    out = []
    for i in range(len(vectors)):
        order = np.argsort(-sims[i])
        out.append([(int(j), float(sims[i, j])) for j in order if j != i][:k])
    return out

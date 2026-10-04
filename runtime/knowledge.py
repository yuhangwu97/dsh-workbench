"""Provider-neutral knowledge ingestion and citation-aware retrieval.

The default provider is deterministic and dependency-free so the reference
service works offline. Deployments can pass an embedding callable to use a
hosted model without changing the stored chunk/citation shape.
"""
from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass
from typing import Callable, Iterable

TOKEN_RE = re.compile(r"[\w\u4e00-\u9fff]+", re.UNICODE)


def _tokens(value: str) -> list[str]:
    return [item.lower() for item in TOKEN_RE.findall(value or "")]


def hash_embedding(text: str, dimensions: int = 64) -> list[float]:
    """Return a stable local embedding for demos and tests.

    It is intentionally not presented as a semantic model. Its purpose is to
    make ingestion/search/citation behavior executable without a provider.
    """
    vector = [0.0] * dimensions
    for token in _tokens(text):
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % dimensions
        sign = 1.0 if digest[4] & 1 else -1.0
        vector[index] += sign * (1.0 + (digest[5] / 255.0))
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [round(value / norm, 8) for value in vector]


def cosine_similarity(left: Iterable[float], right: Iterable[float]) -> float:
    a, b = list(left), list(right)
    if len(a) != len(b) or not a:
        return 0.0
    return sum(x * y for x, y in zip(a, b))


def split_text(text: str, *, chunk_size: int = 900, overlap: int = 120) -> list[dict]:
    """Split plain text into stable, line-aware chunks."""
    normalized = "\n".join(line.rstrip() for line in (text or "").splitlines()).strip()
    if not normalized:
        return []
    chunks: list[dict] = []
    start = 0
    index = 0
    while start < len(normalized):
        end = min(len(normalized), start + max(chunk_size, 120))
        if end < len(normalized):
            boundary = normalized.rfind("\n", start + 240, end)
            if boundary > start:
                end = boundary
        body = normalized[start:end].strip()
        if body:
            chunks.append({"index": index, "text": body, "start": start, "end": end})
            index += 1
        if end >= len(normalized):
            break
        start = max(end - max(overlap, 0), start + 1)
    return chunks


@dataclass(slots=True)
class KnowledgeIndex:
    embed: Callable[[str], list[float]] = hash_embedding

    def ingest(self, source: dict, text: str) -> list[dict]:
        chunks = []
        for item in split_text(text):
            chunk_id = f"{source['id']}:chunk-{item['index'] + 1:04d}"
            chunks.append({
                "id": chunk_id,
                "source_id": source.get("source_id", source["id"]),
                "document_id": source["id"],
                "pack_id": source.get("pack_id", ""),
                "chunk_index": item["index"],
                "text": item["text"],
                "char_start": item["start"],
                "char_end": item["end"],
                "embedding": self.embed(item["text"]),
            })
        return chunks

    def search(self, chunks: Iterable[dict], query: str, *, pack_id: str | None = None, top_k: int = 5) -> list[dict]:
        query_tokens = set(_tokens(query))
        query_vector = self.embed(query)
        ranked = []
        for chunk in chunks:
            if pack_id and chunk.get("pack_id") != pack_id:
                continue
            lexical = len(query_tokens.intersection(_tokens(chunk.get("text", "")))) / max(len(query_tokens), 1)
            semantic = cosine_similarity(query_vector, chunk.get("embedding", []))
            score = max(0.0, min(1.0, 0.55 * semantic + 0.45 * lexical))
            ranked.append((score, chunk))
        ranked.sort(key=lambda item: (item[0], item[1].get("chunk_index", 0)), reverse=True)
        return [{**chunk, "score": round(score, 4)} for score, chunk in ranked[: max(1, min(top_k, 100))]]

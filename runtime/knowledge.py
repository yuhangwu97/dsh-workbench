"""Provider-neutral knowledge ingestion and citation-aware retrieval.

The default provider is deterministic and dependency-free so the reference
service works offline. Deployments can pass an embedding callable to use a
hosted model without changing the stored chunk/citation shape.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import urllib.request
from dataclasses import dataclass, field
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


class RemoteEmbeddingProvider:
    """OpenAI-compatible embedding endpoint with an explicit model name."""

    def __init__(self, endpoint: str, *, api_key: str = "", model: str = "", timeout: float = 15.0) -> None:
        self.endpoint = endpoint
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.name = f"remote:{model or 'default'}"

    def __call__(self, text: str) -> list[float]:
        payload = {"input": [text]}
        if self.model:
            payload["model"] = self.model
        request = urllib.request.Request(self.endpoint, data=json.dumps(payload).encode(), method="POST", headers={"Content-Type": "application/json", **({"Authorization": f"Bearer {self.api_key}"} if self.api_key else {})})
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            body = json.loads(response.read())
        data = body.get("data", body.get("embeddings", []))
        if not isinstance(data, list) or not data:
            raise ValueError("embedding provider returned no vectors")
        vector = data[0].get("embedding") if isinstance(data[0], dict) else data[0]
        if not isinstance(vector, list) or not vector:
            raise ValueError("embedding provider returned an invalid vector")
        return [float(value) for value in vector]


class RemoteRerankProvider:
    """Optional Cohere-compatible rerank endpoint."""

    def __init__(self, endpoint: str, *, api_key: str = "", model: str = "", timeout: float = 15.0) -> None:
        self.endpoint = endpoint
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.name = f"remote:{model or 'default'}"

    def __call__(self, query: str, documents: list[str], top_k: int) -> list[tuple[int, float]]:
        payload = {"query": query, "documents": documents, "top_n": top_k}
        if self.model:
            payload["model"] = self.model
        request = urllib.request.Request(self.endpoint, data=json.dumps(payload).encode(), method="POST", headers={"Content-Type": "application/json", **({"Authorization": f"Bearer {self.api_key}"} if self.api_key else {})})
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            body = json.loads(response.read())
        results = body.get("results", [])
        return [(int(item.get("index", 0)), float(item.get("relevance_score", item.get("score", 0)))) for item in results if isinstance(item, dict)]


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
    rerank: Callable[[str, list[str], int], list[tuple[int, float]]] | None = None
    provider_name: str = "local-hash-v1"
    rerank_name: str | None = None

    @classmethod
    def from_env(cls) -> "KnowledgeIndex":
        endpoint = os.getenv("WORKBENCH_EMBEDDING_ENDPOINT", "").strip()
        if not endpoint:
            return cls()
        provider = RemoteEmbeddingProvider(endpoint, api_key=os.getenv("WORKBENCH_EMBEDDING_API_KEY", ""), model=os.getenv("WORKBENCH_EMBEDDING_MODEL", ""))
        rerank_endpoint = os.getenv("WORKBENCH_RERANK_ENDPOINT", "").strip()
        rerank = None
        rerank_name = None
        if rerank_endpoint:
            rerank_provider = RemoteRerankProvider(rerank_endpoint, api_key=os.getenv("WORKBENCH_RERANK_API_KEY", os.getenv("WORKBENCH_EMBEDDING_API_KEY", "")), model=os.getenv("WORKBENCH_RERANK_MODEL", ""))
            rerank, rerank_name = rerank_provider, rerank_provider.name
        return cls(embed=provider, rerank=rerank, provider_name=provider.name, rerank_name=rerank_name)

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
        candidates = ranked[: max(1, min(top_k * 3, 100))]
        if self.rerank and candidates:
            reranked = self.rerank(query, [chunk.get("text", "") for _, chunk in candidates], min(top_k, len(candidates)))
            by_index = {index: (score, candidates[index][1]) for index, score in reranked if 0 <= index < len(candidates)}
            if by_index:
                return [{**chunk, "score": round(score, 4), "reranked": True} for _, (score, chunk) in sorted(by_index.items(), key=lambda item: item[1][0], reverse=True)[:max(1, min(top_k, 100))]]
        return [{**chunk, "score": round(score, 4), "reranked": False} for score, chunk in candidates[:max(1, min(top_k, 100))]]

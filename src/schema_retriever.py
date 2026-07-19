"""
Schema-slice retrieval for the chat assistant.

Given a user question, return the handful of catalog tables (see
src/schema_catalog.py) most likely needed to answer it. This is the one
place "RAG" applies in this app — retrieving SCHEMA documents, never rows.

Two interchangeable backends:

- EmbeddingRetriever: OpenAI embeddings over the rendered table docs,
  cosine similarity in-memory (74 tiny documents — no vector DB needed).
- KeywordRetriever: dependency-free lexical scorer. Used automatically when
  no OPENAI_API_KEY is configured (and by tests); also the fallback if the
  embedding call fails at startup.

Both always include the shared master tables needed for joins/lookups.
"""
import math
import os
import re
from collections import Counter
from typing import Dict, List

from src.schema_catalog import build_catalog, render_table_doc

# Masters that generated SQL almost always needs for joins or name lookups.
ALWAYS_INCLUDE = ("CLIENT_MASTER", "RM_MASTER", "CLIENT_RM_MAPPING", "PRODUCT_MASTER")

DEFAULT_K = 8

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> List[str]:
    # Naive singular fold ("loans" -> "loan") so plural/singular phrasing
    # matches the singular-ish identifiers in the schema.
    return [t[:-1] if len(t) > 3 and t.endswith("s") else t
            for t in _TOKEN_RE.findall(text.lower())]


class KeywordRetriever:
    """TF-IDF-flavoured lexical match of question tokens against table docs."""

    def __init__(self):
        self._docs = list(build_catalog())
        self._doc_tokens: List[Counter] = []
        df: Counter = Counter()
        for doc in self._docs:
            # Table/column identifiers count double: "loan" should pull
            # ASSET_LOAN_DETAILS ahead of tables that merely mention loans.
            names = _tokens(doc["table"]) * 2
            for c in doc["columns"]:
                names += _tokens(c["name"]) * 2 + _tokens(c["comment"])
            names += _tokens(doc["description"]) + _tokens(doc["domain"])
            counts = Counter(names)
            self._doc_tokens.append(counts)
            df.update(counts.keys())
        n_docs = len(self._docs)
        self._idf = {t: math.log(1 + n_docs / (1 + f)) for t, f in df.items()}

    def retrieve(self, question: str, k: int = DEFAULT_K) -> List[Dict]:
        q_tokens = set(_tokens(question))
        scored = []
        for doc, counts in zip(self._docs, self._doc_tokens):
            score = sum(
                (1 + math.log(counts[t])) * self._idf.get(t, 0.0)
                for t in q_tokens if t in counts
            )
            scored.append((score, doc))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        picked = [doc for score, doc in scored[:k] if score > 0]
        return _with_masters(picked)


class EmbeddingRetriever:
    """OpenAI-embedding cosine retrieval over the rendered table docs."""

    def __init__(self, model: str = "text-embedding-3-small"):
        from langchain_openai import OpenAIEmbeddings  # requires OPENAI_API_KEY

        self._docs = list(build_catalog())
        self._embedder = OpenAIEmbeddings(model=model)
        texts = [render_table_doc(doc) for doc in self._docs]
        self._vectors = self._embedder.embed_documents(texts)

    def retrieve(self, question: str, k: int = DEFAULT_K) -> List[Dict]:
        q_vec = self._embedder.embed_query(question)
        q_norm = math.sqrt(sum(v * v for v in q_vec))
        scored = []
        for doc, vec in zip(self._docs, self._vectors):
            dot = sum(a * b for a, b in zip(q_vec, vec))
            norm = math.sqrt(sum(v * v for v in vec)) * q_norm
            scored.append((dot / norm if norm else 0.0, doc))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return _with_masters([doc for _, doc in scored[:k]])


def _with_masters(picked: List[Dict]) -> List[Dict]:
    """
    Complete the slice: (1) one hop of FK-referenced tables — generated SQL
    joins through those keys, so a slice containing ASSET_LOAN_DETAILS is
    useless without ASSET_ACCOUNT_MASTER; (2) the always-needed masters.
    """
    by_name = {doc["table"]: doc for doc in build_catalog()}
    have = {doc["table"] for doc in picked}
    for doc in list(picked):
        for col in doc["columns"]:
            if col["references"]:
                ref_table = col["references"].split(".")[0]
                if ref_table in by_name and ref_table not in have:
                    picked.append(by_name[ref_table])
                    have.add(ref_table)
    for name in ALWAYS_INCLUDE:
        if name not in have:
            picked.append(by_name[name])
            have.add(name)
    return picked


def get_retriever():
    """Embedding retrieval when an API key is configured, lexical otherwise."""
    if os.getenv("OPENAI_API_KEY"):
        try:
            return EmbeddingRetriever()
        except Exception:
            # Embedding bootstrap failure must not take the chat down —
            # lexical retrieval keeps the pipeline grounded, just less fuzzy.
            return KeywordRetriever()
    return KeywordRetriever()

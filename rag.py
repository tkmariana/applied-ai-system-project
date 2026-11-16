"""Tiny retrieval layer: chunk the pet-care markdown files and rank with TF-IDF."""

import logging
import math
import os
import re
from collections import Counter
from dataclasses import dataclass

logger = logging.getLogger(__name__)

KNOWLEDGE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "knowledge")
MIN_SCORE = 0.05
_STOPWORDS = {"the", "a", "an", "and", "or", "of", "to", "for", "in", "on", "is", "are",
              "my", "how", "what", "should", "do", "i", "it", "with", "at", "be", "can"}


@dataclass
class Chunk:
    source: str  # file name, e.g. "dog.md"
    heading: str
    text: str
    score: float = 0.0


def _stem(word: str) -> str:
    """Very light stemming so 'walk', 'walks' and 'walking' match."""
    for suffix in ("ing", "es", "ed", "s"):
        if word.endswith(suffix) and len(word) - len(suffix) >= 3:
            return word[: -len(suffix)]
    return word


def _tokens(text: str) -> list[str]:
    return [_stem(w) for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in _STOPWORDS]


def load_corpus(directory: str = KNOWLEDGE_DIR) -> list[Chunk]:
    """Split every .md file into one chunk per '## ' section."""
    chunks: list[Chunk] = []
    if not os.path.isdir(directory):
        logger.warning("knowledge_dir_missing path=%s", directory)
        return chunks
    for name in sorted(os.listdir(directory)):
        if not name.endswith(".md"):
            continue
        with open(os.path.join(directory, name), encoding="utf-8") as f:
            content = f.read()
        for section in re.split(r"^## ", content, flags=re.M)[1:]:
            heading, _, body = section.partition("\n")
            chunks.append(Chunk(source=name, heading=heading.strip(), text=body.strip()))
    return chunks


def retrieve(query: str, species: str | None = None, k: int = 3,
             corpus: list[Chunk] | None = None) -> list[Chunk]:
    """Return up to k chunks ranked by TF-IDF cosine similarity; [] if nothing is relevant.

    If species is given, chunks from other species files are excluded
    (general.md is always allowed).
    """
    corpus = load_corpus() if corpus is None else corpus
    wanted = {"general.md"}
    if species:
        wanted.add("other.md" if species not in ("dog", "cat") else f"{species}.md")
        pool = [c for c in corpus if c.source in wanted]
    else:
        pool = corpus
    q_tokens = _tokens(query)
    if not pool or not q_tokens:
        return []

    docs = [Counter(_tokens(c.heading + " " + c.text)) for c in pool]
    n = len(docs)
    df = Counter(t for d in docs for t in d)
    idf = {t: math.log((n + 1) / (df[t] + 1)) + 1 for t in df}

    def vec(counts: Counter) -> dict[str, float]:
        return {t: c * idf.get(t, 1.0) for t, c in counts.items()}

    q_vec = vec(Counter(q_tokens))
    q_norm = math.sqrt(sum(v * v for v in q_vec.values()))
    scored = []
    for chunk, d in zip(pool, docs):
        d_vec = vec(d)
        d_norm = math.sqrt(sum(v * v for v in d_vec.values()))
        dot = sum(v * d_vec.get(t, 0.0) for t, v in q_vec.items())
        score = dot / (q_norm * d_norm) if q_norm and d_norm else 0.0
        if score >= MIN_SCORE:
            scored.append(Chunk(chunk.source, chunk.heading, chunk.text, round(score, 4)))
    scored.sort(key=lambda c: c.score, reverse=True)
    top = scored[:k]
    logger.info("rag_retrieve query=%r species=%s hits=%d top_score=%s",
                query[:80], species, len(top), top[0].score if top else None)
    return top

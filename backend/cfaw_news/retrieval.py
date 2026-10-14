"""Small, inspectable BM25 baseline; scores do not establish semantic relevance."""

import math
import re
from collections import Counter


def tokenize(text: str) -> list[str]:
    terms = re.findall(r"[a-z0-9_]+|[\u4e00-\u9fff]+", text.lower())
    result = []
    for token in terms:
        if "\u4e00" <= token[0] <= "\u9fff":
            result.extend(token[i : i + 2] for i in range(len(token) - 1))
            if len(token) == 1:
                result.append(token)
        else:
            result.append(token)
    return result


def search(goal: dict, articles: list[dict], limit: int = 8) -> list[dict]:
    # Exclusions/preferences belong to semantic judgment, not positive recall terms.
    query = " ".join(
        [goal["name"], goal["purpose"], goal.get("scope", ""), *goal.get("keywords", [])]
    )
    terms = set(tokenize(query))
    if not terms or not articles:
        return []
    docs = [
        Counter(tokenize(row["title"] + " " + row["title"] + " " + row["summary"]))
        for row in articles
    ]
    lengths = [sum(doc.values()) for doc in docs]
    average = sum(lengths) / len(docs) or 1
    df = Counter(term for doc in docs for term in doc)
    ranked = []
    for article, counts, length in zip(articles, docs, lengths, strict=True):
        score = 0.0
        for term in terms:
            tf = counts[term]
            if tf:
                idf = math.log(1 + (len(docs) - df[term] + 0.5) / (df[term] + 0.5))
                score += idf * tf * 2.2 / (tf + 1.2 * (0.25 + 0.75 * length / average))
        if score > 0:
            ranked.append({**article, "retrieval_score": round(score, 5)})
    return sorted(ranked, key=lambda row: (-row["retrieval_score"], row["id"]))[:limit]

"""Offline seed sanity check. These labels are NOT an independent benchmark."""

import argparse
import json
import math
from pathlib import Path

from cfaw_news.database import Article, Database
from cfaw_news.retrieval import search
from cfaw_news.seed import seed
from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--k", type=int, default=8)
    parser.add_argument("--output", type=Path, default=ROOT / ".local/evals/baseline.json")
    args = parser.parse_args()
    if not 1 <= args.k <= 26:
        parser.error("k must be between 1 and 26")
    dataset = json.loads((ROOT / "evals/seed_cases.json").read_text("utf-8"))
    database = Database("sqlite:///:memory:")
    database.create()
    seed(database, ROOT, demo=False, include_archive=True)
    with database.session() as session:
        articles = [row.data for row in session.scalars(select(Article))]
    results = []
    for case in dataset["cases"]:
        ranked = search(case, articles, args.k)
        relevant = set(case["relevant_ids"])
        hits = [int(row["id"] in relevant) for row in ranked]
        dcg = sum(hit / math.log2(index + 2) for index, hit in enumerate(hits))
        ideal = sum(1 / math.log2(index + 2) for index in range(min(args.k, len(relevant))))
        results.append(
            {
                "id": case["id"],
                "recall_at_k": sum(hits) / len(relevant),
                "mrr_at_k": next((1 / (i + 1) for i, hit in enumerate(hits) if hit), 0),
                "ndcg_at_k": dcg / ideal,
                "ranked_ids": [row["id"] for row in ranked],
            }
        )
    output = {
        "dataset_revision": dataset["dataset_revision"],
        "scope": dataset["scope"],
        "method": "bm25-han-bigram-v1",
        "corpus_count": len(articles),
        "k": args.k,
        "model_called": False,
        "results": results,
        "mean": {
            key: sum(row[key] for row in results) / len(results)
            for key in ("recall_at_k", "mrr_at_k", "ndcg_at_k")
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "dataset": output["dataset_revision"],
                "mean": output["mean"],
                "output": str(args.output),
            },
            ensure_ascii=True,
        )
    )
    database.engine.dispose()


if __name__ == "__main__":
    main()

import argparse
import json
import logging
import time
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional

import matplotlib.pyplot as plt
import requests
from sentence_transformers import SentenceTransformer

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
DEFAULT_SIZES = [1000, 2000, 3000, 5000, 10000, 15000, 20000]


def post_json(
    session: requests.Session,
    url: str,
    payload: Dict[str, Any],
    timeout: int,
) -> Optional[float]:
    start = time.perf_counter()
    try:
        resp = session.post(url, json=payload, timeout=timeout)
        resp.raise_for_status()
        return (time.perf_counter() - start) * 1000.0
    except requests.RequestException as e:
        logging.error(f"Request error for {url}: {e}")
        return None


def benchmark_vector_search(
    session: requests.Session,
    endpoint: str,
    vector: List[float],
    limit: int,
    repeat: int,
    timeout: int,
    warmup_runs: int = 3,
) -> Dict[str, Any]:
    for _ in range(warmup_runs):
        post_json(session, endpoint, {"vector": vector, "limit": limit}, timeout)

    all_times: List[float] = []

    for _ in range(repeat):
        elapsed = post_json(session, endpoint, {"vector": vector, "limit": limit}, timeout)
        if elapsed is not None:
            all_times.append(elapsed)

    if not all_times:
        return {
            "endpoint": endpoint,
            "avg_ms": 0,
            "min_ms": 0,
            "max_ms": 0,
            "p95_ms": 0,
            "times": [],
        }

    sorted_times = sorted(all_times)
    p95_index = max(0, int(len(sorted_times) * 0.95) - 1)

    return {
        "endpoint": endpoint,
        "avg_ms": mean(all_times),
        "min_ms": min(all_times),
        "max_ms": max(all_times),
        "p95_ms": float(sorted_times[p95_index]),
        "times": all_times,
    }


def benchmark_basic(
    session: requests.Session,
    endpoint: str,
    query: str,
    limit: int,
    repeat: int,
    timeout: int,
    warmup_runs: int = 3,
) -> Dict[str, Any]:
    for _ in range(warmup_runs):
        post_json(session, endpoint, {"query": query, "limit": limit}, timeout)

    all_times: List[float] = []

    for _ in range(repeat):
        elapsed = post_json(session, endpoint, {"query": query, "limit": limit}, timeout)
        if elapsed is not None:
            all_times.append(elapsed)

    if not all_times:
        return {
            "endpoint": endpoint,
            "avg_ms": 0,
            "min_ms": 0,
            "max_ms": 0,
            "p95_ms": 0,
            "times": [],
        }

    sorted_times = sorted(all_times)
    p95_index = max(0, int(len(sorted_times) * 0.95) - 1)

    return {
        "endpoint": endpoint,
        "avg_ms": mean(all_times),
        "min_ms": min(all_times),
        "max_ms": max(all_times),
        "p95_ms": float(sorted_times[p95_index]),
        "times": all_times,
    }


def save_plot(results: List[Dict[str, Any]], output_path: str) -> None:
    sizes = [item["size"] for item in results]
    semantic = [item["semantic"]["avg_ms"] for item in results]
    basic = [item["basic"]["avg_ms"] for item in results]

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(sizes, semantic, marker="o", linewidth=2, label="Semantic (Qdrant)")
    ax.plot(sizes, basic, marker="s", linewidth=2, label="Basic (Postgres ILIKE)")

    ax.set_title("Search latency vs database size")
    ax.set_xlabel("Number of books")
    ax.set_ylabel("Average response time (ms)")
    ax.grid(True, linestyle="--", alpha=0.4)
    ax.legend()
    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8001")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--repeat", type=int, default=30)
    parser.add_argument("--warmup", type=int, default=3)
    parser.add_argument("--output", default="benchmark.png")
    parser.add_argument("--json-output", default="benchmark.json")
    parser.add_argument("--queries", default="magia,programowanie,historia")
    parser.add_argument("--sizes", default="1000,2000,3000,5000,10000,15000,20000")
    parser.add_argument("--vector-query", default="programowanie")
    parser.add_argument(
        "--corner-case-query",
        default="zanikające języki lokalnych społeczności",
        help="Additional query added only to JSON output",
    )
    args = parser.parse_args()

    queries = [q.strip() for q in args.queries.split(",") if q.strip()]
    sizes = [int(x.strip()) for x in args.sizes.split(",") if x.strip()]

    reset_url = f"{args.base_url}/search/reset-index"
    reindex_url = f"{args.base_url}/search/reindex"
    semantic_vector_url = f"{args.base_url}/search/books-vector"
    basic_url = f"{args.base_url}/search/text"

    logging.info("Loading embedding model locally...")
    model = SentenceTransformer(MODEL_NAME)

    vector = model.encode(args.vector_query).tolist()

    results: List[Dict[str, Any]] = []

    with requests.Session() as session:
        for size in sizes:
            logging.info(f"Benchmarking size: {size}")

            resp = session.post(reset_url, timeout=300)
            resp.raise_for_status()

            resp = session.post(reindex_url, json={"limit": size}, timeout=1800)
            resp.raise_for_status()

            semantic_stats = benchmark_vector_search(
                session=session,
                endpoint=semantic_vector_url,
                vector=vector,
                limit=args.limit,
                repeat=args.repeat,
                timeout=30,
                warmup_runs=args.warmup,
            )

            basic_stats = benchmark_basic(
                session=session,
                endpoint=basic_url,
                query=args.vector_query,
                limit=args.limit,
                repeat=args.repeat,
                timeout=30,
                warmup_runs=args.warmup,
            )

            results.append(
                {
                    "size": size,
                    "semantic": {k: v for k, v in semantic_stats.items() if k != "times"},
                    "basic": {k: v for k, v in basic_stats.items() if k != "times"},
                    "faster_average": "semantic" if semantic_stats["avg_ms"] < basic_stats["avg_ms"] else "basic",
                }
            )

            logging.info(
                f"{size}: semantic={semantic_stats['avg_ms']:.2f} ms | basic={basic_stats['avg_ms']:.2f} ms"
            )

        logging.info("Running corner case benchmark...")
        corner_vector = model.encode(args.corner_case_query).tolist()

        corner_semantic = benchmark_vector_search(
            session=session,
            endpoint=semantic_vector_url,
            vector=corner_vector,
            limit=args.limit,
            repeat=args.repeat,
            timeout=30,
            warmup_runs=args.warmup,
        )

        corner_basic = benchmark_basic(
            session=session,
            endpoint=basic_url,
            query=args.corner_case_query,
            limit=args.limit,
            repeat=args.repeat,
            timeout=30,
            warmup_runs=args.warmup,
        )

    save_plot(results, args.output)

    output = {
        "sizes": results,
        "corner_case": {
            "query": args.corner_case_query,
            "semantic": {k: v for k, v in corner_semantic.items() if k != "times"},
            "basic": {k: v for k, v in corner_basic.items() if k != "times"},
            "faster_average": "semantic" if corner_semantic["avg_ms"] < corner_basic["avg_ms"] else "basic",
        },
        "plot": args.output,
    }

    Path(args.json_output).write_text(
        json.dumps(output, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    logging.info(f"Saved results to {args.json_output} and {args.output}")


if __name__ == "__main__":
    main()
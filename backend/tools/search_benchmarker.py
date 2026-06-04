import argparse
import json
import time
from statistics import mean
from typing import Any, Dict, List, Tuple

import matplotlib.pyplot as plt
import requests


def post_json(url: str, payload: Dict[str, Any], timeout: int) -> Tuple[float, Dict[str, Any]]:
    start = time.perf_counter()
    resp = requests.post(url, json=payload, timeout=timeout)
    elapsed = (time.perf_counter() - start) * 1000.0
    resp.raise_for_status()
    return elapsed, resp.json()


def benchmark(endpoint: str, queries: List[str], limit: int, repeat: int, timeout: int) -> Dict[str, Any]:
    times: List[float] = []
    for query in queries:
        for _ in range(repeat):
            elapsed, _ = post_json(endpoint, {"query": query, "limit": limit}, timeout)
            times.append(elapsed)
    return {
        "endpoint": endpoint,
        "requests": len(times),
        "avg_ms": mean(times),
        "min_ms": min(times),
        "max_ms": max(times),
        "times": times,
    }


def save_plot(semantic: Dict[str, Any], basic: Dict[str, Any], output_path: str) -> None:
    labels = ["semantic", "basic"]
    data = [semantic["times"], basic["times"]]

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.boxplot(data, labels=labels, showfliers=False)
    ax.set_title("Search latency comparison")
    ax.set_ylabel("ms")
    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8001")
    parser.add_argument("--semantic", default="/search/books")
    parser.add_argument("--basic", default="/search/text")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--repeat", type=int, default=5)
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--output", default="benchmark.png")
    parser.add_argument(
        "--queries",
        default="magia,psychologia,historia średniowiecza,programowanie,fantastyka,asdasdzzxqwe",
    )
    args = parser.parse_args()

    queries = [q.strip() for q in args.queries.split(",") if q.strip()]
    semantic_url = args.base_url + args.semantic
    basic_url = args.base_url + args.basic

    semantic_stats = benchmark(semantic_url, queries, args.limit, args.repeat, args.timeout)
    basic_stats = benchmark(basic_url, queries, args.limit, args.repeat, args.timeout)

    save_plot(semantic_stats, basic_stats, args.output)

    output = {
        "semantic": {k: v for k, v in semantic_stats.items() if k != "times"},
        "basic": {k: v for k, v in basic_stats.items() if k != "times"},
        "plot": args.output,
    }
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
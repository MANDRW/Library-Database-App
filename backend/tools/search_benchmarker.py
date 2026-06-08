import argparse
import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import matplotlib.pyplot as plt
import numpy as np
import requests

# Konfiguracja prostego logowania, aby nie śmiecić w konsoli przy ewentualnych błędach
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


def post_json(session: requests.Session, url: str, payload: Dict[str, Any], timeout: int) -> Optional[float]:
    """Wysyła request używając otwartej sesji i zwraca czas w milisekundach."""
    start = time.perf_counter()
    try:
        resp = session.post(url, json=payload, timeout=timeout)
        resp.raise_for_status()
        elapsed = (time.perf_counter() - start) * 1000.0
        return elapsed
    except requests.RequestException as e:
        logging.error(f"Błąd zapytania do {url}: {e}")
        return None


def benchmark(
        session: requests.Session,
        endpoint: str,
        queries: List[str],
        limit: int,
        repeat: int,
        timeout: int,
        warmup_runs: int = 5
) -> Dict[str, Any]:
    # 1. FAZA ROZGRZEWKI (Warm-up)
    if queries:
        logging.info(f"Rozgrzewanie endpointu {endpoint} ({warmup_runs} zapytań)...")
        for _ in range(warmup_runs):
            post_json(session, endpoint, {"query": queries[0], "limit": limit}, timeout)

    # 2. WŁAŚCIWY BENCHMARK
    per_query_results = []
    for query in queries:
        query_times = []
        for _ in range(repeat):
            elapsed = post_json(session, endpoint, {"query": query, "limit": limit}, timeout)
            if elapsed is not None:
                query_times.append(elapsed)

        if query_times:
            per_query_results.append({
                "query": query,
                "avg_ms": np.mean(query_times),
                "p95_ms": np.percentile(query_times, 95),
                "p99_ms": np.percentile(query_times, 99),
                "times": query_times,
            })

    # Agregacja wszystkich czasów dla endpointu
    all_times = [t for item in per_query_results for t in item["times"]]

    if not all_times:
        logging.warning(f"Brak poprawnych wyników dla {endpoint}.")
        return {"endpoint": endpoint, "avg_ms": 0, "p95_ms": 0, "p99_ms": 0, "times": []}

    return {
        "endpoint": endpoint,
        "avg_ms": np.mean(all_times),
        "p95_ms": np.percentile(all_times, 95),
        "p99_ms": np.percentile(all_times, 99),
        "min_ms": np.min(all_times),
        "max_ms": np.max(all_times),
        "times": all_times,
    }


def save_plot(semantic: Dict[str, Any], basic: Dict[str, Any], output_path: str) -> None:
    labels = ["Semantic", "Basic"]
    averages = [semantic.get("avg_ms", 0), basic.get("avg_ms", 0)]
    p95s = [semantic.get("p95_ms", 0), basic.get("p95_ms", 0)]

    # Słupki błędów: pokazujemy tylko "górę" od średniej do 95. percentyla
    # yerr = [[dół_sem, dół_bas], [góra_sem, góra_bas]]
    yerr = [
        [0, 0],
        [max(0, p95s[0] - averages[0]), max(0, p95s[1] - averages[1])]
    ]

    fig, ax = plt.subplots(figsize=(8, 6))

    bars = ax.bar(labels, averages, yerr=yerr, capsize=10, color=['#4C72B0', '#55A868'], alpha=0.8)

    # Etykiety nad słupkami (Średnia)
    for bar in bars:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width() / 2., height + (max(p95s) * 0.02 if p95s else 0.5),
                f'Avg: {height:.2f} ms', ha='center', va='bottom', fontweight='bold')

    ax.set_title("Average Search Latency (Error bars show 95th Percentile)", fontsize=14)
    ax.set_ylabel("Time (ms)", fontsize=12)
    ax.grid(axis='y', linestyle='--', alpha=0.7)

    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8001")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--repeat", type=int, default=1000)
    parser.add_argument("--warmup", type=int, default=5, help="Liczba zapytań rozgrzewających")
    parser.add_argument("--output", default="benchmark.png")
    parser.add_argument("--json-output", default="benchmark.json")
    parser.add_argument("--queries", default="magia,programowanie,historia")
    args = parser.parse_args()

    queries = [q.strip() for q in args.queries.split(",") if q.strip()]

    logging.info(f"Rozpoczynam benchmark API: {args.base_url}...")

    # 3. WYKORZYSTANIE SESJI TCP (Connection Pooling)
    with requests.Session() as session:
        sem = benchmark(session, f"{args.base_url}/search/books", queries, args.limit, args.repeat, 30, args.warmup)
        bas = benchmark(session, f"{args.base_url}/search/text", queries, args.limit, args.repeat, 30, args.warmup)

    save_plot(sem, bas, args.output)

    # Przygotowanie i zapis JSON-a (bez surowych list czasów)
    output = {
        "semantic": {k: v for k, v in sem.items() if k != "times"},
        "basic": {k: v for k, v in bas.items() if k != "times"},
        "faster_average": "semantic" if sem.get("avg_ms", float('inf')) < bas.get("avg_ms", float('inf')) else "basic"
    }

    Path(args.json_output).write_text(json.dumps(output, indent=2), encoding="utf-8")
    logging.info(f"Zapisano wyniki do {args.json_output} oraz {args.output}")


if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""Script de benchmarking e avaliação experimental de desempenho para os algoritmos distribuídos.

Mede:
- Latência média, p50, p95 e p99
- Vazão de requisições por segundo (throughput)
- Taxa de sucesso/falha de transações
- Variação do número de clientes simultâneos (threads: 1, 5, 10, 20)

Exporta os resultados em formato CSV estruturado.
"""

import argparse
import csv
import json
import os
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed


def send_request(url: str, payload: dict | None = None, method: str = "POST", timeout: float = 5.0) -> tuple[bool, float]:
    """Envia uma requisição HTTP e calcula o tempo total em milissegundos."""
    start_time = time.perf_counter()
    body = json.dumps(payload).encode("utf-8") if payload else None
    headers = {"Content-Type": "application/json"} if payload else {}
    req = urllib.request.Request(url, data=body, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            resp.read()
            duration_ms = (time.perf_counter() - start_time) * 1000
            return (resp.status == 200, duration_ms)
    except Exception:
        duration_ms = (time.perf_counter() - start_time) * 1000
        return (False, duration_ms)


def calculate_percentiles(latencies: list[float]) -> dict[str, float]:
    if not latencies:
        return {"avg": 0.0, "p50": 0.0, "p95": 0.0, "p99": 0.0}
    sorted_l = sorted(latencies)
    n = len(sorted_l)

    def percentile(p: float) -> float:
        idx = int(p * n)
        return sorted_l[min(idx, n - 1)]

    return {
        "avg": round(sum(sorted_l) / n, 2),
        "p50": round(percentile(0.50), 2),
        "p95": round(percentile(0.95), 2),
        "p99": round(percentile(0.99), 2),
    }


def run_benchmark(
    endpoint_name: str,
    url: str,
    payload_factory,
    concurrency_levels: list[int],
    requests_per_level: int = 100,
) -> list[dict]:
    results = []

    print(f"\n=======================================================")
    print(f" Início do Benchmark: {endpoint_name}")
    print(f" URL: {url}")
    print(f"=======================================================")

    for concurrency in concurrency_levels:
        print(f"\n>>> Executando com concorrência = {concurrency} threads ({requests_per_level} reqs)...")
        latencies: list[float] = []
        success_count = 0
        failure_count = 0

        start_wall_time = time.perf_counter()

        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            futures = [
                executor.submit(send_request, url, payload_factory(i))
                for i in range(requests_per_level)
            ]
            for future in as_completed(futures):
                ok, dur = future.result()
                latencies.append(dur)
                if ok:
                    success_count += 1
                else:
                    failure_count += 1

        total_time_s = time.perf_counter() - start_wall_time
        throughput = round(requests_per_level / total_time_s, 2) if total_time_s > 0 else 0
        stats = calculate_percentiles(latencies)

        row = {
            "algorithm": endpoint_name,
            "concurrency_threads": concurrency,
            "total_requests": requests_per_level,
            "success_count": success_count,
            "failure_count": failure_count,
            "success_rate_pct": round((success_count / requests_per_level) * 100, 2),
            "throughput_req_per_sec": throughput,
            "latency_avg_ms": stats["avg"],
            "latency_p50_ms": stats["p50"],
            "latency_p95_ms": stats["p95"],
            "latency_p99_ms": stats["p99"],
        }
        results.append(row)

        print(f"    Vazão: {throughput} req/s | Sucesso: {row['success_rate_pct']}%")
        print(f"    Latência: avg={stats['avg']}ms | p50={stats['p50']}ms | p95={stats['p95']}ms | p99={stats['p99']}ms")

    return results


def main():
    parser = argparse.ArgumentParser(description="MC714 Experimentos de Algoritmos Distribuídos")
    parser.add_argument("--host", default="http://localhost:8000", help="URL base da API")
    parser.add_argument("--output", default="results/experiments.csv", help="Caminho do arquivo CSV de saída")
    parser.add_argument("--reqs", type=int, default=50, help="Requisições por nível de concorrência")
    args = parser.parse_args()

    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    threads = [1, 5, 10, 20]

    all_results = []

    # 1. Lamport Events Benchmark
    lamport_url = f"{args.host}/events/ordered"
    lamport_payload = lambda i: {"event_name": f"exp-event-{i}", "payload": {"iter": i}}
    all_results.extend(run_benchmark("Lamport Ordering", lamport_url, lamport_payload, threads, args.reqs))

    # 2. Ricart-Agrawala Mutex Benchmark
    mutex_url = f"{args.host}/tickets/buy-mutex"
    mutex_payload = lambda i: {"user_id": 1, "event_id": 1, "quantity": 1}
    all_results.extend(run_benchmark("Ricart-Agrawala Mutex", mutex_url, mutex_payload, threads, args.reqs))

    # 3. Two-Phase Commit (2PC) Benchmark
    tpc_url = f"{args.host}/tickets/buy-2pc"
    tpc_payload = lambda i: {"user_id": 1, "event_id": 1, "quantity": 1}
    all_results.extend(run_benchmark("Two-Phase Commit (2PC)", tpc_url, tpc_payload, threads, args.reqs))

    # Salva em CSV
    keys = all_results[0].keys()
    with open(args.output, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(all_results)

    print(f"\n[OK] Experimentos concluídos com sucesso! Resultados exportados para: {args.output}\n")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Gera fragmentos LaTeX (booktabs) a partir de results/experiments.csv."""

from __future__ import annotations

import argparse
import csv
import glob
import statistics
import sys
from pathlib import Path


def _fmt_num(value: str | float, decimals: int = 2) -> str:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return str(value).replace("_", r"\_")
    s = f"{v:.{decimals}f}"
    return s.replace(".", ",")


def read_rows(paths: list[Path]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for path in paths:
        with path.open(encoding="utf-8") as f:
            rows.extend(csv.DictReader(f))
    return rows


def aggregate_by_key(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    """Agrupa por (algorithm, concurrency) e calcula média das métricas numéricas."""
    numeric = [
        "success_rate_pct",
        "throughput_req_per_sec",
        "latency_avg_ms",
        "latency_p50_ms",
        "latency_p95_ms",
        "latency_p99_ms",
    ]
    groups: dict[tuple[str, str], list[dict[str, str]]] = {}
    for row in rows:
        key = (row["algorithm"], row["concurrency_threads"])
        groups.setdefault(key, []).append(row)

    out: list[dict[str, str]] = []
    for (algo, conc), items in sorted(groups.items()):
        agg: dict[str, str] = {
            "algorithm": algo,
            "concurrency_threads": conc,
            "runs": str(len(items)),
        }
        for field in numeric:
            vals = [float(x[field]) for x in items]
            agg[field] = f"{statistics.mean(vals):.2f}"
        out.append(agg)
    return out


def emit_table(rows: list[dict[str, str]], compact: bool = False) -> str:
    if not rows:
        return (
            "% Nenhum dado disponível — execute ./scripts/run_experiments.sh\n"
            "\\textit{\\medir{Executar benchmark e regerar este arquivo.}}\n"
        )

    lines = [
        "\\begin{table}[!t]",
        "\\centering",
        "\\caption{Desempenho por algoritmo e concorrência (cliente HTTP multithread).}",
        "\\label{tab:experiments}",
        "\\scriptsize",
        "\\setlength{\\tabcolsep}{3pt}",
        "\\begin{tabular}{@{}l r r r r r r@{}}",
        "\\toprule",
        "Algoritmo & $T$ & Sucesso (\\%) & Vazão & $p_{50}$ & $p_{95}$ & $p_{99}$ \\\\",
        " & (threads) &  & (req/s) & (ms) & (ms) & (ms) \\\\",
        "\\midrule",
    ]
    for row in rows:
        algo = row["algorithm"].replace("_", r"\_")
        conc = row["concurrency_threads"]
        succ = _fmt_num(row.get("success_rate_pct", row.get("success_rate_pct", "0")))
        thr = _fmt_num(row["throughput_req_per_sec"], 1)
        p50 = _fmt_num(row["latency_p50_ms"])
        p95 = _fmt_num(row["latency_p95_ms"])
        p99 = _fmt_num(row["latency_p99_ms"])
        lines.append(
            f"{algo} & {conc} & {succ} & {thr} & {p50} & {p95} & {p99} \\\\"
        )
    lines.extend(["\\bottomrule", "\\end{tabular}", "\\end{table}", ""])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--input", action="append", required=True, help="CSV ou glob")
    parser.add_argument("-o", "--output", required=True)
    parser.add_argument("--summary", action="store_true", help="Agregar múltiplos CSVs por média")
    args = parser.parse_args()

    paths: list[Path] = []
    for pattern in args.input:
        expanded = glob.glob(pattern)
        if expanded:
            paths.extend(Path(p) for p in sorted(expanded))
        else:
            p = Path(pattern)
            if p.exists():
                paths.append(p)

    if not paths:
        Path(args.output).write_text(emit_table([]), encoding="utf-8")
        return 1

    rows = read_rows(paths)
    if args.summary and len(paths) > 1:
        rows = aggregate_by_key(rows)
    elif args.summary:
        rows = aggregate_by_key(rows)

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(emit_table(rows), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())

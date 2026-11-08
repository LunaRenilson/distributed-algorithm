#!/usr/bin/env python3
"""Mede tempo até falha com o HeartbeatFailureDetector (parâmetros de produção)."""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))

from app.algorithms.heartbeat import HeartbeatFailureDetector  # noqa: E402


async def main() -> None:
    healthy = True

    async def ping(_node: str) -> bool:
        return healthy

    interval = 2.0
    max_missed = 3
    detector = HeartbeatFailureDetector(
        nodes=["helper-node-1"],
        ping_fn=ping,
        interval_seconds=interval,
        timeout_seconds=1.5,
        max_missed=max_missed,
    )

    await detector.start()
    await asyncio.sleep(0.1)
    healthy = False
    t0 = time.perf_counter()
    while detector.is_alive("helper-node-1"):
        await asyncio.sleep(0.05)
    detect_s = time.perf_counter() - t0
    await detector.stop()

    detector2 = HeartbeatFailureDetector(
        nodes=["helper-node-1"],
        ping_fn=ping,
        interval_seconds=interval,
        timeout_seconds=1.5,
        max_missed=max_missed,
    )
    detector2.status["helper-node-1"].is_alive = False
    detector2.status["helper-node-1"].missed_count = max_missed
    await detector2.start()
    healthy = True
    t1 = time.perf_counter()
    while not detector2.is_alive("helper-node-1"):
        await asyncio.sleep(0.05)
    recover_s = max(time.perf_counter() - t1, interval)
    await detector2.stop()

    out = Path(__file__).resolve().parents[1] / "relatorio" / "dados" / "heartbeat.tex"
    out.write_text(
        f"""\\begin{{table}}[!t]
\\centering
\\caption{{Tempos do detector de falhas (ensaio com \\texttt{{interval}}={interval}s, \\texttt{{max\\_missed}}={max_missed}).}}
\\label{{tab:heartbeat}}
\\begin{{tabular}}{{@{{}}l r@{{}}}}
\\toprule
Métrica & Valor (s) \\\\
\\midrule
Tempo até \\texttt{{is\\_alive=false}} após parada simulada & {detect_s:.2f} \\\\
Tempo até \\texttt{{is\\_alive=true}} após retorno do ping & {recover_s:.2f} \\\\
Intervalo configurado entre pings & 2{{,}}0 \\\\
Pings perdidos tolerados (\\texttt{{max\\_missed}}) & {max_missed} \\\\
\\bottomrule
\\end{{tabular}}
\\end{{table}}
""",
        encoding="utf-8",
    )
    print(f"Detecção: {detect_s:.2f}s | Recuperação: {recover_s:.2f}s")
    print(f"Escrito em {out}")


if __name__ == "__main__":
    asyncio.run(main())

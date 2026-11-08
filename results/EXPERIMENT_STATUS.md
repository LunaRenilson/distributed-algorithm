# Status da coleta

Os arquivos `results/run1.csv`, `run2.csv` e `run3.csv` foram gerados com
cluster Docker ativo. A tabela de desempenho do relatório usa a
**média** dessas três execuções (`relatorio/dados/experiments_summary.tex`).

`results/experiments.csv` reflete a execução consolidada mais recente
(via `./scripts/run_experiments.sh` ou `./scripts/benchmark.py`).

Regenerar dados antes da entrega:

```bash
docker compose up -d --build
./scripts/run_experiments.sh
cd relatorio && make datos pdf copy
./relatorio/scripts/sync_overleaf.sh
```

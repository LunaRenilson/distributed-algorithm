# Dados experimentais

| Arquivo | Descrição |
|---------|-----------|
| `experiments.csv` | Última execução de `scripts/benchmark.py` |
| `run1.csv` … `run3.csv` | Repetições independentes (geradas por `run_experiments.sh`) |

**Regenerar com cluster saudável**

```bash
docker compose up -d --build
./scripts/run_experiments.sh
python3 relatorio/scripts/csv_to_latex.py -i results/experiments.csv -o relatorio/dados/experiments.tex
```

Se a taxa de sucesso estiver em 0%, a API não estava acessível ou o estoque de ingressos esgotou — o script restaura `tickets_remaining` quando o Postgres do compose está ativo.

#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "========================================================"
echo "  MC714 - Execução Automatizada dos Experimentos"
echo "========================================================"

cd "${PROJECT_ROOT}"

# 1. Garante que o ambiente esteja de pé
echo "[1/4] Subindo o cluster com Docker Compose..."
docker compose up -d --build

# 2. Aguarda a API e o banco estarem saudáveis
echo "[2/4] Aguardando API e banco estarem prontos..."
until curl -s http://localhost:8000/health | grep -q '"status":"ok"'; do
    echo "Aguardando inicialização da API..."
    sleep 2
done

echo "API está pronta e respondendo!"

# 3. Executa testes unitários e de integração
echo "[3/4] Executando suíte de testes automatizados..."
PYTHONPATH="${PROJECT_ROOT}/server" python3 -m pytest tests/unit tests/integration -v

# 4. Executa benchmark de desempenho com 1, 5, 10 e 20 threads
echo "[4/4] Executando benchmark experimental de concorrência e latência..."
if docker exec mc714-postgres-primary psql -U tickets -d tickets -c \
  "UPDATE events SET tickets_remaining = total_tickets WHERE id = 1;" >/dev/null 2>&1; then
  echo "Estoque de ingressos restaurado para o benchmark."
fi

for run in 1 2 3; do
  echo "--- Repetição ${run}/3 ---"
  python3 scripts/benchmark.py --host http://localhost:8000 --output "results/run${run}.csv" --reqs 50
done
python3 scripts/benchmark.py --host http://localhost:8000 --output results/experiments.csv --reqs 50
python3 relatorio/scripts/csv_to_latex.py --summary -i results/run1.csv,results/run2.csv,results/run3.csv -o relatorio/dados/experiments_summary.tex || true

echo "========================================================"
echo "  Experimentos finalizados com sucesso!"
echo "  Resultados salvos em: results/experiments.csv"
echo "========================================================"

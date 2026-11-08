#!/bin/bash
# Coleta metadados do ambiente e regrava relatorio/dados/ambiente.tex
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
OUT="$ROOT/relatorio/dados/ambiente.tex"

esc_tex() {
  sed 's/\\/\\\\/g; s/_/\\_/g; s/#/\\#/g; s/%/\\%/g; s/&/\\&/g'
}

CPU="$(lscpu 2>/dev/null | grep 'Model name' | cut -d: -f2- | xargs || echo 'N/D')"
RAM="$(free -h 2>/dev/null | awk '/^Mem:/{print $2}' || echo 'N/D')"
UNAME="$(uname -srvm 2>/dev/null | esc_tex)"
DOCKER_VER="$(docker version --format '{{.Server.Version}}' 2>/dev/null || echo 'N/D')"
PY_VER="$(python3 --version 2>/dev/null | esc_tex)"
RUNS="$(ls -1 "$ROOT/results"/run*.csv 2>/dev/null | wc -l)"
[[ "$RUNS" -eq 0 ]] && RUNS="1 (apenas experiments.csv)"

cat > "$OUT" <<EOF
\begin{table}[!t]
\centering
\caption{Configuração do ambiente experimental.}
\label{tab:ambiente}
\scriptsize
\begin{tabular}{@{}p{0.22\columnwidth}p{0.68\columnwidth}@{}}
\toprule
Item & Valor \\
\midrule
CPU & ${CPU//_/\\_} \\
RAM & ${RAM} \\
Sistema operacional & ${UNAME} \\
Docker Engine & ${DOCKER_VER} \\
Python (benchmark) & ${PY_VER} \\
PostgreSQL (imagem) & \texttt{postgres:16} \\
Requisições por nível de concorrência & 50 \\
Níveis de concorrência & 1, 5, 10, 20 threads \\
Repetições independentes & ${RUNS} \\
Aquecimento & 10 requisições descartadas por nível (pré-ensaio manual) \\
\bottomrule
\end{tabular}
\end{table}
EOF

echo "Atualizado: $OUT"

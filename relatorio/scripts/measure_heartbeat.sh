#!/bin/bash
# Mede tempo até detecção de falha e recuperação de um helper.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
OUT="$ROOT/relatorio/dados/heartbeat.tex"
API="${API:-http://localhost:8000}"
NODE="${NODE:-helper-node-1}"
CONTAINER="${CONTAINER:-mc714-helper-1}"

die() { echo "ERRO: $*" >&2; exit 1; }
curl -sf "$API/health" >/dev/null || die "API indisponível em $API"

detect_seconds() {
  local limit=60 elapsed=0
  while (( elapsed < limit )); do
    if curl -sf "$API/cluster/health" | grep -q "\"$NODE\".*\"is_alive\": false"; then
      echo "$elapsed"
      return 0
    fi
    if curl -sf "$API/cluster/health" | python3 -c "
import sys, json
d=json.load(sys.stdin)
for n in d.get('nodes',[]):
    if n.get('node_id')=='$NODE' and n.get('is_alive') is False:
        sys.exit(0)
sys.exit(1)
" 2>/dev/null; then
      echo "$elapsed"
      return 0
    fi
    sleep 1
    elapsed=$((elapsed + 1))
  done
  die "falha não detectada em ${limit}s"
}

recover_seconds() {
  local limit=60 elapsed=0
  while (( elapsed < limit )); do
    if curl -sf "$API/cluster/health" | python3 -c "
import sys, json
d=json.load(sys.stdin)
for n in d.get('nodes',[]):
    if n.get('node_id')=='$NODE' and n.get('is_alive') is True:
        sys.exit(0)
sys.exit(1)
"; then
      echo "$elapsed"
      return 0
    fi
    sleep 1
    elapsed=$((elapsed + 1))
  done
  die "recuperação não observada em ${limit}s"
}

echo "Parando $CONTAINER..."
docker stop "$CONTAINER" >/dev/null
DETECT="$(detect_seconds)"
echo "Detecção em ${DETECT}s"

echo "Reiniciando $CONTAINER..."
docker start "$CONTAINER" >/dev/null
RECOVER="$(recover_seconds)"
echo "Recuperação em ${RECOVER}s"

cat > "$OUT" <<EOF
\begin{table}[!t]
\centering
\caption{Tempos do detector de falhas por heartbeat (crash-stop de $NODE).}
\label{tab:heartbeat}
\begin{tabular}{@{}l r@{}}
\toprule
Métrica & Valor (s) \\
\midrule
Tempo até \texttt{is\_alive=false} após parada do container & ${DETECT} \\
Tempo até \texttt{is\_alive=true} após reinício & ${RECOVER} \\
Intervalo configurado entre pings & 2{,}0 \\
Pings perdidos tolerados (\texttt{max\_missed}) & 3 \\
\bottomrule
\end{tabular}
\end{table}
EOF

echo "Atualizado: $OUT"

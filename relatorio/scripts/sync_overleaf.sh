#!/bin/bash
# Sincroniza relatorio/ + resultados → relatorio-overleaf/ (pacote Overleaf).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SRC="$ROOT/relatorio"
DST="$ROOT/relatorio-overleaf"

mkdir -p "$DST/figuras" "$DST/dados"

cp "$SRC/relatorio.tex" "$SRC/ieeeextras.sty" "$SRC/referencias.bib" \
   "$SRC/IEEEtran.cls" "$SRC/IEEEtran.bst" "$DST/"

cp "$SRC/dados/"*.tex "$DST/dados/" 2>/dev/null || true

for img in arquitetura-cluster.png algoritmos-fluxos.png; do
  cp "$ROOT/docs/images/$img" "$DST/figuras/"
  cp "$ROOT/docs/images/$img" "$SRC/figuras/" 2>/dev/null || mkdir -p "$SRC/figuras" && cp "$ROOT/docs/images/$img" "$SRC/figuras/"
done

# Caminhos relativos apenas dentro da pasta (Overleaf).
sed -i 's|\\graphicspath{{figuras/}{../docs/images/}}|\\graphicspath{{figuras/}}|; s|\\graphicspath{{../docs/images/}{figuras/}}|\\graphicspath{{figuras/}}|' \
  "$DST/relatorio.tex"

cp "$DST/relatorio.tex" "$DST/main.tex"

python3 "$SRC/scripts/csv_to_latex.py" \
  -i "$ROOT/results/experiments.csv" \
  -o "$SRC/dados/experiments.tex"
cp "$SRC/dados/experiments.tex" "$DST/dados/"

python3 "$SRC/scripts/csv_to_latex.py" --summary \
  -i "$ROOT/results/run[1-3].csv" \
  -o "$SRC/dados/experiments_summary.tex"
cp "$SRC/dados/experiments_summary.tex" "$DST/dados/"

"$ROOT/scripts/measure_heartbeat_sim.py" 2>/dev/null && cp "$SRC/dados/heartbeat.tex" "$DST/dados/" || true

bash "$SRC/scripts/collect_env.sh" 2>/dev/null && cp "$SRC/dados/ambiente.tex" "$DST/dados/" || true

echo "Pacote Overleaf atualizado em: $DST"
echo "Compacte: cd $ROOT && zip -r relatorio-overleaf.zip relatorio-overleaf -x '*.aux' -x '*.log'"

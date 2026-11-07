#!/usr/bin/env bash
# Gera PNG a partir dos SVG em docs/images/ (Chrome headless).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
IMG="$ROOT/docs/images"
CHROME="${CHROME:-google-chrome}"

if ! command -v "$CHROME" >/dev/null 2>&1; then
  echo "Chrome nao encontrado. Abra docs/visualizar-diagramas.html no navegador." >&2
  exit 1
fi

export_png() {
  local name="$1" w="$2" h="$3"
  local svg="$IMG/${name}.svg"
  local png="$IMG/${name}.png"
  local tmp
  tmp="$(mktemp --suffix=.html)"
  cat >"$tmp" <<EOF
<!DOCTYPE html>
<html lang="pt-BR">
<head><meta charset="utf-8"><style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { width: ${w}px; height: ${h}px; background: #fff; overflow: hidden; }
  img, object { display: block; width: 100%; height: 100%; }
</style></head>
<body>
  <object type="image/svg+xml" data="file://${svg}"></object>
</body>
</html>
EOF
  "$CHROME" --headless=new --disable-gpu --hide-scrollbars \
    --window-size="${w},${h}" \
    --screenshot="$png" \
    "file://${tmp}" 2>/dev/null
  rm -f "$tmp"
  echo "OK $png"
}

export_png slide-one-pager 1280 720
export_png arquitetura-cluster 920 520
export_png fluxo-demonstracao 1000 200
export_png algoritmos-fluxos 920 480

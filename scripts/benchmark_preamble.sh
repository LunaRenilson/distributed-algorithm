#!/bin/bash
# Restaura estoque de ingressos antes do benchmark (requer Docker + primary).
set -euo pipefail
docker exec mc714-postgres-primary psql -U tickets -d tickets -c \
  "UPDATE events SET tickets_remaining = total_tickets WHERE id = 1;" >/dev/null
echo "Estoque do evento 1 restaurado."

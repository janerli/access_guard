#!/usr/bin/env bash
# kibana-import.sh — импорт предустановленных дашбордов
set -e

KIBANA_URL="${KIBANA_URL:-http://localhost:5601}"
DASHBOARDS_DIR="$(dirname "$0")/../kibana/dashboards"

echo "→ Kibana: импорт дашбордов..."

for f in "$DASHBOARDS_DIR"/*.ndjson; do
  [ -f "$f" ] || continue
  echo "  Импортируем: $(basename "$f")"
  curl -sf -X POST "$KIBANA_URL/api/saved_objects/_import?overwrite=true" \
    -H "kbn-xsrf: true" \
    --form file=@"$f" > /dev/null && echo "    OK"
done

echo "  Kibana дашборды импортированы."

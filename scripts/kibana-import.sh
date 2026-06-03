#!/usr/bin/env bash
# kibana-import.sh — импорт предустановленных дашбордов
set -e

KIBANA_URL="${KIBANA_URL:-http://localhost:5601}"
DASHBOARDS_DIR="$(dirname "$0")/../kibana/dashboards"

echo "→ Kibana: ожидание готовности..."
for i in $(seq 1 30); do
  if curl -sf "$KIBANA_URL/api/status" -H "kbn-xsrf: true" > /dev/null 2>&1; then
    echo "  Kibana готова."
    break
  fi
  echo "  Ожидание... ($i/30)"
  sleep 5
done

echo "→ Kibana: импорт дашбордов..."

# Import 00_index_pattern.ndjson first so all dashboards can reference it
for f in "$DASHBOARDS_DIR"/*.ndjson; do
  [ -f "$f" ] || continue
  echo "  Импортируем: $(basename "$f")"
  curl -sf -X POST "$KIBANA_URL/api/saved_objects/_import?overwrite=true" \
    -H "kbn-xsrf: true" \
    --form file=@"$f" > /dev/null && echo "    OK"
done

echo "→ Kibana: обновление списка полей для index pattern..."
# Без этого Kibana показывает 'поля не найдены' если индекс создан после импорта
curl -sf -X POST "$KIBANA_URL/api/data_views/data_view/audit-events-index-pattern/fields/refresh" \
  -H "kbn-xsrf: true" \
  -H "Content-Type: application/json" \
  -d '{}' > /dev/null && echo "  Поля обновлены." || \
curl -sf -X POST "$KIBANA_URL/api/index_patterns/index_pattern/audit-events-index-pattern/fields/refresh" \
  -H "kbn-xsrf: true" \
  -H "Content-Type: application/json" \
  -d '{}' > /dev/null && echo "  Поля обновлены (legacy API)." || \
echo "  Предупреждение: не удалось обновить поля (обновите вручную в Kibana)."

echo "  Kibana дашборды импортированы."

#!/usr/bin/env bash
# elastic-init.sh — создание index templates в Elasticsearch
# Использование:
#   elastic-init.sh          — только создать/обновить templates (безопасно для перезапуска)
#   elastic-init.sh --reset  — создать templates + удалить старые индексы (нужно при смене маппинга)
set -e

ES_URL="${ELASTICSEARCH_URL:-http://localhost:9200}"
TEMPLATE_NAME="audit-events-template"
RESET="${1:-}"

echo "→ Elasticsearch: ожидание готовности..."
for i in $(seq 1 30); do
  if curl -sf "$ES_URL/_cluster/health" > /dev/null 2>&1; then
    echo "  ES готов."
    break
  fi
  echo "  Ожидание... ($i/30)"
  sleep 3
done

echo "→ Elasticsearch: создание index templates..."

curl -sf -X PUT "$ES_URL/_index_template/app-logs-template" \
  -H "Content-Type: application/json" \
  -d '{
    "index_patterns": ["app-logs-*"],
    "template": {
      "settings": { "number_of_shards": 1, "number_of_replicas": 0 },
      "mappings": {
        "properties": {
          "@timestamp": { "type": "date" },
          "level":   { "type": "keyword" },
          "logger":  { "type": "keyword" },
          "event":   { "type": "text", "fields": { "keyword": { "type": "keyword" } } },
          "error":   { "type": "text", "fields": { "keyword": { "type": "keyword" } } },
          "service": { "type": "keyword" }
        }
      }
    }
  }' && echo "  template 'app-logs-template' OK."

curl -sf -X PUT "$ES_URL/_index_template/$TEMPLATE_NAME" \
  -H "Content-Type: application/json" \
  -d '{
    "index_patterns": ["audit-events-*"],
    "template": {
      "settings": {
        "number_of_shards": 1,
        "number_of_replicas": 0,
        "refresh_interval": "5s"
      },
      "mappings": {
        "properties": {
          "@timestamp":      { "type": "date" },
          "event_id":        { "type": "keyword" },
          "audit_log_id":    { "type": "long" },
          "timestamp":       { "type": "date" },
          "actor_id":        { "type": "keyword" },
          "actor_username":  { "type": "keyword" },
          "target_type":     { "type": "keyword" },
          "target_id":       { "type": "keyword" },
          "operation":       { "type": "keyword" },
          "module":          { "type": "keyword" },
          "result":          { "type": "keyword" },
          "ip_address":      { "type": "ip" },
          "user_agent":      { "type": "text" },
          "details":         { "type": "object", "enabled": true },
          "correlation_id":  { "type": "keyword" },
          "department_code": { "type": "keyword" },
          "position_code":   { "type": "keyword" }
        }
      }
    }
  }' && echo "  template '$TEMPLATE_NAME' OK."

# Удаление индексов — ТОЛЬКО при явном флаге --reset.
# Без флага данные аудита сохраняются при перезапуске контейнеров.
if [ "$RESET" = "--reset" ]; then
  echo "→ --reset: удаление старых индексов с неверным маппингом..."
  curl -sf -X DELETE "$ES_URL/audit-events-*" 2>/dev/null && echo "  audit-events-* удалён." || echo "  audit-events-* не найден."
  curl -sf -X DELETE "$ES_URL/app-logs-*"    2>/dev/null && echo "  app-logs-* удалён."    || echo "  app-logs-* не найден."
  echo "  Индексы будут пересозданы при первой записи."
else
  echo "  Индексы не трогаем (используй --reset для пересоздания)."
fi

echo "→ elastic-init готово."

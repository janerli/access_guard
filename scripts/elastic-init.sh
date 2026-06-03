#!/usr/bin/env bash
# elastic-init.sh — создание index template в Elasticsearch
set -e

ES_URL="${ELASTICSEARCH_URL:-http://localhost:9200}"
TEMPLATE_NAME="audit-events-template"

echo "→ Elasticsearch: ожидание готовности..."
for i in $(seq 1 30); do
  if curl -sf "$ES_URL/_cluster/health" > /dev/null 2>&1; then
    echo "  ES готов."
    break
  fi
  echo "  Ожидание... ($i/30)"
  sleep 3
done

echo "→ Elasticsearch: создание index template..."

curl -sf -X PUT "$ES_URL/_index_template/app-logs-template" \
  -H "Content-Type: application/json" \
  -d '{
    "index_patterns": ["app-logs-*"],
    "template": {
      "settings": { "number_of_shards": 1, "number_of_replicas": 0 },
      "mappings": {
        "properties": {
          "level":   { "type": "keyword" },
          "logger":  { "type": "keyword" },
          "event":   { "type": "text", "fields": { "keyword": { "type": "keyword" } } },
          "error":   { "type": "text", "fields": { "keyword": { "type": "keyword" } } },
          "service": { "type": "keyword" }
        }
      }
    }
  }' && echo "  Index template 'app-logs-template' создан."

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
  }' && echo "  Index template '$TEMPLATE_NAME' создан."

# Удаляем старые индексы с неправильным dynamic mapping (text вместо keyword).
# Они будут пересозданы с правильным маппингом из template при следующей записи.
echo "→ Удаление старых индексов с неверным маппингом (если существуют)..."
curl -sf -X DELETE "$ES_URL/audit-events-*" 2>/dev/null && echo "  audit-events-* удалён." || echo "  audit-events-* не найден, пропуск."
curl -sf -X DELETE "$ES_URL/app-logs-*"    2>/dev/null && echo "  app-logs-* удалён."    || echo "  app-logs-* не найден, пропуск."
echo "→ Готово. Индексы будут пересозданы с правильным маппингом при первой записи."

#!/usr/bin/env bash
# elastic-init.sh — создание index template в Elasticsearch
set -e

ES_URL="${ELASTICSEARCH_URL:-http://localhost:9200}"
TEMPLATE_NAME="audit-events-template"

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

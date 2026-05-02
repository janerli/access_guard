#!/usr/bin/env bash
# reset.sh — Сброс всех хранилищ к чистому состоянию
set -e

echo "=== AccessGuard: полный сброс ==="
echo "ВНИМАНИЕ: все данные будут удалены!"
read -p "Продолжить? (y/N): " confirm
[[ $confirm =~ ^[Yy]$ ]] || { echo "Отменено."; exit 0; }

# Остановить контейнеры
docker compose down -v

# Удалить volumes
docker volume rm -f \
  access_guard_postgres_data \
  access_guard_ldap_data \
  access_guard_ldap_config \
  access_guard_kafka_data \
  access_guard_zookeeper_data \
  access_guard_zookeeper_log \
  access_guard_elasticsearch_data \
  access_guard_reports_files \
  2>/dev/null || true

# Удалить celerybeat файлы
rm -f backend/celerybeat-schedule backend/celerybeat.pid

echo "→ Запуск контейнеров..."
docker compose up -d

echo "→ Ожидание готовности..."
sleep 10

echo "→ Наполнение данными..."
bash "$(dirname "$0")/seed.sh"

echo "=== Сброс завершён. ==="

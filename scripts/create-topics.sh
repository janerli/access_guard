#!/bin/bash
set -e
BS=kafka:9092

kafka-topics --create --if-not-exists --bootstrap-server $BS --partitions 3 --replication-factor 1 --topic hr.events
kafka-topics --create --if-not-exists --bootstrap-server $BS --partitions 3 --replication-factor 1 --topic hr.events.dlq
kafka-topics --create --if-not-exists --bootstrap-server $BS --partitions 3 --replication-factor 1 --topic identity.users
kafka-topics --create --if-not-exists --bootstrap-server $BS --partitions 3 --replication-factor 1 --topic identity.lifecycle
kafka-topics --create --if-not-exists --bootstrap-server $BS --partitions 3 --replication-factor 1 --topic access.roles
kafka-topics --create --if-not-exists --bootstrap-server $BS --partitions 3 --replication-factor 1 --topic access.permissions
kafka-topics --create --if-not-exists --bootstrap-server $BS --partitions 3 --replication-factor 1 --topic access.requests
kafka-topics --create --if-not-exists --bootstrap-server $BS --partitions 6 --replication-factor 1 --config retention.ms=2592000000 --topic audit.events
kafka-topics --create --if-not-exists --bootstrap-server $BS --partitions 3 --replication-factor 1 --config retention.ms=2592000000 --topic monitor.alerts
kafka-topics --create --if-not-exists --bootstrap-server $BS --partitions 3 --replication-factor 1 --topic reports.notifications

echo "=== All topics created ==="
kafka-topics --list --bootstrap-server $BS

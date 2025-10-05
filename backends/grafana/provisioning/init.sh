#!/bin/bash

# Wait for Prometheus to be available
echo "Waiting for Prometheus..."
until curl -s "http://prometheus:9090/api/v1/status/config" > /dev/null; do
  sleep 1
done
echo "Prometheus is up!"

# Wait for Loki to be available
echo "Waiting for Loki..."
until curl -s "http://loki:3100/ready" > /dev/null; do
  sleep 1
done
echo "Loki is up!"

# Wait for Tempo to be available
echo "Waiting for Tempo..."
until curl -s "http://tempo:3200/ready" > /dev/null; do
  sleep 1
done
echo "Tempo is up!"

echo "All datasources are available!"

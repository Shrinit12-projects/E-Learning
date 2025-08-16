#!/bin/bash
set -e  # exit on error

echo "🛑 Stopping main application stack..."
docker compose down

# Go into the database services directory
cd elearningdb

echo "🛑 Stopping MongoDB and Redis containers..."
docker compose down -v

echo "🧹 Stopping individual MongoDB and Redis containers (if still running)..."
docker stop elearning-mongo elearning-redis 2>/dev/null || true

echo "🗑 Removing MongoDB and Redis containers..."
docker rm elearning-mongo elearning-redis 2>/dev/null || true

echo "🧼 Removing unused networks..."
docker network prune -f

# Optional: remove data volumes (⚠️ irreversible)
# echo "💣 Removing MongoDB & Redis volumes..."
# docker volume rm elearningdb_mongo-data elearningdb_redis-data 2>/dev/null || true

# Back to project root
cd ..

echo "All services, containers, and networks stopped/removed."

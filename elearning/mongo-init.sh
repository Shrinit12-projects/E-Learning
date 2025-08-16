#!/usr/bin/env bash
set -euo pipefail

echo "⏳ Waiting for Mongo to accept connections..."
until mongosh --host elearning-mongo:27017 --eval "db.adminCommand('ping')" >/dev/null 2>&1; do
  sleep 2
done
echo "✅ Mongo is up."

echo "🔍 Checking replica set status..."
# If rs.status() fails, we attempt to initiate
if ! mongosh --host elearning-mongo:27017 --eval "rs.status()" >/dev/null 2>&1; then
  echo "🚀 Initiating replica set rs0..."
  mongosh --host elearning-mongo:27017 <<'EOF'
rs.initiate({
  _id: "rs0",
  members: [{ _id: 0, host: "elearning-mongo:27017" }]
})
EOF
  echo "✅ Replica set initiated."
else
  echo "ℹ️  Replica set already configured."
fi

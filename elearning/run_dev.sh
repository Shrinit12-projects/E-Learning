#!/bin/bash
set -e  # exit on error
cd elearningdb

echo "Starting MongoDB and Redis containers..."
docker compose up -d mongo redis

echo "Waiting for MongoDB to be ready..."
# Wait until mongosh can connect
until docker exec elearning-mongo mongosh --quiet --eval "db.adminCommand('ping')" > /dev/null 2>&1; do
  sleep 1
done

echo "MongoDB is up. Initiating replica set..."
# Try to initiate the replica set — ignore errors if already initialized
docker exec elearning-mongo mongosh --quiet --eval "
try {
  rs.initiate({
    _id: 'rs0',
    members: [{ _id: 0, host: 'mongo:27017' }]
  });
} catch (e) {
  print('Replica set likely already initiated: ' + e);
}
"

echo "Replica set status:"
docker exec elearning-mongo mongosh --quiet --eval "rs.status()"

echo "All services are ready!"

cd ..

docker compose up --build -d

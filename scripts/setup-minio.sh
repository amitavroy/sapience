#!/bin/bash

# MinIO Setup Script for Development
# This script creates the default bucket for the Sapience application

# Load environment variables from backend/.env if it exists
if [ -f "./backend/.env" ]; then
    echo "📄 Loading environment variables from backend/.env..."
    export $(grep -v '^#' ./backend/.env | xargs)
fi

# Load environment variables from frontend/.env.local if it exists
if [ -f "./frontend/.env.local" ]; then
    echo "📄 Loading environment variables from frontend/.env.local..."
    export $(grep -v '^#' ./frontend/.env.local | xargs)
fi

# Set default values if not provided
MINIO_ROOT_USER=${MINIO_ROOT_USER:-minioadmin}
MINIO_ROOT_PASSWORD=${MINIO_ROOT_PASSWORD:-minioadmin123}
MINIO_BUCKET_NAME=${MINIO_BUCKET_NAME:-sapience-dev}

echo "🚀 Setting up MinIO for Sapience development..."

# Wait for MinIO to be ready
echo "⏳ Waiting for MinIO to be ready..."
until curl -f http://localhost:9000/minio/health/live > /dev/null 2>&1; do
    echo "Waiting for MinIO..."
    sleep 2
done

echo "✅ MinIO is ready!"

# Create the default bucket
echo "📦 Creating default bucket '$MINIO_BUCKET_NAME'..."
docker compose exec minio sh -c "mc alias set myminio http://localhost:9000 $MINIO_ROOT_USER $MINIO_ROOT_PASSWORD"
docker compose exec minio sh -c "mc mb myminio/$MINIO_BUCKET_NAME --ignore-existing"
docker compose exec minio sh -c "mc policy set public myminio/$MINIO_BUCKET_NAME"

echo "✅ MinIO setup complete!"
echo ""
echo "🌐 MinIO Console: http://localhost:9001"
echo "🔑 Username: $MINIO_ROOT_USER"
echo "🔑 Password: $MINIO_ROOT_PASSWORD"
echo "📁 Default Bucket: $MINIO_BUCKET_NAME"
echo ""
echo "📚 MinIO API Endpoint: http://localhost:9000"
echo "🔧 Access Key: $MINIO_ROOT_USER"
echo "🔧 Secret Key: $MINIO_ROOT_PASSWORD"

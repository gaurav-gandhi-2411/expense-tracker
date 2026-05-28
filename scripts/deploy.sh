#!/usr/bin/env bash
# Deploy expense-tracker to GCP Cloud Run (us-central1 always-free tier).
#
# BEFORE RUNNING:
#   1. Confirm the target GCP project:
#      gcloud config get-value project
#      gcloud config set project YOUR_PROJECT_ID   # change if needed
#
#   2. Ensure .env has the four required secrets:
#      DATABASE_URL           (Supabase session-pooler URL, postgresql+psycopg2://...)
#      SUPABASE_JWT_SECRET    (Supabase project settings → API → JWT Secret)
#      SUPABASE_URL           (Supabase project URL, https://xxxx.supabase.co)
#      GROQ_API_KEY
#
#   3. Run from the project root:
#      bash scripts/deploy.sh
#
# NOTES:
#   - First build takes 5-10 min (torch + prophet are large).
#   - First request after idle takes 60-120s (cold start — min-instances=0).
#   - --allow-unauthenticated: app-layer JWT auth is used, not platform-layer.
#   - --min-instances 0: stays within the Cloud Run always-free tier.

set -euo pipefail

# Load .env so secrets don't need to be hardcoded in this script.
if [ -f .env ]; then
    set -a
    # shellcheck disable=SC1091
    source .env
    set +a
fi

# Validate required variables are set and non-empty.
: "${DATABASE_URL:?DATABASE_URL must be set in .env}"
: "${SUPABASE_JWT_SECRET:?SUPABASE_JWT_SECRET must be set in .env}"
: "${SUPABASE_URL:?SUPABASE_URL must be set in .env}"
: "${GROQ_API_KEY:?GROQ_API_KEY must be set in .env}"

echo "GCP project : $(gcloud config get-value project)"
echo "Region      : us-central1"
echo ""

echo "Enabling required Google Cloud APIs (idempotent)..."
gcloud services enable \
    run.googleapis.com \
    cloudbuild.googleapis.com \
    artifactregistry.googleapis.com

echo ""
echo "Building and deploying to Cloud Run..."
echo "(First build typically takes 5-10 minutes due to image size.)"
echo ""

gcloud run deploy expense-tracker \
    --source . \
    --region us-central1 \
    --memory 2Gi \
    --cpu 1 \
    --max-instances 2 \
    --min-instances 0 \
    --timeout 300 \
    --allow-unauthenticated \
    --set-env-vars "DATABASE_URL=${DATABASE_URL},SUPABASE_JWT_SECRET=${SUPABASE_JWT_SECRET},SUPABASE_URL=${SUPABASE_URL},GROQ_API_KEY=${GROQ_API_KEY},RUN_MIGRATIONS_ON_STARTUP=true,ADMIN_ENABLED=false,CORS_ALLOWED_ORIGINS="

echo ""
echo "Deployment complete."
echo "IMPORTANT: The first request after the service goes idle will take 60-120 seconds"
echo "           (cold start with sentence-transformers model load). This is expected."

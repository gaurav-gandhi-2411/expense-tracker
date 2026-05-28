# Deploy expense-tracker to GCP Cloud Run (us-central1 always-free tier).
#
# BEFORE RUNNING:
#   1. Confirm the target GCP project:
#      gcloud config get-value project
#      gcloud config set project YOUR_PROJECT_ID   # change if needed
#
#   2. Ensure .env has the four required secrets:
#      DATABASE_URL           (Supabase session-pooler URL, postgresql+psycopg2://...)
#      SUPABASE_JWT_SECRET    (Supabase project settings -> API -> JWT Secret)
#      SUPABASE_URL           (Supabase project URL, https://xxxx.supabase.co)
#      GROQ_API_KEY
#
#   3. Run from the project root:
#      .\scripts\deploy.ps1
#
# NOTES:
#   - First build takes 5-10 min (torch + prophet are large).
#   - First request after idle takes 60-120s (cold start -- min-instances=0).
#   - --allow-unauthenticated: app-layer JWT auth is used, not platform-layer.
#   - --min-instances 0: stays within the Cloud Run always-free tier.

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# Load .env so secrets don't need to be hardcoded in this script.
if (Test-Path .env) {
    Get-Content .env | ForEach-Object {
        if ($_ -match '^([^#\s][^=]*)=(.*)$') {
            $key = $Matches[1].Trim()
            $val = $Matches[2].Trim()
            [System.Environment]::SetEnvironmentVariable($key, $val, 'Process')
        }
    }
}

# Validate required variables.
$required = @("DATABASE_URL", "SUPABASE_JWT_SECRET", "SUPABASE_URL", "GROQ_API_KEY")
foreach ($var in $required) {
    if (-not [System.Environment]::GetEnvironmentVariable($var, 'Process')) {
        Write-Error "$var must be set in .env"
        exit 1
    }
}

$dbUrl         = [System.Environment]::GetEnvironmentVariable("DATABASE_URL",        'Process')
$jwtSecret     = [System.Environment]::GetEnvironmentVariable("SUPABASE_JWT_SECRET", 'Process')
$supabaseUrl   = [System.Environment]::GetEnvironmentVariable("SUPABASE_URL",        'Process')
$groqKey       = [System.Environment]::GetEnvironmentVariable("GROQ_API_KEY",        'Process')

Write-Host "GCP project : $(gcloud config get-value project)"
Write-Host "Region      : us-central1"
Write-Host ""

Write-Host "Enabling required Google Cloud APIs (idempotent)..."
gcloud services enable `
    run.googleapis.com `
    cloudbuild.googleapis.com `
    artifactregistry.googleapis.com

Write-Host ""
Write-Host "Building and deploying to Cloud Run..."
Write-Host "(First build typically takes 5-10 minutes due to image size.)"
Write-Host ""

$envVars = "DATABASE_URL=${dbUrl},SUPABASE_JWT_SECRET=${jwtSecret},SUPABASE_URL=${supabaseUrl},GROQ_API_KEY=${groqKey},RUN_MIGRATIONS_ON_STARTUP=true,ADMIN_ENABLED=false,CORS_ALLOWED_ORIGINS="

gcloud run deploy expense-tracker `
    --source . `
    --region us-central1 `
    --memory 2Gi `
    --cpu 1 `
    --max-instances 2 `
    --min-instances 0 `
    --timeout 300 `
    --allow-unauthenticated `
    --set-env-vars $envVars

Write-Host ""
Write-Host "Deployment complete."
Write-Host "IMPORTANT: The first request after the service goes idle will take 60-120 seconds"
Write-Host "           (cold start with sentence-transformers model load). This is expected."

#!/usr/bin/env bash
# Build and deploy the current checkout with Cloud Build.
#
#   export PROJECT_ID=mcpledger-prod REGION=us-central1
#   PUBLIC_URL=https://app.mcpledger.dev ./deploy/gcp/deploy.sh
#
# First deploy, before you know the URL: leave PUBLIC_URL unset. The script uses a
# placeholder, prints the Cloud Run URL, and you deploy once more with it.
set -euo pipefail
: "${PROJECT_ID:?set PROJECT_ID}"
REGION="${REGION:-us-central1}"
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

URL="${PUBLIC_URL:-}"
if [ -z "$URL" ]; then
  URL="$(gcloud run services describe mcpledger --region "$REGION" --project "$PROJECT_ID" \
          --format='value(status.url)' 2>/dev/null || true)"
  URL="${URL:-https://placeholder.invalid}"
  echo "PUBLIC_URL not set; using $URL"
fi

subs="_REGION=$REGION,_PUBLIC_URL=$URL"
[ -n "${PADDLE_ENV:-}" ] && subs="$subs,_PADDLE_ENV=$PADDLE_ENV"
[ -n "${PADDLE_CLIENT_TOKEN:-}" ] && subs="$subs,_PADDLE_CLIENT_TOKEN=$PADDLE_CLIENT_TOKEN"
[ -n "${PADDLE_PRICE_TEAM:-}" ] && subs="$subs,_PADDLE_PRICE_TEAM=$PADDLE_PRICE_TEAM"
[ -n "${PADDLE_PRICE_BUSINESS:-}" ] && subs="$subs,_PADDLE_PRICE_BUSINESS=$PADDLE_PRICE_BUSINESS"
[ -n "${MIN_INSTANCES:-}" ] && subs="$subs,_MIN_INSTANCES=$MIN_INSTANCES"

gcloud builds submit "$ROOT" --project "$PROJECT_ID" --region "$REGION" \
  --config "$ROOT/deploy/gcp/cloudbuild.yaml" \
  --service-account "projects/$PROJECT_ID/serviceAccounts/mcpledger-build@$PROJECT_ID.iam.gserviceaccount.com" \
  --substitutions "$subs"

echo
echo "Live at: $(gcloud run services describe mcpledger --region "$REGION" --project "$PROJECT_ID" --format='value(status.url)')"

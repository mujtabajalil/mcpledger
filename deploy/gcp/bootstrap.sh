#!/usr/bin/env bash
# One-time setup of everything MCPLedger needs in a Google Cloud project.
# Safe to re-run: existing resources are left alone.
#
#   export PROJECT_ID=mcpledger-prod REGION=us-central1
#   ./deploy/gcp/bootstrap.sh
#
# Creates: APIs, Artifact Registry repo, Cloud SQL Postgres 16, database + user,
# Secret Manager secrets, a runtime service account and a build service account.
set -euo pipefail

: "${PROJECT_ID:?set PROJECT_ID}"
REGION="${REGION:-us-central1}"
REPO="${REPO:-mcpledger}"
DB_INSTANCE="${DB_INSTANCE:-mcpledger-db}"
DB_TIER="${DB_TIER:-db-g1-small}"
DB_NAME="${DB_NAME:-mcpledger}"
DB_USER="${DB_USER:-mcpledger}"
RUN_SA="mcpledger-run@${PROJECT_ID}.iam.gserviceaccount.com"
BUILD_SA="mcpledger-build@${PROJECT_ID}.iam.gserviceaccount.com"

say() { printf '\n\033[1m== %s\033[0m\n' "$*"; }
exists() { "$@" >/dev/null 2>&1; }

gcloud config set project "$PROJECT_ID" >/dev/null

say "Enabling APIs"
gcloud services enable run.googleapis.com sqladmin.googleapis.com artifactregistry.googleapis.com \
  cloudbuild.googleapis.com secretmanager.googleapis.com iam.googleapis.com logging.googleapis.com \
  monitoring.googleapis.com

say "Artifact Registry repository: $REPO"
exists gcloud artifacts repositories describe "$REPO" --location "$REGION" || \
  gcloud artifacts repositories create "$REPO" --repository-format=docker --location "$REGION" \
    --description "MCPLedger images"

say "Cloud SQL instance: $DB_INSTANCE ($DB_TIER). This takes 5-10 minutes the first time"
if ! exists gcloud sql instances describe "$DB_INSTANCE"; then
  gcloud sql instances create "$DB_INSTANCE" \
    --database-version=POSTGRES_16 --edition=ENTERPRISE --tier="$DB_TIER" --region="$REGION" \
    --storage-type=SSD --storage-size=10 --storage-auto-increase \
    --backup-start-time=21:00 --enable-point-in-time-recovery --retained-backups-count=14 \
    --availability-type=zonal --deletion-protection
fi
exists gcloud sql databases describe "$DB_NAME" --instance "$DB_INSTANCE" || \
  gcloud sql databases create "$DB_NAME" --instance "$DB_INSTANCE"
CONN="$(gcloud sql instances describe "$DB_INSTANCE" --format='value(connectionName)')"

say "Database user and DATABASE_URL secret"
if ! exists gcloud secrets describe mcpledger-database-url; then
  DB_PASS="$(openssl rand -hex 24)"
  if exists gcloud sql users describe "$DB_USER" --instance "$DB_INSTANCE"; then
    gcloud sql users set-password "$DB_USER" --instance "$DB_INSTANCE" --password "$DB_PASS"
  else
    gcloud sql users create "$DB_USER" --instance "$DB_INSTANCE" --password "$DB_PASS"
  fi
  printf 'postgresql+psycopg://%s:%s@/%s?host=/cloudsql/%s' "$DB_USER" "$DB_PASS" "$DB_NAME" "$CONN" | \
    gcloud secrets create mcpledger-database-url --replication-policy=automatic --data-file=-
fi

say "Paddle webhook secret (placeholder until you connect Paddle)"
exists gcloud secrets describe mcpledger-paddle-webhook-secret || \
  printf 'not-configured' | gcloud secrets create mcpledger-paddle-webhook-secret --replication-policy=automatic --data-file=-

say "Service accounts"
exists gcloud iam service-accounts describe "$RUN_SA" || \
  gcloud iam service-accounts create mcpledger-run --display-name "MCPLedger runtime"
exists gcloud iam service-accounts describe "$BUILD_SA" || \
  gcloud iam service-accounts create mcpledger-build --display-name "MCPLedger Cloud Build"

for role in roles/cloudsql.client roles/secretmanager.secretAccessor roles/logging.logWriter roles/monitoring.metricWriter; do
  gcloud projects add-iam-policy-binding "$PROJECT_ID" --member "serviceAccount:$RUN_SA" --role "$role" \
    --condition=None >/dev/null
done
for role in roles/run.admin roles/artifactregistry.writer roles/logging.logWriter roles/cloudsql.client \
            roles/secretmanager.secretAccessor; do
  gcloud projects add-iam-policy-binding "$PROJECT_ID" --member "serviceAccount:$BUILD_SA" --role "$role" \
    --condition=None >/dev/null
done
# The build account deploys Cloud Run services/jobs that run as the runtime account.
gcloud iam service-accounts add-iam-policy-binding "$RUN_SA" --member "serviceAccount:$BUILD_SA" \
  --role roles/iam.serviceAccountUser >/dev/null

say "Done"
cat <<EOF
Cloud SQL connection: $CONN
Next:
  1. First deploy:   ./deploy/gcp/deploy.sh
  2. Then set PUBLIC_URL to the URL it prints (or your domain) and deploy again.
EOF

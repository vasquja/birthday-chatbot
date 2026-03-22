#!/bin/bash
# deploy.sh — Deploy both Cloud Functions
# Prerequisites: gcloud CLI installed and authenticated, PROJECT_ID set

set -e

PROJECT_ID="${GCP_PROJECT_ID:?Set GCP_PROJECT_ID}"
REGION="us-east1"
SPACE_NAME="${CHAT_SPACE_NAME:?Set CHAT_SPACE_NAME}"
PLACES_KEY="${GOOGLE_PLACES_API_KEY:?Set GOOGLE_PLACES_API_KEY}"

echo "Deploying bot_handler..."
gcloud functions deploy bot_handler \
  --gen2 \
  --runtime=python311 \
  --region="$REGION" \
  --source=. \
  --entry-point=bot_handler \
  --trigger-http \
  --allow-unauthenticated \
  --set-env-vars="GCP_PROJECT_ID=$PROJECT_ID,CHAT_SPACE_NAME=$SPACE_NAME,GOOGLE_PLACES_API_KEY=$PLACES_KEY" \
  --project="$PROJECT_ID"

echo "Deploying reminder_checker..."
gcloud functions deploy reminder_checker \
  --gen2 \
  --runtime=python311 \
  --region="$REGION" \
  --source=. \
  --entry-point=reminder_checker \
  --trigger-http \
  --no-allow-unauthenticated \
  --set-env-vars="GCP_PROJECT_ID=$PROJECT_ID,CHAT_SPACE_NAME=$SPACE_NAME,GOOGLE_PLACES_API_KEY=$PLACES_KEY" \
  --project="$PROJECT_ID"

echo ""
echo "Done! Copy the bot_handler URL into Google Cloud Console → Google Chat API → App configuration."
echo "Then create a Cloud Scheduler job pointing to reminder_checker URL with OIDC auth, schedule: '0 9 * * *' (America/New_York)."

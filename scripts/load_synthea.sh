#!/bin/bash

# Synthea Loader Script
# Loads synthetic patient data into the HAPI FHIR server

set -e

# Default values
NUM_PATIENTS=${1:-100}
FHIR_BASE_URL=${FHIR_BASE_URL:-"http://localhost:8080/fhir"}
SYNTHEA_JAR_URL="https://github.com/synthetichealth/synthea/releases/download/master-branch-latest/synthea-with-dependencies.jar"
SYNTHEA_JAR="./synthea.jar"

echo "🏥 Synthea Patient Loader"
echo "========================="
echo "Number of patients: $NUM_PATIENTS"
echo "FHIR Server: $FHIR_BASE_URL"
echo ""

# Check if FHIR server is running
echo "🔍 Checking FHIR server status..."
if ! curl -f "$FHIR_BASE_URL/metadata" > /dev/null 2>&1; then
    echo "❌ Error: FHIR server is not running at $FHIR_BASE_URL"
    echo "Please start the services with: docker-compose up -d"
    exit 1
fi
echo "✅ FHIR server is running"

# Download Synthea if not present
if [ ! -f "$SYNTHEA_JAR" ]; then
    echo "📥 Downloading Synthea..."
    curl -L -o "$SYNTHEA_JAR" "$SYNTHEA_JAR_URL"
    echo "✅ Synthea downloaded"
else
    echo "✅ Synthea already present"
fi

# Create output directory
mkdir -p ./data/synthea

# Generate patients
echo "👥 Generating $NUM_PATIENTS patients..."
java -jar "$SYNTHEA_JAR" \
    --population $NUM_PATIENTS \
    --exporter.fhir.export true \
    --exporter.fhir.directory ./data/synthea \
    --exporter.fhir.transaction_bundle true \
    --exporter.baseDirectory ./data/synthea

echo "✅ Patient generation complete"

# Load patients into FHIR server
echo "📤 Loading patients into FHIR server..."

# Find the transaction bundle file
BUNDLE_FILE=$(find ./data/synthea -name "*.json" | head -1)

if [ -z "$BUNDLE_FILE" ]; then
    echo "❌ Error: No transaction bundle found"
    exit 1
fi

echo "📄 Using bundle file: $BUNDLE_FILE"

# Post the transaction bundle
echo "🚀 Posting transaction bundle..."
RESPONSE=$(curl -s -w "%{http_code}" -X POST \
    -H "Content-Type: application/fhir+json" \
    -d @"$BUNDLE_FILE" \
    "$FHIR_BASE_URL")

HTTP_CODE="${RESPONSE: -3}"
RESPONSE_BODY="${RESPONSE%???}"

if [ "$HTTP_CODE" -eq 200 ] || [ "$HTTP_CODE" -eq 201 ]; then
    echo "✅ Successfully loaded patients into FHIR server"
    echo "📊 Response: $RESPONSE_BODY"
else
    echo "❌ Error loading patients: HTTP $HTTP_CODE"
    echo "📄 Response: $RESPONSE_BODY"
    exit 1
fi

echo ""
echo "🎉 Patient loading complete!"
echo "📊 You can now query patients at: $FHIR_BASE_URL/Patient"
echo "🔍 Example: curl '$FHIR_BASE_URL/Patient?_count=5'" 
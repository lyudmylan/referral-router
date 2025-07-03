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

# Load hospital information first
echo "🏥 Loading hospital information..."
HOSPITAL_FILES=$(find ./data/synthea/fhir -name "hospitalInformation*.json")
for hospital_file in $HOSPITAL_FILES; do
    echo "📄 Loading hospital: $hospital_file"
    RESPONSE=$(curl -s -w "%{http_code}" -X POST \
        -H "Content-Type: application/fhir+json" \
        -d @"$hospital_file" \
        "$FHIR_BASE_URL")
    
    HTTP_CODE="${RESPONSE: -3}"
    if [ "$HTTP_CODE" -eq 200 ] || [ "$HTTP_CODE" -eq 201 ]; then
        echo "✅ Hospital loaded successfully"
    else
        echo "⚠️  Hospital load returned HTTP $HTTP_CODE (may already exist)"
    fi
done

# Load practitioner information
echo "👨‍⚕️ Loading practitioner information..."
PRACTITIONER_FILES=$(find ./data/synthea/fhir -name "practitionerInformation*.json")
for practitioner_file in $PRACTITIONER_FILES; do
    echo "📄 Loading practitioner: $practitioner_file"
    RESPONSE=$(curl -s -w "%{http_code}" -X POST \
        -H "Content-Type: application/fhir+json" \
        -d @"$practitioner_file" \
        "$FHIR_BASE_URL")
    
    HTTP_CODE="${RESPONSE: -3}"
    if [ "$HTTP_CODE" -eq 200 ] || [ "$HTTP_CODE" -eq 201 ]; then
        echo "✅ Practitioner loaded successfully"
    else
        echo "⚠️  Practitioner load returned HTTP $HTTP_CODE (may already exist)"
    fi
done

# Find and load patient bundles
echo "👥 Loading patient bundles..."
PATIENT_FILES=$(find ./data/synthea/fhir -name "*_*.json" | grep -v "hospitalInformation" | grep -v "practitionerInformation")

if [ -z "$PATIENT_FILES" ]; then
    echo "❌ Error: No patient bundles found"
    echo "🔍 Checking available files:"
    find ./data/synthea/fhir -name "*.json" | head -5
    exit 1
fi

for patient_file in $PATIENT_FILES; do
    echo "📄 Loading patient: $patient_file"
    RESPONSE=$(curl -s -w "%{http_code}" -X POST \
        -H "Content-Type: application/fhir+json" \
        -d @"$patient_file" \
        "$FHIR_BASE_URL")
    
    HTTP_CODE="${RESPONSE: -3}"
    RESPONSE_BODY="${RESPONSE%???}"
    
    if [ "$HTTP_CODE" -eq 200 ] || [ "$HTTP_CODE" -eq 201 ]; then
        echo "✅ Patient loaded successfully"
    else
        echo "❌ Error loading patient: HTTP $HTTP_CODE"
        echo "📄 Response: $RESPONSE_BODY"
    fi
done

echo ""
echo "🎉 Patient loading complete!"
echo "📊 You can now query patients at: $FHIR_BASE_URL/Patient"
echo "🔍 Example: curl '$FHIR_BASE_URL/Patient?_count=5'" 
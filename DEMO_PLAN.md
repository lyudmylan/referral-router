# Referral Router Demo Plan

## Prerequisites Check

### 1. System Requirements
- ✅ macOS/Linux/Windows with Docker support
- ✅ Python 3.11+ installed
- ✅ Docker and Docker Compose installed
- ✅ Git installed
- ✅ OpenAI API key

### 2. Environment Setup
```bash
# Clone the repository
git clone https://github.com/lyudmylan/referral-router.git
cd referral-router

# Install Poetry (if not already installed)
pipx install poetry
pipx ensurepath

# Install dependencies
poetry install --with dev

# Create .env file with your OpenAI API key
echo "OPENAI_API_KEY=your_openai_api_key_here" > .env
```

## Demo Execution Steps

### Step 1: Start All Services
```bash
# Build and start all Docker services
docker-compose up -d

# Verify services are running
docker ps

# Check service health (wait 30-60 seconds for startup)
curl http://localhost:8080/fhir/metadata  # HAPI FHIR
curl http://localhost:7001/health         # PDF Service  
curl http://localhost:7002/health         # EMPI Service
```

**Expected Output:**
- All containers should show "Up" status
- Health endpoints should return 200 OK
- PDF service on port 7001 (not 7000 due to macOS AirPlay conflict)

### Step 2: Load Synthea Test Data
```bash
# Load synthetic patient and practitioner data
./scripts/load_synthea.sh

# Verify data was loaded
curl http://localhost:8080/fhir/Patient?_count=5 | jq '.entry[]?.resource.id'
curl http://localhost:8080/fhir/Practitioner?_count=5 | jq '.entry[]?.resource.id'
```

**Expected Output:**
- Patient IDs: ["138", "250", "602", ...]
- Practitioner IDs: ["126", "128", "130", ...]
- No errors in loading process

**Note:** This step is crucial for the referral router to work properly, as it needs real patient and practitioner references in the FHIR server.

### Step 3: Test PDF Extraction Service
```bash
# Test PDF extraction with sample file
curl -X POST http://localhost:7001/extract \
  -F "file=@data/sample_referral.pdf"
```

**Expected Output:**
- HTTP 200 response
- JSON with extracted text content

### Step 4: Test EMPI Service
```bash
# Test patient lookup
curl "http://localhost:7002/patient?email=john.doe@email.com"
```

**Expected Output:**
- HTTP 200 response
- JSON with patient information

### Step 5: Run Complete Demo
```bash
# Process sample referral
poetry run python router.py data/sample_referral.pdf
```

**Expected Output:**
```
🚀 Initializing Referral Router...
📄 Processing referral: data/sample_referral.pdf
2025-07-02 11:07:08,900 - agent_app.main - INFO - Extracting data from PDF: data/sample_referral.pdf
2025-07-02 11:07:09,004 - httpx - INFO - HTTP Request: POST http://localhost:7001/extract "HTTP/1.1 200 OK"
2025-07-02 11:07:09,005 - agent_app.main - INFO - Starting referral processing workflow
[OpenAI API calls for generation and validation]
✅ Referral processed successfully!
🆔 Resource ID: [ID or None]
🔄 Retry count: [0-3]

📋 Final FHIR ServiceRequest:
{
  "resourceType": "ServiceRequest",
  "status": "active",
  "intent": "order",
  ...
}

📦 Posting Result:
{
  "success": true/false,
  "status_code": 200/201,
  "resource_id": "...",
  ...
}
```

### Step 6: Verify FHIR Store
```bash
# Check if ServiceRequest was posted (if successful)
curl http://localhost:8080/fhir/ServiceRequest
```

## Troubleshooting Guide

### Common Issues

#### 1. Port 7000 Already in Use (macOS)
**Problem:** `curl: (7) Failed to connect to localhost port 7000`
**Solution:** PDF service runs on port 7001, not 7000
```bash
curl http://localhost:7001/health  # Correct port
```

#### 2. OpenAI API Key Missing
**Problem:** `openai.OpenAIError: The api_key client option must be set`
**Solution:** Ensure `.env` file exists with valid API key
```bash
echo "OPENAI_API_KEY=sk-..." > .env
```

#### 3. Import Errors
**Problem:** `ModuleNotFoundError: No module named 'graph'`
**Solution:** Use Poetry environment
```bash
poetry run python router.py data/sample_referral.pdf
```

#### 4. Docker Services Not Starting
**Problem:** Services fail to start or are unhealthy
**Solution:** Check logs and restart
```bash
docker-compose logs
docker-compose down && docker-compose up -d
```

#### 5. PDF Extraction Fails
**Problem:** `[Errno 8] nodename nor servname provided`
**Solution:** Verify PDF service is running on correct port
```bash
docker ps | grep pdfsvc
curl http://localhost:7001/health
```

#### 6. No Patients/Practitioners Found
**Problem:** `No patients found in FHIR server. Please ensure patients are loaded before processing referrals.`
**Solution:** Load Synthea test data
```bash
./scripts/load_synthea.sh
curl http://localhost:8080/fhir/Patient?_count=1  # Verify patients exist
```

#### 7. Java Version Issues (Synthea)
**Problem:** `java.lang.UnsupportedClassVersionError: Unsupported major.minor version`
**Solution:** Update Java to version 11+
```bash
# macOS
brew install openjdk@11
export JAVA_HOME=/opt/homebrew/opt/openjdk@11

# Linux
sudo apt-get install openjdk-11-jdk
```

### Service Status Commands
```bash
# Check all services
make status

# View service logs
make logs

# Restart services
make down && make up

# Clean restart
make reset
```

## Demo Variations

### 1. With Patient Email
```bash
poetry run python router.py data/sample_referral.pdf john.doe@email.com
```

### 2. Different PDF Files
```bash
# Use your own PDF
poetry run python router.py /path/to/your/referral.pdf
```

### 3. Verbose Logging
```bash
# Set logging level
export LOG_LEVEL=DEBUG
poetry run python router.py data/sample_referral.pdf
```

## Success Criteria

✅ **Demo is successful when:**
- All services start without errors
- PDF extraction returns valid JSON
- EMPI lookup returns patient data
- OpenAI API calls complete successfully
- FHIR ServiceRequest is generated
- CLI shows success message with retry count
- No critical errors in logs

## Performance Expectations

- **Service Startup:** 30-60 seconds
- **PDF Extraction:** 1-3 seconds
- **LLM Processing:** 10-30 seconds (depends on API response time)
- **Total Demo Time:** 1-2 minutes

## Cleanup

```bash
# Stop all services
docker-compose down

# Remove volumes (optional)
docker-compose down -v

# Clean up temporary files
make clean
```

---

**Last Updated:** July 2, 2025
**Tested On:** macOS with Docker Desktop
**Status:** ✅ Verified Working 
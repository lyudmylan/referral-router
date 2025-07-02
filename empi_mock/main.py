import logging
from typing import Dict, Any, Optional
from fastapi import FastAPI, Query
from pydantic import BaseModel

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="EMPI Mock Service", version="0.1.0")

class PatientResponse(BaseModel):
    success: bool
    patient: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

class HealthResponse(BaseModel):
    status: str
    version: str

# Mock patient database
MOCK_PATIENTS = {
    "john.doe@email.com": {
        "id": "patient-001",
        "name": "John Doe",
        "date_of_birth": "1985-03-15",
        "gender": "male",
        "email": "john.doe@email.com",
        "phone": "+1-555-0123",
        "address": {
            "street": "123 Main St",
            "city": "Anytown",
            "state": "CA",
            "zip": "90210"
        }
    },
    "jane.smith@email.com": {
        "id": "patient-002", 
        "name": "Jane Smith",
        "date_of_birth": "1990-07-22",
        "gender": "female",
        "email": "jane.smith@email.com",
        "phone": "+1-555-0456",
        "address": {
            "street": "456 Oak Ave",
            "city": "Somewhere",
            "state": "NY",
            "zip": "10001"
        }
    }
}

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    return HealthResponse(status="healthy", version="0.1.0")

@app.get("/patient", response_model=PatientResponse)
async def lookup_patient(
    email: Optional[str] = Query(None, description="Patient email"),
    name: Optional[str] = Query(None, description="Patient name"),
    id: Optional[str] = Query(None, description="Patient ID")
):
    """
    Mock patient lookup endpoint
    
    Returns mock patient data for testing purposes
    """
    try:
        # Simple lookup logic
        if email and email in MOCK_PATIENTS:
            return PatientResponse(
                success=True,
                patient=MOCK_PATIENTS[email]
            )
        elif name:
            # Search by name (case insensitive)
            for patient in MOCK_PATIENTS.values():
                if patient["name"].lower() == name.lower():
                    return PatientResponse(
                        success=True,
                        patient=patient
                    )
        elif id:
            # Search by ID
            for patient in MOCK_PATIENTS.values():
                if patient["id"] == id:
                    return PatientResponse(
                        success=True,
                        patient=patient
                    )
        
        # Return a default patient if no match found
        default_patient = {
            "id": "patient-default",
            "name": "Default Patient",
            "date_of_birth": "1980-01-01",
            "gender": "unknown",
            "email": "default@example.com",
            "phone": "+1-555-0000",
            "address": {
                "street": "Default St",
                "city": "Default City",
                "state": "XX",
                "zip": "00000"
            }
        }
        
        return PatientResponse(
            success=True,
            patient=default_patient
        )
        
    except Exception as e:
        logger.error(f"Patient lookup failed: {e}")
        return PatientResponse(
            success=False,
            error=str(e)
        )

@app.get("/")
async def root():
    """Root endpoint with service information"""
    return {
        "service": "EMPI Mock Service",
        "version": "0.1.0",
        "endpoints": {
            "health": "/health",
            "patient": "/patient"
        },
        "available_patients": list(MOCK_PATIENTS.keys())
    } 
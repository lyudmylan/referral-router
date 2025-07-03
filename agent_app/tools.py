import json
import logging
import sqlite3
from typing import Dict, Any, Optional, List
from pathlib import Path
import httpx
from fhirclient import client
from fhirclient.models import servicerequest

logger = logging.getLogger(__name__)

class FHIRTools:
    """Tools for interacting with FHIR servers"""
    
    def __init__(self, base_url: str = "http://localhost:8080/fhir"):
        self.base_url = base_url
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def validate_fhir(self, resource_json: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate a FHIR resource using the $validate operation
        
        Args:
            resource_json: The FHIR resource as a dictionary
            
        Returns:
            Dict with 'valid' boolean and 'errors' list if any
        """
        try:
            # First try to parse with fhirclient
            try:
                if resource_json.get("resourceType") == "ServiceRequest":
                    # Create a mock client for validation
                    mock_client = client.FHIRClient(settings=None)
                    # Try to create a ServiceRequest object
                    service_request = servicerequest.ServiceRequest(resource_json)
                    # If we get here, validation passed
                    logger.info("FHIR validation passed")
                else:
                    return {"valid": False, "errors": ["Only ServiceRequest resources supported"]}
            except Exception as e:
                return {"valid": False, "errors": [f"FHIR validation failed: {str(e)}"]}
            
            # Now validate with FHIR server
            url = f"{self.base_url}/ServiceRequest/$validate"
            response = await self.client.post(
                url,
                json=resource_json,
                headers={"Content-Type": "application/fhir+json"}
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get("resourceType") == "OperationOutcome":
                    # Check for errors in OperationOutcome
                    issues = result.get("issue", [])
                    errors = []
                    for issue in issues:
                        if issue.get("severity") in ["error", "fatal"]:
                            errors.append(issue.get("diagnostics", "Unknown error"))
                    
                    if errors:
                        return {"valid": False, "errors": errors}
                    else:
                        return {"valid": True, "errors": []}
                else:
                    return {"valid": True, "errors": []}
            else:
                return {"valid": False, "errors": [f"HTTP {response.status_code}: {response.text}"]}
                
        except Exception as e:
            logger.error(f"FHIR validation failed: {e}")
            return {"valid": False, "errors": [str(e)]}
    
    async def post_fhir(self, resource_json: Dict[str, Any]) -> Dict[str, Any]:
        """
        Post a FHIR resource to the server
        
        Args:
            resource_json: The FHIR resource as a dictionary
            
        Returns:
            Dict with success status and response data
        """
        try:
            url = f"{self.base_url}/ServiceRequest"
            response = await self.client.post(
                url,
                json=resource_json,
                headers={"Content-Type": "application/fhir+json"}
            )
            
            if response.status_code in [200, 201]:
                result = response.json()
                return {
                    "success": True,
                    "status_code": response.status_code,
                    "resource_id": result.get("id"),
                    "response": result
                }
            else:
                return {
                    "success": False,
                    "status_code": response.status_code,
                    "error": response.text
                }
                
        except Exception as e:
            logger.error(f"FHIR posting failed: {e}")
            return {"success": False, "error": str(e)}

class AuditLogger:
    """SQLite-based audit logger for tracking all operations"""
    
    def __init__(self, db_path: str = "./data/audit.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _init_db(self):
        """Initialize the audit database with required tables"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    operation TEXT NOT NULL,
                    input_data TEXT,
                    output_data TEXT,
                    success BOOLEAN,
                    error_message TEXT,
                    retry_count INTEGER DEFAULT 0
                )
            """)
            conn.commit()
    
    def log_operation(self, operation: str, input_data: Any = None, 
                     output_data: Any = None, success: bool = True, 
                     error_message: str = None, retry_count: int = 0):
        """Log an operation to the audit database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT INTO audit_log 
                    (operation, input_data, output_data, success, error_message, retry_count)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    operation,
                    json.dumps(input_data) if input_data else None,
                    json.dumps(output_data) if output_data else None,
                    success,
                    error_message,
                    retry_count
                ))
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to log to audit database: {e}")

class PDFExtractor:
    """Tool for extracting data from PDFs"""
    
    def __init__(self, service_url: str = "http://localhost:7001"):
        self.service_url = service_url
        self.client = httpx.AsyncClient(timeout=60.0)
    
    async def extract_pdf(self, file_path: str) -> Dict[str, Any]:
        """
        Extract data from a PDF file
        
        Args:
            file_path: Path to the PDF file
            
        Returns:
            Dict with extracted data
        """
        try:
            with open(file_path, "rb") as f:
                files = {"file": f}
                response = await self.client.post(
                    f"{self.service_url}/extract",
                    files=files
                )
            
            if response.status_code == 200:
                return response.json()
            else:
                return {
                    "success": False,
                    "error": f"HTTP {response.status_code}: {response.text}"
                }
                
        except Exception as e:
            logger.error(f"PDF extraction failed: {e}")
            return {"success": False, "error": str(e)}

class EMPILookup:
    """Tool for patient lookup via EMPI"""
    
    def __init__(self, service_url: str = "http://localhost:7002"):
        self.service_url = service_url
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def lookup_patient(self, email: str = None, name: str = None, 
                           patient_id: str = None) -> Dict[str, Any]:
        """
        Look up patient information
        
        Args:
            email: Patient email
            name: Patient name
            patient_id: Patient ID
            
        Returns:
            Dict with patient information
        """
        try:
            params = {}
            if email:
                params["email"] = email
            if name:
                params["name"] = name
            if patient_id:
                params["id"] = patient_id
            
            response = await self.client.get(
                f"{self.service_url}/patient",
                params=params
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                return {
                    "success": False,
                    "error": f"HTTP {response.status_code}: {response.text}"
                }
                
        except Exception as e:
            logger.error(f"EMPI lookup failed: {e}")
            return {"success": False, "error": str(e)} 
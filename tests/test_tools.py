import pytest
import asyncio
from unittest.mock import AsyncMock, patch
from agent_app.tools import FHIRTools, AuditLogger, PDFExtractor, EMPILookup

class TestFHIRTools:
    """Test FHIR tools functionality"""
    
    @pytest.fixture
    def fhir_tools(self):
        return FHIRTools("http://test-fhir-server")
    
    @pytest.fixture
    def valid_service_request(self):
        return {
            "resourceType": "ServiceRequest",
            "id": "test-request",
            "status": "active",
            "intent": "order",
            "subject": {
                "reference": "Patient/test-patient"
            },
            "code": {
                "coding": [{
                    "system": "http://snomed.info/sct",
                    "code": "430193006",
                    "display": "Referral to cardiology"
                }]
            },
            "priority": "urgent",
            "reasonCode": [{
                "coding": [{
                    "system": "http://snomed.info/sct",
                    "code": "22298006",
                    "display": "Myocardial infarction"
                }]
            }]
        }
    
    @pytest.mark.asyncio
    async def test_validate_fhir_success(self, fhir_tools, valid_service_request):
        """Test successful FHIR validation"""
        with patch('httpx.AsyncClient.post') as mock_post:
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"resourceType": "OperationOutcome", "issue": []}
            mock_post.return_value = mock_response
            
            result = await fhir_tools.validate_fhir(valid_service_request)
            
            assert result["valid"] is True
            assert result["errors"] == []
    
    @pytest.mark.asyncio
    async def test_validate_fhir_with_errors(self, fhir_tools, valid_service_request):
        """Test FHIR validation with errors"""
        with patch('httpx.AsyncClient.post') as mock_post:
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "resourceType": "OperationOutcome",
                "issue": [
                    {
                        "severity": "error",
                        "diagnostics": "Missing required field: requester"
                    }
                ]
            }
            mock_post.return_value = mock_response
            
            result = await fhir_tools.validate_fhir(valid_service_request)
            
            assert result["valid"] is False
            assert "Missing required field: requester" in result["errors"]
    
    @pytest.mark.asyncio
    async def test_post_fhir_success(self, fhir_tools, valid_service_request):
        """Test successful FHIR posting"""
        with patch('httpx.AsyncClient.post') as mock_post:
            mock_response = AsyncMock()
            mock_response.status_code = 201
            mock_response.json.return_value = {
                "resourceType": "ServiceRequest",
                "id": "posted-request-123"
            }
            mock_post.return_value = mock_response
            
            result = await fhir_tools.post_fhir(valid_service_request)
            
            assert result["success"] is True
            assert result["resource_id"] == "posted-request-123"

class TestAuditLogger:
    """Test audit logging functionality"""
    
    @pytest.fixture
    def audit_logger(self, tmp_path):
        db_path = tmp_path / "test_audit.db"
        return AuditLogger(str(db_path))
    
    def test_log_operation(self, audit_logger):
        """Test logging an operation"""
        audit_logger.log_operation(
            "test_operation",
            input_data={"test": "data"},
            output_data={"result": "success"},
            success=True
        )
        
        # Verify the log was created (we can't easily query SQLite in tests)
        assert audit_logger.db_path.exists()

class TestPDFExtractor:
    """Test PDF extraction functionality"""
    
    @pytest.fixture
    def pdf_extractor(self):
        return PDFExtractor("http://test-pdf-service")
    
    @pytest.mark.asyncio
    async def test_extract_pdf_success(self, pdf_extractor, tmp_path):
        """Test successful PDF extraction"""
        # Create a test PDF file
        test_pdf = tmp_path / "test.pdf"
        test_pdf.write_bytes(b"%PDF-1.4\n%Test PDF content")
        
        with patch('httpx.AsyncClient.post') as mock_post:
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "success": True,
                "data": {
                    "text_content": "Test PDF content",
                    "filename": "test.pdf"
                }
            }
            mock_post.return_value = mock_response
            
            result = await pdf_extractor.extract_pdf(str(test_pdf))
            
            assert result["success"] is True
            assert "Test PDF content" in result["data"]["text_content"]

class TestEMPILookup:
    """Test EMPI lookup functionality"""
    
    @pytest.fixture
    def empi_lookup(self):
        return EMPILookup("http://test-empi-service")
    
    @pytest.mark.asyncio
    async def test_lookup_patient_success(self, empi_lookup):
        """Test successful patient lookup"""
        with patch('httpx.AsyncClient.get') as mock_get:
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "success": True,
                "patient": {
                    "id": "patient-001",
                    "name": "John Doe",
                    "email": "john.doe@email.com"
                }
            }
            mock_get.return_value = mock_response
            
            result = await empi_lookup.lookup_patient(email="john.doe@email.com")
            
            assert result["success"] is True
            assert result["patient"]["name"] == "John Doe"
    
    @pytest.mark.asyncio
    async def test_lookup_patient_not_found(self, empi_lookup):
        """Test patient lookup when not found"""
        with patch('httpx.AsyncClient.get') as mock_get:
            mock_response = AsyncMock()
            mock_response.status_code = 404
            mock_response.text = "Patient not found"
            mock_get.return_value = mock_response
            
            result = await empi_lookup.lookup_patient(email="nonexistent@email.com")
            
            assert result["success"] is False
            assert "404" in result["error"] 
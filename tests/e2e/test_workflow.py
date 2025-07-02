import pytest
import asyncio
import subprocess
import time
import requests
from pathlib import Path

class TestEndToEndWorkflow:
    """End-to-end tests for the complete referral processing workflow"""
    
    @pytest.fixture(scope="class")
    def docker_services(self):
        """Start Docker services for testing"""
        # Start services
        subprocess.run(["docker-compose", "up", "-d"], check=True)
        
        # Wait for services to be ready
        self._wait_for_services()
        
        yield
        
        # Cleanup
        subprocess.run(["docker-compose", "down"], check=True)
    
    def _wait_for_services(self):
        """Wait for all services to be healthy"""
        services = [
            ("http://localhost:8080/fhir/metadata", "HAPI FHIR"),
            ("http://localhost:7000/health", "PDF Service"),
            ("http://localhost:7001/health", "EMPI Service")
        ]
        
        for url, name in services:
            print(f"Waiting for {name}...")
            for _ in range(30):  # 30 second timeout
                try:
                    response = requests.get(url, timeout=5)
                    if response.status_code == 200:
                        print(f"✅ {name} is ready")
                        break
                except requests.RequestException:
                    time.sleep(1)
            else:
                raise TimeoutError(f"{name} failed to start")
    
    @pytest.mark.asyncio
    async def test_pdf_service_health(self, docker_services):
        """Test PDF service health endpoint"""
        response = requests.get("http://localhost:7000/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
    
    @pytest.mark.asyncio
    async def test_empi_service_health(self, docker_services):
        """Test EMPI service health endpoint"""
        response = requests.get("http://localhost:7001/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
    
    @pytest.mark.asyncio
    async def test_fhir_server_health(self, docker_services):
        """Test FHIR server health endpoint"""
        response = requests.get("http://localhost:8080/fhir/metadata")
        assert response.status_code == 200
        data = response.json()
        assert data["resourceType"] == "CapabilityStatement"
    
    @pytest.mark.asyncio
    async def test_empi_patient_lookup(self, docker_services):
        """Test EMPI patient lookup functionality"""
        response = requests.get(
            "http://localhost:7001/patient",
            params={"email": "john.doe@email.com"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["patient"]["name"] == "John Doe"
    
    @pytest.mark.asyncio
    async def test_pdf_extraction(self, docker_services, tmp_path):
        """Test PDF extraction service"""
        # Create a test PDF file
        test_pdf = tmp_path / "test_referral.pdf"
        test_pdf.write_bytes(b"%PDF-1.4\n%Test PDF content")
        
        with open(test_pdf, "rb") as f:
            response = requests.post(
                "http://localhost:7000/extract",
                files={"file": f}
            )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "text_content" in data["data"]
    
    @pytest.mark.asyncio
    async def test_fhir_validation(self, docker_services):
        """Test FHIR validation functionality"""
        # Create a valid ServiceRequest
        service_request = {
            "resourceType": "ServiceRequest",
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
            "priority": "urgent"
        }
        
        response = requests.post(
            "http://localhost:8080/fhir/ServiceRequest/$validate",
            json=service_request,
            headers={"Content-Type": "application/fhir+json"}
        )
        
        # Should return 200 with validation result
        assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_complete_workflow_with_sample_data(self, docker_services):
        """Test the complete workflow with sample referral data"""
        # This test would require the agent application to be running
        # and a sample PDF file to be available
        # For now, we'll just verify the services are ready
        
        # Check that all services are responding
        services = [
            "http://localhost:8080/fhir/metadata",
            "http://localhost:7000/health", 
            "http://localhost:7001/health"
        ]
        
        for url in services:
            response = requests.get(url, timeout=10)
            assert response.status_code == 200, f"Service {url} not responding"
        
        print("✅ All services are ready for workflow testing")

class TestDockerCompose:
    """Test Docker Compose configuration"""
    
    def test_docker_compose_config(self):
        """Test that docker-compose.yml is valid"""
        result = subprocess.run(
            ["docker-compose", "config"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0, f"Docker Compose config error: {result.stderr}"
    
    def test_docker_compose_services(self):
        """Test that all required services are defined"""
        result = subprocess.run(
            ["docker-compose", "config", "--services"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0
        
        services = result.stdout.strip().split('\n')
        required_services = ['hapi', 'pdfsvc', 'empi', 'agent']
        
        for service in required_services:
            assert service in services, f"Required service {service} not found" 
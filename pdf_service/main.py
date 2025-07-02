import os
import json
import logging
from typing import Dict, Any, Optional
from pathlib import Path

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import pdfplumber
from llama_index.core import Document
from llama_index.readers.file import PDFReader

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="PDF Extraction Service", version="0.1.0")

class ExtractionResponse(BaseModel):
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

class HealthResponse(BaseModel):
    status: str
    version: str

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    return HealthResponse(status="healthy", version="0.1.0")

@app.post("/extract", response_model=ExtractionResponse)
async def extract_pdf(file: UploadFile = File(...)):
    """
    Extract structured data from a referral PDF
    
    Uses pdfplumber for text extraction and LlamaParse for enhanced parsing
    """
    try:
        # Validate file type
        if not file.filename.lower().endswith('.pdf'):
            raise HTTPException(status_code=400, detail="File must be a PDF")
        
        # Save uploaded file temporarily
        temp_path = Path(f"/tmp/{file.filename}")
        with open(temp_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
        
        # Extract text using pdfplumber
        extracted_text = ""
        with pdfplumber.open(temp_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    extracted_text += text + "\n"
        
        # Use LlamaParse for enhanced extraction if available
        try:
            reader = PDFReader()
            documents = reader.load_data(temp_path)
            if documents:
                # Combine LlamaParse output with pdfplumber
                llama_text = "\n".join([doc.text for doc in documents])
                extracted_text = f"{extracted_text}\n\nEnhanced extraction:\n{llama_text}"
        except Exception as e:
            logger.warning(f"LlamaParse failed, using pdfplumber only: {e}")
        
        # Clean up temp file
        temp_path.unlink(missing_ok=True)
        
        # Create structured response
        extraction_data = {
            "filename": file.filename,
            "text_content": extracted_text,
            "extraction_method": "pdfplumber + llama_parse",
            "metadata": {
                "file_size": len(content),
                "pages": len(pdf.pages) if 'pdf' in locals() else "unknown"
            }
        }
        
        return ExtractionResponse(
            success=True,
            data=extraction_data
        )
        
    except Exception as e:
        logger.error(f"PDF extraction failed: {e}")
        return ExtractionResponse(
            success=False,
            error=str(e)
        )

@app.get("/")
async def root():
    """Root endpoint with service information"""
    return {
        "service": "PDF Extraction Service",
        "version": "0.1.0",
        "endpoints": {
            "health": "/health",
            "extract": "/extract"
        }
    } 
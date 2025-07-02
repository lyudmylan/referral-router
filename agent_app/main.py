import asyncio
import logging
import os
from pathlib import Path
from typing import Dict, Any
from agent_app.graph import get_compiled_graph
from agent_app.tools import PDFExtractor, EMPILookup

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ReferralRouter:
    """Main referral router application"""
    
    def __init__(self):
        self.graph = get_compiled_graph()
        self.pdf_extractor = PDFExtractor()
        self.empi_lookup = EMPILookup()
    
    async def process_referral(self, pdf_path: str, patient_email: str = None) -> Dict[str, Any]:
        """
        Process a referral PDF through the complete workflow
        
        Args:
            pdf_path: Path to the PDF file
            patient_email: Optional patient email for EMPI lookup
            
        Returns:
            Dict with processing results
        """
        try:
            # Validate PDF path
            pdf_file = Path(pdf_path)
            if not pdf_file.exists():
                raise FileNotFoundError(f"PDF file not found: {pdf_path}")
            
            # Extract PDF data
            logger.info(f"Extracting data from PDF: {pdf_path}")
            pdf_result = await self.pdf_extractor.extract_pdf(str(pdf_file))
            
            if not pdf_result.get("success", False):
                raise Exception(f"PDF extraction failed: {pdf_result.get('error')}")
            
            # Optional EMPI lookup
            empi_data = {}
            if patient_email:
                logger.info(f"Looking up patient: {patient_email}")
                empi_result = await self.empi_lookup.lookup_patient(email=patient_email)
                if empi_result.get("success", False):
                    empi_data = empi_result.get("patient", {})
                else:
                    logger.warning(f"EMPI lookup failed: {empi_result.get('error')}")
            
            # Initialize state
            initial_state = {
                "pdf_path": str(pdf_file),
                "pdf_data": pdf_result,
                "empi_data": empi_data,
                "draft_json": {},
                "validation_result": {},
                "final_json": {},
                "posting_result": {},
                "retry_count": 0,
                "error_message": ""
            }
            
            # Run the workflow
            logger.info("Starting referral processing workflow")
            config = {"configurable": {"thread_id": f"referral_{pdf_file.stem}"}}
            
            result = await self.graph.ainvoke(initial_state, config)
            
            # Check for errors
            if result.get("error_message"):
                logger.error(f"Workflow failed: {result['error_message']}")
                return {
                    "success": False,
                    "error": result["error_message"],
                    "retry_count": result.get("retry_count", 0)
                }
            
            # Return success result
            return {
                "success": True,
                "pdf_path": pdf_path,
                "final_json": result.get("final_json", {}),
                "posting_result": result.get("posting_result", {}),
                "retry_count": result.get("retry_count", 0),
                "resource_id": result.get("posting_result", {}).get("resource_id")
            }
            
        except Exception as e:
            logger.error(f"Referral processing failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }

async def main():
    """Main CLI entry point"""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python main.py <pdf_path> [patient_email]")
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    patient_email = sys.argv[2] if len(sys.argv) > 2 else None
    
    # Initialize router
    router = ReferralRouter()
    
    # Process referral
    print(f"Processing referral: {pdf_path}")
    if patient_email:
        print(f"Patient email: {patient_email}")
    
    result = await router.process_referral(pdf_path, patient_email)
    
    # Display results
    if result["success"]:
        print("\n✅ Referral processed successfully!")
        print(f"Resource ID: {result.get('resource_id', 'N/A')}")
        print(f"Retry count: {result.get('retry_count', 0)}")
        
        if result.get("final_json"):
            print("\nFinal FHIR ServiceRequest:")
            import json
            print(json.dumps(result["final_json"], indent=2))
    else:
        print(f"\n❌ Processing failed: {result.get('error')}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main()) 
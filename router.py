#!/usr/bin/env python3
"""
Referral Router CLI

Usage:
    python router.py <pdf_path> [patient_email]
"""

import asyncio
import sys
from pathlib import Path

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("Warning: python-dotenv not installed. Make sure environment variables are set manually.")

# Add the agent_app to the Python path
sys.path.insert(0, str(Path(__file__).parent))

from agent_app.main import ReferralRouter

async def main():
    """Main CLI entry point"""
    if len(sys.argv) < 2:
        print("Referral Router MVP")
        print("==================")
        print("Usage: python router.py <pdf_path> [patient_email]")
        print("\nExamples:")
        print("  python router.py data/sample_referral.pdf")
        print("  python router.py data/referral.pdf john.doe@email.com")
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    patient_email = sys.argv[2] if len(sys.argv) > 2 else None
    
    # Validate PDF path
    pdf_file = Path(pdf_path)
    if not pdf_file.exists():
        print(f"❌ Error: PDF file not found: {pdf_path}")
        sys.exit(1)
    
    # Initialize router
    print("🚀 Initializing Referral Router...")
    router = ReferralRouter()
    
    # Process referral
    print(f"📄 Processing referral: {pdf_path}")
    if patient_email:
        print(f"👤 Patient email: {patient_email}")
    
    try:
        result = await router.process_referral(pdf_path, patient_email)
        
        # Display results
        if result["success"]:
            print("\n✅ Referral processed successfully!")
            print(f"🆔 Resource ID: {result.get('resource_id', 'N/A')}")
            print(f"🔄 Retry count: {result.get('retry_count', 0)}")
            
            if result.get("final_json"):
                print("\n📋 Final FHIR ServiceRequest:")
                import json
                print(json.dumps(result["final_json"], indent=2))
            if result.get("posting_result"):
                print("\n📦 Posting Result:")
                import json
                print(json.dumps(result["posting_result"], indent=2))
        else:
            print(f"\n❌ Processing failed: {result.get('error')}")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n⚠️  Processing interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main()) 
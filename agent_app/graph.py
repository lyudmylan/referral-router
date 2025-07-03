import json
import logging
from typing import Dict, Any, TypedDict, Annotated
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from openai import AsyncOpenAI
from agent_app.tools import FHIRTools, AuditLogger, PDFExtractor, EMPILookup

logger = logging.getLogger(__name__)

# State definition
class AgentState(TypedDict):
    pdf_path: str
    pdf_data: Dict[str, Any]
    empi_data: Dict[str, Any]
    draft_json: Dict[str, Any]
    validation_result: Dict[str, Any]
    final_json: Dict[str, Any]
    posting_result: Dict[str, Any]
    retry_count: int
    error_message: str

# Initialize tools
fhir_tools = FHIRTools()
audit_logger = AuditLogger()
pdf_extractor = PDFExtractor()
empi_lookup = EMPILookup()

# Initialize OpenAI client
client = AsyncOpenAI()

async def generator(state: AgentState) -> AgentState:
    """Generate draft FHIR ServiceRequest from PDF data"""
    try:
        pdf_content = state["pdf_data"]["data"]["text_content"]
        empi_info = state.get("empi_data", {})
        
        # Get a real patient ID from the FHIR server
        real_patient_id = None
        try:
            fhir_tools_instance = FHIRTools()
            patients_response = await fhir_tools_instance.client.get(f"{fhir_tools_instance.base_url}/Patient?_count=1")
            if patients_response.status_code == 200:
                patients_data = patients_response.json()
                if patients_data.get("entry") and len(patients_data["entry"]) > 0:
                    real_patient_id = patients_data["entry"][0]["resource"]["id"]
                    # Update empi_info with real patient ID
                    empi_info["id"] = real_patient_id
                    empi_info["reference"] = f"Patient/{real_patient_id}"
        except Exception as e:
            logger.warning(f"Could not get real patient ID: {e}")
        
        if not real_patient_id:
            raise ValueError("No patients found in FHIR server. Please ensure patients are loaded before processing referrals.")
        
        # Get a real practitioner ID from the FHIR server
        real_practitioner_id = None
        try:
            practitioners_response = await fhir_tools_instance.client.get(f"{fhir_tools_instance.base_url}/Practitioner?_count=1")
            if practitioners_response.status_code == 200:
                practitioners_data = practitioners_response.json()
                if practitioners_data.get("entry") and len(practitioners_data["entry"]) > 0:
                    real_practitioner_id = practitioners_data["entry"][0]["resource"]["id"]
        except Exception as e:
            logger.warning(f"Could not get real practitioner ID: {e}")
        
        if not real_practitioner_id:
            raise ValueError("No practitioners found in FHIR server. Please ensure practitioners are loaded before processing referrals.")
        
        # Create prompt for LLM
        prompt = f"""
You are a healthcare data specialist. Convert the following referral document into a FHIR R5 ServiceRequest resource.

PDF Content:
{pdf_content}

Patient Information (use this patient reference):
{json.dumps(empi_info, indent=2)}

Create a valid FHIR R5 ServiceRequest JSON object. Include:
- resourceType: "ServiceRequest"
- status: "active" or "draft"
- intent: "order"
- subject: Reference to the patient (use "Patient/{real_patient_id}")
- code: SNOMED CT code for the requested service
- priority: "routine", "urgent", or "asap"
- reasonCode: SNOMED CT code for the reason
- requester: Reference to the requesting practitioner (use "Practitioner/{real_practitioner_id}")
- encounter: Only include if you have a valid encounter reference, otherwise omit this field

IMPORTANT: Do not include encounter references unless you have a valid encounter ID. If no encounter is mentioned in the referral, omit the encounter field entirely.

Return ONLY the JSON object, no additional text.
"""

        # Call OpenAI
        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1
        )
        
        # Parse JSON from response
        content = response.choices[0].message.content.strip()
        try:
            draft_json = json.loads(content)
        except json.JSONDecodeError:
            # Try to extract JSON from markdown code blocks
            if "```json" in content:
                json_start = content.find("```json") + 7
                json_end = content.find("```", json_start)
                json_str = content[json_start:json_end].strip()
                draft_json = json.loads(json_str)
            else:
                raise ValueError("Could not parse JSON from LLM response")
        
        # Log the operation
        audit_logger.log_operation(
            "generator",
            input_data={"pdf_content": pdf_content[:500] + "..." if len(pdf_content) > 500 else pdf_content},
            output_data=draft_json,
            success=True
        )
        
        return {**state, "draft_json": draft_json}
        
    except Exception as e:
        logger.error(f"Generator failed: {e}")
        audit_logger.log_operation(
            "generator",
            input_data=state.get("pdf_data"),
            error_message=str(e),
            success=False
        )
        return {**state, "error_message": str(e)}

async def validator(state: AgentState) -> AgentState:
    """Validate the draft FHIR ServiceRequest"""
    try:
        draft_json = state["draft_json"]
        
        # Validate with FHIR server
        validation_result = await fhir_tools.validate_fhir(draft_json)
        
        # Log the operation
        audit_logger.log_operation(
            "validator",
            input_data=draft_json,
            output_data=validation_result,
            success=validation_result.get("valid", False)
        )
        
        # If validation succeeds, set final_json
        if validation_result.get("valid", False):
            return {**state, "validation_result": validation_result, "final_json": draft_json}
        else:
            return {**state, "validation_result": validation_result}
        
    except Exception as e:
        logger.error(f"Validator failed: {e}")
        audit_logger.log_operation(
            "validator",
            input_data=state.get("draft_json"),
            error_message=str(e),
            success=False
        )
        return {**state, "error_message": str(e)}

async def fixer(state: AgentState) -> AgentState:
    """Fix validation errors in the FHIR ServiceRequest"""
    try:
        draft_json = state["draft_json"]
        validation_result = state["validation_result"]
        errors = validation_result.get("errors", [])
        
        if not errors:
            return {**state, "final_json": draft_json}
        
        # Create fix prompt
        error_text = "\n".join(errors)
        prompt = f"""
The following FHIR ServiceRequest has validation errors. Please fix them and return a corrected JSON object.

Original JSON:
{json.dumps(draft_json, indent=2)}

Validation Errors:
{error_text}

Return ONLY the corrected JSON object, no additional text.
"""

        # Call OpenAI
        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1
        )
        
        # Parse JSON from response
        content = response.choices[0].message.content.strip()
        try:
            fixed_json = json.loads(content)
        except json.JSONDecodeError:
            if "```json" in content:
                json_start = content.find("```json") + 7
                json_end = content.find("```", json_start)
                json_str = content[json_start:json_end].strip()
                fixed_json = json.loads(json_str)
            else:
                raise ValueError("Could not parse JSON from LLM response")
        
        # Log the operation
        audit_logger.log_operation(
            "fixer",
            input_data={"draft_json": draft_json, "errors": errors},
            output_data=fixed_json,
            success=True,
            retry_count=state.get("retry_count", 0)
        )
        
        return {**state, "draft_json": fixed_json, "retry_count": state.get("retry_count", 0) + 1}
        
    except Exception as e:
        logger.error(f"Fixer failed: {e}")
        audit_logger.log_operation(
            "fixer",
            input_data={"draft_json": state.get("draft_json"), "errors": state.get("validation_result", {}).get("errors", [])},
            error_message=str(e),
            success=False,
            retry_count=state.get("retry_count", 0)
        )
        return {**state, "error_message": str(e)}

async def poster(state: AgentState) -> AgentState:
    """Post the validated FHIR ServiceRequest to the server"""
    try:
        final_json = state["final_json"]
        
        # Post to FHIR server
        posting_result = await fhir_tools.post_fhir(final_json)
        
        # Log the operation
        audit_logger.log_operation(
            "poster",
            input_data=final_json,
            output_data=posting_result,
            success=posting_result.get("success", False)
        )
        
        return {**state, "posting_result": posting_result}
        
    except Exception as e:
        logger.error(f"Poster failed: {e}")
        audit_logger.log_operation(
            "poster",
            input_data=state.get("final_json"),
            error_message=str(e),
            success=False
        )
        return {**state, "error_message": str(e)}

def logger_node(state: AgentState) -> AgentState:
    """Log the final result"""
    try:
        # Log the complete operation
        audit_logger.log_operation(
            "complete_workflow",
            input_data={
                "pdf_path": state.get("pdf_path"),
                "pdf_data": state.get("pdf_data"),
                "empi_data": state.get("empi_data")
            },
            output_data={
                "final_json": state.get("final_json"),
                "posting_result": state.get("posting_result"),
                "retry_count": state.get("retry_count", 0)
            },
            success=state.get("posting_result", {}).get("success", False)
        )
        
        return state
        
    except Exception as e:
        logger.error(f"Logger failed: {e}")
        return {**state, "error_message": str(e)}

# Routing logic
def should_retry(state: AgentState) -> str:
    """Determine if we should retry validation or proceed"""
    validation_result = state.get("validation_result", {})
    retry_count = state.get("retry_count", 0)
    max_retries = 3
    
    if validation_result.get("valid", False):
        return "post"
    elif retry_count < max_retries:
        return "fix"
    else:
        return "end"

def should_continue(state: AgentState) -> str:
    """Determine if we should continue to poster or end"""
    if state.get("posting_result"):
        return "log"
    else:
        return "end"

# Create the graph
def create_graph() -> StateGraph:
    """Create the LangGraph workflow"""
    workflow = StateGraph(AgentState)
    
    # Add nodes
    workflow.add_node("generator", generator)
    workflow.add_node("validator", validator)
    workflow.add_node("fixer", fixer)
    workflow.add_node("poster", poster)
    workflow.add_node("logger", logger_node)
    
    # Add edges
    workflow.add_edge("generator", "validator")
    workflow.add_conditional_edges(
        "validator",
        should_retry,
        {
            "post": "poster",
            "fix": "fixer",
            "end": "logger"
        }
    )
    workflow.add_edge("fixer", "validator")
    workflow.add_conditional_edges(
        "poster",
        should_continue,
        {
            "log": "logger",
            "end": END
        }
    )
    workflow.add_edge("logger", END)
    
    # Set entry point
    workflow.set_entry_point("generator")
    
    return workflow

# Create the compiled graph
def get_compiled_graph():
    """Get the compiled graph with memory"""
    graph = create_graph()
    memory = MemorySaver()
    return graph.compile(checkpointer=memory) 
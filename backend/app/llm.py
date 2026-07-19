import json
from openai import OpenAI
from .config import settings
from .services import validate_explanation


def explain(record: dict) -> dict:
    if not settings.openai_api_key: raise RuntimeError("OPENAI_API_KEY is required for reroute explanations")
    schema={"type":"object","additionalProperties":False,"required":["summary","recommended_action","reasoning_summary","delay_saved_hours","additional_cost","risk_warning","next_steps"],"properties":{"summary":{"type":"string"},"recommended_action":{"type":"string"},"reasoning_summary":{"type":"string"},"delay_saved_hours":{"type":"number"},"additional_cost":{"type":"number"},"risk_warning":{"type":"string"},"next_steps":{"type":"array","items":{"type":"string"}}}}
    client=OpenAI(api_key=settings.openai_api_key, timeout=settings.openai_timeout_seconds)
    response=client.responses.create(model=settings.openai_model,input=[{"role":"system","content":"Explain only the supplied decision record. Do not add IDs, routes, locations, or numbers."},{"role":"user","content":json.dumps(record)}],text={"format":{"type":"json_schema","name":"reroute_explanation","strict":True,"schema":schema}})
    return validate_explanation(json.loads(response.output_text),record)

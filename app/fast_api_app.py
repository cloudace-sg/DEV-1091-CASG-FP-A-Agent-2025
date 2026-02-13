import os
import requests
import logging
import asyncio
import json
import uuid
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from google.adk.cli.fast_api import get_fast_api_app

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("A2A_Translator")

current_dir = os.path.dirname(os.path.abspath(__file__))
app: FastAPI = get_fast_api_app(
    agents_dir=current_dir, web=True, a2a=True, host="0.0.0.0", otel_to_cloud=False
)

# --- NEW HELPER FUNCTION ---
def extract_final_text(adk_response):
    """
    Intelligently finds the final spoken answer from a list of agent turns,
    ignoring tool calls and internal debugging data.
    """
    try:
        # If it's not a list, it might be a simple error message or dict
        if not isinstance(adk_response, list):
            return str(adk_response)

        # Iterate BACKWARDS (from the end) to find the last actual text response
        for turn in reversed(adk_response):
            # Check if this turn has content parts
            if "content" in turn and "parts" in turn["content"]:
                for part in turn["content"]["parts"]:
                    # We only want 'text', not 'functionCall'
                    if "text" in part and part["text"]:
                        return part["text"]
            
            # Older ADK versions might have 'parts' directly at the top level
            if "parts" in turn:
                for part in turn["parts"]:
                    if "text" in part and part["text"]:
                        return part["text"]

        # If we loop through everything and find NO text (only tool calls),
        # it usually means the agent crashed or stopped early.
        return "I processed the request but generated no text response."

    except Exception as e:
        logger.error(f"Extraction Error: {e}")
        return str(adk_response) # Fallback to raw dump if logic fails

@app.post("/a2a/fpaa_orchestrator")
async def gemini_translator(request: Request):
    try:
        data = await request.json()
        request_id = data.get("id")
        
        # 1. Extract Message
        user_msg = ""
        try:
            if "params" in data and "message" in data["params"]:
                parts = data["params"]["message"].get("parts", [])
                if parts and "text" in parts[0]:
                    user_msg = parts[0]["text"]
        except Exception as e:
            logger.warning(f"Failed parsing: {e}")

        if not user_msg:
            user_msg = data.get("input") or ""

        # 2. Call Internal Agent
        port = int(os.environ.get("PORT", 8080))
        base_url = f"http://127.0.0.1:{port}"
        adk_payload = {
            "app_name": "app",
            "newMessage": {"role": "user", "parts": [{"text": user_msg}]},
            "user_id": "gemini_user",
            "session_id": "gemini_session_001"
        }

        loop = asyncio.get_running_loop()
        try:
            await loop.run_in_executor(None, lambda: requests.post(
                f"{base_url}/apps/app/users/gemini_user/sessions/gemini_session_001",
                json={"input": "init"}, timeout=2
            ))
        except: pass 

        response = await loop.run_in_executor(None, lambda: requests.post(
            f"{base_url}/run", json=adk_payload, timeout=30
        ))
        
        # 3. USE SMART EXTRACTION
        text_answer = "Error processing request."
        if response.status_code == 200:
            resp_json = response.json()
            # Use the new helper function instead of blind indexing
            text_answer = extract_final_text(resp_json)
        else:
            text_answer = f"Agent Error: {response.text}"

        # 4. CONSTRUCT DIRECT MESSAGE RESPONSE
        async def sse_generator():
            a2a_result = {
                "kind": "message",
                "messageId": str(uuid.uuid4()),
                "role": "agent",
                "parts": [{
                    "kind": "text", 
                    "text": text_answer
                }]
            }

            rpc_response = {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": a2a_result
            }

            logger.info(f"📤 CLEAN RESPONSE: {text_answer[:50]}...") # Log just the first 50 chars
            yield f"data: {json.dumps(rpc_response)}\n\n"

        return StreamingResponse(sse_generator(), media_type="text/event-stream")

    except Exception as e:
        logger.error(f"💥 Crash: {e}")
        return {"error": str(e)}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
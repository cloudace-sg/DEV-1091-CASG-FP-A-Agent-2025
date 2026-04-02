import os
import pytest
import asyncio
import csv
from dotenv import load_dotenv
from pathlib import Path

from deepeval.metrics import GEval
from deepeval.test_case import LLMTestCase, LLMTestCaseParams
from deepeval import assert_test

from tests.unit.claude_judge import ClaudeJudge 

from google.adk.runners import Runner
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.genai import types

# 1. Load your API Keys
project_root = Path(__file__).resolve().parent.parent.parent
load_dotenv(dotenv_path=project_root / ".env")
os.environ["GEMINI_API_KEY"] = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")

# 2. Import the Orchestrator (The Manager)
from app.agent import orchestrator

# 3. Point to the Routing CSV
def load_routing_dataset():
    # Update this path to file
    csv_file_path = "tests/integration/data/(Routing) DEV-1127 Test Cases - Routing Test.csv"
    test_cases = []
    
    with open(csv_file_path, mode='r', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        for row in reader:
            expected = row.get("Expected Behaviour", "").strip()
            # Skip rows where Expected Behaviour is empty so the test doesn't crash
            if not expected:
                continue
                
            test_cases.append({
                "input": row["User Input (Prompt)"],
                "expected_routing": expected 
            })
    return test_cases

@pytest.mark.parametrize("case", load_routing_dataset())
def test_orchestrator_routing(case):
    raw_input = case["input"]
    expected_routing = case["expected_routing"]

    # 4. Parse the multi-turn conversation
    turn_1_text = raw_input
    turn_2_text = None
    
    if "Turn 2:" in raw_input:
        turns = raw_input.split("Turn 2:")
        turn_1_text = turns[0].replace("Turn 1:", "").strip()
        turn_2_text = turns[1].strip()

    session_service = InMemorySessionService()
    # Keeping the same session.id simulates a continuous conversation!
    session = session_service.create_session_sync(user_id="eval_user", app_name="test")
    runner = Runner(agent=orchestrator, session_service=session_service, app_name="test")

    async def _run_conversation():
        final_answer = ""
        full_trace = ""
        
        # --- EXECUTE TURN 1 ---
        msg1 = types.Content(role="user", parts=[types.Part.from_text(text=turn_1_text)])
        full_trace += f"\n--- USER TURN 1: {turn_1_text} ---\n"
        async for event in runner.run_async(new_message=msg1, user_id="eval_user", session_id=session.id):
            full_trace += f"{str(event)}\n"

        # --- EXECUTE TURN 2 (If it exists) ---
        if turn_2_text:
            msg2 = types.Content(role="user", parts=[types.Part.from_text(text=turn_2_text)])
            full_trace += f"\n--- USER TURN 2: {turn_2_text} ---\n"
            async for event in runner.run_async(new_message=msg2, user_id="eval_user", session_id=session.id):
                full_trace += f"{str(event)}\n"
                if hasattr(event, "content") and event.content:
                    for part in getattr(event.content, "parts", []):
                        if getattr(part, "text", None):
                            final_answer += part.text + " "
                            
        return final_answer, full_trace

    final_answer, full_trace = asyncio.run(_run_conversation())

    # 5. GEval criteria focused ONLY on routing
    judge = ClaudeJudge()
    
    routing_accuracy = GEval(
        name="Agent Routing Accuracy",
        criteria=(
            "Evaluate if the Orchestrator successfully routed the user's turns to the correct sub-agents. "
            "PASS if: "
            "1. The backend trace shows the correct agent 'author' or a valid 'transfer_to_agent' event that matches the Expected Routing. "
            "2. For multi-turn cases, verify that Turn 1 went to the correct agent (usually metrics_agent) AND Turn 2 went to the correct agent (usually investigation_agent) while keeping conversational context. "
            "DO NOT penalize the agent for the exact numerical value or specific business explanation it returns; focus ONLY on whether the right specialist agent was activated at the right time."
        ),
        evaluation_params=[LLMTestCaseParams.ACTUAL_OUTPUT, LLMTestCaseParams.EXPECTED_OUTPUT],
        threshold=0.5,
        model=judge
    )

    test_case = LLMTestCase(
        input=raw_input,
        actual_output=f"AGENT FINAL ANSWER: {final_answer}\n\n[BACKEND TRACE]:\n{full_trace}",
        expected_output=expected_routing
    )

    assert_test(test_case, [routing_accuracy])
import csv
import pytest
import asyncio

import os
from dotenv import load_dotenv

load_dotenv() # It will just silently skip if there's no .env file

from deepeval import assert_test
from deepeval.test_case import LLMTestCase, LLMTestCaseParams
from deepeval.metrics import GEval
from tests.unit.claude_judge import ClaudeJudge 

from app.sub_agents.investigation.agent import investigation_agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

def load_csv_dataset():
    dataset = []
    # ********change file path
    csv_file_path = "tests/integration/data/(Investigation) DEV-1129 Test Case - Tool Logic Case.csv"
    
    with open(csv_file_path, "r", encoding="utf-8-sig") as f:
        rows = list(csv.reader(f))
        
    header_row_idx = -1
    headers = []
    
    # 1. Find the headers safely
    for i, row in enumerate(rows):
        clean_row = [str(cell).strip() for cell in row]
        if "User Input (Prompt)" in clean_row and "Tool" in clean_row:
            header_row_idx = i
            headers = clean_row
            break
            
    if header_row_idx == -1:
        return [{"input": "Dummy", "expected_sql": "Dummy", "expected_tool": "Dummy"}]

    prompt_idx = headers.index("User Input (Prompt)")
    sql_idx = headers.index("Expected Behaviour")
    tool_idx = headers.index("Tool")
        
    # 2. Extract cases
    for row in rows[header_row_idx + 1:]:
        if len(row) > max(prompt_idx, sql_idx, tool_idx):
            prompt = row[prompt_idx].strip()
            sql = row[sql_idx].strip()
            tool = row[tool_idx].strip()
            
            if prompt and sql:
                dataset.append({
                    "input": prompt,
                    "expected_sql": sql,
                    "expected_tool": tool
                })
                
    return dataset if len(dataset) > 0 else [{"input": "Dummy", "expected_sql": "Dummy", "expected_tool": "Dummy"}]

@pytest.mark.parametrize("case", load_csv_dataset())
def test_metrics_agent_execution(case):
    input_text = case["input"]
    expected_sql = case["expected_sql"]
    expected_tool = case["expected_tool"]

    session_service = InMemorySessionService()
    session = session_service.create_session_sync(user_id="eval_user", app_name="test")
    runner = Runner(agent=investigation_agent, session_service=session_service, app_name="test")
    message = types.Content(role="user", parts=[types.Part.from_text(text=input_text)])

    async def _run():
        final_answer = ""
        full_trace = "" 
        async for event in runner.run_async(new_message=message, user_id="eval_user", session_id=session.id):
            full_trace += f"{str(event)}\n"
            if hasattr(event, "content") and event.content:
                for part in getattr(event.content, "parts", []):
                    if getattr(part, "text", None):
                        final_answer += part.text + " "
        return final_answer, full_trace

    final_answer, full_trace = asyncio.run(_run())

    combined_output = f"[AGENT FINAL ANSWER]: {final_answer}\n\n[BACKEND TRACE]: {full_trace}"
    judge = ClaudeJudge()
    
    behavioral_correctness = GEval(
        name="Investigative Logic Alignment",
        criteria=(
            "Evaluate if the Agent's investigative process matches the 'Expected Behaviour' logic. "
            "PASS if: "
            "1. The agent's backend trace shows it followed the logical steps described (e.g., triggered the correct driver analysis). "
            "2. The agent correctly identified the 'SQL Target' table mentioned in the Expected Behaviour. "
            "3. The final answer provides a business explanation that aligns with the 'Calc' or 'Logic' described. "
            "4. Even if the agent's raw SQL query differs slightly in syntax, it is a PASS as long as the logical intent (grouping, filtering, and table choice) matches."
            "- DO NOT PENALIZE the agent if it summarizes the data instead of listing exact dollar amounts."
            "- DO NOT PENALIZE the agent if it investigates Revenue using the Master PnL or Budget Variance tables instead of Product Mix."
            "- DO NOT PENALIZE the agent if it checks Subtype before Location, or skips a dimension entirely, as long as it finds a valid driver."
        ),
        evaluation_params=[LLMTestCaseParams.ACTUAL_OUTPUT, LLMTestCaseParams.EXPECTED_OUTPUT],
        threshold=0.5,
        model=judge
    )

    test_case = LLMTestCase(
        input=input_text,
        actual_output=combined_output,
        expected_output=expected_sql
    )

    assert_test(test_case, [behavioral_correctness])
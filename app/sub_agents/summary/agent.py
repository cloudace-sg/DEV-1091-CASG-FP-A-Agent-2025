# app/sub_agents/summary/agent.py
from .prompts import SUMMARY_AGENT_PROMPT
from google.adk.agents import LlmAgent

# pdf tool
from app.tools.pdf_tool import export_to_pdf

# --- define investigation_agent
summary_agent = LlmAgent(
    name="summary_agent",
    instruction=SUMMARY_AGENT_PROMPT,
    model="gemini-2.5-flash",
    tools=[export_to_pdf]
)

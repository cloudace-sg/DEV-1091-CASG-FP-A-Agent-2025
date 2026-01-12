# app/sub_agents/investigation/agent.py

from google.adk.agents import LlmAgent
from app.tools.bigquery_tool import query_bigquery
from app.tools.investigation_tool import (
    scan_business_health,
    compare_monthly_metric,
    analyze_variance_drivers,
    detect_anomalies
)

from .prompts import INVESTIGATION_AGENT_PROMPT

# --- define investigation_agent
investigation_agent = LlmAgent(
    name="investigation_agent",
    instruction=INVESTIGATION_AGENT_PROMPT,
    tools=[
        query_bigquery, 
        scan_business_health,
        compare_monthly_metric,
        analyze_variance_drivers,
        detect_anomalies
    ],
    model="gemini-2.5-flash"
)

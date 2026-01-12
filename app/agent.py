# app/agent.py <-- orchestrator
# ruff: noqa
# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import datetime
import os
import google.auth

# --- ADK IMPORTSS ---
from google.adk.agents import LlmAgent
from google.adk.apps.app import App
#from google.adk.tools.agent_tool import AgentTool

# --- PROMPT IMPORT ---
from . import prompts 

# --- SUB AGENT IMPORT ---
from .sub_agents.metrics.agent import metrics_agent
from .sub_agents.investigation.agent import investigation_agent
from .sub_agents.summary.agent import summary_agent

# 1. Project Config
SAFE_PROJECT_ID = "strong-kit-475107-k1"
os.environ["GOOGLE_CLOUD_PROJECT"] = SAFE_PROJECT_ID
os.environ["GOOGLE_CLOUD_LOCATION"] = "asia-southeast1"
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "True"

# ==============================================================================
# 3. ORCHESTRATOR DEFINITION
# ==============================================================================

orchestrator = LlmAgent(
    name="fpaa_orchestrator",
    model="gemini-2.5-flash",
    instruction=prompts.ORCHESTRATOR_PROMPT,
    sub_agents=[
        metrics_agent,
        investigation_agent,
        summary_agent
    ],
)

# --- APP DEFINITION ---
app = App(root_agent=orchestrator, name="app")



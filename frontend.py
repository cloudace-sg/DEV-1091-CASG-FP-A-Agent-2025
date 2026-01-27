import streamlit as st
import requests
import uuid
import json
import re
import pandas as pd
import plotly.express as px

# ==============================================================================
# 1. CONFIGURATION & PASSWORD
# ==============================================================================
st.set_page_config(page_title="FP&A AI Agent", page_icon="💰", layout="wide")

# 🔒 PASSWORD PROTECTION
password = st.sidebar.text_input("Enter Demo Password", type="password")
if password != "nadyabuiltthis2026":
    st.warning("🔒 Please enter the password to access the FP&A Agent.")
    st.stop()

BASE_URL = "http://localhost:8000"
APP_NAME = "app"
USER_ID = "test-user@example.com"

# ==============================================================================
# 2. HELPER FUNCTIONS
# ==============================================================================
def create_session_if_needed(session_id):
    """Register session with backend."""
    url = f"{BASE_URL}/apps/{APP_NAME}/users/{USER_ID}/sessions/{session_id}"
    try:
        requests.post(url, json={}, timeout=5)
    except Exception:
        pass

def recursive_find_text(data):
    """Universal search for the best text answer."""
    if isinstance(data, list):
        for item in reversed(data):
            found = recursive_find_text(item)
            if found: return found
    elif isinstance(data, dict):
        if "text" in data and isinstance(data["text"], str) and data["text"].strip():
            return data["text"]
        if "recommendation_output" in data:
            return data["recommendation_output"]
        if "body" in data and isinstance(data["body"], str):
             return data["body"]
        for key in ["parts", "content", "actions", "stateDelta", "artifactDelta", "body"]:
            if key in data:
                found = recursive_find_text(data[key])
                if found: return found
    return None

def clean_formatting(text):
    """Removes backticks and handles LaTeX formatting issues."""
    if isinstance(text, str):
        # Fix the "Math Font" issue by escaping dollar signs if not already escaped
        text = text.replace("$", "\$").replace("\\\$", "\$") 
        return text.replace("`", "")
    return text

# ==============================================================================
# 3. VISUALIZATION ENGINE (The New Part)
# ==============================================================================
# ... inside frontend.py ...

def render_smart_response(text):
    """
    Parses MULTIPLE <<<CHART_DATA: type | {data} >>> tags.
    """
    pattern = r"<<<CHART_DATA: (.*?) \| (.*?) >>>"
    
    parts = re.split(pattern, text, flags=re.DOTALL)
    
    # Iterate in steps of 3 (Text, Type, JSON)
    for i in range(0, len(parts), 3):
        
        # 1. Render Text
        if parts[i].strip():
            st.markdown(parts[i])
            
        # 2. Render Chart (if present)
        if i + 2 < len(parts):
            chart_type = parts[i+1].strip()
            raw_json = parts[i+2].strip()
            
            clean_json = raw_json.replace("```json", "").replace("```", "").replace('\\"', '"')

            try:
                data = json.loads(clean_json)
                df = pd.DataFrame(data)
                
                if "breakdown" in chart_type:
                    fig = px.pie(df, names="label", values="value", title=f"Breakdown Analysis", hole=0.4)
                elif "budget" in chart_type or "compare" in chart_type:
                    fig = px.bar(df, x="label", y=["actual", "budget"], barmode='group', title="Budget vs Actual")
                else:
                    fig = px.line(df, x="label", y="value", title="Trend Analysis", markers=True)
                
                # --- CRITICAL FIX: UNIQUE KEY ---
                # This prevents the "duplicate element" crash
                unique_key = f"chart_{i}_{str(uuid.uuid4())[:8]}"
                
                # UPDATED: Use standard Streamlit parameter
                st.plotly_chart(fig, use_container_width=True, key=unique_key)
                
            except Exception as e:
                st.error(f"Chart Error: {str(e)}")

# ==============================================================================
# 4. SESSION STATE SETUP
# ==============================================================================
if "session_id" not in st.session_state:
    new_id = str(uuid.uuid4())
    st.session_state.session_id = new_id
    create_session_if_needed(new_id)

if "messages" not in st.session_state:
    st.session_state.messages = []
    st.session_state.messages.append({
        "role": "assistant", 
        "content": "Hello! I am your AI Financial Analyst. I'm ready to help."
    })

# ==============================================================================
# 5. MAIN INTERFACE
# ==============================================================================
with st.sidebar:
    st.markdown("### 🤖 Agent Status")
    st.success("System Online")
    if st.button("New Session"):
        st.session_state.messages = []
        del st.session_state.session_id
        st.rerun()

# --- DISPLAY HISTORY (UPDATED LOOP) ---
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        # USE THE NEW RENDERER HERE
        if msg["role"] == "assistant":
            render_smart_response(msg["content"])
        else:
            st.write(msg["content"])

# --- HANDLE INPUT ---
if user_input := st.chat_input("Ask a financial question..."):
    # 1. Add User Message to State
    st.session_state.messages.append({"role": "user", "content": user_input})
    
    # 2. Get AI Response
    with st.spinner("Analyzing..."):
        try:
            run_url = f"{BASE_URL}/run"
            payload = {
                "app_name": APP_NAME,
                "session_id": st.session_state.session_id,
                "userId": USER_ID,
                "newMessage": {
                    "role": "user",
                    "parts": [{"text": user_input}] 
                }
            }
            
            response = requests.post(run_url, json=payload, timeout=120)
            
            if response.status_code == 200:
                data = response.json()
                answer = recursive_find_text(data)
                
                # Fallback
                if not answer: answer = "I processed the request but received no text output."

                # Clean formatting
                final_answer = clean_formatting(answer)

                # 3. Add AI Message to State
                st.session_state.messages.append({"role": "assistant", "content": final_answer})
                
            else:
                st.error(f"API Error {response.status_code}")

        except Exception as e:
            st.error(f"System Error: {str(e)}")

    # 4. Force Reload to show the new message via the render loop
    st.rerun()
import streamlit as st
import requests
import uuid
import json

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
    """Removes backticks to fix the font issue."""
    if isinstance(text, str):
        return text.replace("`", "")
    return text

# ==============================================================================
# 3. SESSION STATE
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
# 4. MAIN INTERFACE
# ==============================================================================
with st.sidebar:
    if st.button("New Session"):
        st.session_state.messages = []
        del st.session_state.session_id
        st.rerun()

# --- DISPLAY HISTORY (This is the ONLY place messages are printed) ---
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

# --- HANDLE INPUT ---
if user_input := st.chat_input("Ask a financial question..."):
    # 1. Add User Message to State
    st.session_state.messages.append({"role": "user", "content": user_input})
    
    # 2. Get AI Response (Visual Spinner only, no printing yet)
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
                if not answer: answer = data

                # === CLEANUP (Fixes the font) ===
                final_answer = clean_formatting(answer)

                # 3. Add AI Message to State (ONLY ONCE)
                st.session_state.messages.append({"role": "assistant", "content": final_answer})
                
            else:
                st.error(f"API Error {response.status_code}")

        except Exception as e:
            st.error(f"System Error: {str(e)}")

    # 4. FORCE RELOAD (Fixes the duplicate bug)
    st.rerun()
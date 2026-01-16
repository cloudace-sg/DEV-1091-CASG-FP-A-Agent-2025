#!/bin/bash

# 1. Start Backend
echo "Starting FastAPI Backend..."
uv run uvicorn app.fast_api_app:app --host 0.0.0.0 --port 8000 &

# 2. Wait for Backend to initialize
sleep 5

# 3. Start Frontend with SECURITY CHECKS DISABLED
echo "Starting Streamlit Frontend..."
uv run streamlit run frontend.py \
  --server.port 8080 \
  --server.address 0.0.0.0 \
  --server.enableCORS=false \
  --server.enableXsrfProtection=false \
  --browser.gatherUsageStats=false
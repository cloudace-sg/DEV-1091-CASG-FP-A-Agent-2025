import sys
import os
import asyncio

# Add current directory to path
sys.path.append(os.getcwd())

print("------------------------------------------------")
print("🕵️‍♂️ SEARCHING FOR AGENT ROUTES...")

try:
    # Import the app exactly like the server does
    from app.fast_api_app import app
    
    found_any = False
    print("\n✅ FOUND THESE URLS:")
    
    # Loop through all routes to find the A2A ones
    for route in app.routes:
        if hasattr(route, "path"):
            if "/a2a/" in route.path:
                print(f"   👉 {route.path}")
                found_any = True
    
    print("------------------------------------------------")
    if found_any:
        print("🎉 ACTION: Update Gemini with one of the URLs above!")
    else:
        print("❌ WARNING: No '/a2a/' routes found.") 
        print("   (This might mean the ADK didn't find your agent.py file)")

except Exception as e:
    print(f"\n❌ ERROR: Could not inspect app. {e}")

import sys
import os

# Add current directory to path
sys.path.append(os.getcwd())

try:
    print("------------------------------------------------")
    print("🕵️‍♂️ INSPECTING APPLICATION ROUTES...")
    from app.fast_api_app import app
    
    found_a2a = False
    print("\n✅ VALID ROUTES FOUND:")
    for route in app.routes:
        if hasattr(route, "path"):
            # Only show relevant routes, skip the boring internal ones
            if "/a2a" in route.path:
                print(f"   👉 {route.path}")
                found_a2a = True
    
    print("------------------------------------------------")
    if found_a2a:
        print("🎉 SUCCESS: Use one of the URLs above!")
    else:
        print("❌ ERROR: No A2A routes found. 'a2a=True' might be ignored.")

except Exception as e:
    print(f"\n❌ CRITICAL ERROR: Could not load app. {e}")

# debug_routes.py
from app.fast_api_app import app

print("\n=== AVAILABLE API ROUTES ===")
for route in app.routes:
    methods = ", ".join(route.methods)
    print(f"Path: {route.path}  | Methods: {methods}")
print("============================\n")
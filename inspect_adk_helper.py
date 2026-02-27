import inspect
from google.adk.cli.fast_api import get_fast_api_app

print("------------------------------------------------")
print("🔍 INSPECTING: get_fast_api_app")
print("------------------------------------------------")

# 1. Print the arguments it accepts
sig = inspect.signature(get_fast_api_app)
print(f"\n👉 SIGNATURE: get_fast_api_app{sig}")

# 2. Print the documentation
print("\n👉 DOCSTRING:")
print(get_fast_api_app.__doc__)
print("------------------------------------------------")

import os
import sys
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

# Force reload settings from .env
from dotenv import load_dotenv
load_dotenv(backend_dir / ".env", override=True)

import app.config as config_module
config_module.settings = config_module.Settings()

from app.config import settings
from app.services.llm import call_openrouter, generate_executive_report

def main():
    print("=========================================================================")
    print("OPENROUTER LIVE MODEL VERIFICATION")
    print("=========================================================================")
    print(f"Configured Provider: {settings.LLM_PROVIDER}")
    print(f"API Key Present    : {bool(settings.LLM_API_KEY)}")
    if settings.LLM_API_KEY:
        print(f"API Key Prefix     : {settings.LLM_API_KEY[:12]}...\n")

    if not settings.LLM_API_KEY:
        print("ERROR: LLM_API_KEY not found in backend/.env!")
        return

    prompt = (
        "Generate a 3-bullet point executive summary of GitHub pricing strategy based on "
        "Free tier ($0), Team tier ($4/mo), and Enterprise tier ($21/mo)."
    )

    print("Sending request to OpenRouter API (Primary Model: qwen/qwen3-next-80b-a3b-instruct:free)...")
    try:
        report_text, model_served = call_openrouter(prompt, settings.LLM_API_KEY)
        print("\n=========================================================================")
        print("RAW RESPONSE SUMMARY & MODEL SERVED")
        print("=========================================================================")
        print(f"Model Served: {model_served}\n")
        print("--- Generated Executive Output ---")
        print(report_text)
        print("=========================================================================")
    except Exception as exc:
        print(f"OpenRouter API call failed: {exc}")

if __name__ == "__main__":
    main()

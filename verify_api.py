import os
from google import genai
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv('GOOGLE_API_KEY')
if not api_key:
    print("❌ Error: GOOGLE_API_KEY not found.")
    exit(1)

print(f"Checking API Key: {api_key[:5]}...{api_key[-3:]}")

try:
    client = genai.Client(api_key=api_key)
    
    # 1. List Available Models
    print("\n--- Listing Available Models for your Key ---")
    try:
        # Paging through models
        pager = client.models.list()
        found_models = []
        for model in pager:
            print(f" - {model.name}")
            found_models.append(model.name)
            
        if not found_models:
            print("⚠️ No models found. Your API key might not have access to any models.")
            
    except Exception as e:
        print(f"❌ Failed to list models: {e}")

    # 2. Test Gemini 2.0 Flash (latest robust model)
    print("\n--- Testing Gemini 2.0 Flash Exp ---")
    try:
        response = client.models.generate_content(
            model='gemini-2.0-flash-exp',
            contents='Hello, simply reply "OK".'
        )
        if response.text:
            print(f"✅ Gemini 2.0 Flash is ACCESSIBLE. Reply: {response.text.strip()}")
        else:
            print("⚠️  Gemini 2.0 Flash returned no text.")
    except Exception as e:
        print(f"❌ Gemini 2.0 Flash Access FAILED: {e}")

except Exception as e:
    print(f"❌ Client Initialization FAILED: {e}")

print("\n--- Verification Complete ---")

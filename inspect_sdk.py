
from google import genai
import inspect

print("Inspecting google.genai.Client.models methods:")
print(dir(genai.Client(api_key="TEST").models))

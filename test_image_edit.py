#!/usr/bin/env python3
"""Test script to explore image editing capabilities with Google AI Studio API."""

import os
from google import genai
from google.genai import types
from dotenv import load_dotenv
from PIL import Image

load_dotenv()

# Initialize client with API key
api_key = os.getenv('GOOGLE_API_KEY')
client = genai.Client(api_key=api_key)

# Test image path
test_image_path = "static/uploads"
image_files = [f for f in os.listdir(test_image_path) if f.endswith(('.jpg', '.jpeg', '.png'))]

if not image_files:
    print("No test images found!")
    exit(1)

test_image = os.path.join(test_image_path, image_files[0])
print(f"Using test image: {test_image}")

# Read image
with open(test_image, "rb") as f:
    image_bytes = f.read()

# Test different models
models_to_test = [
    'gemini-3-pro-image-preview',
    'gemini-2.5-flash-image',
    'gemini-2.0-flash-exp-image-generation',
]

for model_name in models_to_test:
    print(f"\n{'='*60}")
    print(f"Testing: {model_name}")
    print('='*60)
    
    try:
        # Try using the model with image input
        prompt_parts = [
            types.Part.from_text(text="Remove all cars from this street view. Keep everything else the same."),
            types.Part.from_bytes(data=image_bytes, mime_type='image/jpeg')
        ]
        
        response = client.models.generate_content(
            model=model_name,
            contents=[types.Content(role='user', parts=prompt_parts)]
        )
        
        print(f"✓ Model {model_name} accepts image input!")
        print(f"Response type: {type(response)}")
        
        # Check if response contains generated image
        if hasattr(response, 'generated_images'):
            print(f"✓ Model generates images!")
            print(f"Number of images: {len(response.generated_images)}")
        elif hasattr(response, 'text'):
            print(f"Response text (first 200 chars): {response.text[:200]}")
        else:
            print(f"Response attributes: {dir(response)}")
            
    except Exception as e:
        print(f"✗ Error with {model_name}: {e}")

print("\n" + "="*60)
print("Testing complete!")

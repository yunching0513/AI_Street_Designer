#!/usr/bin/env python3
"""Manual smoke test for the configured Gemini image model.

This is intentionally not an automated pytest test because it makes a paid,
live API request. Run it directly when credentials and a sample image exist.
"""

import os
from google import genai
from google.genai import types
from dotenv import load_dotenv

def main():
    load_dotenv()
    api_key = os.getenv('GOOGLE_API_KEY')
    if not api_key:
        raise SystemExit('GOOGLE_API_KEY is required')

    client = genai.Client(api_key=api_key)
    test_image_path = 'static/uploads'
    image_files = [
        filename
        for filename in os.listdir(test_image_path)
        if filename.lower().endswith(('.jpg', '.jpeg', '.png'))
    ]
    if not image_files:
        raise SystemExit('No test images found in static/uploads')

    test_image = os.path.join(test_image_path, image_files[0])
    print(f'Using test image: {test_image}')
    with open(test_image, 'rb') as image_file:
        image_bytes = image_file.read()

    model_name = os.getenv('GEMINI_IMAGE_MODEL', 'gemini-3-pro-image')
    prompt_parts = [
        types.Part.from_text(
            text='Remove all cars from this street view. Keep everything else the same.'
        ),
        types.Part.from_bytes(data=image_bytes, mime_type='image/jpeg'),
    ]
    response = client.models.generate_content(
        model=model_name,
        contents=[types.Content(role='user', parts=prompt_parts)],
        config=types.GenerateContentConfig(response_modalities=['TEXT', 'IMAGE']),
    )
    image_parts = [
        part
        for candidate in (response.candidates or [])
        for part in candidate.content.parts
        if getattr(part, 'inline_data', None)
    ]
    print(f'{model_name}: received {len(image_parts)} image(s)')


if __name__ == '__main__':
    main()

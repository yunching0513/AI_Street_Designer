import os
import uuid
import glob
import time
import sys
import mimetypes
import base64
import json
import tempfile

# Python 3.9 compatibility patch
if sys.version_info < (3, 10):
    try:
        import importlib.metadata
        import importlib_metadata
        importlib.metadata.packages_distributions = importlib_metadata.packages_distributions
    except ImportError:
        pass

from flask import Flask, render_template, request, jsonify, url_for
from google import genai
from google.genai import types
from dotenv import load_dotenv
from PIL import Image
import io

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Vercel serverless environment: use /tmp for writable storage
# Note: /tmp is ephemeral and cleared between invocations
app.config['UPLOAD_FOLDER'] = '/tmp/uploads'
app.config['GENERATED_FOLDER'] = '/tmp/generated'
app.config['KNOWLEDGE_BASE_FOLDER'] = 'knowledge_base'  # Read-only, bundled with deployment

# Ensure directories exist (they may not persist between serverless invocations)
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['GENERATED_FOLDER'], exist_ok=True)
os.makedirs(app.config['KNOWLEDGE_BASE_FOLDER'], exist_ok=True)

# Configure Vertex AI Client
GOOGLE_CLOUD_PROJECT = os.getenv('GOOGLE_CLOUD_PROJECT')
GOOGLE_CLOUD_LOCATION = os.getenv('GOOGLE_CLOUD_LOCATION', 'us-central1')
GOOGLE_APPLICATION_CREDENTIALS = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
GOOGLE_APPLICATION_CREDENTIALS_JSON = os.getenv('GOOGLE_APPLICATION_CREDENTIALS_JSON')
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')

client = None
credentials_file_path = None

# Handle Vercel environment: create temp file from JSON string
if GOOGLE_APPLICATION_CREDENTIALS_JSON and not GOOGLE_APPLICATION_CREDENTIALS:
    try:
        # Create a temporary file for the credentials
        temp_creds = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
        temp_creds.write(GOOGLE_APPLICATION_CREDENTIALS_JSON)
        temp_creds.close()
        credentials_file_path = temp_creds.name
        print(f"✅ Created temporary credentials file from JSON environment variable")
    except Exception as e:
        print(f"❌ Failed to create credentials file from JSON: {e}")
elif GOOGLE_APPLICATION_CREDENTIALS:
    credentials_file_path = GOOGLE_APPLICATION_CREDENTIALS

# Try Vertex AI first (supports edit_image)
if GOOGLE_CLOUD_PROJECT and credentials_file_path:
    try:
        # Set the credentials environment variable for google-auth
        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = credentials_file_path
        
        client = genai.Client(
            vertexai=True,
            project=GOOGLE_CLOUD_PROJECT,
            location=GOOGLE_CLOUD_LOCATION
        )
        print(f"✅ Using Vertex AI")
        print(f"   Project: {GOOGLE_CLOUD_PROJECT}")
        print(f"   Location: {GOOGLE_CLOUD_LOCATION}")
        print(f"   Credentials: {credentials_file_path}")
    except Exception as e:
        print(f"❌ Failed to initialize Vertex AI Client: {e}")
        print(f"   Falling back to Gemini API if available...")

# Fall back to Gemini API (edit_image not supported)
if client is None and GOOGLE_API_KEY:
    try:
        client = genai.Client(api_key=GOOGLE_API_KEY)
        print("⚠️  Using Gemini API (edit_image not supported, will use generate_images)")
    except Exception as e:
        print(f"❌ Failed to initialize API Client: {e}")

if client is None:
    print("❌ No valid credentials found!")
    print("   Please set either:")
    print("   - GOOGLE_CLOUD_PROJECT + GOOGLE_APPLICATION_CREDENTIALS_JSON (for Vertex AI on Vercel)")
    print("   - GOOGLE_CLOUD_PROJECT + GOOGLE_APPLICATION_CREDENTIALS (for Vertex AI locally)")
    print("   - GOOGLE_API_KEY (for Gemini API)")

# Cache for knowledge base summary
KNOWLEDGE_CONTEXT_CACHE = None

def get_knowledge_context():
    """
    Analyzes all files in the knowledge_base folder using Gemini 1.5 Flash.
    Returns a summarized text of design principles.
    """
    global KNOWLEDGE_CONTEXT_CACHE
    if KNOWLEDGE_CONTEXT_CACHE is not None:
        return KNOWLEDGE_CONTEXT_CACHE
    
    if not client:
        return ""

    folder = app.config['KNOWLEDGE_BASE_FOLDER']
    
    print("Scanning knowledge base...")
    
    # 1. Collect Text Files
    txt_content = ""
    for filepath in glob.glob(os.path.join(folder, "*.txt")):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                txt_content += f"\n--- {os.path.basename(filepath)} ---\n{f.read()}\n"
        except Exception as e:
            print(f"Error reading {filepath}: {e}")

    # 2. Upload PDF Files to Gemini
    uploaded_files = []
    for filepath in glob.glob(os.path.join(folder, "*.pdf")):
        try:
            print(f"Uploading {filepath} to Gemini...")
            # Detect mime type
            mime_type, _ = mimetypes.guess_type(filepath)
            if not mime_type:
                mime_type = 'application/pdf'  # default for PDFs
            
            with open(filepath, "rb") as f:
                file_upload = client.files.upload(
                    file=f,
                    config=types.UploadFileConfig(
                        display_name=os.path.basename(filepath),
                        mime_type=mime_type
                    )
                )
            
            # Wait for processing
            while file_upload.state.name == "PROCESSING":
                print(".", end="", flush=True)
                time.sleep(1)
                file_upload = client.files.get(name=file_upload.name)
            
            if file_upload.state.name == "FAILED":
                print(f"Failed to process {filepath}")
                continue
                
            uploaded_files.append(file_upload)
            print(f"Ready: {filepath}")
        except Exception as e:
            print(f"Error uploading {filepath}: {e}")

    # If no knowledge base files, return empty
    if not txt_content and not uploaded_files:
        KNOWLEDGE_CONTEXT_CACHE = ""
        return ""

    # 3. Ask Gemini 1.5 Flash to summarize
    try:
        prompt_parts = []
        if txt_content:
            prompt_parts.append(types.Part.from_text(text=f"Here are some text notes:\n{txt_content}"))
        
        if uploaded_files:
            prompt_parts.append(types.Part.from_text(text="Here are some PDF documents containing design guidelines, diagrams, and images."))
            for uf in uploaded_files:
                prompt_parts.append(types.Part.from_uri(file_uri=uf.uri, mime_type=uf.mime_type))
            
        prompt_parts.append(types.Part.from_text(text="""
        You are an expert urban planner and design assistant. 
        Analyze the provided documents (text and PDFs). 
        The PDFs may contain visual diagrams, cross-sections, and example photos. 
        
        Extract the key DESIGN PRINCIPLES, VISUAL STYLES, and SPECIFIC GUIDELINES for street transformation.
        Focus on:
        1. Road layout and geometry.
        2. Materials and textures.
        3. Street furniture and greenery.
        4. Any specific aesthetic or functional rules.
        
        Summarize these into a concise set of instructions for an AI image generator.
        """))
        
        print("Consulting Gemini 2.0 Flash Exp for Knowledge Base Summary...")
        response = client.models.generate_content(
            model='gemini-2.0-flash-exp',
            contents=[types.Content(parts=prompt_parts)]
        )
        summary = response.text
        print("Knowledge Base Summary Generated.")
        
        KNOWLEDGE_CONTEXT_CACHE = summary
        return summary

    except Exception as e:
        print(f"Error analyzing knowledge base: {e}")
        return ""

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/transform', methods=['POST'])
def transform_image():
    if 'image' not in request.files:
        return jsonify({'error': 'No image uploaded'}), 400
    if not client:
        return jsonify({'error': 'Backend API Client not initialized. Check server logs.'}), 500
    
    file = request.files['image']
    custom_prompt = request.form.get('custom_prompt')
    
    if not file or file.filename == '':
        return jsonify({'error': 'Invalid file'}), 400

    # Save original image
    filename = str(uuid.uuid4()) + "_" + file.filename
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)
    
    # Read and encode the image for inline use (Vertex AI doesn't support File API)
    print(f"Preparing reference image: {filepath}")
    try:
        # Detect mime type
        mime_type, _ = mimetypes.guess_type(filepath)
        if not mime_type:
            mime_type = 'image/jpeg'  # default fallback
        
        # Read image as bytes and encode to base64
        with open(filepath, "rb") as f:
            image_bytes = f.read()
        base64_image = base64.b64encode(image_bytes).decode('utf-8')
        
        print(f"Image prepared (size: {len(image_bytes)} bytes, mime: {mime_type})")
        
    except Exception as e:
        print(f"Error preparing reference image: {e}")
        return jsonify({'error': f'Failed to prepare image: {str(e)}'}), 500
    
    # Get Knowledge context (temporarily disabled for Vertex AI compatibility)
    # knowledge_context = get_knowledge_context()
    knowledge_context = ""
    print("⚠️  Knowledge base context disabled for Vertex AI compatibility")
    
    # Try to match specific Design Prompt from Libraries
    # (Checking against keys in our new dictionaries)
    specialized_prompt = None
    negative_prompt = None
    
    # Import locally to avoid top-level path issues if file missing
    try:
        sys.path.append(os.path.join(app.root_path, 'knowledge_base'))
        from street_prompt_data_taiwan import get_taiwan_design_prompt
        from street_prompt_data_full import get_set_design_prompt
        
        # Check if custom_prompt matches a key (exact or partial)
        # For this demo, let's assume the user might type the exact key or we use the specific logic
        # Ideally, frontend would send a 'style_key'
        
        # Let's try to match strict keys first, or use the custom prompt as is
        # If the user selected a preset from UI, it might be in 'prompt_type' or 'custom_prompt'
        # The current UI sends 'custom_prompt' as the main text.
        
        # We will try to see if the custom_prompt *is* a key in our dictionaries
        p1, np1 = get_taiwan_design_prompt(custom_prompt, custom_prompt)
        if p1:
            specialized_prompt = p1
            negative_prompt = np1
        else:
            p2, np2 = get_set_design_prompt(custom_prompt, custom_prompt)
            if p2:
                specialized_prompt = p2
                negative_prompt = np2
                
    except ImportError as e:
        print(f"Could not import prompt libraries: {e}")

    # Construct prompt
    if specialized_prompt:
        # Use the highly structured specialized prompt
        full_prompt = specialized_prompt
        if knowledge_context:
             full_prompt += f"\n\n[Additional Context from Knowledge Base Files]:\n{knowledge_context}"
    else:
        # Fallback to the generic robust prompt (Role -> User -> Context -> Style)
        full_prompt = f"""
        ## ROLE
        You are an expert AI Urban Planner and Street Designer specialized in transforming street views.

        ## USER REQUEST (PRIMARY GOAL - MANDATORY)
        The user wants to transform this street view with the following specific vision:
        "{custom_prompt if custom_prompt else "Modern city street transformation"}"
        
        CRITICAL INSTRUCTION: You MUST prioritize this User Request above all else. If they ask for a specific element (e.g., "bike lane"), it MUST be visible.

        ## DESIGN GUIDELINES (CONTEXT - REFERENCE)
        Use the following principles from the knowledge base to guide the details of your design:
        --------------------------------------------------
        {knowledge_context if knowledge_context else "No specific guidelines provided."}
        --------------------------------------------------

        ## OUTPUT STYLE
        - Photorealistic, high-resolution, architectural visualization.
        - Natural lighting, realistic shadows and textures.
        - The perspective must match the original image exactly.
        """
    
    print(f"Generating with prompt:\n{full_prompt}")

    try:
        # Use Gemini 3 Pro Image Preview for TRUE image-to-image transformation
        # This model accepts the input image and generates a modified version
        print(f"Transforming image with gemini-3-pro-image-preview (TRUE image-to-image)...")
        
        # Build the prompt with both text instruction and reference image
        prompt_text = f"""Transform this street view image with the following changes:

{full_prompt}

CRITICAL INSTRUCTIONS:
- PRESERVE all buildings, their architecture, facades, and details EXACTLY as they are
- PRESERVE the camera perspective, angle, and viewpoint EXACTLY
- PRESERVE the lighting, weather, and atmospheric conditions
- ONLY modify street-level elements as requested (vehicles, lanes, sidewalks, greenery, etc.)
- Maintain photorealistic quality
- Keep the exact same composition

The result should look like the same street, same buildings, same view - just with the requested street changes applied."""

        if negative_prompt:
            prompt_text += f"\n\nDO NOT include: {negative_prompt}"
        
        transformation_parts = [
            types.Part.from_text(text=prompt_text),
            types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
        ]
        
        response = client.models.generate_content(
            model='gemini-3-pro-image-preview',
            contents=[types.Content(role='user', parts=transformation_parts)]
        )
        
        print(f"Image transformation complete!")
        
        # Extract the generated image from response
        generated_image_data = None
        if hasattr(response, 'candidates') and response.candidates:
            for part in response.candidates[0].content.parts:
                if hasattr(part, 'inline_data') and part.inline_data:
                    generated_image_data = part.inline_data.data
                    break
        
        if not generated_image_data:
            return jsonify({'error': 'No image generated in response'}), 500
            
        # Save the generated image
        generated_filename = "gen_" + filename
        generated_filepath = os.path.join(app.config['GENERATED_FOLDER'], generated_filename)
        with open(generated_filepath, "wb") as f:
            f.write(generated_image_data)
        
        return jsonify({
            'status': 'success',
            'image_url': url_for('static', filename=f'generated/{generated_filename}')
        })

    except Exception as e:
        print(f"Error generating image: {e}")
        return jsonify({'error': f"API Error: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(debug=True, port=8888)

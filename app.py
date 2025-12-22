import os
import uuid
import glob
import time
import sys

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
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['GENERATED_FOLDER'] = 'static/generated'
app.config['KNOWLEDGE_BASE_FOLDER'] = 'knowledge_base'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['GENERATED_FOLDER'], exist_ok=True)
os.makedirs(app.config['KNOWLEDGE_BASE_FOLDER'], exist_ok=True)

# Configure Gemini Client
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
client = None
if GOOGLE_API_KEY:
    try:
        client = genai.Client(api_key=GOOGLE_API_KEY)
    except Exception as e:
        print(f"Failed to initialize GenAI Client: {e}")

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
            with open(filepath, "rb") as f:
                file_upload = client.files.upload(
                    file=f,
                    config=types.UploadFileConfig(display_name=os.path.basename(filepath))
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
    
    # Get Knowledge context
    knowledge_context = get_knowledge_context()
    
    # Construct prompt
    base_prompt = "A photorealistic street view image. "
    if knowledge_context:
        base_prompt += f"\n\n[DESIGN GUIDELINES FROM KNOWLEDGE BASE]:\n{knowledge_context}\n\n"
    
    full_prompt = base_prompt + (custom_prompt if custom_prompt else "Modern city street transformation.")
    print(f"Generating with prompt: {full_prompt}")

    try:
        # Generate with Imagen 4
        response = client.models.generate_images(
            model='imagen-4.0-generate-001',
            prompt=full_prompt,
            config=types.GenerateImagesConfig(
                number_of_images=1,
            )
        )
        
        if response.generated_images:
            # Save the image
            generated_filename = "gen_" + filename
            generated_filepath = os.path.join(app.config['GENERATED_FOLDER'], generated_filename)
            
            # The new SDK might return bytes or a PIL image. Typically response.generated_images[0].image.image_bytes
            # Let's inspect or assume it returns an object with save method or bytes.
            # Usually types.GeneratedImage has 'image' property which is types.Image, containing 'image_bytes'.
            
            image_bytes = response.generated_images[0].image.image_bytes
            with open(generated_filepath, "wb") as f:
                f.write(image_bytes)
                
            return jsonify({
                'status': 'success',
                'image_url': url_for('static', filename=f'generated/{generated_filename}')
            })
        else:
            return jsonify({'error': 'No image generated'}), 500

    except Exception as e:
        print(f"Error generating image: {e}")
        return jsonify({'error': f"API Error: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(debug=True, port=8888)

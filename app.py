import os
import uuid
import glob
import time
import sys
import mimetypes
import base64
import json
import tempfile
import threading
import re

# Python 3.9 compatibility patch
if sys.version_info < (3, 10):
    try:
        import importlib.metadata
        import importlib_metadata
        importlib.metadata.packages_distributions = importlib_metadata.packages_distributions
    except ImportError:
        pass

from flask import Flask, render_template, request, jsonify, url_for, Response
from google import genai
from google.genai import types
from dotenv import load_dotenv
from PIL import Image
import io

try:
    import vercel_blob
except ImportError:
    vercel_blob = None

# Load environment variables
load_dotenv()

# Use Vercel Blob when a token is available (production on Vercel).
# Otherwise fall back to local static folders for dev.
USE_BLOB = bool(os.environ.get('BLOB_READ_WRITE_TOKEN')) and vercel_blob is not None

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['GENERATED_FOLDER'] = 'static/generated'
app.config['KNOWLEDGE_BASE_FOLDER'] = 'knowledge_base'

if not USE_BLOB:
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(app.config['GENERATED_FOLDER'], exist_ok=True)

# Configure Vertex AI Client
GOOGLE_CLOUD_PROJECT = os.getenv('GOOGLE_CLOUD_PROJECT')
GOOGLE_CLOUD_LOCATION = os.getenv('GOOGLE_CLOUD_LOCATION', 'us-central1')
GOOGLE_APPLICATION_CREDENTIALS = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
GOOGLE_APPLICATION_CREDENTIALS_JSON = os.getenv('GOOGLE_APPLICATION_CREDENTIALS_JSON')
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')

client = None
credentials_file_path = None

# Handle Vercel environment: create temp file from JSON string
# (Removed for Render deployment)
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

# ===== Taiwan design knowledge base (curated markdown) =====
TAIWAN_KB_PATH = os.path.join('knowledge_base', 'taiwan_design_principles.md')
_TAIWAN_KB_CACHE = None  # tuple (style_intro, positive_cues, negative_cues) or None

def load_taiwan_knowledge():
    """Read taiwan_design_principles.md once and extract the parts that should
    be injected into image-generation prompts.

    Returns (style_intro, positive_cues, negative_cues). Each may be an empty
    string if the file is missing or the section can't be parsed.
    """
    global _TAIWAN_KB_CACHE
    if _TAIWAN_KB_CACHE is not None:
        return _TAIWAN_KB_CACHE

    path = os.path.join(app.root_path, TAIWAN_KB_PATH)
    if not os.path.exists(path):
        print(f"⚠️  Taiwan knowledge file not found: {path}")
        _TAIWAN_KB_CACHE = ('', '', '')
        return _TAIWAN_KB_CACHE

    try:
        with open(path, 'r', encoding='utf-8') as f:
            md = f.read()
    except Exception as e:
        print(f"⚠️  Failed to read Taiwan knowledge file: {e}")
        _TAIWAN_KB_CACHE = ('', '', '')
        return _TAIWAN_KB_CACHE

    # Section: "## 整體風格與台灣脈絡" -> brief style intro (Chinese, sets tone)
    intro_m = re.search(r'##\s*整體風格與台灣脈絡\s*\n(.*?)(?=\n##\s|\n---)', md, re.DOTALL)
    style_intro = intro_m.group(1).strip() if intro_m else ''

    # Section 12: quick reference card (English short prompts)
    pos_m = re.search(r'##\s*12\.[^\n]*\n(.*?)(?=\n##\s|\Z)', md, re.DOTALL)
    positive_cues = pos_m.group(1).strip() if pos_m else ''

    # Section 13: negative prompts
    neg_m = re.search(r'##\s*13\.[^\n]*\n(.*?)(?=\n##\s|\Z)', md, re.DOTALL)
    negative_cues = neg_m.group(1).strip() if neg_m else ''

    print(f"✅ Loaded Taiwan KB: intro={len(style_intro)}c, +cues={len(positive_cues)}c, -cues={len(negative_cues)}c")
    _TAIWAN_KB_CACHE = (style_intro, positive_cues, negative_cues)
    return _TAIWAN_KB_CACHE

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
            model='gemini-2.5-flash',
            contents=[types.Content(parts=prompt_parts)]
        )
        summary = response.text
        print("Knowledge Base Summary Generated.")
        
        KNOWLEDGE_CONTEXT_CACHE = summary
        return summary

    except Exception as e:
        print(f"Error analyzing knowledge base: {e}")
        return ""

# ===== Co-pilot session storage =====
SESSIONS = {}
SESSIONS_LOCK = threading.Lock()
MAX_SESSIONS = 200  # simple LRU cap

COPILOT_PERSONA = """你是「小綠」🌱，一個熱愛永續設計、活潑友善的 AI 街道設計副駕駛。
你和使用者並肩工作，一起把街道改造得更好。你的個性：友善、有同理心、會主動觀察畫面細節、講話帶一點溫度。
你只用繁體中文回覆，自然口語，每次 2-4 句，可以用 1-2 個表情符號（不要過多）。"""

CHAT_SYSTEM_PROMPT = COPILOT_PERSONA + """

每當使用者傳訊息來，你都要做以下事情：
1. 觀察目前最新的街道圖片。
2. 判斷使用者意圖：
   - "refine" = 使用者想修改畫面（例：「再加幾棵樹」「人行道更寬」「換成夜景」「右邊那家店前面加座位」）
   - "chat" = 純粹聊天 / 問問題 / 表達感想（例：「你覺得這版怎麼樣？」「為什麼要加自行車道？」「不錯欸」）
3. 用親切口吻寫回覆，自然延續對話，必要時主動點出畫面細節。
4. 提供 3 個簡短後續建議（每個 4-10 字），幫使用者繼續共創。
5. 如果是 refine，產出一段精準的英文修改指令給圖片生成模型；不是 refine 就留空字串。

只回 JSON，格式如下：
{
  "intent": "refine" 或 "chat",
  "message": "給使用者的繁中回覆",
  "refine_prompt": "英文修改指令；intent=chat 時為空字串",
  "suggestions": ["建議1", "建議2", "建議3"]
}"""

GREETING_SYSTEM_PROMPT = COPILOT_PERSONA + """

使用者剛剛上傳了一張街道照片，要求改造成：「{user_prompt}」
你已經完成第一版設計，畫面如附圖。

請：
1. 用 2-3 句親切的話打招呼，並具體點出你在畫面中加入了什麼（觀察附圖細節）。
2. 主動丟一個有趣的後續問題邀請使用者繼續共創。
3. 給 3 個簡短後續建議（每個 4-10 字）。

只回 JSON：
{
  "message": "繁中歡迎詞 3-4 句",
  "suggestions": ["建議1", "建議2", "建議3"]
}"""


def _parse_json_response(text):
    """Robustly parse JSON from a possibly fenced LLM response."""
    if not text:
        raise ValueError("Empty response")
    text = text.strip()
    # Strip ```json ... ``` fences if present
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    return json.loads(text)


def _read_image_bytes(path):
    mime_type, _ = mimetypes.guess_type(path)
    if not mime_type:
        mime_type = 'image/jpeg'
    with open(path, 'rb') as f:
        return f.read(), mime_type


def _generate_image_from_reference(image_bytes, mime_type, prompt_text, resolution='2K'):
    """Call the image-to-image model and return the generated image bytes.

    resolution: '1K' | '2K' | '4K' — Nano Banana Pro output size. Falls back
    to the model default if this SDK build lacks ImageConfig.
    """
    transformation_parts = [
        types.Part.from_text(text=prompt_text),
        types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
    ]
    kwargs = dict(
        model='gemini-3-pro-image-preview',
        contents=[types.Content(role='user', parts=transformation_parts)]
    )
    if resolution in ('1K', '2K', '4K'):
        try:
            kwargs['config'] = types.GenerateContentConfig(
                response_modalities=['TEXT', 'IMAGE'],
                image_config=types.ImageConfig(image_size=resolution),
            )
        except Exception as e:
            print(f"ImageConfig unavailable ({e}); using model default resolution")
    response = client.models.generate_content(**kwargs)
    if hasattr(response, 'candidates') and response.candidates:
        for part in response.candidates[0].content.parts:
            if hasattr(part, 'inline_data') and part.inline_data:
                return part.inline_data.data
    return None


def _save_generated_image(session_id, version, image_bytes):
    """Save a generated image, returning (url, version_meta).

    Uses Vercel Blob when configured (production on Vercel) and falls back
    to the local static folder for dev. We also keep the bytes in the
    returned metadata so the co-pilot can refine without re-fetching.
    """
    filename = f"v{version}.png"
    mime_type = 'image/png'

    if USE_BLOB:
        blob_path = f'generated/{session_id}/{filename}'
        blob_result = vercel_blob.put(
            blob_path,
            image_bytes,
            {'access': 'public', 'addRandomSuffix': 'false'}
        )
        image_url = blob_result['url']
        print(f"Uploaded version to Vercel Blob: {image_url}")
    else:
        session_dir = os.path.join(app.config['GENERATED_FOLDER'], session_id)
        os.makedirs(session_dir, exist_ok=True)
        filepath = os.path.join(session_dir, filename)
        with open(filepath, "wb") as f:
            f.write(image_bytes)
        image_url = url_for('static', filename=f'generated/{session_id}/{filename}')

    # Keep only a SHRUNK copy in session memory. Storing full-res bytes
    # (multi-MB at 2K/4K) across up to 200 LRU sessions OOMs the 512 MB
    # instance and gets workers killed mid-request (bare 500/502s).
    small_bytes, small_mime = _shrink_for_llm(image_bytes)
    version_meta = {
        'url': image_url,
        'bytes': small_bytes,
        'mime_type': small_mime,
    }
    return image_url, version_meta


# Text models for 小綠, tried in order — if one is unavailable on this key
# or region the next takes over, and the real error is logged either way.
COPILOT_TEXT_MODELS = ['gemini-2.5-flash', 'gemini-flash-latest', 'gemini-2.0-flash']

def _shrink_for_llm(image_bytes, max_dim=1024):
    """Downscale an image before showing it to the text model — 2K/4K PNGs
    waste tokens and can blow the inline request-size limit, which kills the
    whole chat call."""
    try:
        img = Image.open(io.BytesIO(image_bytes)).convert('RGB')
        img.thumbnail((max_dim, max_dim))
        buf = io.BytesIO()
        img.save(buf, format='JPEG', quality=82)
        return buf.getvalue(), 'image/jpeg'
    except Exception as e:
        print(f"shrink_for_llm failed ({e}); sending original bytes")
        return image_bytes, 'image/png'


def _copilot_generate_json(parts):
    """generate_content with a model fallback chain; returns parsed JSON."""
    last_err = None
    for m in COPILOT_TEXT_MODELS:
        try:
            response = client.models.generate_content(
                model=m,
                contents=[types.Content(role='user', parts=parts)],
                config=types.GenerateContentConfig(response_mime_type='application/json')
            )
            return _parse_json_response(response.text)
        except Exception as e:
            print(f"copilot text model {m} failed: {e}")
            last_err = e
    raise last_err


def _generate_copilot_greeting(image_bytes, mime_type, user_prompt):
    """Have 小綠 review the new image and craft a welcome message + suggestions."""
    fallback = {
        'message': '嗨，我是小綠 🌱 第一版設計出來了！你覺得整體感覺如何？想往哪個方向繼續調整？',
        'suggestions': ['再加一些樹', '加點街頭藝術', '換成夜景氛圍']
    }
    if not client:
        return fallback
    try:
        # str.replace, NOT str.format — the template's JSON example braces
        # make .format() raise KeyError on every single call.
        prompt = GREETING_SYSTEM_PROMPT.replace('{user_prompt}', user_prompt or "讓街道更宜居")
        small_bytes, small_mime = _shrink_for_llm(image_bytes)
        parts = [
            types.Part.from_text(text=prompt),
            types.Part.from_bytes(data=small_bytes, mime_type=small_mime)
        ]
        data = _copilot_generate_json(parts)
        return {
            'message': data.get('message', fallback['message']),
            'suggestions': data.get('suggestions', fallback['suggestions'])[:3]
        }
    except Exception as e:
        print(f"Greeting generation failed: {e}")
        return fallback


def _decide_copilot_response(history, latest_image_bytes, mime_type, user_message):
    """Ask 小綠 to classify intent and produce a chat reply + refine prompt."""
    fallback = {
        'intent': 'chat',
        'message': '嗯！我有聽到 🌱 但我剛剛卡住了，可以再說一次你想調整的地方嗎？',
        'refine_prompt': '',
        'suggestions': ['再多一些綠化', '加長椅與休憩區', '換個天氣']
    }
    if not client:
        return fallback
    try:
        history_text = "\n".join(
            f"{'使用者' if h['role'] == 'user' else '小綠'}：{h['message']}"
            for h in history[-8:]  # keep last 8 turns
        ) or "(尚無歷史)"
        prompt_text = (
            CHAT_SYSTEM_PROMPT
            + f"\n\n=== 對話歷史 ===\n{history_text}\n\n=== 使用者最新訊息 ===\n{user_message}"
        )
        small_bytes, small_mime = _shrink_for_llm(latest_image_bytes)
        parts = [
            types.Part.from_text(text=prompt_text),
            types.Part.from_bytes(data=small_bytes, mime_type=small_mime)
        ]
        data = _copilot_generate_json(parts)
        intent = data.get('intent', 'chat')
        if intent not in ('refine', 'chat'):
            intent = 'chat'
        return {
            'intent': intent,
            'message': data.get('message', fallback['message']),
            'refine_prompt': data.get('refine_prompt', '') or '',
            'suggestions': data.get('suggestions', fallback['suggestions'])[:3]
        }
    except Exception as e:
        print(f"Co-pilot decision failed: {e}")
        return fallback


def _create_session(initial_version_path, initial_prompt):
    """Create a new co-pilot session and return its id."""
    session_id = uuid.uuid4().hex[:12]
    with SESSIONS_LOCK:
        # Simple LRU eviction
        if len(SESSIONS) >= MAX_SESSIONS:
            oldest = next(iter(SESSIONS))
            SESSIONS.pop(oldest, None)
        SESSIONS[session_id] = {
            'versions': [initial_version_path],
            'history': [],
            'initial_prompt': initial_prompt or '',
            'created_at': time.time(),
        }
    return session_id


def _get_session(session_id):
    with SESSIONS_LOCK:
        return SESSIONS.get(session_id)


@app.route('/')
def index():
    return render_template('index.html')

@app.errorhandler(Exception)
def _unhandled_error(e):
    """Return JSON (and log the traceback) instead of Flask's bare HTML 500,
    so the frontend can show a real message and Render logs show the cause."""
    import traceback
    from werkzeug.exceptions import HTTPException
    if isinstance(e, HTTPException):
        return e
    traceback.print_exc()
    return jsonify({'error': f'{e.__class__.__name__}: {str(e)[:200]}'}), 500

@app.route('/api/diag')
def diag():
    # Model health check: which of 小綠's text models actually answer on this
    # deployment's key/region. Open this in a browser when chat misbehaves.
    out = {'client': bool(client), 'image_model': 'gemini-3-pro-image-preview', 'text_models': {}}
    if client:
        for m in COPILOT_TEXT_MODELS:
            try:
                client.models.generate_content(model=m, contents='ping')
                out['text_models'][m] = 'ok'
            except Exception as e:
                out['text_models'][m] = f'error: {str(e)[:200]}'
    return jsonify(out)

@app.route('/api/fetch_street')
def fetch_street():
    # Server-side fetch of a Street View Static image handed over from the
    # schoolzone map (?img=... on the front page). Browser-side fetch would
    # hit CORS and the Maps key's referrer restriction; the backend has
    # neither problem. Restricted to the Street View Static endpoint so this
    # can't be used as an open proxy.
    url = request.args.get('url', '')
    if not url.startswith('https://maps.googleapis.com/maps/api/streetview'):
        return jsonify({'error': 'unsupported url'}), 400
    try:
        import urllib.request
        req = urllib.request.Request(url, headers={'User-Agent': 'ai-street-designer'})
        with urllib.request.urlopen(req, timeout=15) as r:
            data = r.read()
            ctype = r.headers.get('Content-Type', 'image/jpeg')
        if not ctype.startswith('image/'):
            return jsonify({'error': 'not an image'}), 502
        return Response(data, mimetype=ctype)
    except Exception as e:
        return jsonify({'error': f'fetch failed: {e}'}), 502

@app.route('/api/transform', methods=['POST'])
def transform_image():
    if 'image' not in request.files:
        return jsonify({'error': 'No image uploaded'}), 400
    if not client:
        return jsonify({'error': 'Backend API Client not initialized. Check server logs.'}), 500
    
    file = request.files['image']
    custom_prompt = request.form.get('custom_prompt')
    resolution = request.form.get('resolution', '2K')
    if resolution not in ('1K', '2K', '4K'):
        resolution = '2K'
    
    if not file or file.filename == '':
        return jsonify({'error': 'Invalid file'}), 400

    # Read original image bytes directly (avoids writing to read-only FS on Vercel)
    filename = str(uuid.uuid4()) + "_" + file.filename
    print(f"Preparing reference image: {filename}")
    try:
        mime_type, _ = mimetypes.guess_type(file.filename)
        if not mime_type:
            mime_type = 'image/jpeg'  # default fallback

        image_bytes = file.read()
        base64_image = base64.b64encode(image_bytes).decode('utf-8')

        print(f"Image prepared (size: {len(image_bytes)} bytes, mime: {mime_type})")

    except Exception as e:
        print(f"Error preparing reference image: {e}")
        return jsonify({'error': f'Failed to prepare image: {str(e)}'}), 500
    
    # Load Taiwan human-centered street design knowledge (curated markdown).
    # Style intro + the english "quick reference card" go into the prompt;
    # the negative-cue section gets merged into negative_prompt below.
    kb_style_intro, kb_positive_cues, kb_negative_cues = load_taiwan_knowledge()
    knowledge_context_parts = []
    if kb_style_intro:
        knowledge_context_parts.append("[Overall Taiwan Street Style]\n" + kb_style_intro)
    if kb_positive_cues:
        knowledge_context_parts.append("[Concrete Visual Rules]\n" + kb_positive_cues)
    knowledge_context = "\n\n".join(knowledge_context_parts)
    
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

    # Merge curated Taiwan negative cues into whatever negative_prompt the
    # preset matcher produced (if any). Preset wins on top, KB cues append.
    if kb_negative_cues:
        if negative_prompt:
            negative_prompt = f"{negative_prompt}\n{kb_negative_cues}"
        else:
            negative_prompt = kb_negative_cues

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

        generated_image_data = _generate_image_from_reference(image_bytes, mime_type, prompt_text, resolution=resolution)
        print(f"Image transformation complete!")

        if not generated_image_data:
            return jsonify({'error': 'No image generated in response'}), 500

        # Create co-pilot session and save v1 (Vercel Blob in prod, local disk in dev)
        session_id = uuid.uuid4().hex[:12]
        generated_url, version_meta = _save_generated_image(session_id, 1, generated_image_data)
        with SESSIONS_LOCK:
            if len(SESSIONS) >= MAX_SESSIONS:
                SESSIONS.pop(next(iter(SESSIONS)), None)
            SESSIONS[session_id] = {
                'versions': [version_meta],
                'history': [],
                'initial_prompt': custom_prompt or '',
                'resolution': resolution,
                'created_at': time.time(),
            }

        # Ask 小綠 to write a greeting based on what was generated
        greeting = _generate_copilot_greeting(generated_image_data, 'image/png', custom_prompt or '')
        with SESSIONS_LOCK:
            SESSIONS[session_id]['history'].append({'role': 'assistant', 'message': greeting['message']})

        return jsonify({
            'status': 'success',
            'session_id': session_id,
            'version': 1,
            'image_url': generated_url,
            'copilot': {
                'message': greeting['message'],
                'suggestions': greeting['suggestions'],
            }
        })

    except Exception as e:
        print(f"Error generating image: {e}")
        return jsonify({'error': f"API Error: {str(e)}"}), 500


@app.route('/api/chat', methods=['POST'])
def chat_with_copilot():
    """Co-pilot dialogue endpoint: classifies intent, optionally refines the image."""
    if not client:
        return jsonify({'error': 'Backend API Client not initialized.'}), 500

    data = request.get_json(silent=True) or {}
    session_id = data.get('session_id')
    user_message = (data.get('message') or '').strip()

    if not session_id or not user_message:
        return jsonify({'error': 'session_id and message are required'}), 400

    session = _get_session(session_id)
    if not session:
        return jsonify({'error': 'Session not found or expired'}), 404

    latest = session['versions'][-1]
    latest_bytes = latest['bytes']
    mime_type = latest.get('mime_type', 'image/png')

    # Record the user turn before asking the model
    with SESSIONS_LOCK:
        session['history'].append({'role': 'user', 'message': user_message})
        history_snapshot = list(session['history'])

    decision = _decide_copilot_response(history_snapshot, latest_bytes, mime_type, user_message)

    result = {
        'status': 'success',
        'session_id': session_id,
        'intent': decision['intent'],
        'message': decision['message'],
        'suggestions': decision['suggestions'],
    }

    if decision['intent'] == 'refine' and decision['refine_prompt']:
        refine_prompt = decision['refine_prompt']
        original_prompt = session.get('initial_prompt') or ''
        full_prompt = f"""Apply the following refinement to this street view image.

USER'S NEW REQUEST (HIGHEST PRIORITY):
{refine_prompt}

ORIGINAL VISION (context only):
{original_prompt or 'Improve the street design.'}

CRITICAL INSTRUCTIONS:
- PRESERVE all buildings, architecture, facades exactly
- PRESERVE camera perspective and viewpoint exactly
- ONLY adjust street-level elements as instructed
- Photorealistic quality, consistent lighting"""
        try:
            new_image_bytes = _generate_image_from_reference(
                latest_bytes, mime_type, full_prompt,
                resolution=session.get('resolution', '2K'))
        except Exception as e:
            print(f"Refinement generation failed: {e}")
            new_image_bytes = None

        if new_image_bytes:
            with SESSIONS_LOCK:
                version_num = len(session['versions']) + 1
            new_url, new_meta = _save_generated_image(session_id, version_num, new_image_bytes)
            with SESSIONS_LOCK:
                session['versions'].append(new_meta)
                session['history'].append({'role': 'assistant', 'message': decision['message']})
            result.update({
                'image_url': new_url,
                'version': version_num,
            })
        else:
            # Couldn't regenerate — downgrade to a chat response
            result['intent'] = 'chat'
            result['message'] = (
                decision['message']
                + '\n\n（不過我剛剛畫的時候卡住了一下，可以再描述一次你想看到的樣子嗎？）'
            )
            with SESSIONS_LOCK:
                session['history'].append({'role': 'assistant', 'message': result['message']})
    else:
        with SESSIONS_LOCK:
            session['history'].append({'role': 'assistant', 'message': decision['message']})

    return jsonify(result)

if __name__ == '__main__':
    app.run(debug=True, port=8888)

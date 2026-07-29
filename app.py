import base64
import gc
import glob
import hashlib
import hmac
import io
import json
import math
import mimetypes
import os
import re
import resource
import shutil
import sys
import threading
import time
import traceback
import urllib.parse
import urllib.request
import uuid

# Bumped by hand on each deploy-worthy change — /api/diag reports it, so we
# can tell at a glance whether the running instance actually has a fix.
CODE_VERSION = '2026-07-27-openai-image2'

def rss_mb():
    """Resident memory of this worker, in MB (Linux)."""
    try:
        return round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1)
    except Exception:
        return -1

# Python 3.9 compatibility patch
if sys.version_info < (3, 10):
    try:
        import importlib.metadata
        import importlib_metadata
        importlib.metadata.packages_distributions = importlib_metadata.packages_distributions
    except ImportError:
        pass

from flask import Flask, render_template, request, jsonify, url_for, Response, g
from google import genai
from google.genai import types
from dotenv import load_dotenv
from PIL import Image, UnidentifiedImageError
from werkzeug.exceptions import HTTPException
from werkzeug.middleware.proxy_fix import ProxyFix

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

try:
    import vercel_blob
except ImportError:
    vercel_blob = None

try:
    import redis
except ImportError:
    redis = None

# Load environment variables
load_dotenv()

# Use Vercel Blob when a token is available (production on Vercel).
# Otherwise fall back to local static folders for dev.
USE_BLOB = bool(os.environ.get('BLOB_READ_WRITE_TOKEN')) and vercel_blob is not None

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['GENERATED_FOLDER'] = 'static/generated'
app.config['KNOWLEDGE_BASE_FOLDER'] = 'knowledge_base'
app.config['MAX_CONTENT_LENGTH'] = 12 * 1024 * 1024
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)

if not USE_BLOB:
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(app.config['GENERATED_FOLDER'], exist_ok=True)

# Configure Vertex AI Client
GOOGLE_CLOUD_PROJECT = os.getenv('GOOGLE_CLOUD_PROJECT')
GOOGLE_CLOUD_LOCATION = os.getenv('GOOGLE_CLOUD_LOCATION', 'us-central1')
GOOGLE_APPLICATION_CREDENTIALS = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
GOOGLE_APPLICATION_CREDENTIALS_JSON = os.getenv('GOOGLE_APPLICATION_CREDENTIALS_JSON')
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
DIAG_TOKEN = os.getenv('DIAG_TOKEN', '')
REDIS_URL = os.getenv('REDIS_URL', '')
STATE_KEY_PREFIX = os.getenv(
    'STATE_KEY_PREFIX',
    'ai-street-designer',
).strip() or 'ai-street-designer'

GEMINI_IMAGE_MODEL = os.getenv('GEMINI_IMAGE_MODEL', 'gemini-3-pro-image')
OPENAI_IMAGE_MODEL = os.getenv('OPENAI_IMAGE_MODEL', 'gpt-image-2')
COPILOT_TEXT_MODELS = [
    model.strip()
    for model in os.getenv('GEMINI_TEXT_MODELS', 'gemini-flash-latest').split(',')
    if model.strip()
] or ['gemini-flash-latest']
GENAI_HTTP_OPTIONS = types.HttpOptions(
    timeout=240_000,
    retry_options=types.HttpRetryOptions(attempts=1),
)


def _env_int(name, default, minimum=1, maximum=None):
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        value = default
    value = max(minimum, value)
    return min(value, maximum) if maximum is not None else value


MAX_IMAGE_BYTES = 8 * 1024 * 1024
MAX_IMAGE_PIXELS = 24_000_000
MAX_PROMPT_CHARS = 2_000
MAX_CHAT_CHARS = 1_000
MAX_FETCH_BYTES = 5 * 1024 * 1024
OPENAI_MIN_IMAGE_PIXELS = 655_360
OPENAI_MAX_IMAGE_PIXELS = 8_294_400
OPENAI_MAX_IMAGE_EDGE = 3_840
SESSION_TTL_SECONDS = _env_int('SESSION_TTL_SECONDS', 7_200, 300, 86_400)
MAX_SESSIONS = _env_int('MAX_SESSIONS', 40, 5, 200)
MAX_HISTORY_TURNS = _env_int('MAX_HISTORY_TURNS', 30, 8, 100)
MAX_SESSION_VERSIONS = _env_int('MAX_SESSION_VERSIONS', 8, 2, 20)
MAX_GENERATIONS_PER_HOUR = _env_int(
    'MAX_GENERATIONS_PER_HOUR', 6, 1, 100)
MAX_CHATS_PER_10_MINUTES = _env_int(
    'MAX_CHATS_PER_10_MINUTES', 60, 1, 1_000)
MAX_STREET_FETCHES_PER_HOUR = _env_int(
    'MAX_STREET_FETCHES_PER_HOUR', 120, 1, 2_000)

client = None
openai_client = None
redis_client = None
credentials_file_path = None

if REDIS_URL and redis:
    try:
        redis_client = redis.Redis.from_url(
            REDIS_URL,
            decode_responses=False,
            socket_connect_timeout=2,
            socket_timeout=2,
            socket_keepalive=True,
            health_check_interval=30,
        )
        redis_client.ping()
        print("✅ Redis session storage and distributed limits ready")
    except Exception as e:
        redis_client = None
        print(
            "⚠️  Redis unavailable; falling back to process-local state "
            f"({e.__class__.__name__})"
        )
elif REDIS_URL:
    print("⚠️  REDIS_URL is set but the redis package is unavailable")

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
            location=GOOGLE_CLOUD_LOCATION,
            http_options=GENAI_HTTP_OPTIONS,
        )
        print("✅ Using Vertex AI")
        print(f"   Project: {GOOGLE_CLOUD_PROJECT}")
        print(f"   Location: {GOOGLE_CLOUD_LOCATION}")
        print(f"   Credentials: {credentials_file_path}")
    except Exception as e:
        print(f"❌ Failed to initialize Vertex AI Client: {e}")
        print("   Falling back to Gemini API if available...")

# Fall back to Gemini API (edit_image not supported)
if client is None and GOOGLE_API_KEY:
    try:
        client = genai.Client(
            api_key=GOOGLE_API_KEY,
            http_options=GENAI_HTTP_OPTIONS,
        )
        print(f"✅ Gemini API ready ({GEMINI_IMAGE_MODEL})")
    except Exception as e:
        print(f"❌ Failed to initialize API Client: {e}")

if client is None:
    print("⚠️  Gemini credentials not found.")
    print("   To enable Gemini image generation and 小綠, set either:")
    print("   - GOOGLE_CLOUD_PROJECT + GOOGLE_APPLICATION_CREDENTIALS_JSON (for Vertex AI on Vercel)")
    print("   - GOOGLE_CLOUD_PROJECT + GOOGLE_APPLICATION_CREDENTIALS (for Vertex AI locally)")
    print("   - GOOGLE_API_KEY (for Gemini API)")

if OPENAI_API_KEY and OpenAI:
    try:
        # Image edits may take close to two minutes. Keep one request below the
        # Gunicorn timeout and let the user retry instead of silently doubling
        # the request duration inside the SDK.
        openai_client = OpenAI(
            api_key=OPENAI_API_KEY,
            timeout=180.0,
            max_retries=0,
        )
        print(f"✅ OpenAI image generation ready ({OPENAI_IMAGE_MODEL})")
    except Exception as e:
        print(f"❌ Failed to initialize OpenAI Client: {e}")
elif OPENAI_API_KEY and not OpenAI:
    print("❌ OPENAI_API_KEY is set, but the openai package is not installed.")
else:
    print("ℹ️  OPENAI_API_KEY not set; OpenAI image generation is disabled.")

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
        
        print(f"Consulting {COPILOT_TEXT_MODELS[0]} for Knowledge Base Summary...")
        response = client.models.generate_content(
            model=COPILOT_TEXT_MODELS[0],
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
RATE_LIMITS = {}
RATE_LIMITS_LOCK = threading.Lock()
SESSION_INDEX_KEY = f'{STATE_KEY_PREFIX}:sessions'
SESSION_LOCK_SECONDS = 360

RATE_LIMIT_SCRIPT = """
local count = redis.call('INCR', KEYS[1])
if count == 1 then
    redis.call('EXPIRE', KEYS[1], ARGV[1])
end
local ttl = redis.call('TTL', KEYS[1])
return {count, ttl}
"""

LOCK_RELEASE_SCRIPT = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
    return redis.call('DEL', KEYS[1])
end
return 0
"""

# One generation at a time: concurrent multi-MB generations on the 512 MB
# free instance OOM-kill the worker mid-request (gunicorn's bare 500 page).
GEN_LOCK = threading.BoundedSemaphore(1)
GEN_LOCK_HELD = False

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


def _validate_uploaded_image(file):
    """Read and validate an uploaded image from its actual bytes."""
    image_bytes = file.read(MAX_IMAGE_BYTES + 1)
    if not image_bytes:
        raise ValueError('上傳的圖片是空的。')
    if len(image_bytes) > MAX_IMAGE_BYTES:
        raise ValueError('圖片不可超過 8 MB。')

    try:
        with Image.open(io.BytesIO(image_bytes)) as image:
            image_format = (image.format or '').upper()
            width, height = image.size
            if width < 128 or height < 128:
                raise ValueError('圖片長寬至少需要 128 像素。')
            if width * height > MAX_IMAGE_PIXELS:
                raise ValueError('圖片像素過大，請縮小到 2400 萬像素以下。')
            image.verify()
    except ValueError:
        raise
    except (
        Image.DecompressionBombError,
        UnidentifiedImageError,
        OSError,
        SyntaxError,
    ) as e:
        raise ValueError('檔案不是有效的 JPEG、PNG 或 WebP 圖片。') from e

    mime_type = {
        'JPEG': 'image/jpeg',
        'PNG': 'image/png',
        'WEBP': 'image/webp',
    }.get(image_format)
    if not mime_type:
        raise ValueError('目前只支援 JPEG、PNG 與 WebP 圖片。')
    return image_bytes, mime_type


IMAGE_PROVIDER_LABELS = {
    'gemini': 'Google Gemini',
    'openai': 'OpenAI GPT Image',
}

PRESET_STYLE_KEYS = {
    'widen-sidewalks': '連續人行道拓寬 (Widened Sidewalk)',
    'transit-priority': '公車彎與公車優先道 (Bus Bay & Transit Priority)',
    'protected-bike-lane': '自行車專用道 (Protected Bike Lane)',
    'green-street': '街道綠化與設施帶 (Green Street)',
    'reduce-motor-traffic': '減少汽機車與道路空間重分配 (Reduced Motor Traffic)',
}


def _image_provider_is_ready(provider):
    if provider == 'gemini':
        return client is not None
    if provider == 'openai':
        return openai_client is not None
    return False


def _image_provider_options():
    return [
        {
            'value': 'gemini',
            'label': IMAGE_PROVIDER_LABELS['gemini'],
            'model': GEMINI_IMAGE_MODEL,
            'available': _image_provider_is_ready('gemini'),
        },
        {
            'value': 'openai',
            'label': IMAGE_PROVIDER_LABELS['openai'],
            'model': OPENAI_IMAGE_MODEL,
            'available': _image_provider_is_ready('openai'),
        },
    ]


def _openai_image_settings(image_bytes, resolution):
    """Choose a valid gpt-image-2 size while preserving source orientation."""
    try:
        with Image.open(io.BytesIO(image_bytes)) as image:
            width, height = image.size
    except Exception:
        width, height = 3, 2

    is_landscape = width >= height
    ratio = max(width, height) / max(1, min(width, height))
    ratio = min(max(ratio, 1.0), 3.0)

    if resolution == '1K':
        long_edge = 1024
        short_edge = long_edge / ratio
        quality = 'low'
    elif resolution == '4K':
        # gpt-image-2 currently caps the long/short edges at 3840/2160.
        short_edge = min(2160, 3840 / ratio)
        long_edge = min(3840, short_edge * ratio)
        quality = 'high'
    else:
        long_edge = 2048
        short_edge = long_edge / ratio
        quality = 'medium'

    def multiple_of_16(value):
        return max(16, math.ceil(value / 16) * 16)

    long_edge = multiple_of_16(long_edge)
    short_edge = multiple_of_16(short_edge)
    total_pixels = long_edge * short_edge
    if total_pixels < OPENAI_MIN_IMAGE_PIXELS:
        scale = math.sqrt(OPENAI_MIN_IMAGE_PIXELS / total_pixels)
        long_edge = multiple_of_16(long_edge * scale)
        short_edge = multiple_of_16(short_edge * scale)

    while long_edge * short_edge > OPENAI_MAX_IMAGE_PIXELS:
        if long_edge >= short_edge:
            long_edge -= 16
        else:
            short_edge -= 16
    long_edge = min(long_edge, OPENAI_MAX_IMAGE_EDGE)
    short_edge = min(short_edge, OPENAI_MAX_IMAGE_EDGE)

    size = (
        f'{long_edge}x{short_edge}'
        if is_landscape
        else f'{short_edge}x{long_edge}'
    )
    return size, quality


def _generate_gemini_image(image_bytes, mime_type, prompt_text, resolution):
    transformation_parts = [
        types.Part.from_text(text=prompt_text),
        types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
    ]
    kwargs = dict(
        model=GEMINI_IMAGE_MODEL,
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


def _generate_openai_image(image_bytes, mime_type, prompt_text, resolution):
    size, quality = _openai_image_settings(image_bytes, resolution)
    supported_extensions = {
        'image/jpeg': '.jpg',
        'image/jpg': '.jpg',
        'image/png': '.png',
        'image/webp': '.webp',
    }
    extension = supported_extensions.get(mime_type)
    if not extension:
        # gpt-image-2 accepts JPEG, PNG, and WebP. Normalize other browser
        # formats when Pillow can decode them instead of uploading mislabeled
        # bytes.
        with Image.open(io.BytesIO(image_bytes)) as image:
            normalized = io.BytesIO()
            image.convert('RGB').save(normalized, format='JPEG', quality=92)
            image_bytes = normalized.getvalue()
        extension = '.jpg'

    upload = io.BytesIO(image_bytes)
    upload.name = f'reference{extension}'
    response = openai_client.images.edit(
        model=OPENAI_IMAGE_MODEL,
        image=upload,
        prompt=prompt_text,
        size=size,
        quality=quality,
        output_format='png',
    )
    if not response.data or not response.data[0].b64_json:
        return None
    return base64.b64decode(response.data[0].b64_json, validate=True)


def _generate_image_from_reference(
    image_bytes,
    mime_type,
    prompt_text,
    resolution='2K',
    provider='gemini',
):
    """Dispatch one image edit to the provider selected by the user."""
    if provider == 'gemini':
        if not client:
            raise RuntimeError('Gemini image provider is not configured')
        return _generate_gemini_image(
            image_bytes, mime_type, prompt_text, resolution)
    if provider == 'openai':
        if not openai_client:
            raise RuntimeError('OpenAI image provider is not configured')
        return _generate_openai_image(
            image_bytes, mime_type, prompt_text, resolution)
    raise ValueError(f'Unsupported image provider: {provider}')


def _save_generated_image(session_id, version, image_bytes):
    """Save a generated image, returning (url, version_meta).

    Uses Vercel Blob when configured (production on Vercel) and falls back
    to the local static folder for dev. We also keep the bytes in the
    returned metadata so the co-pilot can refine without re-fetching.
    """
    filename = f"v{version}.png"

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
        _prune_generated_dirs()
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


def _prune_generated_dirs(keep=40):
    """Generated images otherwise pile up until the instance is redeployed;
    keep only the newest few session folders."""
    try:
        base = app.config['GENERATED_FOLDER']
        dirs = [os.path.join(base, d) for d in os.listdir(base)]
        dirs = [d for d in dirs if os.path.isdir(d)]
        if len(dirs) <= keep:
            return
        dirs.sort(key=lambda d: os.path.getmtime(d), reverse=True)
        for d in dirs[keep:]:
            shutil.rmtree(d, ignore_errors=True)
    except Exception as e:
        print(f"prune generated dirs failed: {e}")


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


def _prune_sessions_locked(now=None):
    now = now or time.time()
    expired = [
        session_id
        for session_id, session in SESSIONS.items()
        if now - session.get('updated_at', session.get('created_at', now))
        > SESSION_TTL_SECONDS
    ]
    for session_id in expired:
        SESSIONS.pop(session_id, None)


def _make_session_room_locked(now=None):
    _prune_sessions_locked(now)
    while len(SESSIONS) >= MAX_SESSIONS:
        oldest = min(
            SESSIONS,
            key=lambda session_id: SESSIONS[session_id].get(
                'updated_at',
                SESSIONS[session_id].get('created_at', 0),
            ),
        )
        SESSIONS.pop(oldest, None)


def _append_history_locked(session, role, message):
    session['history'].append({'role': role, 'message': message})
    if len(session['history']) > MAX_HISTORY_TURNS:
        del session['history'][:-MAX_HISTORY_TURNS]
    session['updated_at'] = time.time()


def _redis_session_key(session_id):
    return f'{STATE_KEY_PREFIX}:session:{session_id}'


def _serialize_session(session):
    versions = []
    for version in session.get('versions', [])[-MAX_SESSION_VERSIONS:]:
        if not isinstance(version, dict):
            continue
        image_bytes = version.get('bytes', b'')
        if not isinstance(image_bytes, bytes):
            continue
        versions.append({
            'url': str(version.get('url') or ''),
            'bytes_b64': base64.b64encode(image_bytes).decode('ascii'),
            'mime_type': str(
                version.get('mime_type') or 'image/jpeg'
            ),
        })

    history = [
        {
            'role': str(turn.get('role') or ''),
            'message': str(turn.get('message') or ''),
        }
        for turn in session.get('history', [])[-MAX_HISTORY_TURNS:]
        if isinstance(turn, dict)
    ]
    payload = {
        'versions': versions,
        'history': history,
        'initial_prompt': str(session.get('initial_prompt') or ''),
        'resolution': str(session.get('resolution') or '2K'),
        'provider': str(session.get('provider') or 'gemini'),
        'version_count': int(
            session.get('version_count', len(versions))
        ),
        'created_at': float(session.get('created_at') or time.time()),
        'updated_at': float(session.get('updated_at') or time.time()),
    }
    return json.dumps(
        payload,
        ensure_ascii=False,
        separators=(',', ':'),
    ).encode('utf-8')


def _deserialize_session(raw):
    if isinstance(raw, bytes):
        raw = raw.decode('utf-8')
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError('session payload must be an object')

    versions = []
    for version in payload.get('versions', [])[-MAX_SESSION_VERSIONS:]:
        if not isinstance(version, dict):
            continue
        image_bytes = base64.b64decode(
            version.get('bytes_b64') or '',
            validate=True,
        )
        if not image_bytes or len(image_bytes) > MAX_IMAGE_BYTES:
            raise ValueError('invalid persisted image')
        mime_type = version.get('mime_type') or 'image/jpeg'
        if mime_type not in ('image/jpeg', 'image/png', 'image/webp'):
            raise ValueError('invalid persisted image type')
        versions.append({
            'url': str(version.get('url') or ''),
            'bytes': image_bytes,
            'mime_type': mime_type,
        })
    if not versions:
        raise ValueError('persisted session has no image versions')

    history = [
        {
            'role': str(turn.get('role') or ''),
            'message': str(turn.get('message') or ''),
        }
        for turn in payload.get('history', [])[-MAX_HISTORY_TURNS:]
        if isinstance(turn, dict)
    ]
    now = time.time()
    return {
        'versions': versions,
        'history': history,
        'initial_prompt': str(payload.get('initial_prompt') or ''),
        'resolution': str(payload.get('resolution') or '2K'),
        'provider': str(payload.get('provider') or 'gemini'),
        'version_count': max(
            len(versions),
            int(payload.get('version_count') or len(versions)),
        ),
        'created_at': float(payload.get('created_at') or now),
        'updated_at': float(payload.get('updated_at') or now),
        '_operation_lock': threading.Lock(),
    }


def _persist_session(session_id, session):
    if not redis_client:
        return False
    try:
        updated_at = float(session.get('updated_at') or time.time())
        redis_client.set(
            _redis_session_key(session_id),
            _serialize_session(session),
            ex=SESSION_TTL_SECONDS,
        )
        redis_client.zadd(
            SESSION_INDEX_KEY,
            {session_id: updated_at},
        )
        redis_client.zremrangebyscore(
            SESSION_INDEX_KEY,
            0,
            time.time() - SESSION_TTL_SECONDS,
        )
        session_count = int(redis_client.zcard(SESSION_INDEX_KEY))
        if session_count > MAX_SESSIONS:
            oldest_ids = redis_client.zrange(
                SESSION_INDEX_KEY,
                0,
                session_count - MAX_SESSIONS - 1,
            )
            if oldest_ids:
                decoded_ids = [
                    value.decode('utf-8')
                    if isinstance(value, bytes)
                    else str(value)
                    for value in oldest_ids
                ]
                redis_client.delete(*[
                    _redis_session_key(oldest_id)
                    for oldest_id in decoded_ids
                ])
                redis_client.zrem(SESSION_INDEX_KEY, *decoded_ids)
        return True
    except Exception as e:
        print(
            "Redis session write failed; using local cache "
            f"({e.__class__.__name__})"
        )
        return False


def _load_persisted_session(session_id):
    if not redis_client:
        return None
    try:
        raw = redis_client.get(_redis_session_key(session_id))
        if not raw:
            redis_client.zrem(SESSION_INDEX_KEY, session_id)
            return None
        return _deserialize_session(raw)
    except (ValueError, TypeError, UnicodeDecodeError) as e:
        print(
            "Discarding invalid Redis session "
            f"({e.__class__.__name__})"
        )
        try:
            redis_client.delete(_redis_session_key(session_id))
            redis_client.zrem(SESSION_INDEX_KEY, session_id)
        except Exception as cleanup_error:
            print(
                "Redis invalid session cleanup failed "
                f"({cleanup_error.__class__.__name__})"
            )
        return None
    except Exception as e:
        print(
            "Redis session read failed; using local cache "
            f"({e.__class__.__name__})"
        )
        return None


def _touch_persisted_session(session_id, updated_at):
    if not redis_client:
        return
    try:
        key = _redis_session_key(session_id)
        if redis_client.expire(key, SESSION_TTL_SECONDS):
            redis_client.zadd(
                SESSION_INDEX_KEY,
                {session_id: updated_at},
            )
    except Exception as e:
        print(f"Redis session touch failed ({e.__class__.__name__})")


def _session_count():
    if redis_client:
        try:
            redis_client.zremrangebyscore(
                SESSION_INDEX_KEY,
                0,
                time.time() - SESSION_TTL_SECONDS,
            )
            return int(redis_client.zcard(SESSION_INDEX_KEY))
        except Exception as e:
            print(f"Redis session count failed ({e.__class__.__name__})")
    with SESSIONS_LOCK:
        _prune_sessions_locked()
        return len(SESSIONS)


def _acquire_session_operation(session_id, session):
    if redis_client:
        key = f'{STATE_KEY_PREFIX}:lock:session:{session_id}'
        token = uuid.uuid4().hex
        try:
            if redis_client.set(
                key,
                token,
                nx=True,
                ex=SESSION_LOCK_SECONDS,
            ):
                return ('redis', key, token)
            return None
        except Exception as e:
            print(
                "Redis session lock failed; using local lock "
                f"({e.__class__.__name__})"
            )

    operation_lock = session['_operation_lock']
    if operation_lock.acquire(blocking=False):
        return ('local', operation_lock, None)
    return None


def _release_session_operation(handle):
    backend, lock, token = handle
    if backend == 'local':
        lock.release()
        return
    try:
        redis_client.eval(LOCK_RELEASE_SCRIPT, 1, lock, token)
    except Exception as e:
        print(f"Redis session lock release failed ({e.__class__.__name__})")


def _create_session(initial_version_path, initial_prompt):
    """Create a new co-pilot session and return its id."""
    session_id = uuid.uuid4().hex[:12]
    now = time.time()
    with SESSIONS_LOCK:
        _make_session_room_locked(now)
        SESSIONS[session_id] = {
            'versions': [initial_version_path],
            'history': [],
            'initial_prompt': initial_prompt or '',
            'version_count': 1,
            'created_at': now,
            'updated_at': now,
            '_operation_lock': threading.Lock(),
        }
    return session_id


def _get_session(session_id):
    now = time.time()
    with SESSIONS_LOCK:
        _prune_sessions_locked(now)
        session = SESSIONS.get(session_id)
        if session:
            session['updated_at'] = now
    if session:
        _touch_persisted_session(session_id, now)
        return session

    session = _load_persisted_session(session_id)
    if not session:
        return None
    session['updated_at'] = now
    with SESSIONS_LOCK:
        _make_session_room_locked(now)
        existing_session = SESSIONS.get(session_id)
        if existing_session:
            session = existing_session
            session['updated_at'] = now
        else:
            SESSIONS[session_id] = session
    _touch_persisted_session(session_id, now)
    return session


def _refresh_persisted_session(session_id, fallback_session):
    """Reload after acquiring the distributed lock to avoid stale workers."""
    if not redis_client:
        return fallback_session
    persisted_session = _load_persisted_session(session_id)
    if not persisted_session:
        return fallback_session
    persisted_session['updated_at'] = time.time()
    with SESSIONS_LOCK:
        SESSIONS[session_id] = persisted_session
    return persisted_session


def _api_error(message, status, code, retry_after=None):
    payload = {
        'error': message,
        'code': code,
        'request_id': getattr(g, 'request_id', None),
    }
    response = jsonify(payload)
    response.status_code = status
    if retry_after is not None:
        response.headers['Retry-After'] = str(retry_after)
    return response


def _openai_generation_error(error):
    status = getattr(error, 'status_code', None)
    code = getattr(error, 'code', None)
    body = getattr(error, 'body', None)
    if isinstance(body, dict):
        code = code or body.get('code')

    if 'timeout' in error.__class__.__name__.lower():
        return _api_error(
            'OpenAI 圖像生成逾時，請改用 1K 或 2K 後再試。',
            504,
            'openai_timeout',
        )
    if status == 401:
        return _api_error(
            'OpenAI API Key 無效或已撤銷，請在 Render 更新金鑰。',
            503,
            'openai_auth_failed',
        )
    if status == 403:
        return _api_error(
            'OpenAI 專案目前無法使用 GPT Image；請檢查模型權限與組織驗證。',
            503,
            'openai_access_denied',
        )
    if status == 429:
        return _api_error(
            'OpenAI 圖像額度不足或請求過多，請檢查專案用量後稍候再試。',
            429,
            'openai_rate_limited',
            retry_after=60,
        )
    if status == 400 and code == 'moderation_blocked':
        return _api_error(
            '這次圖片或描述未通過 OpenAI 安全檢查，請調整描述後再試。',
            400,
            'openai_moderation_blocked',
        )
    if status == 400:
        return _api_error(
            'OpenAI 無法處理這組圖片設定，請改用 2K 或調整圖片後再試。',
            400,
            'openai_request_invalid',
        )
    if status and status >= 500:
        return _api_error(
            'OpenAI 圖像服務暫時無法回應，請稍後再試。',
            502,
            'openai_upstream_error',
            retry_after=30,
        )
    return None


def _check_rate_limit(scope, limit, window_seconds):
    client_identifier = hashlib.sha256(
        (request.remote_addr or 'unknown').encode('utf-8')
    ).hexdigest()[:24]
    if redis_client:
        rate_key = f'{STATE_KEY_PREFIX}:rate:{scope}:{client_identifier}'
        try:
            count, ttl = redis_client.eval(
                RATE_LIMIT_SCRIPT,
                1,
                rate_key,
                window_seconds,
            )
            if int(count) > limit:
                return _api_error(
                    '操作太頻繁，請稍後再試。',
                    429,
                    'rate_limited',
                    retry_after=max(1, int(ttl)),
                )
            return None
        except Exception as e:
            print(
                "Redis rate limit failed; using local limit "
                f"({e.__class__.__name__})"
            )

    now = time.monotonic()
    key = (scope, client_identifier)
    with RATE_LIMITS_LOCK:
        if len(RATE_LIMITS) > 5_000:
            stale = [
                rate_key
                for rate_key, (started, _, window) in RATE_LIMITS.items()
                if now - started >= window
            ]
            for rate_key in stale:
                RATE_LIMITS.pop(rate_key, None)
            while len(RATE_LIMITS) >= 5_000:
                oldest = min(
                    RATE_LIMITS,
                    key=lambda rate_key: RATE_LIMITS[rate_key][0],
                )
                RATE_LIMITS.pop(oldest, None)

        started, count, window = RATE_LIMITS.get(
            key, (now, 0, window_seconds))
        if now - started >= window_seconds:
            started, count, window = now, 0, window_seconds
        if count >= limit:
            retry_after = max(1, int(window_seconds - (now - started)) + 1)
            return _api_error(
                '操作太頻繁，請稍後再試。',
                429,
                'rate_limited',
                retry_after=retry_after,
            )
        RATE_LIMITS[key] = (started, count + 1, window)
    return None


@app.before_request
def _begin_request():
    g.request_id = uuid.uuid4().hex[:12]
    g.request_started = time.monotonic()


@app.after_request
def _finish_request(response):
    response.headers['X-Request-ID'] = getattr(g, 'request_id', '')
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    if request.path == '/' or request.path.startswith('/api/'):
        response.headers['Cache-Control'] = 'no-store'
    elapsed = (time.monotonic() - getattr(
        g, 'request_started', time.monotonic())) * 1000
    response.headers['Server-Timing'] = f'app;dur={elapsed:.1f}'
    return response


@app.route('/')
def index():
    providers = _image_provider_options()
    configured = [p for p in providers if p['available']]
    default_provider = configured[0]['value'] if configured else 'gemini'
    return render_template(
        'index.html',
        image_providers=providers,
        default_provider=default_provider,
    )


@app.route('/health')
def health():
    """Lightweight liveness endpoint for Render health checks."""
    return jsonify({
        'status': 'ok',
        'code_version': CODE_VERSION,
    })


@app.errorhandler(Exception)
def _unhandled_error(e):
    """Keep every API failure JSON and avoid exposing exception details."""
    if isinstance(e, HTTPException):
        if request.path.startswith('/api/'):
            messages = {
                404: ('找不到這個 API 路徑。', 'not_found'),
                405: ('不支援這個請求方法。', 'method_not_allowed'),
                413: ('上傳內容過大，請縮小圖片後再試。', 'payload_too_large'),
            }
            message, code = messages.get(
                e.code,
                (e.description or '請求失敗。', 'http_error'),
            )
            return _api_error(message, e.code or 500, code)
        return e
    print(
        f"[{getattr(g, 'request_id', '-')}] unhandled error: "
        f"{e.__class__.__name__}: {e}"
    )
    traceback.print_exc()
    return _api_error(
        '伺服器發生未預期錯誤，請稍後再試。',
        500,
        'internal_error',
    )


@app.route('/api/diag')
def diag():
    supplied_token = request.headers.get('X-Diag-Token', '')
    authorized = bool(DIAG_TOKEN) and bool(supplied_token) and hmac.compare_digest(
        supplied_token,
        DIAG_TOKEN,
    )
    if DIAG_TOKEN and not authorized:
        return _api_error(
            '診斷端點需要授權。',
            403,
            'diag_forbidden',
        )

    out = {
        'code_version': CODE_VERSION,
        'rss_mb': rss_mb(),
        'sessions': _session_count(),
        'state_backend': 'redis' if redis_client else 'memory',
        'durable_images': USE_BLOB,
        'generating': GEN_LOCK_HELD,
        'providers': {
            provider: _image_provider_is_ready(provider)
            for provider in IMAGE_PROVIDER_LABELS
        },
        'image_models': {
            'gemini': GEMINI_IMAGE_MODEL,
            'openai': OPENAI_IMAGE_MODEL,
        },
        'session_ttl_seconds': SESSION_TTL_SECONDS,
        'text_models': {},
    }
    if request.args.get('models') != '1':
        out['note'] = 'add ?models=1 with X-Diag-Token to ping text models'
        return jsonify(out)
    if not authorized:
        return _api_error(
            '模型連線測試需要設定 DIAG_TOKEN。',
            403,
            'diag_token_required',
        )
    if client:
        for m in COPILOT_TEXT_MODELS:
            try:
                client.models.generate_content(model=m, contents='ping')
                out['text_models'][m] = 'ok'
            except Exception as e:
                out['text_models'][m] = (
                    f'error: {e.__class__.__name__}'
                )
    return jsonify(out)


def _is_allowed_street_view_url(url):
    parsed = urllib.parse.urlsplit(url)
    return (
        parsed.scheme == 'https'
        and parsed.hostname == 'maps.googleapis.com'
        and parsed.path == '/maps/api/streetview'
    )


@app.route('/api/fetch_street')
def fetch_street():
    # Server-side fetch of a Street View Static image handed over from the
    # schoolzone map (?img=... on the front page). Browser-side fetch would
    # hit CORS and the Maps key's referrer restriction; the backend has
    # neither problem. Restricted to the Street View Static endpoint so this
    # can't be used as an open proxy.
    rate_error = _check_rate_limit(
        'fetch_street',
        MAX_STREET_FETCHES_PER_HOUR,
        3_600,
    )
    if rate_error is not None:
        return rate_error

    url = request.args.get('url', '')
    if not _is_allowed_street_view_url(url):
        return _api_error(
            '只允許 Google Street View Static 圖片網址。',
            400,
            'unsupported_url',
        )
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'ai-street-designer'})
        # Scheme, host, and path are allowlisted above; redirects are checked
        # again before any response body is read.
        with urllib.request.urlopen(req, timeout=15) as r:  # nosec B310
            if not _is_allowed_street_view_url(r.geturl()):
                return _api_error(
                    'Street View 圖片發生不安全的重新導向。',
                    502,
                    'unsafe_redirect',
                )
            data = r.read(MAX_FETCH_BYTES + 1)
            ctype = r.headers.get(
                'Content-Type', 'image/jpeg').split(';', 1)[0].lower()
        if len(data) > MAX_FETCH_BYTES:
            return _api_error(
                'Street View 圖片過大。',
                502,
                'street_image_too_large',
            )
        if ctype not in ('image/jpeg', 'image/png', 'image/webp'):
            return _api_error(
                'Street View 服務沒有回傳有效圖片。',
                502,
                'street_image_invalid',
            )
        return Response(data, mimetype=ctype)
    except Exception as e:
        print(
            f"[{g.request_id}] Street View fetch failed: "
            f"{e.__class__.__name__}: {e}"
        )
        return _api_error(
            '暫時無法取得 Street View 圖片。',
            502,
            'street_fetch_failed',
        )

@app.route('/api/transform', methods=['POST'])
def transform_image():
    rate_error = _check_rate_limit(
        'transform',
        MAX_GENERATIONS_PER_HOUR,
        3_600,
    )
    if rate_error is not None:
        return rate_error

    if 'image' not in request.files:
        return _api_error(
            '請先上傳一張街景圖片。',
            400,
            'image_required',
        )

    file = request.files['image']
    custom_prompt = (request.form.get('custom_prompt') or '').strip()
    preset_id = (request.form.get('preset_id') or '').strip()
    resolution = request.form.get('resolution', '2K')
    provider = (request.form.get('provider') or 'gemini').strip().lower()
    if not custom_prompt:
        return _api_error(
            '請描述你想進行的街道改造。',
            400,
            'prompt_required',
        )
    if len(custom_prompt) > MAX_PROMPT_CHARS:
        return _api_error(
            f'改造描述不可超過 {MAX_PROMPT_CHARS} 個字元。',
            400,
            'prompt_too_long',
        )
    if preset_id and preset_id not in PRESET_STYLE_KEYS:
        return _api_error(
            '不支援的快捷改造選項。',
            400,
            'preset_invalid',
        )
    if provider not in IMAGE_PROVIDER_LABELS:
        return _api_error(
            '不支援的圖像生成器。',
            400,
            'provider_invalid',
        )
    if not _image_provider_is_ready(provider):
        label = IMAGE_PROVIDER_LABELS[provider]
        return _api_error(
            f'{label} 尚未設定 API Key，請先完成伺服器環境變數設定。',
            503,
            'provider_unavailable',
        )
    if resolution not in ('1K', '2K', '4K'):
        resolution = '2K'

    if not file or file.filename == '':
        return _api_error(
            '上傳的圖片無效。',
            400,
            'image_invalid',
        )

    # Read original image bytes directly (avoids writing to read-only FS on Vercel)
    try:
        image_bytes, mime_type = _validate_uploaded_image(file)
        print(
            f"[{g.request_id}] image validated "
            f"(size={len(image_bytes)}, mime={mime_type})"
        )
    except ValueError as e:
        return _api_error(str(e), 400, 'image_invalid')
    
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
        knowledge_path = os.path.join(app.root_path, 'knowledge_base')
        if knowledge_path not in sys.path:
            sys.path.append(knowledge_path)
        from street_prompt_data_taiwan import get_taiwan_design_prompt
        from street_prompt_data_full import get_set_design_prompt
        
        # Check if custom_prompt matches a key (exact or partial)
        # For this demo, let's assume the user might type the exact key or we use the specific logic
        # Ideally, frontend would send a 'style_key'
        
        # Let's try to match strict keys first, or use the custom prompt as is
        # If the user selected a preset from UI, it might be in 'prompt_type' or 'custom_prompt'
        # The current UI sends 'custom_prompt' as the main text.
        
        # We will try to see if the custom_prompt *is* a key in our dictionaries
        option_key = PRESET_STYLE_KEYS.get(preset_id, custom_prompt)
        p1, np1 = get_taiwan_design_prompt(option_key, custom_prompt)
        if p1:
            specialized_prompt = p1
            negative_prompt = np1
        else:
            p2, np2 = get_set_design_prompt(option_key, custom_prompt)
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
    
    print(
        f"[{g.request_id}] prompt ready "
        f"(provider={provider}, chars={len(full_prompt)})"
    )

    try:
        model = GEMINI_IMAGE_MODEL if provider == 'gemini' else OPENAI_IMAGE_MODEL
        print(
            f"[{g.request_id}] transforming image with "
            f"{provider}/{model}"
        )

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

        if not GEN_LOCK.acquire(blocking=False):
            return _api_error(
                '另一張圖正在生成中，免費主機一次只能畫一張——等它畫完再試一次 🌱',
                429,
                'generation_busy',
                retry_after=15,
            )
        global GEN_LOCK_HELD
        GEN_LOCK_HELD = True
        print(
            f"[{g.request_id}] [mem] before generate: {rss_mb()} MB "
            f"(provider={provider}, resolution={resolution})"
        )
        try:
            generated_image_data = _generate_image_from_reference(
                image_bytes,
                mime_type,
                prompt_text,
                resolution=resolution,
                provider=provider,
            )
        finally:
            GEN_LOCK_HELD = False
            GEN_LOCK.release()
        print(
            f"[{g.request_id}] [mem] after generate: {rss_mb()} MB, "
            f"image={len(generated_image_data or b'') / 1024 / 1024:.1f} MB"
        )

        if not generated_image_data:
            return _api_error(
                '圖像服務沒有回傳圖片，請稍後再試。',
                502,
                'empty_image_response',
            )

        # Create co-pilot session and save v1 (Vercel Blob in prod, local disk in dev)
        session_id = uuid.uuid4().hex[:12]
        generated_url, version_meta = _save_generated_image(session_id, 1, generated_image_data)
        now = time.time()
        with SESSIONS_LOCK:
            _make_session_room_locked(now)
            SESSIONS[session_id] = {
                'versions': [version_meta],
                'history': [],
                'initial_prompt': custom_prompt or '',
                'resolution': resolution,
                'provider': provider,
                'version_count': 1,
                'created_at': now,
                'updated_at': now,
                '_operation_lock': threading.Lock(),
            }

        # Full-res bytes are on disk/blob and a shrunk copy is in the session —
        # drop the big buffer before the greeting call so peak RSS stays low.
        del generated_image_data
        gc.collect()
        print(f"[{g.request_id}] [mem] after release: {rss_mb()} MB")

        # Ask 小綠 to write a greeting, reusing the already-shrunk copy
        greeting = _generate_copilot_greeting(
            version_meta['bytes'], version_meta.get('mime_type', 'image/jpeg'), custom_prompt or '')
        with SESSIONS_LOCK:
            _append_history_locked(
                SESSIONS[session_id],
                'assistant',
                greeting['message'],
            )
            session = SESSIONS[session_id]
        _persist_session(session_id, session)

        return jsonify({
            'status': 'success',
            'session_id': session_id,
            'version': 1,
            'image_url': generated_url,
            'provider': provider,
            'copilot': {
                'message': greeting['message'],
                'suggestions': greeting['suggestions'],
            }
        })

    except Exception as e:
        upstream_request_id = getattr(e, 'request_id', None)
        print(
            f"[{g.request_id}] image generation failed with {provider}: "
            f"{e.__class__.__name__}: {e}; "
            f"upstream_request_id={upstream_request_id or '-'}"
        )
        if provider == 'openai':
            openai_error = _openai_generation_error(e)
            if openai_error is not None:
                return openai_error
        upstream_status = getattr(e, 'status_code', None)
        if upstream_status == 429:
            return _api_error(
                '圖像服務目前請求太多或額度不足，請稍後再試。',
                429,
                'provider_rate_limited',
                retry_after=60,
            )
        if 'timeout' in e.__class__.__name__.lower():
            return _api_error(
                '圖像生成逾時。請稍後再試，或先改用較低畫質。',
                504,
                'generation_timeout',
            )
        return _api_error(
            f'{IMAGE_PROVIDER_LABELS[provider]} 圖像生成失敗，請稍後再試。',
            502,
            'generation_failed',
        )


@app.route('/api/chat', methods=['POST'])
def chat_with_copilot():
    """Co-pilot dialogue endpoint: classifies intent, optionally refines the image."""
    rate_error = _check_rate_limit(
        'chat',
        MAX_CHATS_PER_10_MINUTES,
        600,
    )
    if rate_error is not None:
        return rate_error

    if not client:
        return _api_error(
            '小綠對話功能需要設定 Google API Key。',
            503,
            'copilot_unavailable',
        )

    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return _api_error(
            '請求內容必須是 JSON 物件。',
            400,
            'json_invalid',
        )
    session_id = str(data.get('session_id') or '').strip()
    message = data.get('message')
    user_message = message.strip() if isinstance(message, str) else ''

    if not session_id or not user_message:
        return _api_error(
            'session_id 與 message 為必填欄位。',
            400,
            'chat_fields_required',
        )
    if not re.fullmatch(r'[a-f0-9]{12}', session_id):
        return _api_error(
            'session_id 格式無效。',
            400,
            'session_id_invalid',
        )
    if len(user_message) > MAX_CHAT_CHARS:
        return _api_error(
            f'訊息不可超過 {MAX_CHAT_CHARS} 個字元。',
            400,
            'message_too_long',
        )

    session = _get_session(session_id)
    if not session:
        return _api_error(
            '共創工作階段不存在或已逾時，請重新生成一張圖片。',
            404,
            'session_expired',
        )

    operation_handle = _acquire_session_operation(session_id, session)
    if not operation_handle:
        return _api_error(
            '這個共創工作階段正在處理上一個要求，請稍候。',
            409,
            'session_busy',
            retry_after=5,
        )
    try:
        session = _refresh_persisted_session(session_id, session)
        return _chat_with_session(session_id, session, user_message)
    finally:
        _persist_session(session_id, session)
        _release_session_operation(operation_handle)


def _chat_with_session(session_id, session, user_message):
    global GEN_LOCK_HELD
    latest = session['versions'][-1]
    latest_bytes = latest['bytes']
    mime_type = latest.get('mime_type', 'image/png')

    # Record the user turn before asking the model
    with SESSIONS_LOCK:
        _append_history_locked(session, 'user', user_message)
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
        if not GEN_LOCK.acquire(blocking=False):
            return _api_error(
                '另一張圖正在生成中，請等它完成後再調整。',
                429,
                'generation_busy',
                retry_after=15,
            )
        GEN_LOCK_HELD = True
        try:
            new_image_bytes = _generate_image_from_reference(
                latest_bytes,
                mime_type,
                full_prompt,
                resolution=session.get('resolution', '2K'),
                provider=session.get('provider', 'gemini'),
            )
        except Exception as e:
            print(
                f"[{g.request_id}] refinement failed: "
                f"{e.__class__.__name__}: {e}"
            )
            return _api_error(
                '圖片調整失敗，請稍後再試。',
                502,
                'refinement_failed',
            )
        finally:
            GEN_LOCK_HELD = False
            GEN_LOCK.release()

        if not new_image_bytes:
            return _api_error(
                '圖像服務沒有回傳調整後的圖片。',
                502,
                'empty_image_response',
            )

        version_num = session.get(
            'version_count',
            len(session['versions']),
        ) + 1
        new_url, new_meta = _save_generated_image(
            session_id,
            version_num,
            new_image_bytes,
        )
        with SESSIONS_LOCK:
            session['version_count'] = version_num
            session['versions'].append(new_meta)
            if len(session['versions']) > MAX_SESSION_VERSIONS:
                del session['versions'][:-MAX_SESSION_VERSIONS]
            _append_history_locked(
                session,
                'assistant',
                decision['message'],
            )
        result.update({
            'image_url': new_url,
            'version': version_num,
        })
    else:
        with SESSIONS_LOCK:
            _append_history_locked(
                session,
                'assistant',
                decision['message'],
            )

    return jsonify(result)

if __name__ == '__main__':
    app.run(
        debug=os.getenv('FLASK_DEBUG') == '1',
        port=_env_int('PORT', 8888, 1, 65_535),
    )

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
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import urllib.parse
import urllib.request
import uuid

# Bumped by hand on each deploy-worthy change — /api/diag reports it, so we
# can tell at a glance whether the running instance actually has a fix.
CODE_VERSION = '2026-07-30-gallery1'

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

import imageio_ffmpeg
from dotenv import load_dotenv
from flask import Flask, Response, g, jsonify, render_template, request, url_for
from google import genai
from google.genai import types
from PIL import Image, UnidentifiedImageError
from werkzeug.exceptions import HTTPException
from werkzeug.middleware.proxy_fix import ProxyFix

from knowledge_base.knowledge_runtime import (
    build_design_spec,
    build_visual_audit_checklist,
    compile_generation_prompt,
    normalize_language,
    normalize_preferences,
    public_design_spec,
    refine_design_spec,
)

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
VEO_VIDEO_MODEL = os.getenv(
    'VEO_VIDEO_MODEL',
    'veo-3.1-generate-preview',
)
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
MAX_MASK_BYTES = 4 * 1024 * 1024
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
MAX_VIDEOS_PER_DAY = _env_int('MAX_VIDEOS_PER_DAY', 3, 1, 50)
MAX_VIDEO_JOBS_PER_SESSION = 6
MAX_GALLERY_CAPTION_CHARS = 180
MAX_GALLERY_POSTS = _env_int('MAX_GALLERY_POSTS', 500, 20, 5_000)
MAX_GALLERY_PAGE_SIZE = 48

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
GALLERY_INDEX_KEY = f'{STATE_KEY_PREFIX}:gallery:index'
GALLERY_POST_KEY_PREFIX = f'{STATE_KEY_PREFIX}:gallery:post'
GALLERY_SOURCE_KEY_PREFIX = f'{STATE_KEY_PREFIX}:gallery:source'
GALLERY_LIKE_KEY_PREFIX = f'{STATE_KEY_PREFIX}:gallery:likes'
GALLERY_POSTS = {}
GALLERY_SOURCE_IDS = {}
GALLERY_VOTES = {}
GALLERY_LOCK = threading.Lock()

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

EN_COPILOT_PERSONA = """You are Greenie 🌱, a warm, observant AI street-design co-pilot who cares about sustainable, people-first streets.
Work alongside the user, notice visible design details, and reply only in natural English. Keep each response to 2–4 sentences and use no more than two emoji."""

EN_CHAT_SYSTEM_PROMPT = EN_COPILOT_PERSONA + """

For every user message:
1. Inspect the latest street image.
2. Classify the intent:
   - "refine" when the user wants a visible image change.
   - "chat" for questions, reactions, or discussion.
3. Reply warmly and mention visible details when helpful.
4. Offer three short next-step suggestions.
5. For a refinement, write a precise English image-editing instruction; otherwise leave refine_prompt empty.

Return JSON only:
{
  "intent": "refine" or "chat",
  "message": "English reply",
  "refine_prompt": "English image-edit instruction or an empty string",
  "suggestions": ["Suggestion 1", "Suggestion 2", "Suggestion 3"]
}"""

EN_GREETING_SYSTEM_PROMPT = EN_COPILOT_PERSONA + """

The user uploaded a street image and requested: "{user_prompt}"
The first design version is attached.

Please:
1. Welcome the user in 2–3 sentences and identify specific visible changes.
2. Ask one engaging question that invites co-design.
3. Offer three short next-step suggestions.

Return JSON only:
{
  "message": "English welcome message",
  "suggestions": ["Suggestion 1", "Suggestion 2", "Suggestion 3"]
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


def _validate_edit_mask(file, reference_image_bytes):
    """Validate and normalize an optional user-drawn image-edit mask.

    The returned PNG has the same dimensions as the reference image. Opaque
    pixels are preserved and transparent pixels are the requested edit area.
    """
    mask_bytes = file.read(MAX_MASK_BYTES + 1)
    if not mask_bytes:
        raise ValueError('改造範圍遮罩是空的。')
    if len(mask_bytes) > MAX_MASK_BYTES:
        raise ValueError('改造範圍遮罩不可超過 4 MB。')

    try:
        with Image.open(io.BytesIO(reference_image_bytes)) as reference:
            reference_size = reference.size
        with Image.open(io.BytesIO(mask_bytes)) as mask:
            if (mask.format or '').upper() != 'PNG':
                raise ValueError('改造範圍遮罩必須是 PNG。')
            if mask.size != reference_size:
                raise ValueError('改造範圍遮罩必須與上傳圖片尺寸一致。')
            if 'A' not in mask.getbands():
                raise ValueError('改造範圍遮罩必須包含透明區域。')
            normalized = mask.convert('RGBA')
            alpha = normalized.getchannel('A')
            minimum_alpha, maximum_alpha = alpha.getextrema()
            if minimum_alpha == 255:
                raise ValueError('請先在照片上畫出希望 AI 改造的範圍。')
            if maximum_alpha == 0:
                raise ValueError('遮罩不可把整張照片都設為可改造。')
            output = io.BytesIO()
            normalized.save(output, format='PNG', optimize=True)
            return output.getvalue()
    except ValueError:
        raise
    except (
        Image.DecompressionBombError,
        UnidentifiedImageError,
        OSError,
        SyntaxError,
    ) as e:
        raise ValueError('改造範圍遮罩不是有效的 PNG 圖片。') from e


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


def _generate_gemini_image(
    image_bytes,
    mime_type,
    prompt_text,
    resolution,
    mask_bytes=None,
):
    transformation_parts = [
        types.Part.from_text(text=prompt_text),
        types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
    ]
    if mask_bytes:
        transformation_parts.extend([
            types.Part.from_text(text=(
                "The next PNG is an edit-area guide aligned to the reference "
                "image. Transparent pixels identify the area requested for "
                "street-level changes; opaque white pixels should be preserved. "
                "Treat it as guidance and still preserve buildings and viewpoint."
            )),
            types.Part.from_bytes(data=mask_bytes, mime_type='image/png'),
        ])
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


def _generate_openai_image(
    image_bytes,
    mime_type,
    prompt_text,
    resolution,
    mask_bytes=None,
):
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
    request_args = dict(
        model=OPENAI_IMAGE_MODEL,
        image=upload,
        prompt=prompt_text,
        size=size,
        quality=quality,
        output_format='png',
    )
    if mask_bytes:
        mask_upload = io.BytesIO(mask_bytes)
        mask_upload.name = 'edit-mask.png'
        request_args['mask'] = mask_upload
    response = openai_client.images.edit(**request_args)
    if not response.data or not response.data[0].b64_json:
        return None
    return base64.b64decode(response.data[0].b64_json, validate=True)


def _generate_image_from_reference(
    image_bytes,
    mime_type,
    prompt_text,
    resolution='2K',
    provider='gemini',
    mask_bytes=None,
):
    """Dispatch one image edit to the provider selected by the user."""
    if provider == 'gemini':
        if not client:
            raise RuntimeError('Gemini image provider is not configured')
        return _generate_gemini_image(
            image_bytes,
            mime_type,
            prompt_text,
            resolution,
            mask_bytes=mask_bytes,
        )
    if provider == 'openai':
        if not openai_client:
            raise RuntimeError('OpenAI image provider is not configured')
        return _generate_openai_image(
            image_bytes,
            mime_type,
            prompt_text,
            resolution,
            mask_bytes=mask_bytes,
        )
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
        'version': version,
        'url': image_url,
        'bytes': small_bytes,
        'mime_type': small_mime,
    }
    return image_url, version_meta


def _save_generated_video(session_id, job_id, video_bytes):
    """Persist a completed MP4 and return its public URL."""
    filename = f'{job_id}.mp4'
    if USE_BLOB:
        blob_result = vercel_blob.put(
            f'generated/{session_id}/videos/{filename}',
            video_bytes,
            {'access': 'public', 'addRandomSuffix': 'false'},
        )
        return blob_result['url']

    video_dir = os.path.join(
        app.config['GENERATED_FOLDER'],
        session_id,
        'videos',
    )
    os.makedirs(video_dir, exist_ok=True)
    filepath = os.path.join(video_dir, filename)
    with open(filepath, 'wb') as output:
        output.write(video_bytes)
    return url_for(
        'static',
        filename=f'generated/{session_id}/videos/{filename}',
    )


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


def _pending_visual_audit(design_spec):
    language = normalize_language((design_spec or {}).get('language'))
    return {
        'status': 'not_run',
        'score': None,
        'summary': (
            'The model visual audit has not run; please review this concept with users and a design professional.'
            if language == 'en'
            else '尚未完成模型視覺稽核，請由使用者與設計專業者共同確認。'
        ),
        'checks': build_visual_audit_checklist(design_spec or {}),
        'disclaimer': (
            (
                'This checks visible consistency and plausibility only; it does not confirm dimensions, compliance, or constructability.'
            )
            if language == 'en'
            else (
                '只檢查畫面可見的一致性與合理性，不代表尺寸量測、'
                '法規符合或工程可施工性已獲確認。'
            )
        ),
    }


def _normalize_visual_audit(data, design_spec):
    fallback = _pending_visual_audit(design_spec)
    if not isinstance(data, dict):
        return fallback

    expected = {
        item['id']: item for item in build_visual_audit_checklist(design_spec)
    }
    model_checks = {
        str(item.get('id')): item
        for item in data.get('checks', [])
        if isinstance(item, dict)
    }
    checks = []
    for check_id, base in expected.items():
        model_check = model_checks.get(check_id, {})
        status = model_check.get('status')
        if status not in ('pass', 'warning', 'fail'):
            status = 'warning'
        checks.append({
            'id': check_id,
            'label': base['label'],
            'status': status,
            'note': str(model_check.get('note') or '')[:240],
        })

    try:
        score = int(data.get('score'))
    except (TypeError, ValueError):
        score = None
    if score is not None:
        score = max(0, min(100, score))
    return {
        'status': 'reviewed',
        'score': score,
        'summary': str(
            data.get('summary')
            or (
                'The initial visual review is complete.'
                if normalize_language(design_spec.get('language')) == 'en'
                else '已完成畫面初步檢查。'
            )
        )[:400],
        'checks': checks,
        'disclaimer': fallback['disclaimer'],
    }


def _visual_audit_prompt(design_spec):
    language = normalize_language(design_spec.get('language'))
    checklist = build_visual_audit_checklist(design_spec)
    interventions = ('; ' if language == 'en' else '；').join(
        design_spec.get('requested_interventions', [])
    )
    check_lines = '\n'.join(
        f"- {item['id']}: {item['label']}" for item in checklist
    )
    if language == 'en':
        return f"""You are visually auditing a street-design concept image.
Assess only what is visible. Do not claim measured dimensions, legal compliance,
or construction readiness.

Design goal: {design_spec.get('design_label', 'People-first street improvement')}
Expected visible changes: {interventions}

Checks:
{check_lines}

Return JSON only:
{{
  "score": "integer from 0 to 100",
  "summary": "English summary, no more than two sentences",
  "checks": [
    {{"id":"preservation","status":"pass|warning|fail","note":"visible evidence"}},
    {{"id":"requested_change","status":"pass|warning|fail","note":"visible evidence"}},
    {{"id":"continuity","status":"pass|warning|fail","note":"visible evidence"}},
    {{"id":"accessibility","status":"pass|warning|fail","note":"visible evidence"}},
    {{"id":"realism","status":"pass|warning|fail","note":"visible evidence"}}
  ]
}}"""
    return f"""你是街道設計概念圖的視覺稽核員。只依附圖中可見內容檢查，
不可宣稱已量測尺寸、符合法規或可直接施工。

設計目標：{design_spec.get('design_label', '人本街道改善')}
應清楚呈現：{interventions}

逐項檢查：
{check_lines}

只回 JSON：
{{
  "score": 0到100的整數,
  "summary": "繁體中文總結，最多兩句",
  "checks": [
    {{"id":"preservation","status":"pass|warning|fail","note":"可見依據"}},
    {{"id":"requested_change","status":"pass|warning|fail","note":"可見依據"}},
    {{"id":"continuity","status":"pass|warning|fail","note":"可見依據"}},
    {{"id":"accessibility","status":"pass|warning|fail","note":"可見依據"}},
    {{"id":"realism","status":"pass|warning|fail","note":"可見依據"}}
  ]
}}"""


def _audit_generated_design(image_bytes, mime_type, design_spec):
    fallback = _pending_visual_audit(design_spec)
    if not client:
        return fallback
    try:
        small_bytes, small_mime = _shrink_for_llm(image_bytes)
        data = _copilot_generate_json([
            types.Part.from_text(text=_visual_audit_prompt(design_spec)),
            types.Part.from_bytes(data=small_bytes, mime_type=small_mime),
        ])
        return _normalize_visual_audit(data, design_spec)
    except Exception as e:
        print(f"Visual audit failed: {e}")
        return fallback


def _generate_copilot_greeting(
    image_bytes,
    mime_type,
    user_prompt,
    design_spec=None,
):
    """Review the new image and craft a greeting plus visual audit."""
    language = normalize_language((design_spec or {}).get('language'))
    pending_audit = _pending_visual_audit(design_spec or {})
    fallback = {
        'message': (
            'Hi, I’m Greenie 🌱 Your first design is ready. How does the overall direction feel, and what would you like to adjust next?'
            if language == 'en'
            else '嗨，我是小綠 🌱 第一版設計出來了！你覺得整體感覺如何？想往哪個方向繼續調整？'
        ),
        'suggestions': (
            ['Add more trees', 'Improve crossings', 'Try an evening view']
            if language == 'en'
            else ['再加一些樹', '加點街頭藝術', '換成夜景氛圍']
        ),
        'audit': pending_audit,
    }
    if not client:
        return fallback
    try:
        # str.replace, NOT str.format — the template's JSON example braces
        # make .format() raise KeyError on every single call.
        prompt_template = (
            EN_GREETING_SYSTEM_PROMPT
            if language == 'en'
            else GREETING_SYSTEM_PROMPT
        )
        prompt = prompt_template.replace(
            '{user_prompt}',
            user_prompt
            or (
                "Make the street more liveable"
                if language == 'en'
                else "讓街道更宜居"
            ),
        )
        if design_spec:
            prompt += (
                (
                    "\n\nAdd a visual_audit object to the same JSON response."
                    if language == 'en'
                    else "\n\n請在同一份 JSON 另外加入 visual_audit 物件。"
                )
                + "\n"
                + _visual_audit_prompt(design_spec)
                + (
                    "\nUse this outer structure:"
                    if language == 'en'
                    else "\n最外層格式為："
                )
                + '{"message":"...","suggestions":["..."],'
                '"visual_audit":{"score":80,"summary":"...",'
                '"checks":[...]}}'
            )
        small_bytes, small_mime = _shrink_for_llm(image_bytes)
        parts = [
            types.Part.from_text(text=prompt),
            types.Part.from_bytes(data=small_bytes, mime_type=small_mime)
        ]
        data = _copilot_generate_json(parts)
        return {
            'message': data.get('message', fallback['message']),
            'suggestions': data.get('suggestions', fallback['suggestions'])[:3],
            'audit': _normalize_visual_audit(
                data.get('visual_audit'),
                design_spec,
            ) if design_spec else pending_audit,
        }
    except Exception as e:
        print(f"Greeting generation failed: {e}")
        return fallback


def _decide_copilot_response(
    history,
    latest_image_bytes,
    mime_type,
    user_message,
    language='zh-TW',
):
    """Ask 小綠 to classify intent and produce a chat reply + refine prompt."""
    language = normalize_language(language)
    fallback = {
        'intent': 'chat',
        'message': (
            'I hear you 🌱 I got a little stuck—could you tell me once more what you would like to change?'
            if language == 'en'
            else '嗯！我有聽到 🌱 但我剛剛卡住了，可以再說一次你想調整的地方嗎？'
        ),
        'refine_prompt': '',
        'suggestions': (
            ['Add more greenery', 'Add seating', 'Change the weather']
            if language == 'en'
            else ['再多一些綠化', '加長椅與休憩區', '換個天氣']
        ),
    }
    if not client:
        return fallback
    try:
        if language == 'en':
            history_text = "\n".join(
                f"{'User' if h['role'] == 'user' else 'Greenie'}: {h['message']}"
                for h in history[-8:]
            ) or "(No previous conversation)"
            prompt_text = (
                EN_CHAT_SYSTEM_PROMPT
                + f"\n\n=== CONVERSATION ===\n{history_text}"
                f"\n\n=== LATEST USER MESSAGE ===\n{user_message}"
            )
        else:
            history_text = "\n".join(
                f"{'使用者' if h['role'] == 'user' else '小綠'}：{h['message']}"
                for h in history[-8:]
            ) or "(尚無歷史)"
            prompt_text = (
                CHAT_SYSTEM_PROMPT
                + f"\n\n=== 對話歷史 ===\n{history_text}"
                f"\n\n=== 使用者最新訊息 ===\n{user_message}"
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
            'version': int(version.get('version') or 0),
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
    video_jobs = []
    for job in list(session.get('video_jobs', {}).values())[
        -MAX_VIDEO_JOBS_PER_SESSION:
    ]:
        if not isinstance(job, dict):
            continue
        video_jobs.append({
            key: job.get(key)
            for key in (
                'id',
                'operation_name',
                'operation_names',
                'status',
                'version',
                'versions',
                'mode',
                'speed',
                'duration',
                'total_duration',
                'format',
                'aspect_ratio',
                'video_url',
                'error',
                'created_at',
                'updated_at',
            )
            if job.get(key) is not None
        })
    payload = {
        'versions': versions,
        'history': history,
        'video_jobs': video_jobs,
        'initial_prompt': str(session.get('initial_prompt') or ''),
        'language': normalize_language(session.get('language')),
        'design_spec': session.get('design_spec')
        if isinstance(session.get('design_spec'), dict)
        else {},
        'audit': session.get('audit')
        if isinstance(session.get('audit'), dict)
        else {},
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
            'version': int(version.get('version') or 0),
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
    design_spec = payload.get('design_spec')
    if not isinstance(design_spec, dict):
        design_spec = {}
    audit = payload.get('audit')
    if not isinstance(audit, dict):
        audit = {}
    video_jobs = {}
    for job in payload.get('video_jobs', [])[-MAX_VIDEO_JOBS_PER_SESSION:]:
        if not isinstance(job, dict):
            continue
        job_id = str(job.get('id') or '')
        if not re.fullmatch(r'[a-f0-9]{16}', job_id):
            continue
        video_jobs[job_id] = {
            'id': job_id,
            'operation_name': str(job.get('operation_name') or ''),
            'operation_names': [
                str(name)
                for name in (job.get('operation_names') or [])
                if name
            ][:4] or [str(job.get('operation_name') or '')],
            'status': str(job.get('status') or 'queued'),
            'version': int(job.get('version') or 1),
            'versions': [
                int(version)
                for version in (job.get('versions') or [])
                if str(version).isdigit()
            ][:5] or [int(job.get('version') or 1)],
            'mode': (
                'sequence'
                if job.get('mode') == 'sequence'
                else 'single'
            ),
            'speed': str(job.get('speed') or 'natural'),
            'duration': int(job.get('duration') or 8),
            'total_duration': int(
                job.get('total_duration')
                or job.get('duration')
                or 8
            ),
            'format': str(job.get('format') or 'landscape'),
            'aspect_ratio': str(job.get('aspect_ratio') or '16:9'),
            'video_url': str(job.get('video_url') or ''),
            'error': str(job.get('error') or ''),
            'created_at': float(job.get('created_at') or now),
            'updated_at': float(job.get('updated_at') or now),
        }
    return {
        'versions': versions,
        'history': history,
        'video_jobs': video_jobs,
        'initial_prompt': str(payload.get('initial_prompt') or ''),
        'language': normalize_language(payload.get('language')),
        'design_spec': design_spec,
        'audit': audit,
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


EN_API_ERRORS = {
    'design_plan_invalid': 'The design-plan request must be a JSON object.',
    'prompt_required': 'Describe the street transformation you would like to create.',
    'prompt_too_long': f'The transformation description cannot exceed {MAX_PROMPT_CHARS} characters.',
    'preset_invalid': 'This quick transformation option is not supported.',
    'knowledge_runtime_unavailable': 'The street-design knowledge runtime is temporarily unavailable.',
    'image_required': 'Upload a street image first.',
    'image_invalid': 'The uploaded image is invalid. Use a valid JPEG, PNG, or WebP image.',
    'provider_invalid': 'This image-generation provider is not supported.',
    'provider_unavailable': 'The selected image provider is not configured on the server.',
    'design_preferences_invalid': 'The street-context settings are invalid. Review the design plan and try again.',
    'mask_invalid': 'The edit-area mask is invalid. Use a same-size PNG with transparent edit areas.',
    'generation_busy': 'Another image is being generated. Please try again when it is complete.',
    'empty_image_response': 'The image service did not return an image. Please try again.',
    'generation_failed': 'Image generation failed. Please try again shortly.',
    'generation_timeout': 'Image generation timed out. Try again or choose a lower resolution.',
    'provider_rate_limited': 'The image service is busy or out of quota. Please try again later.',
    'copilot_unavailable': 'Greenie requires a configured Google API key.',
    'json_invalid': 'The request body must be a JSON object.',
    'chat_fields_required': 'session_id and message are required.',
    'session_id_invalid': 'The session_id format is invalid.',
    'message_too_long': f'The message cannot exceed {MAX_CHAT_CHARS} characters.',
    'session_expired': 'This co-design session does not exist or has expired. Generate a new image to continue.',
    'session_busy': 'This co-design session is still processing the previous request.',
    'refinement_failed': 'The image refinement failed. Please try again shortly.',
    'rate_limited': 'Too many requests. Please wait before trying again.',
    'not_found': 'This API route was not found.',
    'method_not_allowed': 'This request method is not supported.',
    'payload_too_large': 'The upload is too large. Reduce the image size and try again.',
    'internal_error': 'The server encountered an unexpected error. Please try again later.',
    'openai_timeout': 'OpenAI image generation timed out. Try 1K or 2K and retry.',
    'openai_auth_failed': 'The OpenAI API key is invalid or revoked. Update it on the server.',
    'openai_access_denied': 'This OpenAI project cannot currently use GPT Image. Check model access and organization verification.',
    'openai_rate_limited': 'The OpenAI image quota is exhausted or busy. Check usage and try again later.',
    'openai_moderation_blocked': 'The image or description did not pass the OpenAI safety check. Revise it and try again.',
    'openai_request_invalid': 'OpenAI could not process these image settings. Try 2K or adjust the image.',
    'openai_upstream_error': 'The OpenAI image service is temporarily unavailable.',
    'video_unavailable': 'Google Veo is not configured on the server.',
    'video_payload_invalid': 'The video request must be a JSON object.',
    'video_settings_invalid': 'Choose a supported duration, pace, and format.',
    'video_versions_invalid': 'Choose 3 to 5 different image versions for a connected video.',
    'video_version_invalid': 'This image version is no longer available. Select a recent version.',
    'video_job_not_found': 'This video job does not exist or has expired.',
    'video_generation_failed': 'Google Veo could not generate this video. Please try again later.',
    'video_result_missing': 'Google Veo completed without returning a video.',
    'video_storage_failed': 'The completed video could not be saved.',
    'gallery_payload_invalid': 'The gallery request must be a JSON object.',
    'gallery_consent_required': 'Confirm that you want to publish this generated image.',
    'gallery_caption_too_long': f'The caption cannot exceed {MAX_GALLERY_CAPTION_CHARS} characters.',
    'gallery_version_invalid': 'This generated image is no longer available. Choose a recent version.',
    'gallery_post_not_found': 'This shared street design does not exist.',
    'gallery_visitor_invalid': 'This browser could not be identified for feedback. Refresh and try again.',
    'gallery_storage_failed': 'The shared street design could not be saved. Please try again.',
}


def _request_language():
    header = request.headers.get('X-UI-Language', '')
    if header:
        return normalize_language(header)
    query_language = request.args.get('language', '')
    if query_language:
        return normalize_language(query_language)
    try:
        form_language = request.form.get('ui_language', '')
        if form_language:
            return normalize_language(form_language)
    except HTTPException:
        pass
    try:
        payload = request.get_json(silent=True)
    except HTTPException:
        payload = None
    if isinstance(payload, dict):
        return normalize_language(payload.get('language'))
    return 'zh-TW'


def _api_error(message, status, code, retry_after=None):
    language = _request_language()
    if language == 'en':
        message = EN_API_ERRORS.get(code, message)
    payload = {
        'error': message,
        'code': code,
        'language': language,
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


@app.route('/gallery')
def gallery_page():
    return render_template('gallery.html')


def _preferences_from_payload(payload):
    if not isinstance(payload, dict):
        return normalize_preferences({})
    nested = payload.get('design_preferences')
    if isinstance(nested, dict):
        return normalize_preferences(nested)
    return normalize_preferences(payload)


@app.route('/api/design-plan', methods=['POST'])
def create_design_plan():
    """Retrieve a small, reviewable set of street-design evidence."""
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return _api_error(
            '設計計畫需要 JSON 格式的需求。',
            400,
            'design_plan_invalid',
        )
    custom_prompt = str(payload.get('custom_prompt') or '').strip()
    preset_id = str(payload.get('preset_id') or '').strip()
    language = normalize_language(payload.get('language'))
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
    try:
        spec = build_design_spec(
            custom_prompt,
            preset_id,
            _preferences_from_payload(payload),
            language=language,
        )
    except (OSError, ValueError, json.JSONDecodeError) as e:
        print(
            f"[{g.request_id}] knowledge runtime unavailable: "
            f"{e.__class__.__name__}: {e}"
        )
        return _api_error(
            '街道設計知識庫暫時無法使用。',
            503,
            'knowledge_runtime_unavailable',
        )
    return jsonify({
        'status': 'success',
        'design_spec': public_design_spec(spec),
        'generation_prompt': compile_generation_prompt(spec),
    })


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
        'video': {
            'available': bool(
                client
                and getattr(client.models, 'generate_videos', None)
            ),
            'model': VEO_VIDEO_MODEL,
            'durations_seconds': [4, 6, 8],
            'formats': ['16:9', '9:16'],
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
    language = normalize_language(request.form.get('ui_language'))
    raw_preferences = request.form.get('design_preferences') or '{}'
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
    try:
        design_preferences = normalize_preferences(
            json.loads(raw_preferences)
        )
    except (TypeError, ValueError, json.JSONDecodeError):
        return _api_error(
            '街道情境設定格式不正確，請重新確認設計計畫。',
            400,
            'design_preferences_invalid',
        )

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
    
    mask_bytes = None
    mask_file = request.files.get('mask')
    if mask_file and mask_file.filename:
        try:
            mask_bytes = _validate_edit_mask(mask_file, image_bytes)
        except ValueError as e:
            return _api_error(str(e), 400, 'mask_invalid')

    try:
        design_spec = build_design_spec(
            custom_prompt,
            preset_id,
            design_preferences,
            language=language,
        )
        full_prompt = compile_generation_prompt(design_spec)
    except (OSError, ValueError, json.JSONDecodeError) as e:
        print(
            f"[{g.request_id}] knowledge runtime unavailable: "
            f"{e.__class__.__name__}: {e}"
        )
        return _api_error(
            '街道設計知識庫暫時無法使用。',
            503,
            'knowledge_runtime_unavailable',
        )

    print(
        f"[{g.request_id}] prompt ready "
        f"(provider={provider}, evidence={len(design_spec['evidence'])}, "
        f"chars={len(full_prompt)}, mask={bool(mask_bytes)})"
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
                mask_bytes=mask_bytes,
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
                'language': language,
                'design_spec': public_design_spec(design_spec),
                'audit': _pending_visual_audit(design_spec),
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
            version_meta['bytes'],
            version_meta.get('mime_type', 'image/jpeg'),
            custom_prompt or '',
            design_spec,
        )
        with SESSIONS_LOCK:
            SESSIONS[session_id]['audit'] = greeting.get(
                'audit',
                _pending_visual_audit(design_spec),
            )
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
            'language': language,
            'mask_applied': bool(mask_bytes),
            'design_spec': public_design_spec(design_spec),
            'audit': greeting.get(
                'audit',
                _pending_visual_audit(design_spec),
            ),
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
    requested_language = (
        normalize_language(data.get('language'))
        if data.get('language')
        else None
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
        if requested_language:
            session['language'] = requested_language
        return _chat_with_session(session_id, session, user_message)
    finally:
        _persist_session(session_id, session)
        _release_session_operation(operation_handle)


def _chat_with_session(session_id, session, user_message):
    global GEN_LOCK_HELD
    language = normalize_language(session.get('language'))
    latest = session['versions'][-1]
    latest_bytes = latest['bytes']
    mime_type = latest.get('mime_type', 'image/png')

    # Record the user turn before asking the model
    with SESSIONS_LOCK:
        _append_history_locked(session, 'user', user_message)
        history_snapshot = list(session['history'])

    decision = _decide_copilot_response(
        history_snapshot,
        latest_bytes,
        mime_type,
        user_message,
        language,
    )

    result = {
        'status': 'success',
        'session_id': session_id,
        'language': language,
        'intent': decision['intent'],
        'message': decision['message'],
        'suggestions': decision['suggestions'],
        'design_spec': session.get('design_spec') or {},
        'audit': session.get('audit') or {},
    }

    if decision['intent'] == 'refine' and decision['refine_prompt']:
        refine_prompt = decision['refine_prompt']
        current_spec = session.get('design_spec')
        if not isinstance(current_spec, dict) or not current_spec:
            current_spec = build_design_spec(
                session.get('initial_prompt')
                or (
                    'Improve the people-first street environment'
                    if language == 'en'
                    else '改善街道人本環境'
                ),
                language=language,
            )
        updated_spec = refine_design_spec(current_spec, refine_prompt)
        full_prompt = compile_generation_prompt(
            updated_spec,
            refinement_text=refine_prompt,
        )
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
        audit = _audit_generated_design(
            new_meta['bytes'],
            new_meta.get('mime_type', 'image/jpeg'),
            updated_spec,
        )
        with SESSIONS_LOCK:
            session['version_count'] = version_num
            session['versions'].append(new_meta)
            session['design_spec'] = public_design_spec(updated_spec)
            session['audit'] = audit
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
            'design_spec': public_design_spec(updated_spec),
            'audit': audit,
        })
    else:
        with SESSIONS_LOCK:
            _append_history_locked(
                session,
                'assistant',
                decision['message'],
            )

    return jsonify(result)


def _video_source_version(session, requested_version):
    """Return retained image metadata for an absolute co-design version."""
    versions = session.get('versions', [])
    version_count = int(session.get('version_count') or len(versions))
    first_retained = max(1, version_count - len(versions) + 1)
    for offset, version in enumerate(versions):
        absolute_version = int(
            version.get('version') or first_retained + offset
        )
        if absolute_version == requested_version:
            return version
    return None


def _gallery_post_key(post_id):
    return f'{GALLERY_POST_KEY_PREFIX}:{post_id}'


def _gallery_source_key(source_fingerprint):
    return f'{GALLERY_SOURCE_KEY_PREFIX}:{source_fingerprint}'


def _gallery_like_key(post_id):
    return f'{GALLERY_LIKE_KEY_PREFIX}:{post_id}'


def _redis_text(value):
    if isinstance(value, bytes):
        return value.decode('utf-8')
    return str(value or '')


def _gallery_post_from_mapping(mapping):
    if not mapping:
        return None
    decoded = {
        _redis_text(key): _redis_text(value)
        for key, value in mapping.items()
    }
    post_id = decoded.get('id', '')
    if not re.fullmatch(r'[a-f0-9]{16}', post_id):
        return None
    try:
        return {
            'id': post_id,
            'image_url': decoded.get('image_url', ''),
            'caption': decoded.get('caption', ''),
            'design_label': decoded.get('design_label', ''),
            'street_context': decoded.get('street_context', ''),
            'language': normalize_language(decoded.get('language')),
            'version': max(1, int(decoded.get('version') or 1)),
            'created_at': float(decoded.get('created_at') or 0),
            'likes': max(0, int(decoded.get('likes') or 0)),
            'source_fingerprint': decoded.get('source_fingerprint', ''),
        }
    except (TypeError, ValueError):
        return None


def _public_gallery_post(post):
    return {
        key: post[key]
        for key in (
            'id',
            'image_url',
            'caption',
            'design_label',
            'street_context',
            'language',
            'version',
            'created_at',
            'likes',
        )
    }


def _prune_redis_gallery():
    count = int(redis_client.zcard(GALLERY_INDEX_KEY))
    excess = count - MAX_GALLERY_POSTS
    if excess <= 0:
        return
    oldest_ids = redis_client.zrange(GALLERY_INDEX_KEY, 0, excess - 1)
    if not oldest_ids:
        return
    post_ids = [_redis_text(value) for value in oldest_ids]
    pipeline = redis_client.pipeline()
    for post_id in post_ids:
        pipeline.hget(
            _gallery_post_key(post_id),
            'source_fingerprint',
        )
    source_fingerprints = pipeline.execute()
    pipeline = redis_client.pipeline()
    for post_id, source_fingerprint in zip(
        post_ids,
        source_fingerprints,
    ):
        pipeline.delete(
            _gallery_post_key(post_id),
            _gallery_like_key(post_id),
        )
        if source_fingerprint:
            pipeline.delete(
                _gallery_source_key(_redis_text(source_fingerprint))
            )
    pipeline.zrem(GALLERY_INDEX_KEY, *post_ids)
    pipeline.execute()


def _create_gallery_post(post, source_fingerprint):
    """Persist one idempotent gallery post and return (post, created)."""
    if redis_client:
        source_key = _gallery_source_key(source_fingerprint)
        try:
            existing_id = redis_client.get(source_key)
            if existing_id:
                existing = _gallery_post_from_mapping(
                    redis_client.hgetall(
                        _gallery_post_key(_redis_text(existing_id))
                    )
                )
                if existing:
                    return existing, False
                redis_client.delete(source_key)

            claimed = redis_client.set(
                source_key,
                post['id'],
                nx=True,
            )
            if not claimed:
                existing_id = redis_client.get(source_key)
                existing = _gallery_post_from_mapping(
                    redis_client.hgetall(
                        _gallery_post_key(_redis_text(existing_id))
                    )
                )
                if existing:
                    return existing, False
                raise RuntimeError('gallery source claim has no post')

            stored = dict(post)
            stored['source_fingerprint'] = source_fingerprint
            pipeline = redis_client.pipeline()
            pipeline.hset(
                _gallery_post_key(post['id']),
                mapping=stored,
            )
            pipeline.zadd(
                GALLERY_INDEX_KEY,
                {post['id']: post['created_at']},
            )
            pipeline.execute()
            _prune_redis_gallery()
            return stored, True
        except Exception as error:
            print(
                'Redis gallery write failed; using local gallery '
                f'({error.__class__.__name__})'
            )

    with GALLERY_LOCK:
        existing_id = GALLERY_SOURCE_IDS.get(source_fingerprint)
        if existing_id and existing_id in GALLERY_POSTS:
            return dict(GALLERY_POSTS[existing_id]), False
        stored = dict(post)
        stored['source_fingerprint'] = source_fingerprint
        GALLERY_POSTS[post['id']] = stored
        GALLERY_SOURCE_IDS[source_fingerprint] = post['id']
        GALLERY_VOTES.setdefault(post['id'], set())
        while len(GALLERY_POSTS) > MAX_GALLERY_POSTS:
            oldest_id = min(
                GALLERY_POSTS,
                key=lambda item_id: GALLERY_POSTS[item_id]['created_at'],
            )
            removed = GALLERY_POSTS.pop(oldest_id)
            GALLERY_SOURCE_IDS.pop(
                removed.get('source_fingerprint', ''),
                None,
            )
            GALLERY_VOTES.pop(oldest_id, None)
        return dict(stored), True


def _list_gallery_posts(sort_order, limit):
    posts = None
    if redis_client:
        try:
            post_ids = [
                _redis_text(value)
                for value in redis_client.zrevrange(
                    GALLERY_INDEX_KEY,
                    0,
                    MAX_GALLERY_POSTS - 1,
                )
            ]
            pipeline = redis_client.pipeline()
            for post_id in post_ids:
                pipeline.hgetall(_gallery_post_key(post_id))
            posts = [
                post
                for post in map(
                    _gallery_post_from_mapping,
                    pipeline.execute(),
                )
                if post
            ]
        except Exception as error:
            print(
                'Redis gallery read failed; using local gallery '
                f'({error.__class__.__name__})'
            )
            posts = None
    if posts is None:
        with GALLERY_LOCK:
            posts = [dict(post) for post in GALLERY_POSTS.values()]

    if sort_order == 'popular':
        posts.sort(
            key=lambda post: (post['likes'], post['created_at']),
            reverse=True,
        )
    else:
        posts.sort(key=lambda post: post['created_at'], reverse=True)
    return {
        'items': [
            _public_gallery_post(post)
            for post in posts[:limit]
        ],
        'stats': {
            'works': len(posts),
            'likes': sum(post['likes'] for post in posts),
        },
    }


def _like_gallery_post(post_id, voter_hash):
    if redis_client:
        try:
            post_key = _gallery_post_key(post_id)
            if not redis_client.exists(post_key):
                return None
            added = bool(
                redis_client.sadd(
                    _gallery_like_key(post_id),
                    voter_hash,
                )
            )
            if added:
                likes = int(redis_client.hincrby(post_key, 'likes', 1))
            else:
                likes = int(redis_client.hget(post_key, 'likes') or 0)
            return {'likes': likes, 'new_like': added}
        except Exception as error:
            print(
                'Redis gallery feedback failed; using local gallery '
                f'({error.__class__.__name__})'
            )

    with GALLERY_LOCK:
        post = GALLERY_POSTS.get(post_id)
        if not post:
            return None
        voters = GALLERY_VOTES.setdefault(post_id, set())
        added = voter_hash not in voters
        if added:
            voters.add(voter_hash)
            post['likes'] += 1
        return {'likes': post['likes'], 'new_like': added}


@app.route('/api/gallery', methods=['GET'])
def list_gallery():
    sort_order = request.args.get('sort', 'latest')
    if sort_order not in {'latest', 'popular'}:
        sort_order = 'latest'
    try:
        limit = int(request.args.get('limit', 24))
    except (TypeError, ValueError):
        limit = 24
    limit = min(MAX_GALLERY_PAGE_SIZE, max(1, limit))
    result = _list_gallery_posts(sort_order, limit)
    result.update({'status': 'success', 'sort': sort_order})
    return jsonify(result)


@app.route('/api/gallery', methods=['POST'])
def publish_gallery_post():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return _api_error(
            '成果牆發布資料需要 JSON 格式。',
            400,
            'gallery_payload_invalid',
        )
    if payload.get('consent') is not True:
        return _api_error(
            '請先確認你願意公開這張生成成果。',
            400,
            'gallery_consent_required',
        )
    caption = str(payload.get('caption') or '').strip()
    if len(caption) > MAX_GALLERY_CAPTION_CHARS:
        return _api_error(
            f'作品說明不可超過 {MAX_GALLERY_CAPTION_CHARS} 個字元。',
            400,
            'gallery_caption_too_long',
        )
    session_id = str(payload.get('session_id') or '')
    if not re.fullmatch(r'[a-f0-9]{12}', session_id):
        return _api_error(
            'session_id 格式不正確。',
            400,
            'session_id_invalid',
        )
    version = payload.get('version')
    if isinstance(version, bool) or not isinstance(version, int) or version < 1:
        return _api_error(
            '請選擇一張仍可使用的生成成果。',
            400,
            'gallery_version_invalid',
        )
    limit_response = _check_rate_limit(
        'gallery_publish',
        8,
        24 * 60 * 60,
    )
    if limit_response:
        return limit_response

    session = _get_session(session_id)
    if not session:
        return _api_error(
            '這個共創階段不存在或已過期，請重新生成圖片。',
            404,
            'session_expired',
        )
    source = _video_source_version(session, version)
    if not source or not source.get('url'):
        return _api_error(
            '這張生成成果已不在可用版本中，請選擇較新的版本。',
            404,
            'gallery_version_invalid',
        )

    now = time.time()
    spec = session.get('design_spec')
    if not isinstance(spec, dict):
        spec = {}
    language = normalize_language(
        session.get('language') or spec.get('language')
    )
    post = {
        'id': uuid.uuid4().hex[:16],
        'image_url': str(source['url']),
        'caption': caption,
        'design_label': str(spec.get('design_label') or ''),
        'street_context': str(spec.get('street_context_label') or ''),
        'language': language,
        'version': version,
        'created_at': now,
        'likes': 0,
    }
    source_fingerprint = hashlib.sha256(
        f'{session_id}:{version}'.encode()
    ).hexdigest()
    try:
        stored, created = _create_gallery_post(
            post,
            source_fingerprint,
        )
    except Exception as error:
        print(
            f'[{g.request_id}] gallery storage failed: '
            f'{error.__class__.__name__}: {error}'
        )
        return _api_error(
            '目前無法儲存這張生成成果，請稍後再試。',
            503,
            'gallery_storage_failed',
        )
    return jsonify({
        'status': 'success',
        'post': _public_gallery_post(stored),
        'created': created,
        'gallery_url': url_for('gallery_page'),
    }), 201 if created else 200


@app.route('/api/gallery/<post_id>/like', methods=['POST'])
def like_gallery_post(post_id):
    if not re.fullmatch(r'[a-f0-9]{16}', post_id):
        return _api_error(
            '找不到這個街景成果。',
            404,
            'gallery_post_not_found',
        )
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return _api_error(
            '成果牆回饋資料需要 JSON 格式。',
            400,
            'gallery_payload_invalid',
        )
    visitor_token = str(payload.get('visitor_token') or '')
    if not re.fullmatch(r'[A-Za-z0-9_-]{16,80}', visitor_token):
        return _api_error(
            '無法辨識這次回饋，請重新整理後再試。',
            400,
            'gallery_visitor_invalid',
        )
    limit_response = _check_rate_limit(
        'gallery_like',
        120,
        60 * 60,
    )
    if limit_response:
        return limit_response
    voter_hash = hashlib.sha256(
        f'{post_id}:{visitor_token}'.encode()
    ).hexdigest()
    result = _like_gallery_post(post_id, voter_hash)
    if result is None:
        return _api_error(
            '找不到這個街景成果。',
            404,
            'gallery_post_not_found',
        )
    return jsonify({
        'status': 'success',
        'liked': True,
        **result,
    })


def _video_image(source):
    return types.Image(
        image_bytes=source['bytes'],
        mime_type=source.get('mime_type', 'image/jpeg'),
    )


def _video_prompt(speed, versions=None):
    pace = {
        'gentle': (
            'Move forward at a very slow, relaxed strolling pace with '
            'subtle natural walking motion.'
        ),
        'natural': (
            'Move forward at a natural pedestrian walking pace with smooth, '
            'stable motion.'
        ),
        'brisk': (
            'Move forward at a brisk walking pace while keeping the camera '
            'stable and comfortable.'
        ),
    }[speed]
    continuity = ''
    if versions and len(versions) > 1:
        version_path = ' -> '.join(f'v{version}' for version in versions)
        continuity = (
            ' Use the supplied first and last frames as fixed endpoints. '
            f'Follow this intended progression: {version_path}. Smoothly connect '
            'the street-design changes without sudden morphing or cuts.'
        )
    return (
        'Create a photorealistic first-person pedestrian walk-through from '
        'this redesigned street image. Keep an eye-level camera on the '
        'sidewalk and travel naturally forward into the scene. '
        f'{pace}{continuity} Preserve the exact street design, building geometry, '
        'storefronts, trees, lanes, street furniture, signs, lighting, and '
        'perspective shown in the reference. Use continuous stabilized camera '
        'movement, realistic parallax, and subtle urban ambience. No cuts, no '
        'camera rotation, no dramatic zoom, no new design elements, no close-up '
        'or identifiable people, no dialogue, and no music.'
    )


def _concatenate_video_segments(segment_bytes):
    """Join compatible Veo MP4 segments without recompressing them."""
    if len(segment_bytes) == 1:
        return segment_bytes[0]
    if not 2 <= len(segment_bytes) <= 4:
        raise ValueError('expected 2 to 4 video segments')
    ffmpeg_executable = imageio_ffmpeg.get_ffmpeg_exe()
    with tempfile.TemporaryDirectory(prefix='street-video-') as temp_dir:
        segment_paths = []
        for index, video_bytes in enumerate(segment_bytes):
            if not video_bytes:
                raise ValueError('video segment is empty')
            path = os.path.join(temp_dir, f'segment-{index}.mp4')
            with open(path, 'wb') as output:
                output.write(video_bytes)
            segment_paths.append(path)
        concat_path = os.path.join(temp_dir, 'segments.ffconcat')
        with open(concat_path, 'w', encoding='utf-8') as manifest:
            manifest.write('ffconcat version 1.0\n')
            for path in segment_paths:
                escaped_path = path.replace("'", "'\\''")
                manifest.write(f"file '{escaped_path}'\n")
        output_path = os.path.join(temp_dir, 'street-walkthrough.mp4')
        completed = subprocess.run(
            [
                ffmpeg_executable,
                '-hide_banner',
                '-loglevel',
                'error',
                '-f',
                'concat',
                '-safe',
                '0',
                '-i',
                concat_path,
                '-c',
                'copy',
                '-movflags',
                '+faststart',
                '-y',
                output_path,
            ],
            capture_output=True,
            check=False,
            timeout=120,
        )
        if completed.returncode != 0:
            detail = completed.stderr.decode('utf-8', errors='replace')[-1000:]
            raise RuntimeError(f'ffmpeg concat failed: {detail}')
        with open(output_path, 'rb') as output:
            return output.read()


def _public_video_job(job):
    payload = {
        'job_id': job['id'],
        'status': job['status'],
        'version': job['version'],
        'versions': job.get('versions') or [job['version']],
        'mode': job.get('mode') or 'single',
        'speed': job['speed'],
        'duration': job['duration'],
        'total_duration': job.get('total_duration') or job['duration'],
        'format': job['format'],
        'aspect_ratio': job['aspect_ratio'],
    }
    if job.get('video_url'):
        payload['video_url'] = job['video_url']
    if job.get('error'):
        payload['error'] = job['error']
    return payload


@app.route('/api/videos', methods=['POST'])
def create_video():
    """Start an asynchronous Google Veo image-to-video operation."""
    rate_error = _check_rate_limit('video', MAX_VIDEOS_PER_DAY, 86_400)
    if rate_error is not None:
        return rate_error
    if not client or not getattr(client.models, 'generate_videos', None):
        return _api_error(
            'Google Veo 尚未在伺服器設定完成。',
            503,
            'video_unavailable',
        )

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return _api_error(
            '影片請求必須是 JSON 物件。',
            400,
            'video_payload_invalid',
        )
    session_id = str(data.get('session_id') or '').strip()
    if not re.fullmatch(r'[a-f0-9]{12}', session_id):
        return _api_error(
            'session_id 格式無效。',
            400,
            'session_id_invalid',
        )
    mode = str(data.get('mode') or 'single')
    try:
        duration = int(data.get('duration'))
    except (TypeError, ValueError):
        return _api_error(
            '請選擇支援的影片長度、步行節奏與畫面比例。',
            400,
            'video_settings_invalid',
        )
    if mode == 'sequence':
        raw_versions = data.get('versions')
        try:
            video_versions = [
                int(version)
                for version in (
                    raw_versions
                    if isinstance(raw_versions, list)
                    else []
                )
            ]
        except (TypeError, ValueError):
            video_versions = []
        if (
            len(video_versions) not in {3, 4, 5}
            or len(set(video_versions)) != len(video_versions)
            or any(version < 1 for version in video_versions)
        ):
            return _api_error(
                '請選擇 3 到 5 個不同的圖片版本來製作連貫影片。',
                400,
                'video_versions_invalid',
            )
    elif mode == 'single':
        try:
            video_versions = [int(data.get('version'))]
        except (TypeError, ValueError):
            return _api_error(
                '請選擇支援的影片長度、步行節奏與畫面比例。',
                400,
                'video_settings_invalid',
            )
    else:
        return _api_error(
            '請選擇支援的影片素材模式。',
            400,
            'video_settings_invalid',
        )
    speed = str(data.get('speed') or '')
    video_format = str(data.get('format') or '')
    if (
        duration not in {4, 6, 8}
        or (mode == 'sequence' and duration != 8)
        or speed not in {'gentle', 'natural', 'brisk'}
        or video_format not in {'landscape', 'portrait'}
    ):
        return _api_error(
            '請選擇支援的影片長度、步行節奏與畫面比例。',
            400,
            'video_settings_invalid',
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
        sources = [
            _video_source_version(session, version)
            for version in video_versions
        ]
        if any(source is None for source in sources):
            return _api_error(
                '這個圖片版本已不在工作階段中，請選擇較新的版本。',
                404,
                'video_version_invalid',
            )
        aspect_ratio = '9:16' if video_format == 'portrait' else '16:9'
        config_kwargs = {
            'number_of_videos': 1,
            'duration_seconds': duration,
            'aspect_ratio': aspect_ratio,
            'resolution': '720p',
            'generate_audio': True,
            'person_generation': 'allow_adult',
            'enhance_prompt': True,
            'negative_prompt': (
                'warped buildings, morphing signs, jump cuts, camera shake, '
                'new vehicles, close-up faces, children, duplicated objects, '
                'text distortion'
            ),
        }
        operation_names = []
        if mode == 'sequence':
            transitions = zip(
                sources[:-1],
                sources[1:],
                video_versions[:-1],
                video_versions[1:],
            )
        else:
            transitions = [
                (sources[0], None, video_versions[0], None)
            ]
        for first_source, last_source, first_version, last_version in transitions:
            segment_config = dict(config_kwargs)
            segment_versions = [first_version]
            if last_source is not None:
                segment_config['last_frame'] = _video_image(last_source)
                segment_versions.append(last_version)
            operation = client.models.generate_videos(
                model=VEO_VIDEO_MODEL,
                prompt=_video_prompt(speed, segment_versions),
                image=_video_image(first_source),
                config=types.GenerateVideosConfig(**segment_config),
            )
            operation_name = str(getattr(operation, 'name', '') or '')
            if not operation_name:
                raise RuntimeError('Veo did not return an operation name')
            operation_names.append(operation_name)
        now = time.time()
        job_id = uuid.uuid4().hex[:16]
        job = {
            'id': job_id,
            'operation_name': operation_names[0],
            'operation_names': operation_names,
            'status': 'queued',
            'version': video_versions[-1],
            'versions': video_versions,
            'mode': mode,
            'speed': speed,
            'duration': duration,
            'total_duration': (
                duration * (len(video_versions) - 1)
                if mode == 'sequence'
                else duration
            ),
            'format': video_format,
            'aspect_ratio': aspect_ratio,
            'video_url': '',
            'error': '',
            'created_at': now,
            'updated_at': now,
        }
        jobs = session.setdefault('video_jobs', {})
        jobs[job_id] = job
        while len(jobs) > MAX_VIDEO_JOBS_PER_SESSION:
            oldest_id = min(
                jobs,
                key=lambda item: jobs[item].get('created_at', 0),
            )
            jobs.pop(oldest_id, None)
        session['updated_at'] = now
        return jsonify(_public_video_job(job)), 202
    except Exception as error:
        print(
            f'[{g.request_id}] Veo create failed: '
            f'{error.__class__.__name__}: {error}'
        )
        return _api_error(
            'Google Veo 無法建立影片，請確認付費額度與模型權限後再試。',
            502,
            'video_generation_failed',
            retry_after=30,
        )
    finally:
        _persist_session(session_id, session)
        _release_session_operation(operation_handle)


@app.route('/api/videos/<job_id>', methods=['GET'])
def get_video(job_id):
    """Poll Veo and persist the completed MP4 exactly once."""
    session_id = str(request.args.get('session_id') or '').strip()
    if (
        not re.fullmatch(r'[a-f0-9]{12}', session_id)
        or not re.fullmatch(r'[a-f0-9]{16}', job_id)
    ):
        return _api_error(
            '影片工作階段格式無效。',
            400,
            'session_id_invalid',
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
            '影片狀態正在更新，請稍候再查詢。',
            409,
            'session_busy',
            retry_after=3,
        )

    try:
        session = _refresh_persisted_session(session_id, session)
        job = session.get('video_jobs', {}).get(job_id)
        if not job:
            return _api_error(
                '找不到這個影片任務，可能已經逾時。',
                404,
                'video_job_not_found',
            )
        if job['status'] in {'completed', 'failed'}:
            return jsonify(_public_video_job(job))

        operation_names = job.get('operation_names') or [
            job['operation_name']
        ]
        operations = [
            client.operations.get(
                types.GenerateVideosOperation(name=operation_name)
            )
            for operation_name in operation_names
        ]
        now = time.time()
        job['updated_at'] = now
        operation_errors = [
            getattr(operation, 'error', None)
            for operation in operations
            if getattr(operation, 'error', None)
        ]
        if operation_errors:
            job['status'] = 'failed'
            job['error'] = (
                'Google Veo 無法完成這支影片，請調整設定後再試。'
            )
            session['updated_at'] = now
            print(
                f'[{g.request_id}] Veo operation failed: '
                f'{operation_errors[0]}'
            )
            return jsonify(_public_video_job(job))
        if not all(getattr(operation, 'done', False) for operation in operations):
            job['status'] = 'in_progress'
            session['updated_at'] = now
            return jsonify(_public_video_job(job))

        segment_bytes = []
        for operation in operations:
            response = getattr(operation, 'response', None)
            generated_videos = (
                getattr(response, 'generated_videos', None) or []
            )
            if not generated_videos:
                job['status'] = 'failed'
                job['error'] = 'Google Veo 完成任務，但沒有回傳影片。'
                session['updated_at'] = now
                return jsonify(_public_video_job(job))
            video_file = generated_videos[0].video
            downloaded = client.files.download(file=video_file)
            if not downloaded:
                raise RuntimeError('Veo video download was empty')
            segment_bytes.append(downloaded)
        video_bytes = _concatenate_video_segments(segment_bytes)
        job['video_url'] = _save_generated_video(
            session_id,
            job_id,
            video_bytes,
        )
        job['status'] = 'completed'
        session['updated_at'] = now
        return jsonify(_public_video_job(job))
    except Exception as error:
        print(
            f'[{g.request_id}] Veo poll failed: '
            f'{error.__class__.__name__}: {error}'
        )
        return _api_error(
            '影片狀態暫時無法更新，系統會保留任務，請稍後再試。',
            502,
            'video_generation_failed',
            retry_after=10,
        )
    finally:
        _persist_session(session_id, session)
        _release_session_operation(operation_handle)

if __name__ == '__main__':
    app.run(
        debug=os.getenv('FLASK_DEBUG') == '1',
        port=_env_int('PORT', 8888, 1, 65_535),
    )

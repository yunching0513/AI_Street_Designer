"""Dynamic street-design knowledge retrieval and prompt compilation.

The runtime intentionally treats the generated image as a concept
visualization, not a measured drawing or compliance determination.
"""

from __future__ import annotations

import copy
import json
import os
import re
from functools import lru_cache
from pathlib import Path

RUNTIME_VERSION = "1.0.0"
DEFAULT_BUNDLE_DIR = Path(__file__).resolve().parent / "street_skill"

CONTEXT_LABELS = {
    "auto": "由照片與需求初步判讀",
    "urban_core": "市中心街道",
    "main_street": "主要街道",
    "residential": "住宅生活街道",
    "school": "通學環境",
    "transit_corridor": "大眾運輸廊道",
    "neighbourhood": "鄰里街道",
}
INTENSITY_LABELS = {
    "light": "輕量改善",
    "balanced": "平衡改造",
    "transformative": "大幅重分配",
}
PRESERVE_LABELS = {
    "buildings": "既有建築、店面與出入口",
    "camera": "原始視角與構圖",
    "emergency_access": "救災與必要通行",
    "existing_trees": "健康既有樹木",
    "parking": "部分路邊停車",
    "loading": "裝卸與短停需求",
    "transit": "公車營運與停靠",
}
PRIORITY_LABELS = {
    "walking": "步行連續性",
    "cycling": "自行車安全",
    "transit": "大眾運輸",
    "greenery": "遮蔭與綠化",
    "accessibility": "無障礙",
    "safety": "道路安全",
    "local_activity": "店家與街道活動",
}

PRESET_PROFILES = {
    "widen-sidewalks": {
        "label": "連續人行道拓寬",
        "elements": {
            "sidewalk",
            "curb_ramp",
            "street_cross_section",
            "motor_vehicle_lane",
        },
        "topics": {
            "pedestrian",
            "accessibility",
            "cross_section",
            "road_safety",
        },
        "visual_requirements": [
            "形成連續、清楚且無障礙的步行淨空帶",
            "路口設置與行人動線對正的緣石坡道及觸覺提示",
            "由車道或路側空間重分配，不改動既有建築量體",
        ],
        "negative_constraints": [
            "不可讓人行道突然中斷或被機車、植栽與街道家具阻塞",
            "不可生成階梯、過陡坡道或無法銜接的路緣",
        ],
        "spatial_order": [
            "建築／店面",
            "連續步行淨空帶",
            "設施與綠化帶",
            "路緣",
            "車道",
        ],
    },
    "transit-priority": {
        "label": "公車停靠與大眾運輸優先",
        "elements": {
            "bus_lane",
            "curb_ramp",
            "street_cross_section",
            "motor_vehicle_lane",
        },
        "topics": {
            "transit",
            "accessibility",
            "cross_section",
            "road_safety",
        },
        "visual_requirements": [
            "候車與上下車區直接銜接連續人行動線",
            "公車優先空間以清楚鋪面或標線辨識",
            "保留乘客候車、輪椅迴轉與行人通過的空間",
        ],
        "negative_constraints": [
            "不可讓候車設施阻塞主要步行淨空帶",
            "不可讓乘客被迫直接從混合車流中上下車",
        ],
        "spatial_order": [
            "建築／店面",
            "步行淨空帶",
            "候車設施",
            "無障礙上下車區",
            "公車優先空間",
            "一般車道",
        ],
    },
    "protected-bike-lane": {
        "label": "保護型自行車道",
        "elements": {
            "bicycle_lane",
            "protected_cycle_track",
            "buffer_zone",
            "curb_ramp",
            "street_cross_section",
        },
        "topics": {
            "cycling",
            "accessibility",
            "cross_section",
            "road_safety",
            "intersections",
        },
        "visual_requirements": [
            "自行車動線連續、可辨識，並與快速車流保持保護或緩衝",
            "避免停車開門區、路緣及固定物侵入有效騎乘空間",
            "路口維持清楚的自行車穿越與駕駛視線",
        ],
        "negative_constraints": [
            "不可讓車道在路口或公車站前突然消失",
            "不可把分隔物放進自行車有效淨寬",
            "不可讓汽機車停放在自行車道上",
        ],
        "spatial_order": [
            "建築／店面",
            "人行道",
            "設施帶",
            "保護型自行車道",
            "緩衝／分隔帶",
            "車道",
        ],
    },
    "green-street": {
        "label": "綠色生活街道",
        "elements": {
            "sidewalk",
            "street_cross_section",
            "curb_ramp",
            "buffer_zone",
            "motor_vehicle_lane",
        },
        "topics": {
            "green_infrastructure",
            "trees_public_realm",
            "pedestrian",
            "maintenance",
            "accessibility",
        },
        "visual_requirements": [
            "樹木、雨水花園與座椅集中於設施帶並提供連續遮蔭",
            "保留清楚連續的步行淨空帶與店面能見度",
            "植栽尺度、樹穴與排水做法應呈現可維護性",
        ],
        "negative_constraints": [
            "不可用零散盆栽代替可維護的綠色基盤",
            "不可讓植栽、樹穴或座椅阻塞無障礙動線",
        ],
        "spatial_order": [
            "建築／店面",
            "步行淨空帶",
            "樹木／雨水／家具設施帶",
            "路緣",
            "車道",
        ],
    },
    "reduce-motor-traffic": {
        "label": "降低私人運具占用",
        "elements": {
            "traffic_calming_zone",
            "shared_street",
            "street_cross_section",
            "motor_vehicle_lane",
            "curb_ramp",
        },
        "topics": {
            "speed_management",
            "traffic_calming",
            "pedestrian",
            "road_safety",
            "engagement",
        },
        "visual_requirements": [
            "縮減私人汽機車可見占用並把空間重分配給步行、騎行與停留",
            "以入口處理、鋪面與街道配置傳達低速及行人優先",
            "仍保留救災、裝卸與必要進出的可信路徑",
        ],
        "negative_constraints": [
            "不可留下與原圖相同的車輛主導斷面",
            "不可用完全封死的做法阻斷救災與必要進出",
            "不可生成不合尺度的廣場或空蕩高速公路",
        ],
        "spatial_order": [
            "建築／店面",
            "行人活動與步行空間",
            "綠化／家具",
            "低速必要通行帶",
        ],
    },
}

GENERIC_PROFILE = {
    "label": "自訂人本街道改造",
    "elements": {"street_cross_section", "curb_ramp", "motor_vehicle_lane"},
    "topics": {"pedestrian", "accessibility", "road_safety", "cross_section"},
    "visual_requirements": [
        "以人本、安全、連續及可維護的街道空間回應使用者需求",
        "保留無障礙動線、必要通行及既有建築出入口",
        "讓新增元素在斷面位置、尺度與材質上可信且一致",
    ],
    "negative_constraints": [
        "不可用裝飾性物件取代真正的空間重分配",
        "不可遮擋店面、出入口、救災動線或主要視線",
    ],
    "spatial_order": [
        "建築／店面",
        "步行淨空帶",
        "設施／緩衝帶",
        "移動空間",
    ],
}

KEYWORD_SIGNALS = {
    "cycling": (
        "bike",
        "bicycle",
        "cycle",
        "自行車",
        "腳踏車",
        "單車",
    ),
    "walking": ("walk", "pedestrian", "sidewalk", "步行", "行人", "人行道"),
    "transit": ("bus", "transit", "公車", "巴士", "大眾運輸"),
    "greenery": (
        "green",
        "tree",
        "plant",
        "rain garden",
        "綠",
        "樹",
        "植栽",
        "雨水花園",
    ),
    "accessibility": (
        "accessible",
        "wheelchair",
        "barrier-free",
        "無障礙",
        "輪椅",
        "坡道",
    ),
    "safety": ("safe", "calm", "speed", "安全", "減速", "低速", "庇護"),
    "local_activity": (
        "seat",
        "cafe",
        "shop",
        "座椅",
        "咖啡",
        "店家",
        "活動",
    ),
}

LEGAL_FORCE_LABELS = {
    "mandatory": "臺灣現行強制性規範",
    "recommended": "建議值／指引",
    "advisory": "參考原則",
    "comparative": "國際比較參考",
}

EN_CONTEXT_LABELS = {
    "auto": "AI-assisted initial reading",
    "urban_core": "Urban core street",
    "main_street": "Main street",
    "residential": "Residential living street",
    "school": "School-zone street",
    "transit_corridor": "Transit corridor",
    "neighbourhood": "Neighbourhood street",
}
EN_INTENSITY_LABELS = {
    "light": "Light-touch improvement",
    "balanced": "Balanced transformation",
    "transformative": "Major space reallocation",
}
EN_PRESERVE_LABELS = {
    "buildings": "existing buildings, storefronts, and entrances",
    "camera": "original viewpoint and composition",
    "emergency_access": "emergency and essential access",
    "existing_trees": "healthy existing trees",
    "parking": "some curbside parking",
    "loading": "loading and short-stay access",
    "transit": "bus operations and stops",
}
EN_PRIORITY_LABELS = {
    "walking": "walking continuity",
    "cycling": "cycling safety",
    "transit": "public transport",
    "greenery": "shade and greenery",
    "accessibility": "accessibility",
    "safety": "road safety",
    "local_activity": "shops and street activity",
}
EN_LEGAL_FORCE_LABELS = {
    "mandatory": "Current mandatory Taiwan requirement",
    "recommended": "Recommended value or guidance",
    "advisory": "Advisory design principle",
    "comparative": "International comparative reference",
}
EN_PROFILE_COPY = {
    "widen-sidewalks": {
        "label": "Continuous widened sidewalk",
        "visual_requirements": [
            "Create a continuous, legible, step-free clear walking zone.",
            "Align curb ramps and tactile cues with pedestrian desire lines.",
            "Reallocate carriageway or curb space without altering buildings.",
        ],
        "negative_constraints": [
            "Do not allow the sidewalk to end abruptly or be blocked by scooters, planting, or furniture.",
            "Do not create steps, excessively steep ramps, or disconnected curbs.",
        ],
        "spatial_order": [
            "Buildings and storefronts",
            "Clear walking zone",
            "Furniture and planting zone",
            "Curb",
            "Carriageway",
        ],
    },
    "transit-priority": {
        "label": "Accessible transit stop and priority",
        "visual_requirements": [
            "Connect waiting and boarding areas directly to a continuous pedestrian route.",
            "Make transit-priority space legible through coherent paving or markings.",
            "Retain room for waiting passengers, wheelchair turning, and through movement.",
        ],
        "negative_constraints": [
            "Do not let shelters or stop furniture block the primary walking zone.",
            "Do not force passengers to board directly from mixed traffic.",
        ],
        "spatial_order": [
            "Buildings and storefronts",
            "Clear walking zone",
            "Waiting facilities",
            "Accessible boarding area",
            "Transit-priority space",
            "General traffic lane",
        ],
    },
    "protected-bike-lane": {
        "label": "Protected bicycle lane",
        "visual_requirements": [
            "Keep the cycling route continuous, legible, and protected or buffered from faster traffic.",
            "Keep door zones, curbs, and fixed objects outside the effective riding space.",
            "Maintain clear cycle crossings and driver sight lines at intersections.",
        ],
        "negative_constraints": [
            "Do not let the bicycle lane disappear at intersections or transit stops.",
            "Do not place separators inside the effective riding width.",
            "Do not place cars or scooters in the bicycle lane.",
        ],
        "spatial_order": [
            "Buildings and storefronts",
            "Sidewalk",
            "Furniture zone",
            "Protected bicycle lane",
            "Buffer or separator",
            "Carriageway",
        ],
    },
    "green-street": {
        "label": "Green living street",
        "visual_requirements": [
            "Concentrate trees, rain gardens, and seating in a maintainable furniture zone with continuous shade.",
            "Keep a clear continuous walking zone and visible storefronts.",
            "Show credible planting scale, tree pits, drainage, and maintenance access.",
        ],
        "negative_constraints": [
            "Do not substitute scattered decorative pots for maintainable green infrastructure.",
            "Do not let planting, tree pits, or seating block the accessible route.",
        ],
        "spatial_order": [
            "Buildings and storefronts",
            "Clear walking zone",
            "Trees, drainage, and furniture zone",
            "Curb",
            "Carriageway",
        ],
    },
    "reduce-motor-traffic": {
        "label": "Reduced private motor-vehicle dominance",
        "visual_requirements": [
            "Reduce visible private vehicle occupation and reallocate space to walking, cycling, and staying.",
            "Use entry treatments, paving, and street layout to communicate low speed and pedestrian priority.",
            "Retain a credible path for emergency, loading, and essential access.",
        ],
        "negative_constraints": [
            "Do not retain the same vehicle-dominated cross-section as the source image.",
            "Do not completely block emergency or essential access.",
            "Do not create an out-of-scale plaza or an implausibly empty highway.",
        ],
        "spatial_order": [
            "Buildings and storefronts",
            "Pedestrian activity and walking space",
            "Greenery and furniture",
            "Low-speed essential access lane",
        ],
    },
    "generic": {
        "label": "Custom people-first street transformation",
        "visual_requirements": [
            "Respond with a safe, continuous, maintainable people-first street design.",
            "Protect accessible routes, essential access, and existing building entrances.",
            "Make new elements credible in cross-section position, scale, and material.",
        ],
        "negative_constraints": [
            "Do not use decorative objects as a substitute for real space reallocation.",
            "Do not block storefronts, entrances, emergency access, or critical sight lines.",
        ],
        "spatial_order": [
            "Buildings and storefronts",
            "Clear walking zone",
            "Furniture or buffer zone",
            "Movement space",
        ],
    },
}
EN_ELEMENT_LABELS = {
    "bicycle_lane": "Bicycle lane",
    "protected_cycle_track": "Protected cycle track",
    "shared_use_path": "Shared-use path",
    "independent_bicycle_path": "Independent bicycle path",
    "buffer_zone": "Buffer zone",
    "curb_ramp": "Curb ramp",
    "bollard": "Bollard",
    "traffic_calming_zone": "Traffic-calming zone",
    "motor_vehicle_lane": "Motor-vehicle lane",
    "bus_lane": "Bus lane",
    "shared_street": "Shared street",
    "parking_bay": "Parking bay",
    "street_cross_section": "Street cross-section",
    "sidewalk": "Sidewalk",
}
EN_PARAMETER_LABELS = {
    "clear_width": "clear width",
    "rideable_width": "rideable width",
    "design_device_width": "design-user envelope",
    "running_slope": "running slope",
    "facility_selection": "facility selection",
    "additional_width": "additional width",
    "side_clearance": "side clearance",
    "aaa_facility_selection": "all-ages-and-abilities facility selection",
    "shy_distance": "shy distance",
    "surface_quality": "surface quality",
    "design_speed": "design speed",
    "cross_slope": "cross slope",
    "superelevation": "superelevation",
    "longitudinal_grade": "longitudinal grade",
    "lane_width": "lane width",
    "riding_sight_distance": "riding sight distance",
    "surface_contrast": "surface contrast",
    "clear_height": "clear height",
    "top_clear_width": "top landing clear width",
    "top_cross_slope": "top landing cross slope",
    "clear_gap": "clear gap",
    "height": "height",
    "shape_safety": "safe form",
    "visual_contrast": "visual contrast",
    "maximum_speed": "maximum speed",
    "design_scope": "design scope",
    "entry_treatment": "entry treatment",
    "emergency_access": "emergency access",
    "minimum_width_use": "use of minimum width",
    "effective_width": "effective width",
    "combined_width": "combined width",
    "wheelchair_clear_width": "wheelchair clear width",
    "balance_room_each_side": "lateral balance allowance",
    "combined_active_travel_width": "combined active-travel width",
    "carriageway_width": "carriageway width",
    "wide_cycle_access": "wide-cycle access",
    "maintenance_clear_width": "maintenance clear width",
    "inner_turn_radius": "inner turn radius",
    "turn_envelope": "turning envelope",
}
EN_PRINCIPLE_SUMMARIES = {
    "surface_quality": "Provide a firm, even, and slip-resistant riding surface.",
    "surface_contrast": "Use material or colour contrast to make the facility legible.",
    "facility_selection": "Select the facility type from context, speed, volume, and user needs.",
    "aaa_facility_selection": "Use an all-ages-and-abilities facility appropriate to the operating context.",
    "shape_safety": "Use forms and edges that reduce collision and snagging risk.",
    "visual_contrast": "Maintain sufficient visual contrast for detection and wayfinding.",
    "design_scope": "Treat the full street cross-section and its user interactions as one system.",
    "entry_treatment": "Make the transition into the low-speed area visually and physically legible.",
    "emergency_access": "Retain a credible emergency-access path while calming traffic.",
    "minimum_width_use": "Treat a minimum width as a constrained exception, not the default design target.",
}
EN_TOPIC_LABELS = {
    "accessibility": "accessibility",
    "cycling": "cycling",
    "maintenance": "maintenance",
    "engagement": "community engagement",
    "road_safety": "road safety",
    "materials": "materials",
    "cross_section": "cross-section design",
    "school_streets": "school streets",
    "geometric_design": "geometric design",
    "pedestrian": "walking",
    "trees_public_realm": "trees and public realm",
    "drainage": "drainage",
    "green_infrastructure": "green infrastructure",
    "tactical_urbanism": "tactical urbanism",
    "parking_curb": "curb management",
    "transit": "public transport",
    "intersections": "intersections",
}


def normalize_language(language) -> str:
    value = str(language or "").strip().lower()
    return "en" if value.startswith("en") else "zh-TW"


def _bundle_dir() -> Path:
    override = os.getenv("STREET_SKILL_DIR", "").strip()
    if override:
        candidate = Path(override).expanduser()
        if (candidate / "references").is_dir():
            return candidate / "references"
        return candidate
    return DEFAULT_BUNDLE_DIR


def _read_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


@lru_cache(maxsize=4)
def _load_bundle_cached(bundle_dir: str) -> dict:
    root = Path(bundle_dir)
    rules = _read_jsonl(root / "rules.jsonl")
    cards = _read_jsonl(root / "knowledge-cards.jsonl")
    manuals_payload = json.loads((root / "manuals.json").read_text("utf-8"))
    manuals = {
        item["id"]: item for item in manuals_payload.get("manuals", [])
    }
    meta_path = root / "bundle-meta.json"
    meta = json.loads(meta_path.read_text("utf-8")) if meta_path.exists() else {}
    return {
        "rules": rules,
        "cards": cards,
        "manuals": manuals,
        "meta": meta,
    }


def load_bundle() -> dict:
    return _load_bundle_cached(str(_bundle_dir().resolve()))


def _clean_text(value, maximum=2000) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:maximum]


def _safe_choice(value, allowed, default):
    value = _clean_text(value, 40)
    return value if value in allowed else default


def _safe_list(value, allowed, maximum=8):
    if not isinstance(value, list):
        value = []
    output = []
    for item in value:
        key = _clean_text(item, 40)
        if key in allowed and key not in output:
            output.append(key)
        if len(output) >= maximum:
            break
    return output


def normalize_preferences(preferences=None) -> dict:
    source = preferences if isinstance(preferences, dict) else {}
    context = _safe_choice(
        source.get("street_context"),
        CONTEXT_LABELS,
        "auto",
    )
    intensity = _safe_choice(
        source.get("intervention_intensity"),
        INTENSITY_LABELS,
        "balanced",
    )
    target_speed = source.get("target_speed_kmh")
    try:
        target_speed = int(target_speed) if target_speed not in (None, "") else None
    except (TypeError, ValueError):
        target_speed = None
    if target_speed not in (10, 20, 30, 40):
        target_speed = None

    preserve = _safe_list(source.get("preserve"), PRESERVE_LABELS)
    for required in ("buildings", "camera", "emergency_access"):
        if required not in preserve:
            preserve.insert(0, required)
    priorities = _safe_list(source.get("priorities"), PRIORITY_LABELS)
    return {
        "street_context": context,
        "target_speed_kmh": target_speed,
        "intervention_intensity": intensity,
        "preserve": preserve,
        "priorities": priorities,
    }


def _detect_priorities(text: str) -> list[str]:
    lowered = text.casefold()
    return [
        key
        for key, terms in KEYWORD_SIGNALS.items()
        if any(term.casefold() in lowered for term in terms)
    ]


def _profile_for_request(preset_id: str, request_text: str) -> dict:
    if preset_id in PRESET_PROFILES:
        return copy.deepcopy(PRESET_PROFILES[preset_id])
    profile = copy.deepcopy(GENERIC_PROFILE)
    detected = _detect_priorities(request_text)
    if "cycling" in detected:
        profile["elements"].update(
            {"bicycle_lane", "protected_cycle_track", "buffer_zone"}
        )
        profile["topics"].add("cycling")
    if "transit" in detected:
        profile["elements"].add("bus_lane")
        profile["topics"].add("transit")
    if "greenery" in detected:
        profile["topics"].update(
            {"green_infrastructure", "trees_public_realm", "maintenance"}
        )
    if "safety" in detected:
        profile["elements"].update(
            {"traffic_calming_zone", "shared_street"}
        )
        profile["topics"].update({"speed_management", "traffic_calming"})
    return profile


def _tokenize(text: str) -> set[str]:
    return {
        token
        for token in re.findall(
            r"[a-z0-9_]+|[\u4e00-\u9fff]{2,}",
            text.casefold(),
        )
        if len(token) > 1
    }


def _rule_score(rule, profile, context, request_tokens):
    element = rule.get("element")
    applies = rule.get("applies_when") or {}
    contexts = set(applies.get("contexts") or [])
    score = 0
    if element in profile["elements"]:
        score += 14
    elif element in {"curb_ramp", "street_cross_section"}:
        score += 4
    elif element in {
        "bicycle_lane",
        "protected_cycle_track",
        "shared_use_path",
        "independent_bicycle_path",
        "buffer_zone",
    } and "cycling" not in profile["topics"]:
        score -= 12
    if context != "auto" and context in contexts:
        score += 5
    elif context == "auto" and contexts:
        score += 2
    manual_id = rule.get("manual_id", "")
    if manual_id.startswith("tw-"):
        score += 5
    if rule.get("review", {}).get("status") == "source_checked":
        score += 2
    if rule.get("legal_force") == "mandatory":
        score += 2
    haystack = " ".join(
        (
            rule.get("title", ""),
            rule.get("statement", ""),
            rule.get("parameter", ""),
            element or "",
        )
    )
    score += min(6, len(request_tokens & _tokenize(haystack)) * 2)
    return score


def _card_score(card, profile, context, request_tokens):
    elements = set(card.get("elements") or [])
    topics = set(card.get("topics") or [])
    contexts = set(card.get("contexts") or [])
    score = 0
    score += len(elements & profile["elements"]) * 8
    score += len(topics & profile["topics"]) * 5
    if context != "auto" and context in contexts:
        score += 4
    elif context == "auto" and contexts:
        score += 1
    if card.get("review", {}).get("status") == "source_checked":
        score += 2
    haystack = " ".join(
        (
            card.get("title", ""),
            card.get("summary", ""),
            card.get("application", ""),
        )
    )
    score += min(6, len(request_tokens & _tokenize(haystack)) * 2)
    return score


def _value_label(rule, language="zh-TW") -> str:
    value = rule.get("value") or {}
    unit = value.get("unit") or ""
    labels = (
        (
            ("minimum", "Minimum"),
            ("preferred", "Preferred"),
            ("maximum", "Maximum"),
            ("exact", "Specified"),
        )
        if normalize_language(language) == "en"
        else (
            ("minimum", "最低"),
            ("preferred", "建議"),
            ("maximum", "上限"),
            ("exact", "指定"),
        )
    )
    for key, label in labels:
        candidate = value.get(key)
        if candidate is not None and candidate is not False:
            if key == "exact" and candidate is True:
                return ""
            return f"{label} {candidate:g}{unit}" if isinstance(
                candidate, (int, float)
            ) else f"{label} {candidate}{unit}"
    return ""


def _public_rule(rule, manuals, language="zh-TW"):
    language = normalize_language(language)
    manual = manuals.get(rule.get("manual_id"), {})
    source = rule.get("source") or {}
    authority = manual.get("authority", "")
    legal_force = rule.get("legal_force", "advisory")
    if not rule.get("manual_id", "").startswith("tw-"):
        legal_force = "comparative"
    original_title = rule.get("title")
    original_statement = rule.get("statement")
    value_label = _value_label(rule, language)
    if language == "en":
        element_label = EN_ELEMENT_LABELS.get(
            rule.get("element"),
            str(rule.get("element") or "Street design").replace("_", " ").title(),
        )
        parameter_label = EN_PARAMETER_LABELS.get(
            rule.get("parameter"),
            str(rule.get("parameter") or "design criterion").replace("_", " "),
        )
        title = f"{element_label} — {parameter_label}"
        if value_label:
            statement = f"Design criterion: {value_label}."
        else:
            statement = EN_PRINCIPLE_SUMMARIES.get(
                rule.get("parameter"),
                (
                    f"Apply the cited source guidance for {parameter_label}; "
                    "verify the exact clause during detailed design."
                ),
            )
        authority_labels = EN_LEGAL_FORCE_LABELS
        fallback_authority = "Design reference"
        manual_title = (
            manual.get("title")
            or manual.get("local_title")
            or rule.get("manual_id")
        )
    else:
        title = original_title
        statement = original_statement
        authority_labels = LEGAL_FORCE_LABELS
        fallback_authority = "設計參考"
        manual_title = (
            manual.get("local_title")
            or manual.get("title")
            or rule.get("manual_id")
        )
    return {
        "kind": "rule",
        "id": rule.get("rule_id"),
        "title": title,
        "statement": statement,
        "original_title": original_title,
        "original_statement": original_statement,
        "source_language": rule.get("source_language") or "unknown",
        "value_label": value_label,
        "element": rule.get("element"),
        "parameter": rule.get("parameter"),
        "legal_force": legal_force,
        "authority_label": authority_labels.get(
            legal_force,
            authority or fallback_authority,
        ),
        "manual_id": rule.get("manual_id"),
        "manual_title": manual_title,
        "publisher": manual.get("publisher"),
        "section": source.get("section"),
        "page": source.get("page"),
        "source_url": source.get("url")
        or manual.get("document_url")
        or manual.get("landing_url"),
        "effective_from": (rule.get("version") or {}).get("effective_from"),
        "professional_review_required": True,
    }


def _public_card(card, manuals, language="zh-TW"):
    language = normalize_language(language)
    manual = manuals.get(card.get("manual_id"), {})
    source = card.get("source") or {}
    original_title = card.get("title")
    original_statement = card.get("summary")
    if language == "en":
        topics = [
            EN_TOPIC_LABELS.get(topic, topic.replace("_", " "))
            for topic in (card.get("topics") or [])[:3]
        ]
        topic_text = ", ".join(topics) or "street-design practice"
        title = f"Method reference — {topic_text.title()}"
        statement = (
            f"Comparative method guidance covering {topic_text}; apply it "
            "alongside current Taiwan requirements and project-specific review."
        )
        authority_label = "Method and international comparative reference"
        manual_title = (
            manual.get("title")
            or manual.get("local_title")
            or card.get("manual_id")
        )
        application = statement
        version_warning = (
            "Check the current source edition before project use."
            if card.get("version_warning")
            else None
        )
    else:
        title = original_title
        statement = original_statement
        authority_label = "方法與國際比較參考"
        manual_title = (
            manual.get("local_title")
            or manual.get("title")
            or card.get("manual_id")
        )
        application = card.get("application")
        version_warning = card.get("version_warning")
    return {
        "kind": "method",
        "id": card.get("card_id"),
        "title": title,
        "statement": statement,
        "original_title": original_title,
        "original_statement": original_statement,
        "source_language": card.get("translation_status") or "translated-note",
        "application": application,
        "authority_label": authority_label,
        "manual_id": card.get("manual_id"),
        "manual_title": manual_title,
        "publisher": manual.get("publisher"),
        "section": source.get("section"),
        "page": source.get("page"),
        "source_url": manual.get("document_url")
        or manual.get("landing_url"),
        "version_warning": version_warning,
        "professional_review_required": True,
    }


def retrieve_evidence(
    request_text: str,
    preset_id: str = "",
    preferences=None,
    minimum=5,
    maximum=12,
    language="zh-TW",
) -> list[dict]:
    language = normalize_language(language)
    prefs = normalize_preferences(preferences)
    profile = _profile_for_request(preset_id, request_text)
    bundle = load_bundle()
    tokens = _tokenize(request_text)
    rules = sorted(
        bundle["rules"],
        key=lambda item: (
            -_rule_score(
                item,
                profile,
                prefs["street_context"],
                tokens,
            ),
            item.get("rule_id", ""),
        ),
    )
    cards = sorted(
        bundle["cards"],
        key=lambda item: (
            -_card_score(
                item,
                profile,
                prefs["street_context"],
                tokens,
            ),
            item.get("card_id", ""),
        ),
    )

    selected_rules = []
    seen_parameters = set()
    target_rule_count = min(8, max(4, maximum - 3))
    for rule in rules:
        score = _rule_score(
            rule,
            profile,
            prefs["street_context"],
            tokens,
        )
        if score < 4:
            continue
        key = (rule.get("element"), rule.get("parameter"))
        if key in seen_parameters:
            continue
        selected_rules.append(
            _public_rule(rule, bundle["manuals"], language)
        )
        seen_parameters.add(key)
        if len(selected_rules) >= target_rule_count:
            break

    selected_cards = []
    for card in cards:
        score = _card_score(
            card,
            profile,
            prefs["street_context"],
            tokens,
        )
        if score < 5:
            continue
        selected_cards.append(
            _public_card(card, bundle["manuals"], language)
        )
        if len(selected_cards) >= 3:
            break

    evidence = selected_rules + selected_cards
    if len(evidence) < minimum:
        for card in cards:
            item = _public_card(card, bundle["manuals"], language)
            if item["id"] not in {entry["id"] for entry in evidence}:
                evidence.append(item)
            if len(evidence) >= minimum:
                break
    return evidence[:maximum]


def build_design_spec(
    request_text: str,
    preset_id: str = "",
    preferences=None,
    language="zh-TW",
) -> dict:
    language = normalize_language(language)
    request_text = _clean_text(request_text)
    prefs = normalize_preferences(preferences)
    profile = _profile_for_request(preset_id, request_text)
    detected = _detect_priorities(request_text)
    priorities = prefs["priorities"] or detected or ["walking", "safety"]
    evidence = retrieve_evidence(
        request_text,
        preset_id,
        {**prefs, "priorities": priorities},
        language=language,
    )
    if language == "en":
        profile_copy = EN_PROFILE_COPY.get(
            preset_id if preset_id in PRESET_PROFILES else "generic"
        )
        context_labels = EN_CONTEXT_LABELS
        intensity_labels = EN_INTENSITY_LABELS
        preserve_labels = EN_PRESERVE_LABELS
        priority_labels = EN_PRIORITY_LABELS
        assumptions = [
            "A single street image cannot reliably measure right-of-way width; numeric values are design checks, not claims that the image meets an exact dimension.",
            "This output is a concept visualization, not a compliance determination or construction drawing.",
        ]
    else:
        profile_copy = profile
        context_labels = CONTEXT_LABELS
        intensity_labels = INTENSITY_LABELS
        preserve_labels = PRESERVE_LABELS
        priority_labels = PRIORITY_LABELS
        assumptions = [
            "單張街景無法可靠量測道路寬度；數值僅作設計檢核提示，不宣稱圖中已精確達標。",
            "此成果為概念視覺化，不是法規符合性判定或施工圖。",
        ]
    if prefs["street_context"] == "auto":
        assumptions.append(
            "The user has not confirmed a street type; generation uses a general Taiwan urban-street context."
            if language == "en"
            else "街道類型尚未由使用者指定，生成時採一般臺灣都市街道情境。"
        )
    if prefs["target_speed_kmh"] is None:
        assumptions.append(
            "The legal speed limit is not inferred from the image; generation only communicates a credible low-speed design intent."
            if language == "en"
            else "未由照片推定法定速限；生成時只以低速、可預期行為的空間語言表達。"
        )
    return {
        "runtime_version": RUNTIME_VERSION,
        "language": language,
        "status": "concept",
        "jurisdiction": "Taiwan",
        "request_text": request_text,
        "preset_id": preset_id if preset_id in PRESET_PROFILES else "",
        "design_label": profile_copy["label"],
        "street_context": prefs["street_context"],
        "street_context_label": context_labels[prefs["street_context"]],
        "target_speed_kmh": prefs["target_speed_kmh"],
        "intervention_intensity": prefs["intervention_intensity"],
        "intervention_intensity_label": intensity_labels[
            prefs["intervention_intensity"]
        ],
        "preserve": [
            {"id": item, "label": preserve_labels[item]}
            for item in prefs["preserve"]
        ],
        "priorities": [
            {"id": item, "label": priority_labels[item]}
            for item in priorities
            if item in priority_labels
        ],
        "requested_interventions": profile_copy["visual_requirements"],
        "spatial_order": profile_copy["spatial_order"],
        "negative_constraints": profile_copy["negative_constraints"],
        "evidence": evidence,
        "assumptions": assumptions,
        "refinement_history": [],
        "source_note": (
            "Current Taiwan requirements take precedence; international manuals are comparative methods only. Detailed design still requires site measurement, authority requirements, and professional review."
            if language == "en"
            else "臺灣現行規範優先；國際手冊只作比較與方法參考。正式設計仍須依基地量測、主管機關要求與專業審查確認。"
        ),
    }


def _source_line(item, index, language="zh-TW") -> str:
    language = normalize_language(language)
    location = (", " if language == "en" else "，").join(
        part
        for part in (
            f"§{item.get('section')}" if item.get("section") else "",
            f"p.{item.get('page')}" if item.get("page") else "",
        )
        if part
    )
    value = (
        f"; {item['value_label']}"
        if language == "en" and item.get("value_label")
        else f"；{item['value_label']}"
        if item.get("value_label")
        else ""
    )
    if language == "en":
        return (
            f"[E{index}] {item['title']}: {item['statement']}{value} "
            f"({item['manual_title']}{', ' + location if location else ''}; "
            f"{item['authority_label']})"
        )
    return (
        f"[E{index}] {item['title']}：{item['statement']}{value}"
        f"（{item['manual_title']}{'，' + location if location else ''}；"
        f"{item['authority_label']}）"
    )


def compile_generation_prompt(
    spec: dict,
    refinement_text: str = "",
) -> str:
    language = normalize_language(spec.get("language"))
    request_text = spec.get("request_text") or (
        "Improve the people-first street environment"
        if language == "en"
        else "改善街道人本環境"
    )
    separator = ", " if language == "en" else "、"
    priorities = separator.join(
        item["label"] for item in spec.get("priorities", [])
    )
    preserved = separator.join(
        item["label"] for item in spec.get("preserve", [])
    )
    evidence_lines = "\n".join(
        _source_line(item, index, language)
        for index, item in enumerate(spec.get("evidence", []), 1)
    )
    interventions = "\n".join(
        f"- {item}" for item in spec.get("requested_interventions", [])
    )
    constraints = "\n".join(
        f"- {item}" for item in spec.get("negative_constraints", [])
    )
    refinement = (
        f"\n[CURRENT USER REFINEMENT]\n{_clean_text(refinement_text)}\n"
        if refinement_text
        else ""
    )
    speed = (
        (
            f"Spatial design language for a {spec['target_speed_kmh']} km/h target speed"
            if language == "en"
            else f"{spec['target_speed_kmh']} km/h 的目標速度空間語言"
        )
        if spec.get("target_speed_kmh")
        else (
            "Do not claim a legal speed limit; communicate a credible low-speed safety intent"
            if language == "en"
            else "不自行宣稱法定速限；以可信的低速安全空間語言表達"
        )
    )
    return f"""[ROLE]
You are a street-design visualization specialist working in a Taiwan context.
Create a photorealistic concept image, not a measured plan or compliance claim.

[USER'S DESIGN GOAL — PRIMARY]
{request_text}
{refinement}
[CONFIRMED DESIGN FRAME]
- Design: {spec.get('design_label')}
- Street context: {spec.get('street_context_label')}
- Intervention intensity: {spec.get('intervention_intensity_label')}
- Speed intent: {speed}
- Priorities: {priorities}
- Preserve: {preserved}

[VISIBLE INTERVENTIONS]
{interventions}

[CROSS-SECTION ORDER, BUILDING EDGE TO ROAD]
{" → ".join(spec.get("spatial_order", []))}

[RETRIEVED DESIGN EVIDENCE]
Use these as design checks. Taiwan requirements control; international items are
comparative methods. Do not claim exact dimensions that cannot be verified from
the source photograph.
{evidence_lines}

[NEGATIVE CONSTRAINTS]
{constraints}

[IMAGE EDITING REQUIREMENTS]
- Preserve every building, facade, storefront opening, camera position,
  perspective, weather, and overall lighting.
- Change only street-level space and objects needed for the confirmed design.
- Make paths continuous, geometry buildable-looking, markings coherent, and
  accessibility details visually plausible.
- Avoid invented signs, illegible text, duplicated people, floating objects,
  blocked doors, and conflicts between pedestrians, cycles, buses, and vehicles.
- Maintain realistic Taiwanese street materials, drainage, planting, and use.
"""


def refine_design_spec(spec: dict, refinement_text: str) -> dict:
    refinement_text = _clean_text(refinement_text, 1000)
    original = spec.get("request_text") or ""
    preferences = {
        "street_context": spec.get("street_context"),
        "target_speed_kmh": spec.get("target_speed_kmh"),
        "intervention_intensity": spec.get("intervention_intensity"),
        "preserve": [item["id"] for item in spec.get("preserve", [])],
        "priorities": [item["id"] for item in spec.get("priorities", [])],
    }
    language = normalize_language(spec.get("language"))
    combined_request = (
        f"{original}; refinement: {refinement_text}"
        if language == "en"
        else f"{original}；後續調整：{refinement_text}"
    )
    updated = build_design_spec(
        combined_request,
        spec.get("preset_id") or "",
        preferences,
        language=language,
    )
    history = list(spec.get("refinement_history") or [])
    history.append(refinement_text)
    updated["refinement_history"] = history[-10:]
    updated["original_request_text"] = spec.get(
        "original_request_text",
        original,
    )
    return updated


def build_visual_audit_checklist(spec: dict) -> list[dict]:
    language = normalize_language(spec.get("language"))
    if language == "en":
        return [
            {
                "id": "preservation",
                "label": "Buildings, entrances, viewpoint, and lighting remain consistent",
                "status": "pending",
            },
            {
                "id": "requested_change",
                "label": f"{spec.get('design_label', 'The requested transformation')} is clearly visible",
                "status": "pending",
            },
            {
                "id": "continuity",
                "label": "Walking, cycling, and transit routes are continuous and conflict-aware",
                "status": "pending",
            },
            {
                "id": "accessibility",
                "label": "Accessible clear space, ramps, and crossing connections look plausible",
                "status": "pending",
            },
            {
                "id": "realism",
                "label": "Scale, paving, drainage, planting, and markings look credible",
                "status": "pending",
            },
        ]
    checks = [
        {
            "id": "preservation",
            "label": "建築、出入口、視角與光線是否維持一致",
            "status": "pending",
        },
        {
            "id": "requested_change",
            "label": f"{spec.get('design_label', '指定改造')}是否清楚可見",
            "status": "pending",
        },
        {
            "id": "continuity",
            "label": "步行／自行車／大眾運輸動線是否連續且不互相衝突",
            "status": "pending",
        },
        {
            "id": "accessibility",
            "label": "無障礙淨空、坡道與穿越銜接是否視覺合理",
            "status": "pending",
        },
        {
            "id": "realism",
            "label": "尺度、鋪面、排水、植栽與標線是否可信",
            "status": "pending",
        },
    ]
    return checks


def public_design_spec(spec: dict) -> dict:
    """Return a detached, JSON-safe copy for API responses and persistence."""
    return json.loads(json.dumps(spec, ensure_ascii=False))

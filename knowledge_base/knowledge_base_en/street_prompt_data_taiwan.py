# street_prompt_data_taiwan.py

"""
Taiwan Human-Oriented Transport Design Dictionary
Reference: 都市人本交通規劃設計手冊 (Urban Human-Oriented Transport Planning & Design Manual)
Integrates local Taiwanese street elements with SET methodology.
"""

TAIWAN_STREET_DESIGN_DICT = {
    # ------------------------------------------------------------------
    # Category 1: 標線與鋪面改善 (Re-marking / Surface Treatments)
    # ------------------------------------------------------------------
    "標線型人行道 (Green Sidewalk)": {
        "en_name": "Green Marked Sidewalk",
        "set_typology": "Re-marking Streets",
        "description": "Install a 'Green Marked Sidewalk' (commonly seen in Taiwan) along the roadside. Paint a vibrant green walking zone separated by white lines. Ensure continuity.",
        "keywords": "green painted sidewalk, high visibility green pavement, white edge lines, pedestrian walking zone on asphalt, tactical urbanism, Taiwan street style, safety separation",
        "negative_prompt": "raised curb, physical barrier, grey asphalt only, cars parked on green paint",
        "manual_ref": "手冊 3.3.1 標線型人行道：供行人通行之空間，以綠色鋪面為主。"
    },

    "行穿線退縮與庇護島 (Z-Crosswalk)": {
        "en_name": "Setback Crosswalk with Refuge Island",
        "set_typology": "Intersection Safety",
        "description": "Redesign the intersection by setting back the zebra crossing (moving it away from the corner). Install a concrete 'Pedestrian Refuge Island' in the middle of the road.",
        "keywords": "setback crosswalk, pedestrian refuge island, concrete median island, zebra crossing moved back, Z-shaped crossing, safety bollards, universal design, accessible curb ramp",
        "negative_prompt": "crosswalk right at corner, cars blocking path, dangerous intersection, no island",
        "manual_ref": "手冊 4.2.2 行人穿越道退縮 / 4.2.3 行人庇護島：縮短穿越距離，避免轉彎車輛視線死角。"
    },

    "彩色鋪面路口 (Colored Intersection)": {
        "en_name": "Colored Intersection",
        "set_typology": "Traffic Calming",
        "description": "Apply colored anti-skid coating to the entire intersection area to alert drivers. Use a distinct color (like brick red or yellow) to indicate a conflict zone.",
        "keywords": "colored asphalt intersection, brick red road surface, anti-skid pavement, visual warning zone, traffic calming, high contrast road markings",
        "negative_prompt": "wet slippery road, standard grey asphalt, construction mess",
        "manual_ref": "手冊 5.2 鋪面色彩：利用色彩區隔空間，提高駕駛警覺。"
    },

    # ------------------------------------------------------------------
    # Category 2: 街道空間重分配 (Re-purposing Sections)
    # ------------------------------------------------------------------
    "路口人行道外推 (Curb Extension)": {
        "en_name": "Curb Extension (Bulb-out)",
        "set_typology": "Re-purposing Sections",
        "description": "Widen the sidewalk at the intersection corners (Bulb-out). This shortens the crossing distance and prevents illegal corner parking.",
        "keywords": "curb extension, bulb-out, widened sidewalk corner, concrete curb, bollards, prevents corner parking, pedestrian safety, shorter crosswalk",
        "negative_prompt": "cars parking at corner, wide turning radius for cars, narrow sidewalk",
        "manual_ref": "手冊 4.2.1 路口人行道外推：縮短穿越距離，增加駕駛視距，防止違停。"
    },

    "機車彎與設施帶 (Motorcycle Bay & Furniture Zone)": {
        "en_name": "Furniture Zone & Motorcycle Parking",
        "set_typology": "Re-purposing Parking",
        "description": "Create a dedicated 'Furniture Zone' between the sidewalk and road. Place street trees, utility boxes, and indented motorcycle parking bays (Motorcycle Bends) in this zone, keeping the walking path clear.",
        "keywords": "sidewalk furniture zone, indented motorcycle parking bay, street trees aligned, utility boxes organized, clear pedestrian path, orderly motorcycle parking, Taiwan streetscape",
        "negative_prompt": "motorcycles blocking sidewalk, clutter, messy parking, walking obstruction",
        "manual_ref": "手冊 3.2.3 公共設施帶 / 機車彎：將機車退出人行道，收納於設施帶間的停車彎。"
    },

    "騎樓整平與延伸 (Arcade Leveling)": {
        "en_name": "Arcade Leveling & Extension",
        "set_typology": "Accessibility",
        "description": "Ensure the 'Veranda/Arcade' (covered walkway under buildings) is perfectly level and barrier-free. Extend the paving material to the sidewalk for a seamless wide walking area.",
        "keywords": "covered arcade walkway, leveled flooring, barrier-free design, seamless connection to sidewalk, tile pavement, bright lighting, accessible for wheelchair, Taiwan shopfront",
        "negative_prompt": "steps, height difference, motorcycles in arcade, blocked path, clutter",
        "manual_ref": "手冊 3.4 騎樓：騎樓地坪應平整，並與人行道順平。"
    },

    # ------------------------------------------------------------------
    # Category 3: 寧靜區與通學巷 (Entire Street / Traffic Calming)
    # ------------------------------------------------------------------
    "通學巷 (School Zone)": {
        "en_name": "School Zone Traffic Calming",
        "set_typology": "Re-purposing Entire Streets",
        "description": "Design a 'School Zone' with traffic calming measures. Use zig-zag markings, speed limit '30' painted on the road, and distinct colored pavement.",
        "keywords": "school zone, speed limit 30 painting, zig-zag road markings, colored pavement, safety barriers, students walking, traffic calming, safe route to school",
        "negative_prompt": "speeding cars, highway, danger, dark alley",
        "manual_ref": "手冊 6.2 通學巷：設置速限30、彩色鋪面與減速設施。"
    },

    "高原式路口 (Raised Intersection)": {
        "en_name": "Raised Intersection",
        "set_typology": "Traffic Calming",
        "description": "Raise the entire intersection to the height of the sidewalk. This forces cars to slow down and creates a flat crossing for pedestrians.",
        "keywords": "raised intersection, table-top crossing, speed table, flush curb, paver stones on road, traffic calming, slow cars, pedestrian priority",
        "negative_prompt": "steep ramps, standard asphalt road, fast cars",
        "manual_ref": "手冊 5.3 高原式路口：路口抬高與人行道齊平，強迫車輛減速。"
    }
}

# ------------------------------------------------------------------
# 輔助函式：針對台灣環境優化 Prompt
# ------------------------------------------------------------------
def get_taiwan_design_prompt(option_key, custom_text=""):
    data = TAIWAN_STREET_DESIGN_DICT.get(option_key)
    if not data:
        return None, None
        
    prompt = f"""
    [Role]
    You are an AI Urban Planner specializing in **Taiwanese Urban Design Standards** (Human-Oriented Transport Manual).
    
    [Task]
    Apply the measure "{data['en_name']}" to the uploaded street view.
    
    [Design Guidelines]
    - **Core Function**: {data['description']}
    - **Local Context**: Ensure the design fits a Taiwanese street context (e.g., using specific road marking styles, arcade structures if present).
    - **Reference Manual**: Based on concept: {data['manual_ref']}
    
    [Visual Requirements]
    - **Keywords**: {data['keywords']}
    - **Perspective**: Maintain original camera angle.
    - **Lighting**: Bright, clear daytime.
    
    [User Customization]
    User note: "{custom_text}"
    """
    return prompt, data['negative_prompt']
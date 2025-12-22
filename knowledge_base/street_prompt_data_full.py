# street_prompt_data_full.py

"""
Street Experiments (SET) Design Tool Dictionary
Based on the 4 Typologies of Street Experiments:
1. Re-marking Streets (標線與彩繪)
2. Re-purposing Parking (停車位再利用)
3. Re-purposing Sections of Streets (部分路段重塑)
4. Re-purposing Entire Streets (全路段/整條街重塑)
"""

SET_DESIGN_TOOL_DICT = {
    # ------------------------------------------------------------------
    # Category 1: Re-marking Streets (僅改變路面視覺，不改變硬體結構)
    # ------------------------------------------------------------------
    "路面藝術與彩繪 (Asphalt Art)": {
        "en_name": "Asphalt Art Intervention",
        "set_typology": "Re-marking Streets",
        "description": "Apply tactical urbanism 'Asphalt Art' to the road surface. Use bright, geometric colors to reclaim asphalt space for visuals without physical construction. Keep the road flat.",
        "keywords": "colorful geometric asphalt art, street mural on ground, painted intersection, vibrant road patterns, tactical urbanism paint, artistic crosswalk, visual traffic calming",
        "negative_prompt": "raised structures, walls, construction site, messy graffiti, 3d structures on road"
    },
    
    "路口安全改善 (Intersection Repair)": {
        "en_name": "Intersection Safety Re-marking",
        "set_typology": "Re-marking Streets",
        "description": "Redesign the intersection markings to prioritize pedestrian safety. Paint high-visibility crosswalks and 'neck-downs' (painted curb extensions) to shorten crossing distances visually.",
        "keywords": "high-visibility crosswalks, painted curb extensions, neck-downs, traffic calming markings, white thermoplastic lines, safety zones, pedestrian priority markings",
        "negative_prompt": "confusing lines, faded paint, cars blocking crosswalk, dangerous intersection"
    },

    # ------------------------------------------------------------------
    # Category 2: Re-purposing Parking (將停車格改為活動空間)
    # ------------------------------------------------------------------
    "路邊休憩座 (Parklet)": {
        "en_name": "Parklet Installation",
        "set_typology": "Re-purposing Parking",
        "description": "Convert roadside parking spaces into a 'Parklet'. Install a wooden platform flush with the sidewalk, equipped with public seating and planters. Create a social spot.",
        "keywords": "wooden parklet, curbside seating area, modular wood deck, outdoor cafe vibe, public benches, planters as barriers, people sitting, warm lighting, Schanigarten",
        "negative_prompt": "parked cars, metal fences, trash, heavy traffic right next to seats"
    },
    
    "自行車停放區 (Bike Corral)": {
        "en_name": "On-Street Bike Corral",
        "set_typology": "Re-purposing Parking",
        "description": "Replace one car parking spot with a 'Bike Corral' that can hold 10+ bicycles. Install U-shaped bike racks surrounded by protective bollards or planters.",
        "keywords": "bicycle corral, bike parking racks, row of bicycles, cargo bikes, protective bollards, street reclaiming, cyclist friendly, orderly bike parking",
        "negative_prompt": "cars parked in bike spots, broken bikes, messy pile of bikes"
    },

    # ------------------------------------------------------------------
    # Category 3: Re-purposing Sections (改變街道的部分幾何結構)
    # ------------------------------------------------------------------
    "路緣外推 (Curb Extension / Bulb-out)": {
        "en_name": "Tactical Curb Extension",
        "set_typology": "Re-purposing Sections",
        "description": "Physically widen the sidewalk at corners or mid-block using temporary materials. Use epoxy gravel, paint, or flexible posts to extend the pedestrian space into the road.",
        "keywords": "curb extension, bulb-out, widened pedestrian corner, flexible posts, bollards, epoxy gravel surface, beige pavement, tactical widening, pedestrian safety",
        "negative_prompt": "narrow sidewalk, cars turning fast, asphalt dominance"
    },
    
    "快閃廣場 (Pop-up Plaza)": {
        "en_name": "Pop-up Plaza",
        "set_typology": "Re-purposing Sections",
        "description": "Transform an underused slip lane or triangular intersection into a small pedestrian plaza. Fill the space with movable chairs, umbrellas, and potted trees.",
        "keywords": "pedestrian plaza, colorful movable chairs, bistro tables, sun umbrellas, large potted trees, epoxy gravel flooring, gathering space, vibrant public life",
        "negative_prompt": "cars driving through, empty asphalt, dark shadows, loneliness"
    },

    # ------------------------------------------------------------------
    # Category 4: Re-purposing Entire Streets (徹底改變街道功能)
    # ------------------------------------------------------------------
    "臨時自行車專用道 (Pop-up Bike Lane)": {
        "en_name": "Pop-up Bike Lane",
        "set_typology": "Re-purposing Entire Streets",
        "description": "Convert a vehicle lane into a protected bike lane. Use traffic cones, planters, or armadillos (separators) to create a safe corridor for cyclists.",
        "keywords": "pop-up bike lane, bright orange cones, planter protection, green bike path, cyclists riding, tactical bike infrastructure, wide cycling lane, separated from traffic",
        "negative_prompt": "motorcycles, cars in bike lane, dangerous traffic, faded markings"
    },
    
    "遊戲街道 (Play Street)": {
        "en_name": "Play Street",
        "set_typology": "Re-purposing Entire Streets",
        "description": "Close the street to cars temporarily to create a 'Play Street'. The road is filled with children playing, chalk drawings on the ground, and play equipment.",
        "keywords": "children playing on street, street chalk drawings, hopscotch, toys, road barriers closing street, happy kids, safe neighborhood, car-free zone, sunny day",
        "negative_prompt": "moving cars, danger, angry drivers, smog, dark colors"
    },
    
    "通學巷 (School Street)": {
        "en_name": "School Street",
        "set_typology": "Re-purposing Entire Streets",
        "description": "Create a safe zone outside a school. Use barriers to block cars. Fill the street with parents and students walking. Add colorful 'School Zone' paintings on the ground.",
        "keywords": "school street, parents and children walking, school zone road painting, safety barriers, no cars, morning sunlight, happy students, backpacks, safe route",
        "negative_prompt": "traffic jam, idling cars, dangerous crossing, grey asphalt"
    },
    
    "行人徒步區 (Open Street / Pedestrianization)": {
        "en_name": "Full Pedestrianization",
        "set_typology": "Re-purposing Entire Streets",
        "description": "Permanently or temporarily remove all cars. The entire street width is for people. Add market stalls, benches, and trees in the middle of the road.",
        "keywords": "pedestrian only street, market stalls, walking people, street musicians, open air, stone pavement, trees in middle of road, vibrant city life, no vehicles",
        "negative_prompt": "cars, buses, trucks, traffic lights, exhaust fumes"
    }
}

# ------------------------------------------------------------------
# 輔助函式：取得 Prompt
# ------------------------------------------------------------------
def get_set_design_prompt(option_key, user_custom_text=""):
    data = SET_DESIGN_TOOL_DICT.get(option_key)
    if not data:
        return None, None
        
    prompt = f"""
    [System]
    Act as a professional Urban Designer using the 'Street Experiments Tool' (SET) methodology.
    
    [Objective]
    Apply a "{data['set_typology']}" intervention to the provided street view image.
    
    [Measure Details]
    - **Measure Name**: {data['en_name']}
    - **Design Logic**: {data['description']}
    
    [Visual Elements for Generation]
    - **Key Elements**: {data['keywords']}
    
    [User Customization]
    The user specifically requested: "{user_custom_text}"
    (Integrate this seamlessly into the {data['en_name']} design.)
    
    [Output Requirement]
    Generate a high-fidelity, photorealistic image of the transformed street. 
    Ensure the perspective matches the original image.
    """
    return prompt, data['negative_prompt']

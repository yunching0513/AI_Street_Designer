from knowledge_base.knowledge_runtime import (
    build_design_spec,
    compile_generation_prompt,
    load_bundle,
    refine_design_spec,
)


def test_bundled_skill_data_is_available():
    bundle = load_bundle()

    assert len(bundle['rules']) == 98
    assert len(bundle['cards']) == 23
    assert 'tw-urban-road-spec-2026' in bundle['manuals']


def test_retrieval_is_contextual_and_taiwan_first():
    spec = build_design_spec(
        '在主要街道加入安全的保護型自行車道',
        'protected-bike-lane',
        {
            'street_context': 'main_street',
            'target_speed_kmh': 30,
            'priorities': ['cycling', 'safety'],
        },
    )

    assert 5 <= len(spec['evidence']) <= 12
    assert spec['evidence'][0]['manual_id'].startswith('tw-')
    assert any(
        item.get('element') in ('bicycle_lane', 'protected_cycle_track')
        for item in spec['evidence']
    )
    assert all(item['source_url'] for item in spec['evidence'])


def test_prompt_keeps_authority_and_concept_limitations_visible():
    spec = build_design_spec(
        '拓寬人行道並保留既有樹木',
        'widen-sidewalks',
        {
            'street_context': 'residential',
            'preserve': ['existing_trees'],
        },
    )
    prompt = compile_generation_prompt(spec)

    assert 'Taiwan requirements control' in prompt
    assert 'not a measured plan or compliance claim' in prompt
    assert '健康既有樹木' in prompt
    assert '[E1]' in prompt


def test_refinement_retrieves_again_and_preserves_design_frame():
    original = build_design_spec(
        '增加連續人行道',
        'widen-sidewalks',
        {
            'street_context': 'school',
            'target_speed_kmh': 30,
            'intervention_intensity': 'balanced',
        },
    )
    refined = refine_design_spec(original, 'Add more shade trees')

    assert refined['street_context'] == 'school'
    assert refined['target_speed_kmh'] == 30
    assert refined['intervention_intensity'] == 'balanced'
    assert refined['refinement_history'] == ['Add more shade trees']
    assert 5 <= len(refined['evidence']) <= 12

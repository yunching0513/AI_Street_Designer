# Street-design knowledge runtime — phase 1

This phase turns the `design-human-centered-streets` Skill into a repeatable
image-generation workflow instead of injecting one long Markdown file into
every prompt.

## The three priority integrations

1. **Contextual evidence retrieval**
   - Each request retrieves 5–12 structured rules and method cards.
   - Current Taiwan requirements take precedence.
   - International guidance is clearly labeled as comparative reference.
   - Every visible item includes its manual, section/page when available,
     authority label, and source link.

2. **Persistent `StreetDesignSpec`**
   - The initial generation and every co-pilot refinement share the same
     jurisdiction, context, target-speed intent, priorities, preserved
     elements, spatial order, constraints, evidence, and assumptions.
   - Refinements trigger retrieval again without discarding the confirmed
     design frame.
   - The session stores the current spec and audit in both memory and Redis.

3. **Edit-area mask and visual audit**
   - A user may paint the street-level area that is allowed to change.
   - OpenAI receives the alpha PNG through the Images Edit mask field.
   - Gemini receives the same aligned PNG as an additional range guide.
   - The generated concept is checked for preservation, requested change,
     continuity, accessibility, and visual realism.
   - The audit never claims dimensional accuracy, legal compliance, or
     constructability.

## Participatory image and prompt flow

The interface uses a confirm-before-generate flow:

1. Upload a street image and choose or describe a transformation.
2. Set street context, target-speed intent, intervention intensity, priorities,
   and items to preserve.
3. Optionally paint the editable road area.
4. Review the generated design plan, retrieved evidence, assumptions, and the
   exact prompt.
5. Confirm generation.
6. Compare before/after, inspect evidence and the visual audit, then refine with
   the co-pilot.

The server rebuilds the design spec from validated user preferences at
generation time. It does not trust rule text posted back by the browser.

## Runtime data

Run:

```bash
./scripts/sync_street_skill.py
```

This copies only structured, license-safe derived data into
`knowledge_base/street_skill/`. It does not copy source PDFs or figure images.
Set `STREET_SKILL_DIR` to use a different deployed bundle directory.

## API

- `POST /api/design-plan` returns a reviewable `design_spec` and the compiled
  image prompt.
- `POST /api/transform` accepts `design_preferences` JSON and an optional
  same-size alpha PNG in the `mask` field.
- `POST /api/chat` retains and updates the spec for image refinements.

## Recommended 3D path

Full 3D modeling is not the best default for phase 1: a single street photo
does not reliably establish width, grade, depth, or hidden geometry, and a full
model would imply more precision than the evidence supports.

The recommended sequence is:

1. **Next: parametric 2.5D cross-section**
   - Convert `StreetDesignSpec.spatial_order` and user-confirmed widths into an
     editable SVG cross-section.
   - Let users drag widths and immediately see the remaining right-of-way.
   - Use the confirmed cross-section as an additional visual condition for the
     street-image model.
2. **Then: lightweight 3D**
   - Generate a simple Three.js street massing model from the confirmed
     cross-section and segment length.
   - Keep buildings as protected context planes or simple massing.
   - Export consistent viewpoints or depth/normal guides for image generation.
3. **Only with measured data: engineering-grade model**
   - Use survey, GIS, point cloud, or BIM/CAD inputs.
   - Keep this separate from the concept-image workflow and require
     professional verification.

This makes 2.5D the useful bridge between participation and generated imagery,
while reserving full 3D for projects with enough geometric evidence.

# CCELAM ArchiCAD IFC Translator Preset — "CCELAM QS Export"

Export standard for design teams issuing ArchiCAD models into the CCELAM
drawings-to-closure pipeline. Issue this specification with the Employer's
Information Requirements (ISO 19650-2 exchange information requirement).
Models are accepted into the pipeline only after passing the G1 intake
gate (`g1_intake_gate.py`); this preset is what makes them pass.

Note on mechanics: ArchiCAD IFC translators are created inside ArchiCAD
(File → Interoperability → IFC → IFC Translators...). Build the translator
once from this specification, then export it (the Translators dialog
supports export/import of translator files) and circulate that file with
this document so every design office exports identically.

---

## 1. Translator settings

| Setting | Required value | Why |
|---|---|---|
| Name | `CCELAM QS Export` | Identifiable in transmittals |
| IFC schema | **IFC4** | Practice standard; G1.1 warns on IFC2X3 |
| Model View Definition | **IFC4 Reference View** (Design Transfer View acceptable where the recipient must edit) | QTO needs data fidelity, not editability |
| Geometry conversion | BREP where exact quantity geometry matters; otherwise extruded | Stable NetVolume/NetArea derivation |
| **Derive BIM data from model geometry → Base Quantities: ON** | **Mandatory** | This is the single setting that drives G1.5. Without it, Qto_* sets are absent and the rules engine falls back to geometry derivation |
| Element classification export | ON, with the project classification system mapped (see §3) | Drives SMM7/NRM2 mapping confidence (G1.6) |
| Properties to export | All IFC standard Psets + the CCELAM custom property mapping (§2) | Rules-engine conditions read Psets |
| Spatial structure | Site → Building → Storey complete; every element assigned to a storey | Location columns in the BOQ and defects schedule |
| Units | Project in **millimetres** or **metres**, declared | G1.2 |
| Owner history / GlobalId | Never strip or regenerate GUIDs between issues | The golden thread (G1.3): GlobalIds must be STABLE across revisions, or certified lines lose their anchors |

## 2. Property mapping (ArchiCAD → IFC Pset)

Configure under the translator's Property Mapping. The CCELAM rules engine
(`measurement_rules.yaml`) conditions on these:

| ArchiCAD source | Target Pset.Property | Used for |
|---|---|---|
| Building Material / Composite name | `Pset_*Common` material reference + IfcMaterial | Material substring rules (e.g. concrete grade `c25/c30/c35` keys — exact tokens, see precision note) |
| Structural function (load-bearing) | `Pset_WallCommon.LoadBearing` etc. | Structure vs partition split |
| Position (external/internal) | `Pset_*Common.IsExternal` | External works / facade sections |
| Fire rating | `Pset_*Common.FireRating` | Specification-sensitive rates |
| Renovation status | `Pset_*Common` / custom `CCELAM_Status` | New work vs existing (excluded from measure) |
| Custom: provisional flag | `CCELAM_QS.Provisional` (Boolean) | Marks provisional items in the bill |

Precision note: concrete grade tokens are `c25`, `c30`, `c35` (lower-case,
prefixed) — never bare `25/30/35`, which collides with dimension strings
such as `250 mm` (the substring defect corrected in the Quantify build).

## 3. Classification

Map the project classification (Uniclass 2015 or the project system) in
the translator so every measurable element exports an
IfcClassificationReference. The mapper uses classification first,
class+Pset second; classified models produce materially fewer review
flags.

## 4. Issue discipline

1. Export with `CCELAM QS Export` only — no ad-hoc translators.
2. File naming per the project information standard; one model per
   building/zone as agreed.
3. Run `g1_intake_gate.py <file>.ifc --report <file>_G1.json` (the QS
   runs it on receipt; design teams are encouraged to pre-run it).
4. PASS → quantification proceeds. WARN → proceeds with flags recorded
   in the BOQ assumptions. FAIL → model returned with the G1 report;
   no measurement is performed on a failed model.
5. Re-issues: GlobalIds stable; the transmittal states what changed.

## 5. Revit equivalence

Revit models follow the same acceptance rule (G1 on the exported IFC, or
native capture via the C# add-in / Dynamo / pyRevit paths producing
`model_quantities.json`). Either way the gate principle holds: nothing is
measured from a model that has not passed intake.

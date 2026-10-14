# Trial: the small satellite through the whole tool (October 2026)

A trial of the released flow on the largest bundled example (14 units, 24 interfaces, 54 wires, 24 harnesses), with the command line only. It is **example data**: the engineering values are the demo values of `harness templates`, the part ratings and interface voltages were typed in as test inputs, and the segment lengths are made up. It shows how the tool behaves, not that any harness is right. A real design of the owner's was not available.

## What was run
`harness new` (small-satellite), `harness generate`, `harness config --apply-profile ecss-q-st-30-11c` and `ecss-e-st-20-07c`, the demo values merged in, ratings and 28 V on the power interfaces, `harness import-lengths`, `harness generate` again, `harness drc`, `harness verify`, `harness export`, `harness verify --outputs`, `harness review` and `harness release` of one harness, and a look at the drawing.

## Results
- Generation: 24 harnesses, 54 wires, 0 errors; gauges stayed *pending* until lengths were imported, then were decided (AWG 22 on the power pair). 280 output files; both verifiers clean.
- Power and return pins land on pins 1 and 3 (pin 2 unassigned) once the profile is on.
- The new rules stayed quiet with the generous test ratings and reacted when the numbers were tightened (110 degC ambient: 11 `temperature-margin` errors; 2.6 A: 24 `current-over-contact` and 14 `current-over-wire` errors). `bundle-current` did not fire at 2.6 A because a two-wire bundle has K = 0.9 and AWG 22 allows 3.0 A x 0.9 = 2.7 A: correct.
- The report named what it could not check: bundle separation, bond resistance, multipactor, partial-load factor L, wire surface temperature.

## Defects found
1. **Fixed here.** With a grounding concept of floating ends, the shield rules reported every plain twisted pair as an unconnected shield (31 false warnings, of which 19 were twisted pairs); a twisted pair has no shield. The four shield rules now skip it (regression test in `tests/test_standard_rules.py`).
2. **Fixed here.** The explanation of `unchecked-config` told people to "fill in the placeholder" even for notes that need an analysis outside the tool.

## Observations, not changed
- **Release with placeholders.** `harness release` succeeded while every configuration file was still a placeholder and 13 parts were unapproved (warnings do not block). This is the known gap asked about earlier (should the release gate refuse while config files are placeholders?): still the owner's decision.
- **Two bundle factors.** The demo `bundle_derating` and the profile's `bundle_factor_by_count` can both be set. The table decides sizing and `bundle-current`; the old rule `current-over-wire` still uses the single factor, so it is the stricter one. Remove `bundle_derating` when the table is meant to rule.
- **Import by header.** A length file without `harness,segment,length` headings gives "Harness 'W024-L1' does not exist", which points at the wrong cause. The templates have the right headings.
- **Drawing.** The power harness drawing reads well; its "Shields" paragraph lists a twisted pair as a shield group (the data model's name for the group).

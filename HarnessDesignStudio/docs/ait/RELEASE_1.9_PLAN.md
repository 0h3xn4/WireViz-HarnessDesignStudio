# Release 1.9 plan: make the Systems engineer role work and give every role an output

Status: plan, written 2026-10-27 on top of 1.8.1 (published 2026-10-28). Carried out as 1.9.0 (published 2026-10-28; D-179 and D-180). Source:
`docs/AUDIT_1.8.0.md` section 3.2 and section 4 "1.9". Decisions from D-178.

## Aim

A person who picks the **Systems engineer** role on a blank project can add a device with its first
connector, connect two connectors, get a sensible pin pairing, fix what is marked and hand over a
connection list (ICD style), without ever seeing an interface, a wire list or the command line.

## What stays fixed

- Every new model field is optional and sparse. A project that does not use a new feature writes
  byte-identical files, and `python -m tools.output_hashes --check docs/ui/OUTPUT_HASHES_1.2.0.json`
  prints `identical`.
- No new DRC rule unless a workstream says so and the rule count in `docs/RULES.md` is regenerated.
- The pairing of pins is always confirmed by the person (the owner's rule: the tool proposes, a
  person accepts).
- Nothing here is a statement of compliance. No tag, no merge by the agent.

## Workstreams (each its own branch and pull request, independent files as far as possible)

### W1 The Systems engineer path in the screens (D1, D2, D5, D6, D7, D11, D12, D13, D15, D26)
- First connector in **Add device** (name, family, pin count); "Add a connector" inside **Connect
  connectors** when a device has none.
- **Pair by pin number** and **Paste a pairing** (two columns, TSV) buttons in the link window; both
  show the proposal and wait for the person to accept.
- **Next step** page: after a harness exists it must not stay on "Fix what is marked" forever. It
  preselects the first failed rule, says in one sentence what to do, offers Waive/Approve where the
  rule allows it, and a warning alone never holds the page.
- Keep the person on the Next step page or the diagram after each step.
- Systems rail: hide the engineering menu entries (they stay in the command palette, Ctrl+K).
- One wording pass keyed on "the project has links or hand-made harnesses": tour step 3, empty states
  of Harness/Lists/tree ("Press Generate"), Generate as primary button with no device, "Not
  generated" chips for hand-made harnesses, release blockers that quote command-line commands.
- Problem counts agree: "14 of 24" where a filter is active; chip "Check passed" is never shown next
  to a failed rule.
- Pin **role** column (visible and editable) in the Devices tab.

### W2 A connection list as output (F-02, F-08)
- `connections.csv` and `connections.xlsx` (ICD style: from device/connector/pin, to
  device/connector/pin, signal, role, notes) written by `generate`/`export` when the project has
  links; absent otherwise (so old projects stay byte-identical).
- Links in the block diagram and in `traceability.csv`.
- `export` and the Outputs screen work for a project with links and no harness (no "run generate
  first").
- Independent verifier (`core/outputs/verify.py`) checks the new files; manifest and checksums list
  them; docs (`docs/OUTPUTS.md` or the equivalent) and CHANGELOG.

### W3 Model and core (B-03 follow-ups, A-10, plan_create_harness)
- Optional per-pin `direction` (in / out / bidirectional / unspecified) on `Pin`, sparse; used by the
  link checks in place of name guessing when set; editable in the Devices tab data model only (the
  column is added by W1 later, W3 provides `core/` only plus the CLI import/export column).
- Counterpart word table (TX/RX, MOSI/MISO, ...) moved from code to a project config key with the
  current table as default; link checks and pairing proposal read it.
- `plan_create_harness` in one pass (no repeated scans of all links per connector).
- Schema/JSON-Schema export, `docs/CONFIG.md`, `docs/FILE_FORMAT.md` updated, tests incl. property
  tests for the pairing.

### Later in 1.9 (not started in this round)
Change-control identity switch; requirement IDs in outputs; `.gitattributes` and `merge-fix`; README
cut to 60 lines plus a 10-minute tour; incremental integrity and background autosave; export
style-object reuse and per-harness incremental export; single bundle rule; coax/twisted-pair shield
ends.

## Owner questions this plan does not need answered, but that decide later work
See `docs/AUDIT_1.8.0.md` section 8 (kladow, Sam's tool, the workshop export failure, deliverable
per role, standards, variants, licence and signing, who tests, role defaults). The two role defaults
stay as built in 1.8.0 until the owner answers.

*Answered on 2026-10-28 (D-181): kladow, Sam's tool and the export failure are discarded; the deliverable per role follows the recommendation; the test with people is later. The role defaults stay.*

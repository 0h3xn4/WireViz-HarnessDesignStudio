# Session schedule and consent sheet

For action A-12. One row per participant. Targets and method are in `README.md`; task cards in `tasks.md`. Nobody who built or reviewed the tool takes part, and nobody uses real program data.

| # | Persona (Dana, Sam, Elena, Rui) | Participant code | Date and time | Facilitator | Build (version, model hash) | Consent to record (screen / audio / none) | Material prepared (`usability_setup`) | `results.csv` rows entered | `sus.csv` row entered |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | | | | | | | | | |
| 2 | | | | | | | | | |
| 3 | | | | | | | | | |
| 4 | | | | | | | | | |
| 5 | | | | | | | | | |

Use codes, not names, in this table and in the results; keep the list that links codes to people separately and outside the repository. Three to five participants per persona is the target; the owner decides how many personas are covered.

## Consent text (read aloud before the session)
"We are testing the tool, not you. You may stop at any time. With your agreement we record the screen (and audio) so that we can check what happened; the recording is used only for this evaluation, is kept only as long as needed, and shows no program data. Do you agree?"

## After the last session
Run `python -m tools.usability_summary results.csv sus.csv`, triage the tasks below target as priority bugs (README), and enter the outcome in `compliance/docs/SValP_SVS.md` (VAL-07) with the number of participants, the SUS and the success rate. The numbers point at problems; with so few people they do not prove a percentage.

# Usability test kit

You run the sessions; this kit prepares them and turns the results into a triage list. Targets (UX.md section 9): at least 90% task success, SUS of at least 80, first diagram and plans in under 15 minutes without the manual.

## Before a session
1. Install the build under test (the packages exist for Ubuntu and Windows; write the version and the system on the result sheet). Run `python -m tools.usability_setup ~/usability` to create the task material: an empty project for T1, `icd.csv` with two bad rows (T4; import it into `t6-t7-generated`), a project with one corrupt file (T8) and a project with generated harnesses, none of them released yet (T6, T7).
2. Write down which role each participant used (next to the build in `session_schedule.md`). The first start of the version after 1.7.0 asks *Who are you working as?* (Systems engineer or Electrical / AIT engineer); in version 1.7.0 itself a first run opened the **Simple** workspace (the Next step page, fewer things on screen), which is now the Systems engineer role, and a settings file that already holds values has the **Electrical / AIT engineer** role. To start a participant in the other role use **View > Role**. Nobody has run the tasks in both roles yet, and the roles have not been measured with test users, so no result here says that the Systems engineer role is easier.
3. 3 to 5 participants per persona (the personas of [`../UX.md`](../UX.md#2-personas): Dana, systems engineer; Sam, software engineer; Elena, harness (EE) engineer; Rui, reviewer or AIT technician). Nobody who built or reviewed the tool.
4. Screen and audio recording only with consent. Participants must not use real program data.

## During a session (about 60 minutes)
1. Say: "We test the tool, not you. Think aloud. I will not help; if you are stuck, say so and we move on."
2. Give one task card at a time (`tasks.md`). Start the timer when they start reading; stop at success or after the time limit.
3. Record per task: success (1 or 0), seconds, wrong clicks, and every remark such as "I don't know what this means".
4. After the last task hand over the SUS questionnaire (`sus.md`).

## After the sessions
1. Fill one row per participant and task in `results.csv` (copy `results-template.csv`) and one row per participant in `sus.csv`.
2. Run `python -m tools.usability_summary results.csv sus.csv`. It prints success, time, wrong clicks and SUS, and lists every task below target as a priority bug.
3. Triage: each priority bug gets a ticket with the task, what the participant did, and what they said. Fix, then retest the failing task with two new participants.

The numbers from this tool are only as good as the sessions: with 3 to 5 people they point at problems, they do not prove a percentage.

Also in this folder: `session_schedule.md` (schedule and consent sheet) and `screen_reader_pass.md` (the manual screen-reader part of the accessibility audit).

Next: [UX specification, section 9](../UX.md#9-usability-test-plan-you-run-it-findings-become-priority-bugs), [screen-reader pass](screen_reader_pass.md)

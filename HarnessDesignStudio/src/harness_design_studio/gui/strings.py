"""All user-visible UI strings live here so translation is possible later."""

APP_TITLE = "Harness Design Studio"
EMPTY_STATE = (
    "No project open. Create a new project, start from an example or open an existing one to begin."
)
EMPTY_CANVAS = "Your diagram is empty.\nAdd your first unit from the palette on the left, press Ctrl+K to find a command, or bring in a table with File > Import."
CANVAS = "Block diagram canvas"
CANVAS_HELP = "Tab and Shift+Tab move between units and links, Enter shows the item in the harness plans, Space selects it, Ctrl+A selects everything, Shift+arrow keys move the selected units, Ctrl+F finds, Escape clears the selection. The Interface table tab lists every interface and is the screen-reader friendly alternative."
MINIMAP = "Minimap: click to move the view"

GLOSSARY: list[tuple[str, str]] = [
    (
        "Harness",
        "A bundle of wires with connectors at the ends that carries signals between units. Every harness gets its own drawing and wire list.",
    ),
    (
        "Interface",
        "A logical connection between two units, such as RS-422 between the computer and a wheel. The tool turns interfaces into wires.",
    ),
    (
        "Nominal / redundant",
        "The main chain and its backup chain. They must never share a connector or harness, so one failure cannot take out both.",
    ),
    ("Pinout", "A table of which signal is on which pin of a connector."),
    (
        "Twisted pair",
        "Two wires twisted together to reduce noise. Used for most data and power pairs.",
    ),
    (
        "Derating",
        "Using a wire or contact below its maximum current for safety. The factors come from your project standard.",
    ),
    ("Spare pin", "A pin deliberately left unused so later changes need no new connector."),
    ("Splice", "A joint where several wires are connected together inside a harness."),
    (
        "Cross-strap",
        "A connection between the nominal chain and the redundant chain. Allowed only with a written justification.",
    ),
    (
        "Waiver",
        "A recorded decision to accept a warning. It needs a justification and appears in reports.",
    ),
    (
        "Zone",
        "A place on the spacecraft (a panel or deck). Units in different zones usually need different harnesses.",
    ),
]

TOUR_STEPS: list[tuple[str, str]] = [
    (
        "add",
        "Start here: press Add in the project panel and pick Unit. Each unit is a box in your system, like a computer or a wheel.",
    ),
    (
        "canvas",
        "This is your block diagram. Drag units to move them. The lane a unit sits in is its zone.",
    ),
    (
        "types",
        "To connect two units, open the arrow next to Connect and pick an interface type, then click the two units. Only valid choices light up.",
    ),
    (
        "problems",
        "Problems and a to-do list appear in the Problems tab here and update as you work. Click any line to jump to the item.",
    ),
    (
        "generate",
        "Generate harnesses builds the harness plans from this diagram. You see a preview first, and one Undo takes it back.",
    ),
]

PROPERTIES = "Properties"
NOTHING_SELECTED = (
    "Select a unit or an interface to see its details. The rest of the diagram fades, so you can "
    "follow its links."
)
UNIT = "Unit"
INTERFACE = "Interface"
FIELD_ID = "ID"
FIELD_NAME = "Name"
FIELD_CHAIN = "Chain (nominal / redundant)"
CHAIN_TIP = "Nominal is the main chain, redundant is the backup"
FIELD_ZONE_AUTO = "Zone (set by where you place the unit)"
FIELD_SUBSYSTEM = "Subsystem"
FIELD_MAX_A = "Max current (A)"
FIELD_VOLTAGE = "Voltage (V)"
FIELD_REQUIREMENT = "Requirement ID (for traceability)"
CONNECTORS_PHYSICAL = "Connectors (physical)"
GUIDED_HIDES_PHYSICAL = "Connectors, pins and parts are chosen for you in Guided mode. Switch to Expert mode to see and change them."
REDUNDANT_COPY = "Create redundant copy"
AUTO = "Auto"
AUTO_TIP = "Chosen for you; confirm to accept"
CONFIRM = "Confirm"
CONFIRM_AUTO = "Confirm auto-filled connectors"
LIBRARY_PART = "Library part"
ANY_TYPE = "any interface type"
CARRIES = "Carries: {}"
PARTS_UNVERIFIED = "Part numbers are unverified example data."
PART_UNVERIFIED = "example data"
APPROVAL = {"approved": "approved", "pending": "not approved yet", "not_approved": "not approved"}
ENDS = "Ends"
FROM = "From"
TO = "To"
SIGNALS = "Signals: {}"
NUMBER_HELP = "Enter a number in the unit shown, for example 2.5."
INVALID_VALUE = "This value is not valid."
PROBLEMS = "Problems"
INTERFACE_TABLE = "Interface table"
NO_PROBLEMS = "No problems. Nice work."
WAIVED = "Waived"
SEV_WARNING = "⚠ Warning:"
SEV_ERROR = "✕ Error:"
SEV_INFO = "ⓘ Info:"
SHOW = "Show"
REQUIREMENT_LABEL = "Requirement: {}"
WAIVE = "Waive…"
FILTER_PLACEHOLDER = "Filter by ID, unit or type"
NEW_INTERFACE = "＋ Interface…"
NO_PLANS_TITLE = "No harness plans yet."

CANCEL = "Cancel"
CLOSE = "Close"
ADD = "Add"
WAIVE_TITLE = "Waive this warning?"
WAIVE_PROMPT = "Justification (required, shown in reports)"
WAIVE_OK = "Waive with justification"
WAIVE_TOO_SHORT = "Please explain why this is acceptable (at least 10 characters)."
NEW_INTERFACE_TITLE = "New interface"
NEW_INTERFACE_NOTE = "Connectors are chosen for you and marked Auto until you confirm them. Units that cannot take this type are shown disabled with the reason."
FIELD_TYPE = "Interface type"
IMPORT_TITLE = "Import interfaces"
IMPORT_STEPS = "Step 1: open a .csv or .xlsx file, or paste CSV text. Step 2: check the column matching. Step 3: read the preview. Nothing changes until you confirm."
OPEN_FILE = "Open file…"
NO_FILE = "No file chosen"
CSV_CONTENT = "CSV content"
CSV_PLACEHOLDER = "Interface,Type,From unit,To unit,Redundancy\nIF-010,RS-422,OBC,RW1,nominal"
IMPORT_PREVIEW = "Import preview"
NOT_MAPPED = "(not used)"
IMPORT_SUMMARY = "{} of {} rows can be imported; {} have errors and will be skipped."
IMPORT_EMPTY = "Nothing to import yet."
IMPORT_SHEET = "{} (sheet: {})"
IMPORT_COLUMNS = ("Row", "Interface", "Type", "From", "To", "Status")
IMPORT_N = "Import {} row{} (one undo step)"
GLOSSARY_TITLE = "Glossary"
ISSUES_TITLE = "This project has problems"
ISSUES_RECOVERED = "Some parts could not be loaded. Everything else was loaded. The original folder is protected: it cannot be overwritten."
SAVE_SALVAGED = "Save salvaged copy…"
COMMANDS_TITLE = "Commands"
COMMANDS_PLACEHOLDER = "Type a command or an ID…"
TOUR_SKIP = "Skip tour"
TOUR_BACK = "Back"
TOUR_NEXT = "Next"
TOUR_FINISH = "Finish"
TOUR_STEP = "Step {} of {}"
UNDO = "Undo"
REDO = "Redo"
DELETE = "Delete"
GUIDED = "Guided"
EXPERT = "Expert"
GUIDED_TIP = "Guided mode: logical layer only. Physical details are filled in for you and marked until you confirm them."
EXPERT_TIP = "Expert mode: all physical details (connectors, pins, parts)."
TOOL_SELECT = "Select"
TOOL_CONNECT = "Connect"
TOOL_SELECT_TIP = "Select and move (Esc)"
TOOL_CONNECT_TIP = "Connect two units (C). The arrow next to it lists the interface types: pick one, then click the first and the second unit."
HINT = "Hint"
ZOOM_IN = "Zoom in"
ZOOM_OUT = "Zoom out"
FIT = "Fit"
NOMINAL = "nominal"
REDUNDANT = "redundant"
AUTO_LEGEND = "auto-filled, not reviewed"
TOOLBAR = "Main toolbar"
SEARCH_BUTTON = "Search  Ctrl+K"
FILTER_LABEL = "Show"
FILTER_ALL = "All interfaces"
FILTER_CLASS = "By signal class"
FILTER_CONNECTOR = "By connector"
FILTER_BUNDLE = "By bundle (harness)"
FILTER_VALUE = "Filter value"
FILTER_TIP = (
    "Show one signal class, connector or bundle and fade the rest "
    "(the diagram and the project are not changed)"
)
GENERATE = "Generate harnesses"
GENERATE_TIP = "Build harness plans from the diagram (you see a preview first; Undo reverts it)"
GEN_PREVIEW_TITLE = "Generate harnesses"
GEN_APPLY = "Apply"
GEN_RUNNING = "Generating harnesses…"
GEN_CANCELLED = "Generation cancelled. Nothing was changed."
GEN_UP_TO_DATE = "Harnesses are already up to date. Nothing to change."
GEN_WITH_ERRORS = "Some harnesses could not be generated ({0} problem(s)). Fix the connectors or interfaces named in the list, then generate again."
GEN_PLACEHOLDERS = "Some engineering values are not filled in yet, so wire gauges stay blank and related checks say 'not checked'. Help > User guide, section 11 (What an engineer must fill in), shows what to fill in."
GEN_PREVIEW_HEAD = "Nothing changes until you press Apply, and Undo reverses it."
RELEASE_CONFIRM = "Release"
PLACEHOLDER_REASON = "Reason for releasing on placeholder values (kept in the change log)"
UNAPPROVED_PARTS_REASON = (
    "Reason for releasing with parts that are not approved (kept in the change log)"
)
UNAPPROVED_PARTS_WARNING = (
    "These parts are not approved, or are example data: {0}. A release needs a written reason."
)
PLACEHOLDER_WARNING = (
    "These configuration files are still placeholders: {0}. A release needs a written reason."
)
REVIEW_CONFIRM = "Submit for review"
NEW_REV_CONFIRM = "Start new revision"
GEN_STATUS = {
    "none": "Not generated yet.",
    "current": "Up to date with the diagram.",
    "stale": "Out of date: the diagram changed since the last generation. Press Generate harnesses.",
}
PLANS_VERIFY_OK = "Independent check: {0}"
PLANS_VERIFY_BAD = "Independent check found problems: {0}"
WIRE_COLUMNS = ["Wire", "Signal", "From", "To", "AWG", "Length (m)", "Colour", "Locked"]
EXPLAIN = "Why is it like this?"
ALL_SAVED = "All changes saved"
UNSAVED = "Unsaved changes (autosaved to the recovery journal)"


def units_text(n: int) -> str:
    return f"{n} unit" if n == 1 else f"{n} units"


def interfaces_text(n: int) -> str:
    return f"{n} interface" if n == 1 else f"{n} interfaces"


def problems_text(n: int) -> str:
    return f"{n} problem" if n == 1 else f"{n} problems"


STATUS_COUNTS = "{} · {} · model {}"
SELECTED = "Selected: {}"
NOTHING_SEL = "Nothing selected"
A_NEW = "New project…"
A_NEW_EXAMPLE = "New project from an example…"
EXAMPLE_TITLE = "Start from an example"
EXAMPLE_TEXT = "Choose what to start from:"
A_OPEN = "Open project…"
A_SAVE = "Save"
A_SAVE_AS = "Save as…"
A_IMPORT = "Import interfaces…"
A_QUIT = "Quit"
A_ADD_ZONE = "Add zone…"
A_DARK = "Dark theme"
A_LABELS = "Show all link labels"
A_SCALE = "Interface size"
A_COMMANDS = "Search and commands"
A_TOUR = "Replay the tour"
A_GLOSSARY = "Glossary"
A_SAMPLE = "Open the sample project"
A_ABOUT = "About"
A_ISSUES = "Show project problems"
M_FILE = "&File"
M_EDIT = "&Edit"
M_VIEW = "&View"
M_HELP = "&Help"
M_ADD_UNIT = "Add unit"
M_CONNECT_WITH = "Connect with"
ADD_UNIT_PREFIX = "Add unit:"
CONNECT_PREFIX = "Connect with"
GO_TO_UNIT = "Go to unit"
GO_TO_INTERFACE = "Go to interface"
ZONE_NAME = "Zone name"
DELETE_TITLE = "Delete {}?"
DELETE_BODY = "<p>This will also remove:</p><ul><li>{n} interface{s}{ifs}</li><li>{c} connector(s) of the unit</li></ul><p>You can undo this with Ctrl+Z.</p>"
BANNER_READ_ONLY = "Read-only: this project was saved by a newer version of the tool, or is open in another window. You cannot change it here."
BANNER_RECOVERED = "Parts of this project could not be loaded. Everything else was loaded. The original folder is protected."
BANNER_SAMPLE = "This is the sample project (example data). Save a copy to keep your changes."
SAVE_COPY = "Save a copy…"
SHOW_DETAILS = "Show details"
UNSAVED_TITLE = "Unsaved changes"
UNSAVED_BODY = "The project has changes that are not saved to its files."
SAVE = "Save"
DISCARD = "Discard changes"
NEW_FOLDER = "Choose an empty folder for the new project"
NEW_NAME_TITLE = "New project"
NEW_NAME = "Project name"
OPEN_FOLDER = "Open a project folder"
SAVE_AS_FOLDER = "Choose an empty folder for the copy"
LOCKED_TITLE = "Project already open"
LOCKED_BODY = "This project is already open in another window or session. Close it there first, or open this copy read-only."
OPEN_READ_ONLY = "Open read-only"
RESTORE_TITLE = "Unsaved changes found"
RESTORE_BODY = "The last session ended before its changes were saved. Restore them?"
RESTORE = "Restore"
DISCARD_CHANGES = "Discard them"
PROJECT_HAS_ERRORS = "The project has consistency errors. See Help ▸ Show project problems."
RESTORE_FAILED = "The unsaved changes could not be restored. They are still in the recovery folder."
SAVED = "Saved."
CHANGED_TITLE = "Project changed on disk"
CHANGED_BODY = "The project files changed outside this window (for example after a Git pull). Reload to see the new version."
RELOAD = "Reload"
KEEP_MINE = "Keep my version"
KEEP_MINE_NOTE = "Keeping your version. Saving will be refused until you reload or save a copy, so nobody's changes are overwritten."
ABOUT_TEXT = "Harness Design Studio {}\nOffline spacecraft harness design tool. No data ever leaves this computer."
MORE_PROBLEMS = "…and {} more. Resolve the ones above first."

DRC_CHECKING = "Design rules: checking…"
DRC_DONE = "Design rules: {total} rules, {passed} passed, {failed} failed, {unchecked} not checked."
DRC_ALL_PASSED = "Design rules: all {total} rules passed."
DRC_STALE = "Design rules: out of date. Change the design or press Check again."
DRC_FAILED = "Design rule check failed: {}"
DRC_FAILED_WHY = "The design rules could not be checked, so the design is not confirmed clean. Change something to try again."
NOTHING_TO_SHOW = "This item has no place on the diagram (it is a setting or a part)."

EXPORT = "Export outputs"
EXPORT_TIP = "Write drawings, wire lists, BOM, tests, labels and exports to the project's outputs folder; they are checked independently first"
EXPORT_SAVE_FIRST = "Save the project to a folder first; outputs are written next to it."
EXPORT_NO_HARNESSES = "There are no harnesses yet. Generate harnesses first."
EXPORT_READ_ONLY = (
    "This project is read-only, so nothing was exported. Save a copy to a new folder first."
)
EXPORT_DAMAGED = "Parts of this project could not be loaded, so nothing was exported. See Help > Show project problems, or save a copy to a new folder."
EXPORT_RUNNING = "Exporting outputs…"
EXPORT_CANCELLED = "Export cancelled. Nothing was written."
EXPORT_DONE = "{0} files written to the outputs folder (design {1})."
EXPORT_FAILED = (
    "The outputs failed their independent check, so nothing was written ({0} problem(s))."
)
OUT_STATUS = {
    "none": "Outputs: not exported yet.",
    "current": "Outputs: up to date with the design.",
    "stale": "Outputs: out of date, the design changed after the last export.",
    "modified": "Outputs: files were changed after export.",
    "unreadable": "Outputs: the manifest cannot be read; export again.",
    "unsaved": "Outputs: save the project to export.",
}
OK = "OK"

RELEASE = "Release…"
RELEASE_TIP = "Release the selected harness: records a baseline and the change log, and locks it"
NEW_REV_TIP = "Unlock a released harness by starting its next revision (the released one is kept)"
CHANGES = "Changes…"
CHANGES_TIP = "Show what changed since a baseline"
HISTORY = "Change log…"
HISTORY_TIP = "Who changed what, when and why"
RELEASE_TITLE = "Release {0}"
REVIEW_TITLE = "Submit {0} for review"
NEW_REV_TITLE = "New revision of {0}"
YOUR_NAME = "Your name"
CHECKED_BY = "Checked by (optional)"
COMMENT = "Comment (what changed or why)"
BLOCKED = "Blocked until these are fixed:"
READY_TO_RELEASE = "Nothing blocks this release."
RELEASE_DONE = "{0} released. Export the outputs again so the drawings show the released status."
CHANGES_TITLE = "Changes in {0}"
COMPARE_WITH = "Compare the working design with"
NO_BASELINE = "{0} has no baseline yet; it is created when the harness is released."
NO_DIFF = "No differences."
MARK_DIAGRAM = "Mark on diagram"
CLEAR_MARKS = "Clear marks"
HISTORY_TITLE = "Change log of {0}"
NO_HISTORY = "Nothing has been recorded yet."

CANVAS_NAME = "Block diagram: {0}, {1}"
CANVAS_SELECTED = "Selected: {0} {1}."
CANVAS_NONE = "Nothing selected."
PANELS_HIDDEN = "The window is narrow, so the palette and properties are hidden. Widen the window or use the View menu to show them."
PROPERTIES_HIDDEN = (
    "Properties are hidden because the window is narrow. Widen the window or use the View menu."
)
A_GUIDE = "User guide"
GUIDE_MISSING = (
    "The user guide is not installed with this build. It is in docs/guide/USER_GUIDE.md."
)
PREVIEW_SHEET = "Drawing sheet preview"
PREVIEW_PREV = "Previous sheet"
PREVIEW_NEXT = "Next sheet"
PREVIEW_PAGE = "Sheet {0} of {1} (preview: what the export will draw)"
PREVIEW_NONE = "Select a harness to see its drawing."
TAB_WHY = "Why"
A_ARRANGE = "Arrange diagram"
ARRANGE_DONE = "Diagram arranged: units stay in their lanes, ordered to shorten links. Undo restores the old positions."
ARRANGE_NOTHING = "The diagram is already arranged."

TOAST_CLOSE = "Close this message"
UNDO_STALE = "That change is no longer the latest one. Use Edit > Undo to step back."
FILE_ERROR = (
    "Could not save{where}: {reason}. Nothing was lost; choose another folder or free some space."
)
SAVE_BAD_TEXT = "Nothing was saved: the project contains text that cannot be written to a file (for example an unpaired special character). Remove or retype it, then save again."
A_MINIMAP = "Show overview map"
WHY_READ_ONLY = "This project is read-only."
WHY_NO_SELECTION = "Select something in the diagram first."
WHY_SELECT_UNIT = "Select a unit first."
WHY_IS_REDUNDANT = "This unit is already a redundant copy."
WHY_HAS_REDUNDANT = "This unit already has a redundant copy: {0}."
REDUNDANT_TIP = "Make a redundant copy of the selected unit"
DELETE_TIP = "Delete the selected item (shows what it affects first)"
GEN_NO_INTERFACES = (
    "There is nothing to generate yet. Add units and connect them with interfaces first."
)
DELETE_HARNESS = "Delete harness"
DELETE_HARNESS_TIP = "Delete the selected harness (not possible once it is released). A generated one comes back the next time you generate."
DELETE_HARNESS_TITLE = "Delete {0}"
DELETE_HARNESS_BODY = "<b>{0}</b> and its {1} wire(s) will be deleted. You can undo this."
HARNESS_DELETED = "{0} deleted."
GROUPED_PROBLEMS = "{0}: {1} problems of the same kind"

A_WIRE_COLOURS = "Wire colours..."
WIRE_COLOURS_TITLE = "Wire colours"
WIRE_COLOURS_HELP = (
    "Pick the colour of the wire for each signal. The wires take the colours the next time you "
    "generate the harnesses, and the harness drawings draw them (with the colour code as text). "
    "A signal without a colour is drawn grey. The tool defines no colours of its own."
)
WIRE_COLOUR_NONE = "no colour"
WIRE_COLOURS_TABLE = "Wire colour for each signal"
WIRE_COLOURS_SIGNAL = "Signal"
WIRE_COLOURS_COLUMN = "Colour"
WIRE_COLOURS_NO_SIGNALS = "The project has no interface types with signals yet."
WIRE_COLOURS_SET = "Wire colours saved. Generate the harnesses to apply them."

CONNECTOR_AT_END = "Connector at the {} end, unit {}"
COMMANDS_LIST = "Matching commands"
LEGEND_NAME = "Key to the pictures in the diagram"
LEGEND_GENDER = "solid: male (pins) · outline: female (sockets) · dashed: not set"


# ---- m6a strings ----------------------------------------------------------------------------
NAME_ONE_LINE = "A name is one line. Remove the line break."
# ---- messages from the editor controller ------------------------------------------------------
UNDONE = "Undone: {}"
REDONE = "Redone: {}"
CONNECT_PICK_TYPE = "Pick an interface type on the left."
CONNECTOR_WORD = "connector"
UNIT_WORD = "unit"
CONNECT_FIRST = "Click the first {} for {}."
CONNECT_NONE_FREE = (
    "No other unit has a free {} connector. Pick another type, or add a unit that supports it."
)
CONNECT_SECOND = "Now click the second {}. Valid ones are highlighted."
CLICK_CONNECTOR = "Click a connector (the small square) on the unit."
PICK_TYPE_SHORT = "Pick a type"
PICK_TYPE_FIRST = "Pick an interface type first."
IF_ADDED = "Interface {} added."
IF_ADDED_AUTO = " Connectors were chosen for you and are marked Auto until you confirm them."
DELETED = "Deleted {}."
NOW_IN_ZONE = "{} is now in {}."
REDUNDANT_SKIPPED = " {} interface(s) could not be mirrored (no free connector): {}."
REDUNDANT_DONE = "Created {} and mirrored its interfaces (names end in -R).{}"
WAIVED = "Waived. The justification will appear in the DRC report."
ZONE_ADDED = "Zone {} added."
IMPORTED = "Imported {} interface{} in one step."
CHOOSE_EMPTY_NEW = "Choose an empty folder for the new project."
CHOOSE_EMPTY = "Choose an empty folder."
NO_FOLDER_YET = "This project has no folder yet. Use Save As to choose one."
FOLDER_HAS_PROJECT = "That folder already contains a project. Choose an empty folder."
AUTOSAVE_FAILED = "Autosave is not working: {}"
GEN_STALE = "The project changed while the plan was being made, so nothing was applied. Press Generate again."
GEN_FAILED = "Generation could not be completed ({}). Nothing was changed."
EXPORT_ERROR = "Export could not be completed ({}). Nothing was written."
OPEN_NO_LOCK = "This project was opened read-only because it cannot be locked for editing here: {}"
UNKNOWN_INTERFACE_TYPE = "This project has no interface type {}."
UNSAVED_NO_JOURNAL = "Unsaved changes (not kept anywhere until you save)"
RELOAD_FAILED = "The project could not be reloaded ({}). Your open version is unchanged; use Save a copy to keep it."
ALREADY_OPEN = "That project is already open in this window."
RESTORE_BODY_CHANGED = "The project files were changed after these unsaved changes were made (for example by a Git pull). Restoring brings back the old state of everything; saving then replaces the newer files. Restore only if that is what you want."
CHANGES_DURING_JOB = (
    "The project was edited while this ran, so the result was dropped. Please try again."
)
ISSUES_LIST = "Problems found while opening the project"
HISTORY_LIST = "Change log"
DIFF_BASELINE = "Compare with released revision"
DIFF_LIST = "Changes since the released revision"
ARRANGE_LABEL = "Arrange diagram"
REVIEW_SUBMITTED = "{} submitted for review."
NEW_REV_STARTED = "New revision of {} started; it can be edited again."
WIRE_COLOURS_LABEL = "Set wire colours"
CHAIN_HELP = "Chain must be nominal, redundant or none."
INTERFACE_COLUMNS = ["ID", "Name", "Type", "From", "To", "Chain", "Max current (A)", "Requirement"]
# names of the steps in the Undo / Redo menu and the toasts ("Undone: Add zone")
STEP_ADD = "Add {}"
STEP_DELETE = "Delete {}"
STEP_MOVE = "Move {}"
STEP_REDUNDANT_COPY = "Create redundant copy of {}"
STEP_FIX = "Fix: {}"
STEP_WAIVE = "Waive {}"
STEP_CONFIRM = "Confirm connectors"
STEP_RENAME = "Rename {}"
STEP_EDIT = "Edit {}"
STEP_CHOOSE_CONNECTOR = "Choose connector"
STEP_CHANGE_PART = "Change connector part"
STEP_ADD_ZONE = "Add zone"
STEP_ADD_INTERFACE = "Add interface"
STEP_GENERATE = "Generate harnesses"
STEP_IMPORT = "Import {} interfaces"
# words on the unit pictures and in the lists
TAG_FROM = "FROM"
TAG_NOMINAL = "NOMINAL"
TAG_REDUNDANT = "REDUNDANT"
NO_FREE_CONNECTOR = "No free {} connector"
NO_TYPE = "No type"
AND_MORE = "… and {} more"
PROGRESS_VERIFY = "Independent check"
FOLDER_UNUSABLE = "the folder cannot be used"
TABLE_FILES = "Tables (*.csv *.xlsx)"

# ==== UX foundation (theme, icons, state chips, shared tables) ==============================
A_THEME = "Theme"
A_THEME_SYSTEM = "Follow the system"
A_THEME_LIGHT = "Light"
A_THEME_DARK = "Dark"
STATUS_COUNTS_NOHASH = "{} · {} · model"
DOCK_CLOSE = "Close panel"
SHOW_ON_DIAGRAM = "Show on the diagram"
# state chips (gui/states.py): the word shown beside the icon
STATE_LABELS = {
    "pass": "Pass",
    "fail": "Fail",
    "warning": "Warning",
    "info": "Info",
    "pending": "Pending",
    "not-checked": "Not checked",
    "locked": "Locked",
    "released": "Released",
    "stale": "Out of date",
    "draft": "Draft",
    "in-review": "In review",
    "revised": "Revised",
}
# tables (gui/tables.py)
TABLE_HEADER_UNIT = "{} ({})"
TABLE_COPY_TIP = "Ctrl+C copies the selected cells (tab separated)"
TABLE_COPIED = "Copied {} cells"
STATUS_HASH = "Model hash"

# ---- diagram canvas: selection, navigation, search, menus (block appended for the canvas work) ----
READ_ONLY_REFUSAL = (
    "This project is read-only, so nothing was changed. Use Save as to make a copy you can edit."
)
STEP_DELETE_MANY = "Delete {} items"
DELETED_MANY = "Deleted {} items."
STEP_MOVE_MANY = "Move {} units"
STEP_ALIGN = "Align units"
STEP_DISTRIBUTE = "Space units evenly"
STEP_DUPLICATE = "Duplicate {}"
STEP_DUPLICATE_MANY = "Duplicate {} units"
DUPLICATED = "Copied as {}. The copy has the connectors of the original but none of its links."
STEP_EDIT_MANY = "Edit {} items"
CANVAS_SELECTED_MANY = "{} items selected."
# edit and view menu
A_SELECT_ALL = "Select all"
A_DUPLICATE = "Duplicate"
A_ALIGN = "Align"
A_DISTRIBUTE = "Space evenly"
A_FIND = "Find in diagram"
A_FIT_ALL = "Fit all"
A_ZOOM_100 = "Zoom to 100 %"
A_ZOOM_SELECTION = "Zoom to selection"
A_LEGEND = "Show legend"
A_SNAP = "Snap to grid"
ALIGN_NAMES = {
    "left": "Align left edges",
    "hcenter": "Align centres (vertical line)",
    "right": "Align right edges",
    "top": "Align top edges",
    "vmiddle": "Align middles (horizontal line)",
    "bottom": "Align bottom edges",
}
DISTRIBUTE_NAMES = {
    "horizontal": "Space evenly, side by side",
    "vertical": "Space evenly, one above the other",
}
WHY_NEED_TWO_UNITS = "Select at least two units."
WHY_NEED_THREE_UNITS = "Select at least three units."
WHY_NEED_UNIT_SELECTED = "Select a unit first."
WHY_SELECT_NO_ROOM = "There is no free room for a copy."
DUPLICATE_TIP = "Copy the selected units with their connectors (Ctrl+D)"
SELECT_ALL_TIP = "Select every unit and link in the diagram (Ctrl+A)"
FIND_TIP = "Find a unit or link by ID, name, connector or type (Ctrl+F)"
FIT_TIP = "Show the whole diagram (F)"
ZOOM_IN_TIP = "Zoom in (Ctrl+=)"
ZOOM_OUT_TIP = "Zoom out (Ctrl+-)"
ZOOM_100_TIP = "Real size, 100 % (Ctrl+0)"
ZOOM_SELECTION_TIP = "Fill the view with the selection (Shift+F)"
ARRANGE_TIP = "Tidy the diagram: order the units to shorten and uncross links (Ctrl+Shift+L)"
ZOOM_LEVEL_NAME = "Zoom level"
ZOOM_LEVEL_TIP = "Zoom level of the diagram. Click to go back to 100 % (Ctrl+0)."
ZOOM_PERCENT = "{} %"
ARRANGING = "Arranging the diagram"
# find in diagram
SEARCH_NAME = "Find in diagram"
SEARCH_PLACEHOLDER = "Find unit, link, connector or type"
SEARCH_TIP = "Type to mark every match. Enter goes to the next one, Shift+Enter to the one before, Escape closes."
SEARCH_COUNT_NAME = "Number of matches"
SEARCH_PREV = "Previous match (Shift+Enter)"
SEARCH_NEXT = "Next match (Enter)"
SEARCH_CLOSE = "Close search (Escape)"
SEARCH_NONE = "No match"
SEARCH_POSITION = "{0} of {1}"
# legend
LEGEND_TITLE = "Legend"
LEGEND_TOGGLE_TIP = "Show or fold the key to the pictures (View > Show legend hides it)"
LEGEND_TOGGLE_NAME = "Legend, fold or unfold"
# empty states
EMPTY_NO_LINKS = (
    "No links yet. Press C to connect two units, or pick an interface type in the palette."
)
# context menu
CM_OPEN_PLAN = "Show in harness plans"
CM_CONNECT_FROM = "Connect from here with"
CM_ADD_HERE = "Add unit here"
NOT_GENERATED = "Not generated yet: {} is not in any harness plan. Generate the harnesses first."
# deleting
DELETE_MANY_TITLE = "Delete {} items?"
DELETE_MANY_BODY = (
    "<p>These will be deleted:</p><ul>{items}</ul>{plans}<p>You can undo this with Ctrl+Z.</p>"
)
DELETE_IF_TITLE = "Delete {}?"
DELETE_IF_BODY = "<p><b>{iid}</b> ({type}) connects <b>{a}</b> and <b>{b}</b>.</p>{plans}<p>You can undo this with Ctrl+Z.</p>"
DELETE_IF_PLAN = "<p>In harness <b>{h}</b>, {n} wire(s) belong to it. They become out of date and come back, or go, the next time you generate.</p>"
# properties of several items
MULTI_UNITS = "{} units"
MULTI_LINKS = "{} links"
MULTI_MIXED = "{} units and {} links"
MULTI_HEAD = "Selection"
MULTI_HELP = "Fields shown here change every selected item at once. A field that reads (different) holds different values; leave it alone to keep them."
MULTI_DIFFERENT = "(different)"
MULTI_DELETE = "Delete selection"
MULTI_ONLY_SOME = "These fields apply to {} only."
SELECTED_MANY = "Selected: {} items"
EMPTY_HINT_NAME = "What to do next"
# ==== UX release / export / import wave (ux/rel): releases panel, release dialogs, export, import wizard, new project ====
# what a release locks / what a revision makes editable (gui/lock_tree.py)
LOCK_GROUP_WIRES = "Wires"
LOCK_GROUP_PINS = "Pins"
LOCK_GROUP_INTERFACES = "Interfaces"
LOCK_GROUP_CONNECTORS = "Connectors"
LOCK_GROUP_UNITS = "Units"
LOCK_GROUP_PARTS = "Parts"
LOCK_GROUP_TYPES = "Interface types"
LOCK_GROUP_CONFIG = "Config files"
LOCK_GROUP_OTHER = "Other items of the harness"
LOCK_NOTHING = "nothing"
LOCK_STAYS_EDITABLE = "{} stay editable"
LOCK_NOT_SET = "not set (pending)"
LOCK_NOT_SET_NOTE = (
    "No value yet. The release records it as not set; giving it a value later needs a new revision."
)
LOCK_PLACEHOLDER = "placeholder values"
LOCK_PLACEHOLDER_NOTE = "This file is still marked as a placeholder: its numbers were never reviewed, and the release freezes them as they are."
LOCK_PIN_CABLE = "cable"
LOCK_PIN_UNIT = "unit connector"
LOCK_ALSO = "also locked by {}"
LOCK_TREE_HEADER = "Locked object"
# release and revise dialogs
RELEASE_LOCKS_HEAD = "This release locks: {}."
RELEASE_LOCKS_TREE = "What this release locks"
RELEASE_LOCKS_TIP = "Open a group (arrow keys, Enter) to see every object, and the values of the config files that are frozen."
RELEASE_LOCKS_PLACEHOLDERS = (
    "Still placeholders when released: {}. The release freezes these numbers unreviewed."
)
REVISE_EXPLAIN = (
    "<b>What happens.</b> {0} gets revision {2} as a new draft; revision {1} stays on record as "
    "a frozen baseline that you can compare with. What only {0} locks becomes editable again, "
    "and the change log records who started the revision and why."
)
REVISE_EDITABLE_HEAD = "What becomes editable: {}."
REVISE_EDITABLE_NONE = "What becomes editable: nothing besides the harness itself."
REVISE_EDITABLE_TREE = "What becomes editable"
REVISE_STILL_LOCKED = "Still locked because another released harness uses it: {}."
REVISE_STILL_TREE = "Stays locked"
HINT_HEAD = "To enable “{0}”: {1}."
HINT_NAME = "enter your name"
HINT_COMMENT = "write at least 10 characters in the comment ({} more to go)"
HINT_PLACEHOLDER_REASON = (
    "give a reason of at least 10 characters for releasing on placeholder values"
)
HINT_PARTS_REASON = "give a reason of at least 10 characters for releasing unapproved parts"
HINT_BLOCKERS = "fix what is listed above first"
HINT_OK = "Ready: everything needed is filled in."
COMMENT_MIN = 10
# releases panel (gui/releases_panel.py)
REL_TITLE = "Releases"
REL_ACCESSIBLE = "Releases and change control"
REL_HARNESS = "Harness"
REL_ALL = "All harnesses"
REL_HARNESS_ITEM = "{0} — {1} (revision {2})"
REL_TIMELINE = "Timeline of reviews, releases and new revisions"
REL_TIMELINE_NAME = "Timeline"
REL_COLUMNS = {
    "id": "Entry",
    "harness": "Harness",
    "revision": "Revision",
    "event": "Event",
    "by": "By",
    "when": "When",
    "comment": "Comment",
    "baseline": "Baseline",
}
REL_BASELINE_CHIP = "Baseline {0}"
REL_BASELINE_TIP = (
    "A frozen copy of revision {0} was kept when it was released; you can compare with it."
)
REL_NO_BASELINE_TIP = "No frozen copy: this step did not release a revision."
REL_EMPTY_ALL = "Nothing has been reviewed, released or revised yet. Submit a draft for review or release it, and the step appears here."
REL_EMPTY_ONE = "{0} has no review, release or new revision yet."
REL_SUBMIT = "Submit for review"
REL_RELEASE = "Release…"
REL_REVISE = "New revision…"
REL_SUBMIT_TIP = "Mark the draft harness as ready for review"
REL_RELEASE_TIP = (
    "Release the harness: records a baseline and the change log, and locks what it uses"
)
REL_REVISE_TIP = (
    "Unlock a released harness by starting its next revision (the released one is kept)"
)
REL_CHOOSE_HARNESS = "Choose a harness first (or select a line of the timeline)."
REL_READ_ONLY = "This project is read-only, so nothing can be released or revised."
REL_WRONG_STATE = "{0} is {1}; this step is for harnesses that are {2}."
REL_DIFF_TITLE = "Differences"
REL_BEFORE = "Compare revision"
REL_AFTER = "with"
REL_WORKING = "Working design"
REL_REVISION = "Revision {0}"
REL_DIFF_NEED_HARNESS = (
    "Choose a harness (or select a line of the timeline) to compare its revisions."
)
REL_DIFF_NO_BASE = "{0} has no baseline yet; a baseline is created when the harness is released."
REL_DIFF_SAME = "Choose two different revisions to compare."
REL_DIFF_NONE = "No differences between {0} and {1}."
REL_DIFF_SUMMARY = "{0} compared with {1}: {2}."
REL_DIFF_NAME = "Changes grouped by kind"
REL_DIFF_TABLE = "Changed objects"
REL_ALL_KINDS = "All kinds"
REL_GROUP_ITEM = "{0}: {1}"
REL_COUNTS_ZERO = "no changes"
REL_ADDED = "Added"
REL_REMOVED = "Removed"
REL_CHANGED = "Changed"
REL_WHOLE_OBJECT = "(whole object)"
REL_DID_NOT_EXIST = "(did not exist)"
REL_NO_LONGER = "(removed)"
REL_DIFF_COLUMNS = {
    "change": "Change",
    "kind": "Kind",
    "id": "Object",
    "field": "Field",
    "before": "Before",
    "after": "After",
}
REL_MARK_TIP = "Mark the units, interfaces and harnesses that changed on the diagram"
REL_CLEAR_TIP = "Remove the marks from the diagram"
# export dialog (gui/export_dialog.py)
EXP_TITLE = "Export outputs"
EXP_ACCESSIBLE = "Export outputs"
EXP_FOLDER = "Output folder"
EXP_FOLDER_UNSAVED = "(none yet: the project has no folder)"
EXP_FOLDER_TIP = "The outputs always go to the outputs folder of the project; the full path is shown so you can copy it."
EXP_FULL_NOTE = (
    "Every export writes the complete set, so the outputs folder always matches the design and "
    "the independent check can verify it. The tick marks choose what the result list shows "
    "and what “Copy selection to folder…” copies."
)
EXP_TREE_NAME = "Harnesses and documents"
EXP_TREE_TIP = (
    "Tick the documents you want to see in the result and to copy. Space ticks or unticks."
)
EXP_SELECT_ALL = "Select all"
EXP_SELECT_NONE = "Select none"
EXP_SELECT_ALL_TIP = "Tick every harness and document"
EXP_SELECT_NONE_TIP = "Untick every harness and document"
EXP_SYSTEM = "System documents"
EXP_HARNESS_ITEM = "{0}  {1}"
EXP_COUNT_ITEM = "{0} ({1})"
EXP_BLOCK_UNSAVED = "This project has no folder yet, so there is nowhere to write the outputs. Save the project first; the outputs then go to an “outputs” folder next to it."
EXP_SAVE_PROJECT = "Save project…"
EXP_SAVE_PROJECT_TIP = "Choose an empty folder for the project; the outputs are written next to it"
EXP_OPEN_AFTER = "Open the folder after the export"
EXP_OPEN_AFTER_TIP = "Show the outputs folder in the file manager when the export has finished"
EXP_BUTTON = "Export"
EXP_BUTTON_TIP = "Write the complete set to the outputs folder (Enter)"
EXP_AGAIN = "Export again"
EXP_CLOSE_TIP = "Close this window (Esc)"
EXP_RUNNING = "Exporting…"
EXP_PROGRESS_NAME = "Export progress"
EXP_CANCEL_TIP = "Stop the export; nothing is written (Esc)"
EXP_CHECK_FAILED = (
    "The independent check found {0} problem(s) in the outputs, so nothing was written:"
)
EXP_WRITE_FAILED = "The outputs could not be written. {0}"
EXP_BANNER_DISMISS = "Dismiss"
EXP_BANNER_DISMISS_TIP = "Hide this message"
EXP_RESULT_HEAD = "{0} files written to {1}. Design {2}."
EXP_SHOWING = "Showing {0} of {1} files by your selection."
EXP_RESULT_NAME = "Files written"
EXP_COLUMNS = {"path": "File", "doc": "Document", "harness": "Harness", "size": "Size"}
EXP_SYSTEM_SCOPE = "System"
EXP_WHOLE_FOLDER = "(whole folder)"
EXP_REVEAL = "Reveal in folder"
EXP_REVEAL_TIP = "Show the selected file in its folder in the file manager (Ctrl+Enter)"
EXP_OPEN = "Open"
EXP_OPEN_TIP = "Open the selected file with the program your system uses for it (Enter)"
EXP_REVEAL_FOLDER = "Reveal output folder"
EXP_REVEAL_FOLDER_TIP = "Show the outputs folder in the file manager"
EXP_COPY = "Copy selection to folder…"
EXP_COPY_TIP = "Copy the ticked documents (without the manifest) to a folder you choose"
EXP_COPY_NONE = "Nothing is ticked, so there is nothing to copy."
EXP_COPY_DONE = (
    "Copied {0} files to {1}. The manifest is not copied: it describes the whole outputs folder."
)
EXP_COPY_NOT_EMPTY = "Choose an empty folder for the copy."
EXP_COPY_FOLDER = "Choose an empty folder for the copy"
EXP_SELECTED_NONE = "Select a file in the list."
EXP_PREVIEW_NAME = "Drawing preview"
EXP_PREVIEW_NONE = "No picture for this kind of file. Open it to see it."
EXP_PREVIEW_HINT = "Select a drawing to see it here."
EXP_PREVIEW_CAPTION = "Preview drawn from the design data: the same sheet the file holds."
EXP_LAST_NONE = "Last export: none yet."
EXP_LAST_CURRENT = "Last export: up to date with the design."
EXP_LAST_STALE = "Last export: the design changed after it."
EXP_LAST_MODIFIED = "Last export: files were changed afterwards."
EXP_LAST_UNREADABLE = "Last export: its manifest cannot be read."
EXP_NOTE_CHANGED = (
    "The project was edited while the export ran, so its result was dropped. Please export again."
)
# import wizard (gui/import_wizard.py, gui/import_kinds.py)
IMP_TITLE = "Import data"
IMP_ACCESSIBLE = "Import wizard"
IMP_STEP_FILE = "1  Choose what and which file"
IMP_STEP_MAP = "2  Match the columns and check the first rows"
IMP_STEP_CHECK = "3  Conflicts and placeholders"
IMP_STEP_APPLY = "4  Import"
IMP_KIND_PROMPT = "What do you want to import?"
IMP_KIND_INTERFACES = "Interfaces"
IMP_KIND_INTERFACES_TIP = (
    "A table (CSV or XLSX) with one interface per row: ID, type, the two units and the redundancy."
)
IMP_KIND_PARTS = "Approved parts"
IMP_KIND_PARTS_TIP = "A parts list (CSV or XLSX) with an approval status per part. You say what the status values mean; nothing is guessed."
IMP_KIND_LENGTHS = "Segment lengths"
IMP_KIND_LENGTHS_TIP = "Lengths from the mechanical design (CSV or XLSX). The columns are read by position: harness, segment, length."
IMP_KIND_VALUES = "Engineering values: ampacity table"
IMP_KIND_VALUES_TIP = "A CSV or XLSX with two columns: wire gauge (AWG) and the ampere value. It replaces the ampacity table of the derating values."
IMP_KIND_NETLIST = "KiCad netlist"
IMP_KIND_NETLIST_TIP = "The .net file exported from KiCad: creates or updates the connectors of one unit, with fixed signals on their pins."
IMP_FILE_LABEL = "File"
IMP_FILE_NAME = "Import file"
IMP_FILE_BROWSE = "Choose file…"
IMP_FILE_BROWSE_TIP = "Choose the file to import"
IMP_FILE_NONE = "No file chosen yet."
IMP_FILE_READ = "Read {0}: {1}."
IMP_FILE_SHEET = "sheet “{0}”"
IMP_FILE_ROWS = "{0} data rows"
IMP_FILE_COMPONENTS = "{0} components"
IMP_FILTER_TABLES = "Tables (*.csv *.xlsx)"
IMP_FILTER_NETLIST = "KiCad netlists (*.net *.xml);;All files (*)"
IMP_MAP_INTRO = "These are the first rows as the import will read them. Change a choice and the rows are read again."
IMP_NOT_MAPPED = "(not used)"
IMP_COLUMN_N = "(column {0})"
IMP_PREVIEW_NAME = "First rows"
IMP_PREVIEW_MORE = "Showing the first {0} of {1} rows."
IMP_PARTS_APPROVED = "Approved when it says"
IMP_PARTS_PENDING = "Not decided when it says"
IMP_PARTS_REJECTED = "Not approved when it says"
IMP_PARTS_WORDS_TIP = "Words separated by commas, for example: Approved, EPPL. A value in none of the lists is an error for its row."
IMP_PARTS_CATEGORY = "Category for rows that have none"
IMP_PARTS_SOURCE = "Library source recorded: {0}"
IMP_LENGTHS_UNIT = "Unit of the length column"
IMP_LENGTHS_NOTE = (
    "The columns are read by position, not by their headings: harness, segment, length."
)
IMP_VALUES_NOTE = "Two columns: wire gauge (AWG) and ampacity (A). The table replaces the one in the derating values."
IMP_NET_UNIT = "Unit the connectors belong to"
IMP_NET_UNIT_NONE = "(choose a unit)"
IMP_NET_PREFIX = "References that mark connectors"
IMP_NET_REFS = "Only these references"
IMP_NET_REFS_TIP = "Optional: references separated by commas, for example J1, J2. Empty means every component that starts with the prefix."
IMP_NET_IDS = "Connector IDs"
IMP_NET_IDS_TIP = "Optional: one REF=ID per line, for example J1=OBC1-J01. Otherwise the symbol field HarnessConnector, else the unit and the reference."
IMP_NET_PARTS = "Part for each connector"
IMP_NET_PARTS_TIP = "One REF=PART per line, for example J1=MD-9S. Needed when the symbol has no field HarnessPart and the connector is new."
IMP_NET_SIGNALS = "Net name to signal"
IMP_NET_SIGNALS_TIP = (
    "Optional: one NAME=SIGNAL per line to translate a KiCad net name to an interface signal name."
)
IMP_NET_PINFUNC = "Use the pin names of the symbol instead of the net names"
IMP_CHECK_INTRO = (
    "Every row with the reason it can or cannot be imported, and what stays pending afterwards."
)
IMP_CHECK_SUMMARY = "{0} of {1} rows can be imported; {2} have problems."
IMP_CHECK_ALL_OK = "All {0} rows can be imported."
IMP_CHECK_BLOCKS = "One problem stops the whole import (nothing is imported from a list with an error, as on the command line). Fix the file and choose it again."
IMP_CHECK_SKIPS = "Rows with a problem are skipped; the others are imported."
IMP_CHECK_ONLY = "Only rows that need attention"
IMP_CHECK_ONLY_TIP = "Hide the rows that are fine"
IMP_ROWS_NAME = "Rows and reasons"
IMP_PENDING_NAME = "Placeholders and pending values"
IMP_PENDING_HEAD = "Placeholders and pending values this import leaves"
IMP_PENDING_NONE = "Nothing is left pending by this import."
IMP_COLUMNS = {"row": "Row", "item": "Item", "result": "Result", "reason": "Reason"}
IMP_PENDING_COLUMNS = {"item": "Item", "what": "What stays open"}
IMP_WILL_ADD = "Will add"
IMP_WILL_UPDATE = "Will update"
IMP_WILL_SET = "Will set"
IMP_SKIPPED = "Skipped"
IMP_WARNING = "Warning"
IMP_BLOCKED = "The import would be refused: {0}"
IMP_EMPTY = "The file has no rows to import."
IMP_APPLY_HEAD = "Ready to import {0}."
IMP_APPLY_ONE_STEP = "This is one undo step called “{0}”. Undo (Ctrl+Z) takes all of it back."
IMP_APPLY_PENDING = "{0} placeholders or pending values stay open; see the previous page."
IMP_APPLY_SKIPPED = "{0} rows with problems are skipped."
IMP_LABEL = "Import {0} row{1}"
IMP_DONE = "Imported {0} row{1} in one step. {2}"
IMP_FAILED = "The import was refused: {0}"
IMP_NEXT_INTERFACES = "Generate harnesses to give the new interfaces wires."
IMP_NEXT_PARTS = "Parts that are still pending approval show up when you release a harness."
IMP_NEXT_LENGTHS = "Generate harnesses again to update the wire lengths."
IMP_NEXT_VALUES = "The derating values stay marked as placeholders until you review them."
IMP_NEXT_NETLIST = "Generate harnesses again to connect interfaces to the fixed pins."
IMP_P_AUTO = "connectors chosen for you and marked Auto until you confirm them"
IMP_P_PART_PENDING = "approval is pending: nobody has approved this part yet"
IMP_P_CONFIG = "stays marked as a placeholder until you review the values and clear the flag"
IMP_P_SIGNAL = "no interface type uses this signal ({0}); map it or ignore it"
IMP_HINT_PART = "enter {0}=PART in “Part for each connector”"
IMP_HINT_ID = "enter {0}=ID in “Connector IDs”"
IMP_HINT_REF = "Name the connectors in “Only these references”"
IMP_HINT_MAP = "map it in “Net name to signal”"
IMP_NO_UNIT = "Choose the unit these connectors belong to."
IMP_NO_DERATING = "This project has no derating configuration to put the table in."
IMP_NEED_ID_COLUMN = "No column looks like a part ID or part number; choose one."
IMP_BAD_PAIR = "{0} “{1}” must look like REF=VALUE"
IMP_BACK = "Back"
IMP_NEXT = "Next"
IMP_READ_ONLY = (
    "This project is read-only, so nothing can be imported. Save a copy to a new folder first."
)
IMP_VALUES_SAME = "The table is the same as the one already in the derating values, so there is nothing to import."
# new project dialog (gui/new_project_dialog.py)
NP_TITLE = "New project"
NP_ACCESSIBLE = "New project"
NP_FOLDER = "Project folder"
NP_FOLDER_TIP = "A new folder, or an empty one. The project files are written in it."
NP_BROWSE = "Choose folder…"
NP_BROWSE_TIP = "Choose or create the project folder"
NP_NAME = "Project name"
NP_NAME_TIP = "Shown in the title bar and on the drawings"
NP_TEMPLATE = "Start from"
NP_TEMPLATE_NAME = "Project to start from"
NP_TEMPLATE_TIP = (
    "Choose what the project starts with. Every example opens as a normal project you can change."
)
NP_EMPTY_TITLE = "Empty project"
NP_CREATE = "Create project"
NP_CREATE_TIP = "Create the project and open it (Enter)"
NP_HINT_HEAD = "To create the project: {0}."
NP_HINT_FOLDER = "choose a folder"
NP_HINT_NAME = "give it a name"
NP_ERR_FOLDER_NONE = "Choose a folder for the project."
NP_ERR_FOLDER_FILE = "That is a file, not a folder. Choose a folder."
NP_ERR_FOLDER_LINK = "That folder is a link. Choose a real folder."
NP_ERR_FOLDER_WRITE = "Nothing can be written in {0}. Choose another folder."
NP_ERR_NAME_NONE = "Give the project a name."
NP_ERR_NAME_LONG = "The name is too long: {0} characters, at most 200."
NP_ERR_NAME_CHARS = "The name must not contain line breaks or other control characters."
NP_HINT_FOLDER_FIX = "use a folder that is new or empty (see the message above)"
NP_HINT_NAME_FIX = "fix the name (see the message above)"
# ==== Checks view, engineering value dialog, pending values link (ux/checks) ========
NOT_CHECKED_HEADING = "Not checked"
CHECKS = "Checks"
CHECKS_TABLE = "Design rules"
CHECKS_SUMMARY = "{total} rules: {passed} passed · {failed} failed · {unchecked} not checked · {values} pending values"
CHECKS_SUMMARY_PASSED = "{} passed"
CHECKS_SUMMARY_FAILED = "{} failed"
CHECKS_SUMMARY_UNCHECKED = "{} not checked"
CHECKS_SUMMARY_VALUES = "{} pending values"
CHECKS_RULES_LABEL = "{} rules:"
CHECKS_PLACEHOLDER_PASSES = (
    "{} of the passed rules used placeholder values that nobody has reviewed."
)
CHECKS_CHECKING = "Checking the design rules…"
CHECKS_CANCEL = "Cancel"
CHECKS_CANCEL_TIP = "Stop the running check"
CHECKS_CANCELLED = "The check was cancelled. The results below are out of date."
CHECKS_AGAIN = "Check again"
CHECKS_AGAIN_TIP = "Run the design rules now"
CHECKS_NO_RESULT = "No design rule check has finished for this project yet."
CHECKS_FAILED_TITLE = "The check itself failed"
CHECKS_FILTER_LABEL = "Show"
CHECKS_FILTER_TEXT = "Filter rules"
CHECKS_FILTER_TEXT_HINT = "Type a rule name, ID or requirement"
CHECKS_FILTER_ALL = "All rules"
CHECKS_FILTER_FAIL = "Failed"
CHECKS_FILTER_UNCHECKED = "Not checked or pending"
CHECKS_FILTER_NOT_CHECKED = "Not checked"
CHECKS_FILTER_PENDING = "Pending"
CHECKS_FILTER_PASS = "Passed"  # noqa: S105
CHECKS_SHOWING = "Showing {} of {} rules"
CHECKS_COL_ID = "ID"
CHECKS_COL_RULE = "Rule"
CHECKS_COL_SEVERITY = "Severity"
CHECKS_COL_RESULT = "Result"
CHECKS_COL_OPEN = "Open"
CHECKS_COL_WAIVED = "Waived"
CHECKS_SEVERITY = {"error": "Error", "warning": "Warning", "info": "Info"}
CHECKS_RESULT_PLACEHOLDER = "Pass (placeholder values)"
CHECKS_TIP_NOTES = "This rule only lists what the other rules said they could not look at. Its notes are the objects below."
CHECKS_TIP_REQUIREMENTS = "Standard requirements: {}"
CHECKS_TIP_NO_REQUIREMENTS = "No standard requirement is linked to this rule."
CHECKS_TIP_PASS_PLACEHOLDER = (
    "Passed, but it reads placeholder values from {}. Nobody has reviewed them."  # noqa: S105
)
CHECKS_PICK_A_RULE = "Select a rule to see what it found and what it needs."
CHECKS_DETAIL_REQUIREMENTS = "Requirements: {}"
CHECKS_MISSING_HEADING = "What is missing"
CHECKS_MISSING_UNIT = "Unit: {}"
CHECKS_MISSING_DATA = "Missing in the design data: {}"
CHECKS_MISSING_ANALYSIS = "Needs an analysis outside this tool: {}"
CHECKS_SUPPLY = "Supply value…"
CHECKS_SUPPLY_TIP = "Open the engineering values and type this one in"
CHECKS_SUPPLY_NAME = "Supply value… for {}"
CHECKS_PLACEHOLDER_NOTE = "This rule passed using placeholder values from {}. Nobody has reviewed them, so treat the result as provisional."
CHECKS_OBJECTS_HEADING = "Offending objects ({})"
CHECKS_OBJECTS_NONE = "Nothing was found."
CHECKS_OBJECTS_NONE_PARTLY = "Nothing was found in what could be checked."
CHECKS_OBJECTS_TABLE = "Offending objects of {}"
CHECKS_OBJ_OBJECT = "Object"
CHECKS_OBJ_MESSAGE = "Message"
CHECKS_OBJ_SEVERITY = "Severity"
CHECKS_OBJ_WAIVER = "Waiver"
CHECKS_SHOW_TIP = "Show the selected object on the diagram (Enter)"
CHECKS_WHOLE_DESIGN = "(whole design)"
CHECKS_DETAILS = "Rule details"
CHECKS_SEGMENT_TIP = "show only these rules"
CHECKS_NOTES_HEADING = "What the check said it did not look at"
# pending values link (status bar)
PENDING_LINK = "{values} values pending · {rules} rules not checked"
PENDING_LINK_VALUES = "{} values pending"
PENDING_LINK_RULES = "{} rules not checked"
PENDING_LINK_TIP = "Show the design rules that were not checked because a value is missing"
PENDING_LINK_NAME = "Pending values"
# engineering value dialog
CONFIG_TITLE = "Engineering values"
CONFIG_INTRO = "These values come from your programme's standard. The tool never supplies a number itself; a value you type here is stored in the project's config files."
CONFIG_ONLY_MISSING = "Only values that are still missing"
CONFIG_FILE_GROUP = "config/{}.json"
CONFIG_PLACEHOLDER_TOGGLE = "Values in this file are placeholders (not reviewed)"
CONFIG_PLACEHOLDER_TIP = (
    "Untick when the values in this file have been reviewed against the standard"
)
CONFIG_NOT_SET = "(not set)"
CONFIG_YES = "yes"
CONFIG_NO = "no"
CONFIG_NEEDED_FOR = "{what}. Needed for: {used_by}."
CONFIG_SOURCE = "Source: {}"
CONFIG_PLACEHOLDER_SUFFIX = "(placeholder file, not reviewed)"
CONFIG_LOCKED = "Locked: {}"
CONFIG_APPLY = "Apply"
CONFIG_APPLY_TIP = "Set the changed values in one step (Ctrl+Enter)"
CONFIG_CANCEL = "Cancel"
CONFIG_NO_CHANGES = "Nothing changed yet."
CONFIG_CHANGES = "{} changes will be applied as one step you can undo."
CONFIG_READ_ONLY = "This project is open read-only, so values cannot be changed."
CONFIG_FIX_FIRST = "Fix the marked values first."
CONFIG_LABEL_ONE = "Set {}"
CONFIG_LABEL_MANY = "Set {} engineering values"
CONFIG_DONE_ONE = "Set {}."
CONFIG_DONE_MANY = "Set {} engineering values."
CONFIG_FIELD_NAME = "{label} ({unit})"
CONFIG_PAIRS_HINT_TIP = "{hint}"
CONFIG_REFUSED = "The change was refused. The message at the bottom of the window says why."

# ==== Canvas state marks (ux/cstate): CV-6 to CV-23 ==============================================
CORNER_NAME = "State of the harnesses and outputs"
CORNER_GEN_STALE = "Harnesses out of date: Generate again"
CORNER_GEN_NONE = "Harnesses not generated yet"
CORNER_GEN_CURRENT = "Harnesses up to date"
CORNER_OUT_STALE = "Outputs out of date: Export again"
CORNER_OUT_NONE = "Outputs not exported yet"
CORNER_OUT_MODIFIED = "Output files changed since export"
CORNER_OUT_UNREADABLE = "Output list unreadable"
CORNER_ALL_CURRENT = "Harnesses and outputs up to date"
BADGE_CLICK = "Click to show them in Problems."
BADGE_PENDING_TIP = "{}. They are not entered yet; the checks that need them stay silent."
BADGE_NOT_CHECKED_TIP = "Not checked yet: the design check has no result for this project."
LOCK_TIP = "Locked by {harness}, released as revision {rev}. Start a new revision to change it."
LOCK_TIP_MORE = " It is also locked by {}."
LOCK_TIP_COSMETIC = " Names, notes and the position can still be edited."
AUTO_COUNT = "{} auto"
AUTO_CHIP_TIP = "{n} connector(s) chosen for you and not confirmed yet."
AUTO_CHIP_MORE = "More: right-click and choose Why?"
CONN_COUNT = "{} conn"
CONN_COUNT_TIP = "{} connectors on this unit"
CONN_MORE = "+{}"
CONN_MORE_TIP = "{} more connectors; the unit's properties list them all"
TAG_FLIGHT = "FLIGHT"
TAG_GROUND = "GROUND"
TAG_NOMINAL_TIP = "On the nominal chain; this project also has a redundant one"
TAG_REDUNDANT_TIP = "On the redundant chain"
ZONE_TAG_TIP = "Tag set for zone {} in this program (the project file does not hold it)"
LEGEND_BADGE_FAIL = "problems found"
LEGEND_BADGE_WARNING = "warnings"
LEGEND_BADGE_PENDING = "value still to enter (V ?, A ?)"
LEGEND_BADGE_NOT_CHECKED = "not checked yet"
LEGEND_LOCK = "locked by a release (harness, revision)"
LINK_TIP_WHY = "Why? Right-click the link and choose Why?"
CM_SHOW_PROBLEMS = "Show problems"
CM_WHY = "Why?"
CM_ZONE_TAG = "Tag zone {} as"
CM_TAG_FLIGHT = "Flight"
CM_TAG_GROUND = "Ground"
CM_TAG_NONE = "No tag"
WHY_NOTHING_TO_SHOW = "nothing to show here"
WHY_NOTHING_CHOSEN = "nothing was chosen for you here"


# ==== App shell (ux/shell): top bar, banners, tabs, palette, layout ===================================
SHELL_MAIN_TABS = "Main views"
SHELL_RIGHT_TABS = "Side panels"
SHELL_LEFT_TABS = "Project and palette"
TAB_DIAGRAM = "Diagram"
TAB_HARNESS = "Harness"
TAB_LISTS = "Lists"
TAB_CHECKS = "Checks"
TAB_RELEASES = "Releases"
TAB_INSPECTOR = "Inspector"
TAB_PROBLEMS = "Problems"
TAB_PROJECT = "Project"
TAB_TIP = "{} (Ctrl+{})"
# empty states of views that are not installed yet
EMPTY_VIEW_TITLE = "{} is not available yet"
EMPTY_VIEW_HARNESS = "Pick a harness in the project tree, or double-click a link in the diagram, to see its connectors, pins, wires and drawing. Generate harnesses first if there are none."
EMPTY_VIEW_LISTS = "The wire list, pinouts, bill of materials and test tables appear here once harnesses are generated."
EMPTY_VIEW_TREE = "The project tree lists units, interfaces, harnesses, parts, interface types, configuration and imports."
EMPTY_VIEW_INSPECTOR = "Select a unit or a link on the diagram to see and edit its fields."
EMPTY_VIEW_WHY = "Select a connector, pin or wire to read why it is like this."
EMPTY_VIEW_PROBLEMS = "Design problems for the selection appear here."
# top bar
TB_ACCESSIBLE = "Project bar"
TB_NAME = "Project name"
TB_HASH_TIP = "Short fingerprint of the current design (model {})"
TB_DIRTY = "Unsaved changes"
TB_CLEAN = "Saved"
TB_DIRTY_TIP = "The design has changes that are not saved to the project folder yet (they are kept in the recovery journal)."
TB_CLEAN_TIP = "Everything is saved to the project folder."
TB_UNSAVED_PROJECT = "Not saved yet"
TB_GENERATE = "Generate"
TB_CHECK = "Check"
TB_CHECK_TIP = "Run the design rule check now (it also runs by itself a moment after each change)"
TB_EXPORT = "Export…"
TB_EXPORT_TIP = "Choose and write the drawings, lists and exports to the outputs folder"
TB_GENERATE_READ_ONLY = "This project is open read-only, so harnesses cannot be generated."
TB_CHIP_NAME = "Status of the plans and the outputs"
CHIP_UP_TO_DATE = "Up to date"
CHIP_UP_TO_DATE_TIP = "The harness plans match the diagram and the exported files match the plans."
CHIP_PLANS_CURRENT = "Plans up to date"
CHIP_PLANS_CURRENT_TIP = "The harness plans match the diagram. Nothing has been exported yet."
CHIP_PLANS_STALE = "Plans out of date"
CHIP_PLANS_STALE_TIP = "The diagram changed after the harnesses were generated. Press Generate."
CHIP_OUTPUTS_STALE = "Outputs out of date"
CHIP_OUTPUTS_STALE_TIP = (
    "The design changed after the files in the outputs folder were exported. Export again."
)
CHIP_OUTPUTS_CHANGED = "Outputs changed"
CHIP_OUTPUTS_CHANGED_TIP = (
    "The files in the outputs folder cannot be read or were changed outside the tool. Export again."
)
CHIP_NOT_GENERATED = "Not generated"
CHIP_NOT_GENERATED_TIP = "No harnesses have been generated for this design yet."
CHIP_GENERATING = "Generating…"
CHIP_EXPORTING = "Exporting…"
CHIP_ARRANGING = "Arranging…"
CHIP_CHECKING = "Checking…"
CHIP_CHECKING_TIP = "The design rule check is running."
CHIP_RUNNING_TIP = "A job is running. You can cancel it in the progress window."
# banners
BN_PLANS_STALE = "The harness plans are out of date: the diagram changed after they were generated."
BN_OUTPUTS_STALE = "The exported files are out of date: the design changed after the last export."
BN_BOTH_STALE = "The harness plans and the exported files are out of date: the design changed after they were made."
BN_DETAIL_GENERATED = "Last generated at model {}."
BN_DETAIL_NOT_GENERATED = "Nothing has been generated yet."
BN_DETAIL_ORDER = "Generate first, then export, so the files match the plans."
BN_GENERATE = "Generate"
BN_EXPORT = "Export…"
BN_DISMISS = "Hide this notice until the design changes again"
BN_RETRY = "Try again"
BN_START_REVISION = "Start new revision…"
BN_REFUSAL_NAME = "Change refused"
# status bar
STATUS_PATH_NONE = "Not saved to a folder yet"
STATUS_PATH_SAMPLE = "Sample project (not saved)"
STATUS_PATH_NAME = "Project folder"
STATUS_RULES = "{} rules · v{}"
STATUS_RULES_TIP = "{} design rules are checked. Tool version {}."
STATUS_GENERATED = "Generated at model {}"
STATUS_NOT_GENERATED = "Not generated"
STATUS_GENERATED_TIP = "Fingerprint of the design data the harness plans were generated from"
STATUS_NOT_GENERATED_TIP = "No harnesses have been generated yet"
# actions, menus and shortcuts
A_GENERATE = "Generate harnesses"
A_CHECK = "Run checks"
A_EXPORT = "Export…"
A_RELEASE = "Release harness…"
A_REVISE = "Start new revision…"
A_REVIEW = "Submit harness for review…"
A_CANCEL_CHECK = "Cancel the running check"
A_NEW_INTERFACE = "New interface…"
A_RESET_LAYOUT = "Reset layout"
A_RESET_LAYOUT_TIP = "Put the panels back where they were when the program was installed"
A_NEXT_PANE = "Next panel"
A_PREV_PANE = "Previous panel"
A_GO_DIAGRAM = "Go to Diagram"
A_GO_HARNESS = "Go to Harness"
A_GO_LISTS = "Go to Lists"
A_GO_CHECKS = "Go to Checks"
A_GO_RELEASES = "Go to Releases"
A_GO_HARNESS_ID = "Go to harness"
A_VALUES = "Engineering values…"
A_VALUES_TIP = "Supply the values the design rules are waiting for"
M_IMPORT = "Import"
A_IMPORT_INTERFACES = "Interfaces…"
A_IMPORT_PREFIX = "Import"
M_GO = "&Go"
M_PANELS = "Panels"
UNDO_LABELLED = "Undo {}"
REDO_LABELLED = "Redo {}"
UNDO_NOTHING = "Nothing to undo"
REDO_NOTHING = "Nothing to redo"
NO_HARNESS_FOR_ACTION = "Choose a harness first (there is more than one)."
NO_HARNESSES_FOR_ACTION = "There are no harnesses yet. Generate harnesses first."
VIEW_NOT_INSTALLED = "{} is not available in this version yet."
CHECK_STARTED = "Checking the design rules…"
CHECK_FINISHED = "Checks finished: {failed} failed · {unchecked} not checked."
CHECK_FINISHED_CLEAN = "Checks finished: nothing failed · {unchecked} not checked."
CHECK_SHOW = "Show checks"
PALETTE_NO_MATCH = "No command matches."
PANE_CANVAS = "Diagram"
PANE_TREE = "Project panel"
PANE_INSPECTOR = "Inspector"
PANE_FOCUSED = "{} has the keyboard focus"
M_DESIGN = "&Design"
# ==== UX harness view, lists and generate plan (gui/harness_view.py, lists_panel.py, plan_table.py) ==
PREVIEW_HELP = "Drawing preview. Wheel zooms, drag pans, + and - zoom, 0 fits, Page Up and Page Down change sheet."
PREVIEW_ZOOM_FIT = "Fit"
PREVIEW_FIRST = "This is the first sheet"
PREVIEW_LAST = "This is the last sheet"

# Harness view (gui/harness_view.py)
HV_PINS_TITLE = "Connectors and pins"
HV_WIRES_TITLE = "Wires"
HV_DRAWING_TITLE = "Drawing"
HV_WHY_TITLE = "Why"
HV_HARNESS = "Harness"
HV_HARNESS_TIP = "Choose the harness to show"
HV_INTERFACES = "Interfaces: {}"
HV_INTERFACES_NONE = "Interfaces: none"
HV_GENERATED_FROM = "Generated from {}"
HV_GENERATED_FROM_TIP = "Hash of the design that Generate last read: {}"
HV_NOT_GENERATED = "Not generated yet"
HV_FILTER_PINS = "Filter pins"
HV_FILTER_WIRES = "Filter wires"
HV_SHOW_SPARE = "Show spare pins"
HV_SHOW_SPARE_TIP = "Spare pins carry no signal and no wire; they are hidden until you ask for them"
HV_PIN_COUNT = "{} pins shown"
HV_PIN_COUNT_SPARE = "{} pins shown, {} spare hidden"
HV_WIRE_COUNT = "{} wires"
HV_NO_WIRES = "This harness has no wires."
HV_COL_CONNECTOR = "Connector"
HV_COL_PIN = "Pin"
HV_COL_SIGNAL = "Signal"
HV_COL_WIRE = "Wire"
HV_COL_FROM = "From"
HV_COL_TO = "To"
HV_COL_GAUGE = "Gauge"
HV_COL_LENGTH = "Length"
HV_COL_COLOUR = "Colour"
HV_COL_SHIELD = "Shield"
HV_COL_LOCKED = "Locked"
HV_COL_STATE = "State"
HV_PENDING = "pending"
HV_LOCKED_WORD = "Locked"
HV_LOCK_PIN = "You fixed this pin by hand; Generate keeps it where it is."
HV_LOCK_WIRE = (
    "You set the gauge, colour, part or length of this wire by hand; Generate keeps them."
)
HV_STATE_AUTO = "Auto-filled"
HV_STATE_AUTO_TIP = "Chosen by Generate; nobody has reviewed it yet."
HV_PENDING_GAUGE = "Gauge pending"
HV_PENDING_LENGTH = "Length pending"
HV_PENDING_BOTH = "Gauge and length pending"
HV_GAUGE_PENDING_TIP = "The gauge is not decided yet. It stays pending until the values that wire sizing needs are supplied."
HV_LENGTH_PENDING_TIP = "The length is not known yet: a routing segment on its path has no length."
HV_REL_DRAFT = "Draft · rev {}"
HV_REL_REVIEW = "In review · rev {}"
HV_REL_RELEASED = "Released · rev {}"
HV_REL_REVISED = "Revised · rev {}"
HV_REL_TIP = {
    "draft": "Draft: it can still be edited and regenerated.",
    "in-review": "In review: submitted for review, not released yet.",
    "released": "Released: the harness and what it uses are locked. Revise it to change it.",
    "revised": "A new revision of a released harness: editable again, the released one is kept.",
}
HV_GEN_CURRENT = "Up to date"
HV_GEN_STALE = "Out of date"
HV_GEN_NONE = "Not generated"
HV_OUT_CURRENT = "Outputs current"
HV_OUT_STALE = "Outputs out of date"
HV_OUT_NONE = "Not exported"
HV_OUT_UNSAVED = "Not saved"
HV_OUT_MODIFIED = "Outputs changed"
HV_OUT_UNREADABLE = "Outputs unreadable"
HV_CHECKING = "Checking…"
HV_CHECKING_TIP = (
    "The independent check and the outputs state are being worked out in the background."
)
HV_VERIFY_OK = "Check passed"
HV_VERIFY_BAD = "Check found {} problem(s)"
HV_VERIFY_FAILED = "Could not check: {}"
HV_VERIFIED_IN = "Checked in {} ms in the background; this view refreshed in {} ms."
HV_REGENERATE = "Regenerate"
HV_REGENERATE_TIP = "Generate all harnesses again from the diagram. Generate covers every harness, not only this one; a preview comes first and Undo reverts it"
HV_EXPORT = "Export"
HV_REVIEW = "Open in review"
HV_REVIEW_TIP = "Open {} in the review view"
HV_REVISE = "Revise…"
HV_WHY_NO_HARNESS = "Select a harness first."
HV_WHY_RELEASED = "{} is released. Revise it to make changes."
HV_WHY_NOT_RELEASED = "Only a released harness can be revised."
HV_WHY_RELEASE_NOT_DRAFT = "Only a draft or a harness in review can be released."
HV_EMPTY_TITLE = "No harnesses yet"
HV_EMPTY_NO_INTERFACES = "Add interfaces on the diagram or import a table (Ctrl+Shift+I). Then press Generate to build the harnesses."
HV_EMPTY_READY = "The diagram has {} interface(s) and no harnesses yet. Press Generate to build them. You see a preview first and Undo reverts it."
HV_GENERATE_NOW = "Generate harnesses"
HV_WHY_HARNESS = "Harness {}"
HV_WHY_WIRE = "Wire {}"
HV_WHY_CONNECTOR = "Connector {}"
HV_WHY_PIN = "Pin {}"
HV_WHY_HINT = "Select a wire, connector or pin to see why it is as it is."
HV_WHY_OPEN = "Show in Why panel"
HV_WHY_OPEN_TIP = "Show the reasons for the selection in the Why panel"
HV_WHY_NONE = (
    "No reason is recorded for this one (it was made by hand, or the harness was not generated)."
)

# Lists panel (gui/lists_panel.py)
LP_WIRELIST = "Wire list"
LP_PINOUTS = "Pinouts"
LP_BOM = "BOM"
LP_MASS = "Mass and length"
LP_TESTS = "Test tables"
LP_LABELS = "Labels"
LP_SYSTEM_BOM = "System BOM"
LP_TABS = "Lists"
LP_HARNESS = "Harness"
LP_HARNESS_TIP = "The harness the lists are for (the system BOM covers all harnesses)"
LP_FILTER = "Filter rows"
LP_FILTER_TIP = "Keep the rows that contain every word you type (Ctrl+F)"
LP_ONLY_OPEN = "Only pending or not checked"
LP_ONLY_OPEN_TIP = "Show only the rows that still have a pending or not-checked value"
LP_EXPORT = "Export table"
LP_EXPORT_TIP = "Save the rows you see (as filtered and sorted) as CSV or an Excel workbook"
LP_EXPORT_CSV = "CSV file…"
LP_EXPORT_XLSX = "Excel workbook…"
LP_COUNT = "{} of {} rows"
LP_COUNT_ALL = "{} rows"
LP_STALE = "The diagram changed after the harnesses were generated, so these lists show the earlier harnesses. Regenerate to bring them up to date."
LP_STALE_CHIP = "Out of date"
LP_REGENERATE_TIP = "Generate all harnesses again from the diagram (a preview comes first)"
LP_EMPTY_TITLE = "No lists yet"
LP_EMPTY_NO_INTERFACES = "The lists are made from generated harnesses. Add interfaces on the diagram or import a table (Ctrl+Shift+I), then press Generate."
LP_EMPTY_READY = "The lists are made from generated harnesses. Press Generate to build them; you see a preview first."
LP_NO_ROWS = "This list has no rows."
LP_EXPORT_NONE = "There is nothing to export: this list has no rows."
LP_EXPORT_DONE = "Saved {} rows to {}"
LP_APPROVAL_MISSING = "The part is not in the parts list."

# Generate plan table (gui/plan_table.py)
GP_HARNESS = "Harness"
GP_NAME = "Name"
GP_CHANGE = "Change"
GP_LOCKED = "Locked pins kept"
GP_NEW = "New"
GP_CHANGED = "Changed"
GP_UNCHANGED = "Unchanged"
GP_REMOVED = "Removed"
GP_FROZEN = "Released, kept"
GP_TIPS = {
    "new": "Generate creates this harness.",
    "changed": "Generate rewrites this harness; Undo restores it.",
    "unchanged": "Generate leaves this harness exactly as it is.",
    "removed": "Generate removes this harness: nothing needs it any more. Undo restores it.",
    "frozen": "This harness is released. Generate does not touch it.",
}
GP_TABLE = "Harnesses Generate will create, change or leave"
GP_LOCKS_ELSEWHERE = "{} more locked pin(s) outside these harnesses stay where you put them."
GP_NONE = "Generate has nothing to do for any harness."
HV_DRAWING_BUSY = "Drawing the sheets…"
# ==== UX tree and inspector (gui/project_tree.py, gui/inspector.py, gui/why_panel.py) ==============
TREE_NAME = "Project tree"
TREE_HELP = (
    "Units, interfaces, harnesses, parts, interface types, configuration and imports. Arrow keys "
    "move, Enter selects, Ctrl+Enter opens, Right and Left open and close a group, typing jumps "
    "to a name, / filters."
)
TREE_ROOTS = {
    "units": "Units",
    "interfaces": "Interfaces",
    "harnesses": "Harnesses",
    "parts": "Parts",
    "interface_types": "Interface types",
    "config": "Configuration",
    "imports": "Imports",
}
TREE_EMPTY = {
    "units": "No units yet. Add one with the Add button.",
    "interfaces": "No interfaces yet. Add one with Ctrl+I or import a table.",
    "harnesses": "No harnesses yet. Generate them from the interfaces.",
    "parts": "No parts yet. Import an approved parts list.",
    "interface_types": "No interface types yet.",
}
TREE_IMPORTS = {
    "interfaces": "Interfaces (CSV, XLSX)…",
    "parts": "Approved parts…",
    "lengths": "Segment lengths…",
    "engineering": "Engineering values…",
    "netlist": "KiCad netlist…",
}
TREE_IMPORT_TIP = "Import {}. Press Enter or double-click to start."
TREE_IMPORT_READ_ONLY = "This project is read-only, so nothing can be imported."
TREE_FILTER_NAME = "Filter the project tree"
TREE_FILTER_PLACEHOLDER = "Filter"
TREE_FILTER_TIP = "Filter the project tree by ID or name (press / in the tree)"
TREE_NO_MATCH = "Nothing matches “{}”."
TREE_ADD = "Add"
TREE_ADD_TIP = "Add something to the project"
TREE_ADD_ENTRIES = {"unit": "Unit…", "interface": "Interface…"}
TREE_ADD_IN = "Add {}…"
TREE_MENU_SELECT = "Select on the diagram"
TREE_MENU_OPEN = "Open"
TREE_MENU_COPY_ID = "Copy ID"
TREE_MENU_EXPAND = "Expand all"
TREE_MENU_COLLAPSE = "Collapse all"
TREE_N_ERRORS = ("{} error", "{} errors")
TREE_N_WARNINGS = ("{} warning", "{} warnings")
TREE_N_NOT_CHECKED = ("{} not checked", "{} not checked")
TREE_CONFIG_PLACEHOLDER = "Placeholder"
TREE_CONFIG_PENDING = "{} pending"
TREE_TIP_UNIT = "Unit {}: {}. Subsystem {}, zone {}, chain {}."
TREE_TIP_INTERFACE = "Interface {}: {} ({})."
TREE_TIP_HARNESS = "Harness {}: {}. Revision {}, {}."
TREE_TIP_PART = "Part {}: {} ({})."
TREE_TIP_TYPE = "Interface type {}: {} ({} interface)."
TREE_TIP_CONFIG_PLACEHOLDER = (
    "Configuration {} is still a placeholder: nobody has reviewed its values."
)
TREE_TIP_CONFIG_MISSING = "{} not set yet: {}."
TREE_TIP_CONFIG_OK = "Configuration {} is set and reviewed."
TREE_NO_ZONE = "none yet"
TREE_VALUE_WORD = ("value", "values")
WHY_NAME = "Why"
WHY_TAB_TIP = "Why the selected object is the way it is"
WHY_EMPTY = "Select a unit, link, harness, wire, connector or pin to see why it is the way it is."
WHY_TITLE = "Why: {} {}"
WHY_KIND = {
    "unit": "unit",
    "interface": "link",
    "harness": "harness",
    "wire": "wire",
    "connector": "connector",
    "pin": "pin",
}
WHY_INTRO = "What the tool recorded when it generated this."
WHY_NONE = "Nothing was recorded for this yet. Generate the harnesses to get the reasons."
WHY_SHOW_ALL = "Show all {}"
WHY_SHOW_FEWER = "Show fewer"
WHY_SHOW_ALL_TIP = "Show every recorded reason"
WHY_PENDING = "Pending"
WHY_PLACEHOLDER = "Placeholder"
WHY_PLACEHOLDER_NOTE = (
    "Generated on placeholder values from: {}. Nobody has reviewed them, so treat the result as "
    "provisional."
)
WHY_RULE_NAME = "Rule {}"
INS_NAME = "Inspector"
INS_TAB_INSPECTOR = "Inspector"
INS_TAB_WHY = "Why"
INS_TAB_PROBLEMS = "Problems"
INS_TAB_PROBLEMS_N = "Problems ({})"
INS_NO_PROBLEMS_HOST = "The problems list is not attached yet."
INS_REVISE = "Start new revision"
INS_REVISE_TIP = "Start a new revision of {}: it becomes a draft you can edit; the released revision stays on record"
INS_BANNER_COSMETIC = "Names and notes can still be changed."
INS_BANNER_RELEASED = "Released {} {}"
INS_BANNER_DRAFT = "{} is a draft (revision {})."
INS_BANNER_IN_REVIEW = "{} is in review (revision {}). It can be edited until it is released."
INS_BANNER_REVISED = "{} is revision {}, a draft after a release. It can be edited."
INS_USED_IN = "Used in"
INS_USED_IN_N = "Used in ({})"
INS_USED_NONE = "Not used anywhere yet."
INS_USED_COLUMNS = ("Kind", "ID", "How")
INS_USED_KINDS = {"interface": "Link", "harness": "Harness", "wire": "Wire", "unit": "Unit"}
INS_USED_TIP = "Double-click or press Enter to show it on the diagram"
INS_FACTS_NAME = "Properties of {} {}"
INS_FACT_COLUMNS = ("Property", "Value", "Status")
INS_VALUES_NAME = "Engineering values of {}"
INS_STATUS_NOT_SET = "Not set"
INS_STATUS_UNREVIEWED = "Unreviewed"
INS_STATUS_UNREVIEWED_TIP = "{} is still a placeholder file: nobody has reviewed this value."
INS_STATUS_NOT_SET_TIP = "Not set yet. {}"
INS_STATUS_UNVERIFIED = "Not verified"
INS_STATUS_UNVERIFIED_TIP = "Example data that no engineer has verified."
INS_FACT_KIND = {
    "harness": "Harness",
    "part": "Part",
    "interface_type": "Interface type",
    "config": "Configuration",
}
INS_FACT_LABELS = {
    "name": "Name",
    "revision": "Revision",
    "state": "State",
    "interfaces": "Interfaces",
    "wires": "Wires",
    "connectors": "Connectors",
    "released_on": "Released on",
    "approver": "Released by",
    "category": "Category",
    "manufacturer": "Maker",
    "part_number": "Part number",
    "approval": "Approval",
    "pins": "Pins",
    "description": "Description",
    "construction": "Construction",
    "signals": "Signals",
    "placeholder": "Review",
}
INS_FACT_REVIEWED = "Reviewed"
INS_FACT_PLACEHOLDER = "Placeholder: not reviewed yet"
INS_NOTHING = (
    "Nothing selected. Pick a unit or a link on the diagram, or a row in the project tree."
)
TREE_FILTER_CLEAR = "Clear the filter"
LISTS_EXPORT_TITLE = "Export table"
LISTS_EXPORT_FILTER = {"csv": "CSV files (*.csv)", "xlsx": "Excel workbooks (*.xlsx)"}
LISTS_EXPORTED = "Saved {}."


# ---- Devices view (custom devices, docs/ux-custom-devices-audit.md) -------------------------------
TAB_DEVICES = "Devices"
A_GO_DEVICES = "Go to Devices"
DV_ACCESSIBLE = "Devices: connectors and pins of a unit"
EMPTY_VIEW_DEVICES = "The connectors and pins of a unit appear here: pick a unit on the diagram or in the project tree."
DV_EMPTY_TITLE = "No devices yet"
DV_EMPTY_BODY = (
    "A device is a unit with its connectors and pins. Add a unit to see its pinout here."
)
DV_ADD = "Add a unit…"
DV_ADD_TIP = "Add a unit to the project"
DV_DEVICE = "Device"
DV_DEVICE_TIP = "The unit whose connectors and pins are shown. A unit picked on the diagram or in the project tree is shown here."
DV_SUBSYSTEM = "Subsystem {}"
DV_CHAIN = {"nominal": "Nominal chain", "redundant": "Redundant chain", "none": "No chain"}
DV_STATE_TIP = "{}"
DV_STATE_DRAFT = "Draft"
DV_STATE_IN_USE = "In use"
DV_STATE_LOCKED = "Locked"
DV_STATE_READ_ONLY = "Read-only"
DV_DUPLICATE = "Duplicate"
DV_DUPLICATE_TIP = "Copy this unit with its connectors and pins (not its links)"
DV_EXPORT = "Export pinout…"
DV_EXPORT_TIP = "Save the pinout below as a CSV file or an Excel workbook, to compare with the interface control document"
DV_EXPORT_TITLE = "Export pinout"
DV_EXPORTED = "Saved {}."
DV_COUNTS = "{connectors}, {pins}, {signals} set, {interfaces}"
DV_N_CONNECTORS = ("{} connector", "{} connectors")
DV_N_PINS = ("{} pin", "{} pins")
DV_N_SIGNALS = ("{} signal", "{} signals")
DV_N_INTERFACES = ("{} interface", "{} interfaces")
DV_CONNECTORS = "Connectors"
DV_CONNECTORS_TIP = "The box connectors of this unit"
DV_COL_CONNECTOR = "Connector"
DV_COL_PART = "Part"
DV_COL_PINS = "Pins"
DV_COL_GENDER = "Gender"
DV_COL_STATE = "State"
DV_NO_CONNECTORS = "This unit has no connectors yet."
DV_CARD_PART = "Part"
DV_CARD_GENDER = "Gender"
DV_CARD_KEYING = "Keying"
DV_CARD_CARRIES = "Carries"
DV_CARD_ALLOCATION = "Pin allocation"
DV_CARD_NOTES = "Notes"
DV_CARD_ANY = "any interface type"
DV_CARD_NONE = "not set"
DV_GENDER = {"male": "male", "female": "female", "unspecified": "not set"}
DV_ALLOC_FIXED = "Fixed pinout: this table is the truth. Every signal of every interface on this connector needs a pin of its name, and pins without a name are never used."
DV_ALLOC_AUTO = "Automatic: Generate puts the signals of the interfaces on free pins."
DV_PINS = "Pins"
DV_PIN_TABLE = "Pins of {}"
DV_PIN_FILTER = "Filter pins"
DV_PIN_FILTER_TIP = "Show the pins that contain these words in any cell"
DV_CONTACT = "Contact"
DV_CONTACT_TIP = (
    "Show the contact size and the termination of each pin. No output or check uses them yet"
)
DV_PIN_COUNT = "{} of {} pins"
DV_PIN_COUNT_ALL = "{} pins"
DV_COL_PIN = "Pin"
DV_COL_SIGNAL = "Signal"
DV_COL_MODE = "Mode"
DV_COL_INTERFACE = "Interface"
DV_COL_DIRECTION = "Direction"
DV_COL_CLASS = "Class"
DV_COL_WIRE = "Wire"
DV_COL_CONTACT_SIZE = "Contact size"
DV_COL_TERMINATION = "Termination"
DV_MODE = {"free": "Free", "fixed": "Fixed", "locked": "Locked"}
DV_MODE_TIP = {
    "free": "Free: Generate may put a signal here; a signal typed here is kept",
    "fixed": "Fixed: the device defines this pin; interfaces connect to the pin of their signal's name",
    "locked": "Locked: Generate never moves this pin",
}
DV_TERMINATION = {"crimp": "crimp", "solder": "solder", "unspecified": ""}
DV_STATE_SPARE = "Spare"
DV_STATE_AUTO = "Auto-filled"
DV_STATE_AUTO_TIP = "Generate put this signal here; it can move at the next Generate"
DV_STATE_LOCKED_PIN = "Locked"
DV_STATE_ERROR = "Error"
DV_STATE_WARNING = "Warning"
DV_STATE_NOTE = "Note"
DV_NOTES = "Notes on this connector"
DV_NOTES_TABLE = "Notes on {}"
DV_NOTES_NONE = "No notes: every check passes."
DV_NOTES_COUNT = ("{} note", "{} notes")
DV_NOTES_TIP = "Double-click or press Enter to select the pin the note is about"
DV_COL_SEVERITY = "Severity"
DV_COL_WHERE = "Where"
DV_COL_CHECK = "Check"
DV_COL_NOTE = "Note"
DV_PREVIEW = "Pinout as exported"
DV_PREVIEW_TABLE = "Pinout as exported"
DV_PREVIEW_HINT = (
    "These are the rows of system/box_pinouts.csv for this unit: what you see is what you ship."
)
DV_WHY_TIP = "Double-click or press Enter to see why the pin is the way it is"
DV_EXPORT_FILTER = "CSV files (*.csv);;Excel workbooks (*.xlsx)"


# ---- Devices view: editing, dialogs, undo steps (custom devices) ----------------------------------
STEP_ADD_DEVICE = "Add device {}"
STEP_ADD_CONNECTOR = "Add connector {}"
STEP_CHANGE_PART_RESIZE = "Change part of {} and resize pins"
STEP_CHANGE_PART_OF = "Change part of {}"
STEP_EDIT_PIN = "Edit pin {}"
STEP_RENAME_PIN = "Rename pin {} to {}"
STEP_ADD_PIN = "Add pin to {}"
STEP_DELETE_PINS = "Delete pins {} of {}"
STEP_PASTE_PINS = "Paste {} into {}"
STEP_CLEAR_SIGNALS = "Clear {} signals of {}"
STEP_SET_MODE = "Set mode of {} pins of {}"
STEP_FILL_PINS = "Fill pins {} from {}"
STEP_ASSIGN_PINS = "Assign pins {} to {}"
STEP_UNASSIGN_PINS = "Unassign pins {} of {}"
STEP_ADD_PART = "Add part {}"
STEP_ADD_TYPE = "Add interface type {}"
A_ADD_DEVICE = "Device…"
A_ADD_DEVICE_TIP = "Add a device: a unit with its own connectors and pins, named in the Devices tab"
DV_NAME = "Device name"
DV_NAME_TIP = "The name of this device. Press Enter to keep it"
DV_SUBSYSTEM_LABEL = "Subsystem"
DV_SUBSYSTEM_TIP = "The subsystem of this device: pick one or type a new one"
DV_CHAIN_LABEL = "Chain"
DV_CHAIN_TIP = "Whether this device is on the nominal chain, the redundant chain or neither"
DV_READ_ONLY_BANNER = (
    "This project is read-only (saved by a newer tool version). Use Save as to make changes."
)
DV_REVISE = "Start new revision…"
DV_REVISE_TIP = "Start a new revision of the released harness that uses this device"
DV_REVISE_TIP_FOR = (
    "Start a new revision of {}, which uses this device; the released revision stays on record"
)
DV_PART_PICKER = "Part for a new connector"
DV_PART_PICKER_TIP = "Search the connector parts of the library; the first entry makes a new part"
DV_NEW_PART = "New part…"
DV_ADD_CONNECTOR = "Add connector"
DV_ADD_CONNECTOR_TIP = (
    "Add a connector with the part chosen above; its pins are numbered from the part's pin count"
)
DV_DELETE_CONNECTOR = "Delete connector"
DV_DELETE_CONNECTOR_TIP = "Delete the selected connector and its pins"
DV_DELETE_CONNECTOR_Q = "Delete connector {} and its pins?"
DV_DELETE_CONNECTOR_IFS = "{} will lose its connector."
DV_DELETE_CONNECTOR_OK = "Delete connector"
DV_DELETE_BLOCKED = (
    "{} cannot be deleted: {} was made by hand (or is released) and has wires on it."
)
DV_OUTDATED = "{} will be out of date."
DV_PICK_PART = "Choose a connector part from the list, or make one with New part."
DV_CARD_PART_TIP = "The library part of this connector. A part with another pin count asks whether to resize the pins"
DV_CARD_GENDER_TIP = "Male or female. Not set means the cable end cannot be checked to fit"
DV_CARD_KEYING_TIP = (
    "The keying of this connector (for example B); it must match the mating connector"
)
DV_CARRIES_EDIT = "Carries…"
DV_CARRIES_TIP = "Choose the interface types this connector is meant for (none means any)"
DV_CARRIES_SUGGEST = "Complete for: {}"
DV_CARRIES_SUGGEST_TIP = "The pins of this connector carry every signal of these interface types: add them to what it carries"
DV_NEW_TYPE_MENU = "New interface type…"
DV_PART_Q = "Change the part of {} to {}?"
DV_PART_RESIZE = "Resize the pins to {}"
DV_PART_SET_GENDER = "Set the gender to {}"
DV_PART_OK = "Change part"
DV_PART_BLOCKED = "The part has {} pins and the connector has {}: pin {} would have to go but is in use. Clear or delete it first, or choose a part with more pins."
DV_ADD_PIN = "Add pin"
DV_ADD_PIN_TIP = "Add pin: add a pin after the current one, numbered with the next free number"
DV_DELETE_PINS = "Delete"
DV_DELETE_PINS_TIP = "Delete pins: delete the selected pins, after showing what they touch"
DV_DELETE_PINS_Q = "Delete pins {}?"
DV_DELETE_PINS_OK = "Delete pins"
DV_FILL = "Fill…"
DV_FILL_TIP = (
    "Put the signals of an interface type (for example CANH, CANL) on the selected pins, in order"
)
DV_ASSIGN = "Assign…"
DV_ASSIGN_TIP = "Assign to interface: put an interface that ends on this device on the selected pins and lock them to it"
DV_UNASSIGN = "Unassign from interface"
DV_PASTE = "Paste"
DV_PASTE_EMPTY = "There is nothing to paste: copy cells from a spreadsheet first."
DV_PASTE_NEEDS_PIN = "A pasted table with a header row needs a Pin column."
DV_PASTE_PICK_CELL = (
    "Click a Pin, Signal, Mode, Contact size or Termination cell first; the paste starts there."
)
DV_PIN_EXISTS = "This connector already has a pin '{}' (names are the same ignoring case)."
DV_TEXT_TOO_LONG = "At most 200 characters."
DV_SIGNAL_EDIT_TIP = "Pick a signal of an interface type or type your own. A name no interface type has cannot be connected to"
# dialogs (devices_dialogs.py)
DVD_PART_TITLE = "New connector part"
DVD_PART_ID = "Part ID"
DVD_PART_ID_TIP = "A short unique name, for example MY-HD-9-F"
DVD_PART_PINS = "Pins"
DVD_PART_PINS_TIP = "The number of contacts of this connector"
DVD_PART_GENDER = "Gender"
DVD_PART_GENDER_TIP = "Female (socket) or male (plug)"
DVD_PART_MAKER = "Manufacturer"
DVD_PART_MAKER_TIP = "Optional"
DVD_PART_NUMBER = "Manufacturer part number"
DVD_PART_NUMBER_TIP = "Optional"
DVD_PART_DESCRIPTION = "Description"
DVD_PART_DESCRIPTION_TIP = (
    "Optional. The gender of a connector is read from this text when it says male or female"
)
DVD_PART_PAIR = "Also make the mating part"
DVD_PART_PAIR_TIP = "Make the other half too, with the opposite gender, and let each name the other"
DVD_PART_MATE = "Mating part ID"
DVD_PART_MATE_TIP = "Leave empty to use the same ID with the other letter (X-F and X-M)"
DVD_PART_NEEDS_ID = "Type an ID for the part."
DVD_PART_NOTE = "A part made here is marked pending and unverified. The tool never approves a part: that stays a decision of whoever owns the parts list."
DVD_PART_OK = "Make part"
DVD_TYPE_TITLE = "New interface type"
DVD_TYPE_ID = "Type ID"
DVD_TYPE_ID_TIP = "A short unique name, for example heater_ctl"
DVD_TYPE_NAME = "Name"
DVD_TYPE_NAME_TIP = "The name people see, for example Heater control"
DVD_TYPE_CATEGORY = "Category"
DVD_TYPE_CATEGORY_TIP = "What kind of interface this is"
DVD_TYPE_SIGNALS = "Signals"
DVD_TYPE_SIGNALS_TIP = "One signal per line: name, then direction (out, in, bidir or passive), then a pair name if it is twisted with another"
DVD_TYPE_SIGNALS_EXAMPLE = "CANH bidir BUS\nCANL bidir BUS\nCANGND passive"
DVD_TYPE_HINT = "One signal per line: its name, then out, in, bidir or passive, then a pair name for signals that are twisted together. The type is marked unverified until someone confirms it."
DVD_TYPE_NEEDS_ID = "Type an ID for the interface type."
DVD_TYPE_OK = "Make interface type"
DVD_FILL_TITLE = "Fill from interface type"
DVD_FILL_PINS = "Selected pins: {}"
DVD_FILL_TYPE = "Interface type"
DVD_FILL_TYPE_TIP = "The signals of this type go on the selected pins in order"
DVD_FILL_PREVIEW = "Signals and pins"
DVD_FILL_FIXED = "These pins are fixed by the device design"
DVD_FILL_FIXED_TIP = (
    "Fixed pins keep their signal; Generate puts each interface on the pin of its signal's name"
)
DVD_FILL_NO_TYPE = "There is no interface type yet. Make one first."
DVD_FILL_OK = "Fill pins"
DVD_NEW_TYPE = "New interface type…"
DVD_NEW_TYPE_TIP = "Define an interface type that is not in the list"
DVD_ASSIGN_TITLE = "Assign to interface"
DVD_ASSIGN_PINS = "Selected pins: {}"
DVD_ASSIGN_INTERFACE = "Interface"
DVD_ASSIGN_INTERFACE_TIP = "An interface that ends on this device"
DVD_ASSIGN_PIN_FOR = "Pin for {}"
DVD_ASSIGN_NONE = "No interface ends on this device yet. Make one with New interface."
DVD_ASSIGN_OK = "Assign pins"
DVD_NEW_INTERFACE = "New interface…"
DVD_NEW_INTERFACE_TIP = "Make an interface from this device to another, then assign it"


# ---- import wizard: a device's pinout (core/pinout_import.py) ---------------------------------------
IMP_KIND_PINOUT = "Device pinout"
IMP_KIND_PINOUT_TIP = "A pinout table (CSV or XLSX) with one pin per row: connector, pin, signal, mode, contact size, termination. Creates or updates the connectors of one device; columns the project cannot store are left out."
IMP_NEXT_PINOUT = "Generate harnesses again to connect interfaces to the pins; signals that no interface type has stay free text."
IMP_PIN_DEVICE = "Device"
IMP_PIN_DEVICE_TIP = "The unit whose connectors the table defines, or a new device"
IMP_PIN_DEVICE_NEW = "New device…"
IMP_PIN_NEW_NAME = "Name of the new device"
IMP_PIN_NEW_NAME_TIP = "Needed when the device is new; its ID is the next free DEV number"
IMP_PIN_SUBSYSTEM = "Subsystem of the new device"
IMP_PIN_SUBSYSTEM_TIP = "Optional; the most used subsystem when empty"
IMP_PIN_PART = "Part for new connectors"
IMP_PIN_PART_TIP = (
    "A connector part of the library, used for every new connector that has no part of its own"
)
IMP_PIN_PART_NONE = "(none)"
IMP_PIN_PARTS = "Part for each connector"
IMP_PIN_PARTS_TIP = "Optional: one NAME=PART per line, for example J1=MY-HD-9-F, for new connectors that need another part"
IMP_PIN_GENDER = "Gender of new connectors"
IMP_PIN_GENDER_TIP = "Male or female; the gender of the part when not set"
IMP_PIN_GENDER_PART = "(the part's)"
IMP_PIN_CONNECTOR = "Connector for rows without one"
IMP_PIN_CONNECTOR_TIP = "Used when the table has no Connector column (J01 when empty)"
IMP_PIN_REPLACE = "Drop the pins of an existing connector that the table does not name"
IMP_PIN_REPLACE_TIP = "Off: the pins of the table are merged into the connector and the others stay"
IMP_PIN_NEEDS_PIN = "Match a column to Pin: the table needs one."
IMP_PIN_NEEDS_DEVICE = "Name the new device, or choose an existing one."
IMP_P_PIN_SIGNAL = "no interface type has this signal ({0}); it stays free text"
# ---- retiring the bottom tabs and the Palette: where their functions went ---------------------
TAB_INTERFACES = "Interfaces"
TAB_INTERFACES_TIP = "Every interface as a table you can edit with the keyboard (Ctrl+Shift+T)"
A_GO_INTERFACES = "Go to Interface table"
TODO_HEADING = "To do ({})"
A_CHANGES = "Show changes of harness…"
A_HISTORY = "Show change log of harness…"
A_DELETE_HARNESS = "Delete harness…"
HV_MORE = "More"
HV_MORE_TIP = "Changes since a baseline, the change log, and deleting this harness"

# ---- Fix all (n) and the command palette overlay (SH-24, SH-11) -------------------------------
CHECKS_FIX_ALL = "Fix all ({})"
CHECKS_FIX_ALL_TIP = (
    "Apply the one-click fix of every open problem that has one ({}), as one step: {}. "
    "Undo takes all of them back."
)
CHECKS_FIX_ALL_NONE = "Nothing to fix automatically: no open problem has a one-click fix."
STEP_FIX_ALL = "Fix all ({})"
FIX_ALL_DONE = "Fixed {} in one step: {}."
FIX_ALL_SKIPPED = " {} left alone: {}"
FIX_ALL_NOTHING = "Nothing could be fixed automatically. {}"
COMMANDS_HELP = "Type to search, Up and Down to choose, Enter to run, Esc to close."
COMMANDS_KEYS = "Up, Down: choose · Enter: run · Esc: close"

# ---- UI overhaul M2: the shell (navigation rail, areas, top bar, status bar, Problems panel) ----
AREA_HOME = "Home"
AREA_MODEL = "Model"
AREA_CHECKS = "Checks"
AREA_DRAWINGS = "Drawings"
AREA_OUTPUTS = "Outputs"
AREA_REVISIONS = "Revisions"
AREA_SETTINGS = "Settings"
AREA_HOME_TIP = "Home: your project, new and recent projects, the examples"
AREA_MODEL_TIP = (
    "Model: the diagram of units and interfaces, and the devices with their connectors and pins"
)
AREA_CHECKS_TIP = "Checks: the design rules, what passed, what failed and what could not be checked"
AREA_DRAWINGS_TIP = "Drawings: the harness drawings with their connectors, pins and wires"
AREA_OUTPUTS_TIP = "Outputs: the wire list, pinouts, bill of materials and the other tables"
AREA_REVISIONS_TIP = "Revisions: reviews, releases and what changed between revisions"
AREA_SETTINGS_TIP = "Settings: theme, interface size and the project's configuration"
RAIL_NAME = "Areas"
RAIL_COLLAPSE = "Show icons only"
RAIL_EXPAND = "Show the names"
CRUMB_SEPARATOR = "  ›  "
CRUMBS_NAME = "Where you are"
TB_REVISION_NONE = ""
TB_REVISION = "Revision {}"
TB_REVISION_TIP = "The revision of the released harnesses ({})"
TB_SAVE_SAVED = "Saved"
TB_SAVE_UNSAVED = "Unsaved changes"
TB_SAVE_DRAFT = "Not saved to a folder yet"
GO_HOME = "Go to Home"
GO_SETTINGS = "Go to Settings"
HOME_TITLE = "Home"
HOME_PROJECT = "Current project"
HOME_NO_PROJECT = "No project folder yet: the design is open in memory."
HOME_ACTIONS = "Start"
HOME_NEW = "New project…"
HOME_OPEN = "Open project…"
HOME_EXAMPLE = "New from an example…"
HOME_SAMPLE = "Open the sample project"
HOME_SUMMARY = "{} units, {} interfaces, {} harnesses"
SETTINGS_TITLE = "Settings"
SETTINGS_APPEARANCE = "Appearance"
SETTINGS_THEME = "Theme"
SETTINGS_THEME_SYSTEM = "Follow the system"
SETTINGS_THEME_LIGHT = "Light"
SETTINGS_THEME_DARK = "Dark"
SETTINGS_SCALE = "Interface size"
SETTINGS_EDITOR = "Editing"
SETTINGS_MODE = "Mode"
SETTINGS_PROJECT = "Project"
SETTINGS_PROJECT_TEXT = (
    "The project's configuration files and engineering values are edited under Checks."
)
SETTINGS_PROJECT_BUTTON = "Open the engineering values…"
JOB_NAME = "Background jobs"
JOB_IDLE = "No background job"
JOB_RUNNING = "{}…"
JOB_CANCEL = "Cancel"
JOB_CANCEL_TIP = "Cancel the running job"
JOB_LAST_CHECK = "Last check: {}"
JOB_LAST_CHECK_NONE = "No check yet"
OFFLINE_TEXT = "Offline"
OFFLINE_TIP = (
    "This program works offline: nothing leaves this computer, no account, no update check."
)
PROBLEMS_PANEL_TITLE = "Problems"
PROBLEMS_PANEL_NAME = "Problems of the project"
PROBLEMS_SHOW = "Show the problems panel"
PROBLEMS_HIDE = "Hide the problems panel"
PROBLEMS_BUTTON = "Problems ({})"
PROBLEMS_EMPTY = "No problems. Every rule that could be checked passed."
PROBLEMS_COL_SEVERITY = "Severity"
PROBLEMS_COL_RULE = "Rule"
PROBLEMS_COL_OBJECT = "Object"
PROBLEMS_COL_MESSAGE = "Message"
PROBLEMS_FILTER_ALL = "All"

PANE_PROBLEMS = "Problems panel"
SHELL_RESET_DONE = "The window layout is back to the default."
TB_REVISION_NAME = "Revision"
JOB_GENERATING = "Generating harnesses"
JOB_EXPORTING = "Exporting outputs"
JOB_ARRANGING = "Arranging the diagram"
JOB_CHECKING = "Checking the design rules"
A_PROBLEMS = "Problems panel"
A_PROBLEMS_TIP = "Show or hide the list of all open problems at the bottom of the window"

# ---- UI overhaul M3: the workflow stepper, Home, the lock banner ------------------------------------
STEP_GENERATE = "Generate"
STEP_REVIEW = "Check"
STEP_RELEASE = "Release"
STEP_GENERATE_RUNNING = "generating the harnesses"
STEP_GENERATE_DONE = "the harness plans match the design"
STEP_GENERATE_STALE = "the design changed after the last generation"
STEP_GENERATE_TODO = "not generated yet"
STEP_GENERATE_FIRST = "generate the harnesses first"
STEP_READ_ONLY = "this project is open read-only"
STEP_REVIEW_RUNNING = "the design rules are being checked"
STEP_REVIEW_TODO = "not checked yet (F5 runs the rules now)"
STEP_REVIEW_FAILED = "{} rule(s) failed"
STEP_REVIEW_PASSED = "every rule that could be checked passed."
STEP_REVIEW_UNCHECKED = "{} rule(s) could not be checked yet."
STEP_IN_REVIEW = "{} harness(es) in review."
STEP_REVIEW_FIRST = "check the design first."
STEP_RELEASE_ALL = "all {} harness(es) released"
STEP_RELEASE_COUNT = "{} of {} released"
TB_RELEASE = "Release…"
TB_RELEASE_TIP = "Release a harness: lock its data and outputs as a numbered revision"
TB_STEPS_NAME = "Workflow: generate, check, release"
LOCK_BANNER_ONE = (
    "Harness {} is released (revision {}) and locked. To change it, start a new revision."
)
LOCK_BANNER_MANY = (
    "{} harnesses are released and locked. To change one, start a new revision of it."
)
LOCK_BANNER_ACTION = "Start new revision…"
LOCK_BANNER_SHOW = "Show the revisions"
HOME_RECENT = "Recent projects"
HOME_RECENT_NONE = "No recent projects yet. Create one or open an example below."
HOME_EXAMPLES = "Examples"
HOME_OPEN_BTN = "Open"
HOME_REMOVE = "Remove from the list"
HOME_MISSING = "The folder is gone: {}"
HOME_EXAMPLE_FLATSAT = "Try the flatsat example"
HOME_EXAMPLE_FLATSAT_TIP = "Open a copy of the 23-unit flatsat example (example numbers, not engineering data) in your Documents folder"
HOME_EXAMPLE_OPEN = "Open this example"
HOME_COUNTS = "{} units · {} interfaces · {} harnesses"
HOME_DRAFT = "{} draft"
HOME_IN_REVIEW = "{} in review"
HOME_RELEASED = "{} released"

# ---- UI overhaul M3: empty states ------------------------------------------------------------
EMPTY_FILTERED_TITLE = "No row matches"
EMPTY_FILTERED_HINT = "Change or clear the filter to see the rows again."
EMPTY_INTERFACES_TITLE = "No interfaces yet"
EMPTY_INTERFACES_HINT = "An interface is a pair of connectors with a signal between them. Add one, or import a table with File > Import."
EMPTY_INTERFACES_ACTION = "New interface"
EMPTY_RELEASES_TITLE = "Nothing reviewed or released yet"
EMPTY_RELEASES_HINT = "Submit a draft for review or release it, and the step appears here."
EMPTY_CHECKS_TITLE = "Nothing was found"
EMPTY_CHECKS_HINT = "The rule check found no open problems. Run it again after the next change."
EMPTY_DEVICES_TITLE = "No devices yet"
EMPTY_DEVICES_HINT = "Devices come from the library or from an import."
EMPTY_LIST_TITLE = "Nothing to list yet"
EMPTY_LIST_HINT = "Generate the harnesses and the list fills in."

# ---- UI overhaul M4: model editors as sheets -------------------------------------------------
SHEET_PASTED = "{0} cell(s) pasted."
SHEET_PASTED_SKIPPED = " {0} left out (read-only column or past the end of the table)."
SHEET_COLUMNS_MENU = "Show columns"
TAB_UNITS = "Units"
TAB_UNITS_TIP = (
    "Every unit as a table: edit names and notes in place, paste from Excel (Ctrl+Shift+J)"
)
UNIT_TABLE = "Unit table"
UNIT_COLUMNS = ["ID", "Name", "Subsystem", "Zone", "Chain", "Interfaces", "Connectors", "Notes"]
STEP_PASTE = "Paste {0} cell(s)"
EMPTY_UNITS_TITLE = "No units yet"
EMPTY_UNITS_HINT = (
    "Add a unit from the palette on the diagram, or import a table with File > Import."
)
A_GO_UNITS = "Go to Unit table"
UNIT_FILTER_PLACEHOLDER = "Filter by ID, name, subsystem, zone or notes"
NEW_UNIT = "New unit"

# ---- UI overhaul M5: Checks and Problems ------------------------------------------------------
CHECKS_STALE = "Out of date"
CHECKS_STALE_TIP = "The design changed after these results. Press Check again to update them."
CHECKS_STALE_SOON = "The design changed after these results; checking again in a moment."
PROBLEMS_GO_TO = "Go to {0}"
PROBLEMS_DETAILS = "Details and fixes"
PROBLEMS_MENU = "Problem"

# ---- UI overhaul M7: the import wizard ------------------------------------------------------------
IMP_READING = "Reading {0:,} rows in the background…"
IMP_READING_NAME = "Reading the rows"
IMP_READING_CANCELLED = (
    "Reading the rows was cancelled. Change a choice or press Back to start again."
)
IMP_PASTE_TEXT = "Paste table text instead…"
IMP_PASTE_TEXT_TIP = (
    "Interfaces only: paste the rows of a table (CSV text) instead of choosing a file"
)

# ---- UI overhaul M8: Outputs files and Revisions --------------------------------------------------
OUT_FILES_NAME = "Exported files"
OUT_FILES_TITLE = "Exported files"
OUT_COLUMNS = {
    "file": "File", "doc": "Document", "scope": "Harness", "format": "Format",
    "size": "Size", "when": "Written", "sha": "SHA-256", "state": "State",
}  # fmt: skip
OUT_STATE_MATCHES = "Matches export"
OUT_STATE_CHANGED = "Changed since export"
OUT_STATE_MISSING = "Missing"
OUT_STATE_UNLISTED = "Not in the export"
OUT_STATE_MANIFEST = "Manifest"
OUT_REASON = {
    OUT_STATE_MATCHES: "The file on disk has the SHA-256 the export recorded.",
    OUT_STATE_CHANGED: "The file on disk is not the one the export wrote (its SHA-256 differs from the manifest).",
    OUT_STATE_MISSING: "The manifest lists this file but it is not in the folder.",
    OUT_STATE_UNLISTED: "The folder holds this file but the manifest does not list it.",
    OUT_STATE_MANIFEST: "The list of files, with their SHA-256, that the export wrote beside them.",
}
OUT_COPY = "Copy to folder…"
OUT_COPY_TIP = "Copy the selected files, as they are on disk, to an empty folder"
OUT_VERIFY = "Verify"
OUT_VERIFY_TIP = "Read the folder again and compare every file with the manifest"
OUT_READING = "Reading the files…"
OUT_READ_FAILED = "The outputs folder could not be read: {0}"
OUT_SUMMARY = "{0} files in {1}, made from design {2}"
OUT_SUMMARY_BAD = "; {0} differ from the export"
OUT_EMPTY_TITLE = "Nothing exported yet"
OUT_EMPTY_HINT = "Export the outputs (Export…) and the files appear here with their checksums."
REL_LOCKS = "{0} revision {1} is released and locks {2}. Start a new revision to change them."
REL_LOCK_KINDS = {
    "unit": "{0} unit(s)",
    "interface": "{0} link(s)",
    "box_connector": "{0} unit connector(s)",
    "config": "{0} configuration file(s)",
}

# ---- UI overhaul M9: Settings ------------------------------------------------------------------
SETTINGS_SECTIONS_NAME = "Settings sections"
SETTINGS_SECTION_APPEARANCE = "Appearance"
SETTINGS_SECTION_EDITING = "Editing"
SETTINGS_SECTION_PROJECT = "Project"
SETTINGS_SECTION_SHORTCUTS = "Keyboard shortcuts"
SETTINGS_SECTION_ABOUT = "About"
SETTINGS_SECTION_LICENCES = "Licences"
SETTINGS_REDUCE_MOTION = "Reduce motion"
SETTINGS_REDUCE_MOTION_TIP = "Turn off the fades and slides of menus, lists and tooltips"
SETTINGS_SCALE_HINT = "Changes the size of text and controls at once. 100 % is the usual size."
SETTINGS_SNAP = "Snap units to the grid"
SETTINGS_SNAP_TIP = "Units jump to the grid while you drag them (hold Alt to drag freely)"
SETTINGS_LABELS = "Show every link label"
SETTINGS_LABELS_TIP = "Name every link in the diagram, however many there are"
SETTINGS_SHORTCUTS_TEXT = (
    "Every key that does something in the window. They are fixed and cannot be changed."
)
SETTINGS_SHORTCUTS_FILTER = "Filter the shortcuts…"
SETTINGS_SHORTCUTS_FILTER_NAME = "Filter shortcuts"
SHORTCUT_COLUMNS = ("Action", "Shortcut")
SHORTCUTS_EMPTY = "No shortcut matches"
SHORTCUTS_EMPTY_HINT = "Clear the filter to see all of them."
SHORTCUTS_TABLE_NAME = "Keyboard shortcuts"
SHORTCUTS_EXTRA = (
    ("Table: edit the selected cell", "Enter or F2"),
    ("Table: keep the old text of a cell", "Esc"),
    ("Table: paste a block of cells", "Ctrl+V"),
    ("Table: copy the selected cells", "Ctrl+C"),
    ("Diagram: place a unit without snapping", "Alt while dragging"),
    ("Diagram: pan", "Middle button, or Space, and drag"),
    ("Dialog: go to the next control", "Tab"),
)
ABOUT_TITLE = "Harness Design Studio"
ABOUT_VERSION = "Version {0}"
ABOUT_OFFLINE = "Offline spacecraft harness design tool. No data ever leaves this computer."
ABOUT_RUNTIME = "Python {0}, Qt {1}, PySide6 {2}"
ABOUT_SETTINGS_FILE = "Your settings are kept in {0}"
ABOUT_LICENCE_PROJECT = (
    "Licence of this program: placeholder, not yet chosen (docs/DECISIONS.md, D-02)."
)
LICENCES_TEXT = (
    "The fonts and icons that are part of the interface, and the library the windows are made with."
)
LICENCES_PICK = "Component"
LICENCES_TABLE_NAME = "Licences of the interface components"
LICENCES_TEXT_NAME = "Licence text"
LICENCE_COLUMNS = ("Component", "Licence", "Used for")
LICENCE_QT = (
    "Qt for Python (PySide6, shiboken6) is used under the GNU Lesser General Public Licence 3.0, as an "
    "unmodified library. The licence text, and the GPL 3 text it refers to, are in the LICENSES folder "
    "installed with the program (a package) or with the PySide6 package (an installation from the "
    "source). The source of Qt for Python is available from the Qt Project (https://code.qt.io)."
)
LICENCE_MISSING = "The licence file of {0} is missing from this installation."

# ---- 1.4.0 M1: edit a wire -----------------------------------------------------------------------
HV_EDIT_TAB = "Edit wire"
WIRE_EDIT_NONE = "Select a wire in the table or in the drawing to change it."
WIRE_EDIT_ONE = "Wire {0}"
WIRE_EDIT_MANY = "{0} wires selected"
WIRE_EDIT_FROM_TO = "{0} to {1}"
WIRE_GAUGE = "Gauge (AWG)"
WIRE_TYPE = "Type"
WIRE_COLOUR = "Colour"
WIRE_LENGTH = "Length (m)"
WIRE_LABEL = "Label"
WIRE_NOTE = "Note"
WIRE_VARIOUS = "various"
WIRE_GAUGE_TIP = "The wire gauge, a whole number. Setting it keeps it when you generate again."
WIRE_TYPE_TIP = "The wire part from the library. Setting it keeps it when you generate again."
WIRE_COLOUR_TIP = "The wire colour (IEC 60757 names, or your own text). Setting it keeps it when you generate again."
WIRE_LENGTH_TIP = "The length of the wire in metres. Setting it keeps it when you generate again."
WIRE_LABEL_TIP = "Text for the wire labels instead of the signal name. Always kept."
WIRE_NOTE_TIP = "Your remark about the wire. It appears in the wire list. Always kept."
WIRE_APPLY = "Apply"
WIRE_APPLY_TIP = "Apply the changed fields to the selected wires (Ctrl+Enter)"
WIRE_RESET = "Reset to generated"
WIRE_RESET_TIP = (
    "Give the selected wires back to generation: the next Generate sets their gauge, type, colour "
    "and length from the design again. Label and note stay."
)
WIRE_STATE_GENERATED = "Generated: Generate sets the gauge, type, colour and length."
WIRE_STATE_KEPT = "Your values: Generate keeps the gauge, type, colour and length."
WIRE_STATE_MIXED = "Some of the selected wires are yours, some are generated."
WIRE_STATE_RELEASED = "{0} is released (revision {1}). Start a new revision to change its wires."
WIRE_STATE_READ_ONLY = "This project is read-only."
STEP_EDIT_WIRES = "Edit wires"
STEP_RESET_WIRES = "Reset wires"
WIRE_APPLIED = "Changed {0}."
WIRE_RESET_DONE = "Reset {0}; Generate sets their values."
WIRE_NOTHING_CHANGED = "Nothing to change."

# ---- 1.4.0 M2: wires that a person draws ----------------------------------------------------------
WIRE_ENDS = "Ends"
WIRE_FROM = "From"
WIRE_TO = "To"
WIRE_CONNECTOR = "Connector"
WIRE_PIN = "Pin"
WIRE_END_TIP = (
    "The connector and pin where the wire {0}s. You can move the ends of a wire that you drew."
)
WIRE_NEW = "New wire"
WIRE_SIGNAL = "Signal"
WIRE_SIGNAL_TIP = "A name for the signal the wire carries (optional), for example HEATER."
WIRE_ADD = "Add wire"
WIRE_ADD_TIP = "Add a wire that you draw between the two pins. Generate keeps it as it is."
WIRE_DELETE = "Delete wire"
WIRE_DELETE_TIP = (
    "Delete the selected wires that you drew (a generated wire goes when its interface goes)"
)
WIRE_STATE_MANUAL = "You drew this wire: Generate keeps it as it is."
WIRE_STATE_MANUAL_MANY = "You drew these wires: Generate keeps them as they are."
STEP_ADD_WIRE = "Add wire"
STEP_DELETE_WIRES = "Delete wires"
WIRE_NEW_NO_HARNESS = "Choose a harness first."

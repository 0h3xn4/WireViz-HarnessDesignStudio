"""All user-visible UI strings live here so translation is possible later."""

APP_TITLE = "Harness Design Studio"
EMPTY_STATE = (
    "No project open. Create a new project, start from an example or open an existing one to begin."
)
EMPTY_CANVAS = "Your diagram is empty.\nAdd your first unit from the palette on the left."
CANVAS = "Block diagram canvas"
CANVAS_HELP = "Tab and Shift+Tab move between units and links, Enter selects, Shift+arrow keys move the selected unit, Escape clears the selection. The Interface table tab lists every interface and is the screen-reader friendly alternative."
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
        "palette",
        "Start here: add units from the palette. Each is a box in your system, like a computer or a wheel.",
    ),
    (
        "canvas",
        "This is your block diagram. Drag units to move them. The lane a unit sits in is its zone.",
    ),
    (
        "types",
        "To connect two units, pick an interface type, then click the two units. Only valid choices light up.",
    ),
    (
        "bottom",
        "Problems and a to-do list appear here and update as you work. Click any line to jump to the item.",
    ),
    (
        "generate",
        "Generate harnesses builds the harness plans from this diagram. You see a preview first, and one Undo takes it back.",
    ),
]

PALETTE = "Palette"
ADD_UNIT = "Add a unit"
ADD_UNIT_TIP = "Add a {} to the diagram"
CONNECT_WITH = "Connect with"
CONNECT_HELP = "Pick an interface type, then click the first and the second unit."
BRING_IN_DATA = "Bring in data"
IMPORT_BUTTON = "Import interfaces from CSV / XLSX…"
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
TODO = "To-do"
INTERFACE_TABLE = "Interface table"
HARNESS_PLANS = "Harness plans"
NO_PROBLEMS = "No problems. Nice work."
WAIVED = "Waived"
SEV_WARNING = "⚠ Warning:"
SEV_ERROR = "✕ Error:"
SEV_INFO = "ⓘ Info:"
SHOW = "Show"
REQUIREMENT_LABEL = "Requirement: {}"
WAIVE = "Waive…"
ALL_DONE = "Nothing left to do."
FILTER_PLACEHOLDER = "Filter by ID, unit or type"
NEW_INTERFACE = "＋ Interface…"
NO_PLANS_TITLE = "No harness plans yet."
NO_PLANS_BODY = (
    "No harnesses yet. Build the diagram, resolve the problems, then press Generate harnesses."
)

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
TOOL_CONNECT_TIP = "Connect two units (C)"
HINT = "Hint"
ZOOM_IN = "Zoom in"
ZOOM_OUT = "Zoom out"
FIT = "Fit"
NOMINAL = "nominal"
REDUNDANT = "redundant"
AUTO_LEGEND = "auto-filled, not reviewed"
PROBLEMS_AND_STATUS = "Problems and status"
TOOLBAR = "Main toolbar"
SEARCH_BUTTON = "Search / commands  Ctrl+K"
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
PLANS_COLUMNS = ["Harness", "Name", "Wires", "Interfaces", "Status", "Origin"]
WIRE_COLUMNS = ["Wire", "Signal", "From", "To", "AWG", "Length (m)", "Colour", "Locked"]
EXPLAIN = "Why is it like this?"
EXPLAIN_NONE = "No explanation recorded (this item was made by hand)."
ALL_SAVED = "All changes saved"
UNSAVED = "Unsaved changes (autosaved to the recovery journal)"


def units_text(n: int) -> str:
    return f"{n} unit" if n == 1 else f"{n} units"


def interfaces_text(n: int) -> str:
    return f"{n} interface" if n == 1 else f"{n} interfaces"


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
A_SCALE = "UI scale"
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
DRC_DONE = "Design rules: all {} rules checked."
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

REVIEW = "Submit for review"
REVIEW_TIP = "Mark the selected draft harness as ready for review"
RELEASE = "Release…"
RELEASE_TIP = "Release the selected harness: records a baseline and the change log, and locks it"
NEW_REV = "New revision…"
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
RELEASED_LOCKED = "released (locked)"
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
HARNESS_LIST = "Harnesses"
WIRE_LIST = "Wires of the selected harness"
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
TAB_DRAWING = "Drawing"
OUTLINE = "Outline"
OUTLINE_HELP = "Every unit with its interfaces as a tree. Arrow keys move, Enter selects; the selection follows the diagram."
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
BOTTOM_TABS = "Problems, to-do list, interfaces, harness plans and outline"
ARRANGE_LABEL = "Arrange diagram"
REVIEW_SUBMITTED = "{} submitted for review."
NEW_REV_STARTED = "New revision of {} started; it can be edited again."
WIRE_COLOURS_LABEL = "Set wire colours"
CHAIN_HELP = "Chain must be nominal, redundant or none."
INTERFACE_COLUMNS = ["ID", "Name", "Type", "From", "To", "Chain", "Max A", "Requirement"]
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
HARNESS_GENERATED = "generated"
HARNESS_BY_HAND = "by hand"
PROGRESS_VERIFY = "Independent check"
FOLDER_UNUSABLE = "the folder cannot be used"
TABLE_FILES = "Tables (*.csv *.xlsx)"

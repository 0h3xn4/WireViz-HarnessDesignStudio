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
# ==== Checks view, engineering value dialog, pending values link (ux/checks) ======================
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
TAB_PALETTE = "Palette"
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
TB_GENERATE = "Generate harnesses"
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
PANELS_HIDDEN_SHORT = "The window is short, so the bottom panel is hidden to keep the diagram large. Use the View menu to show it."
CHECK_STARTED = "Checking the design rules…"
CHECK_FINISHED = "Checks finished: {failed} failed · {unchecked} not checked."
CHECK_FINISHED_CLEAN = "Checks finished: nothing failed · {unchecked} not checked."
CHECK_SHOW = "Show checks"
PALETTE_NO_MATCH = "No command matches."
PANE_CANVAS = "Diagram"
PANE_TREE = "Project panel"
PANE_INSPECTOR = "Inspector"
PANE_BOTTOM = "Bottom panel"
PANE_FOCUSED = "{} has the keyboard focus"
M_DESIGN = "&Design"

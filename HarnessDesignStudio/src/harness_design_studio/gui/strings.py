"""All user-visible UI strings live here so translation is possible later."""

APP_TITLE = "Harness Design Studio"
EMPTY_CANVAS = "Your diagram is empty.\nAdd your first device with the button below, or with Add in the project panel. Press Ctrl+K to find a command, or bring in a table with File > Import."
CANVAS = "Block diagram canvas"
CANVAS_HELP = "Tab and Shift+Tab move between devices and links, Enter shows the item in the harness plans, Space selects it, Ctrl+A selects everything, Shift+arrow keys move the selected devices, Ctrl+F finds, Escape clears the selection. The Interface table tab lists every interface and is the screen-reader friendly alternative."
MINIMAP = "Minimap: click to move the view"

GLOSSARY: list[tuple[str, str]] = [
    (
        "Harness",
        "A bundle of wires with connectors at the ends that carries signals between devices. Every harness gets its own drawing and wire list.",
    ),
    (
        "Interface",
        "A logical connection between two devices, such as RS-422 between the computer and a wheel. The tool turns interfaces into wires.",
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
        "A place on the spacecraft (a panel or deck). Devices in different zones usually need different harnesses.",
    ),
]

TOUR_STEPS: list[tuple[str, str]] = [
    (
        "add",
        "Start here: press Add in the project panel and pick Device. Each device is a box in your system, like a computer or a wheel.",
    ),
    (
        "canvas",
        "This is your block diagram. Drag devices to move them. The lane a device sits in is its zone.",
    ),
    (
        "types",
        "To connect two devices, press Connect and click the two devices. The Link connectors window opens and pairs their pins by name. To connect by interface type instead, use the arrow next to Connect, or Edit > Connect with an interface type.",
    ),
    (
        "problems",
        "Problems and a to-do list appear in the Problems tab here and update as you work. Click any line to jump to the item.",
    ),
    (
        "generate",
        "Generate harnesses builds the harness plans from this diagram. You see a preview first, and one Undo takes it back.",
    ),
    (
        "role",
        "The bar on the left lists the areas of the program. What it lists depends on your role: change the role any time in View > Role.",
    ),
]

PROPERTIES = "Properties"
NOTHING_SELECTED = (
    "Select a device or an interface to see its details. The rest of the diagram fades, so you can "
    "follow its links."
)
UNIT = "Device"
INTERFACE = "Interface"
FIELD_ID = "ID"
FIELD_NAME = "Name"
FIELD_CHAIN = "Chain (nominal / redundant)"
CHAIN_TIP = "Nominal is the main chain, redundant is the backup"
FIELD_ZONE_AUTO = "Zone (set by where you place the device)"
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
FILTER_PLACEHOLDER = "Filter by ID, device or type"
NEW_INTERFACE = "＋ Interface…"

CANCEL = "Cancel"
CLOSE = "Close"
ADD = "Add"
WAIVE_TITLE = "Waive this warning?"
WAIVE_PROMPT = "Justification (required, shown in reports)"
WAIVE_OK = "Waive with justification"
WAIVE_TOO_SHORT = "Please explain why this is acceptable (at least 10 characters)."
NEW_INTERFACE_TITLE = "New interface"
NEW_INTERFACE_NOTE = "Connectors are chosen for you and marked Auto until you confirm them. Devices that cannot take this type are shown disabled with the reason."
FIELD_TYPE = "Interface type"
IMPORT_TITLE = "Import interfaces"
IMPORT_STEPS = "Step 1: open a .csv or .xlsx file, or paste CSV text. Step 2: check the column matching. Step 3: read the preview. Nothing changes until you confirm."
OPEN_FILE = "Open file…"
NO_FILE = "No file chosen"
CSV_CONTENT = "CSV content"
CSV_PLACEHOLDER = "Interface,Type,From device,To device,Redundancy\nIF-010,RS-422,OBC,RW1,nominal"
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
TOOL_CONNECT_TIP = "Connect two devices pin by pin (C): click the first device, then the second. The arrow next to it is the older way, by interface type."
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
    return f"{n} device" if n == 1 else f"{n} devices"


def interfaces_text(n: int) -> str:
    return f"{n} interface" if n == 1 else f"{n} interfaces"


def problems_text(n: int) -> str:
    return f"{n} problem" if n == 1 else f"{n} problems"


SELECTED = "Selected: {}"
NOTHING_SEL = "Nothing selected"
A_NEW = "New project…"
A_NEW_EXAMPLE = "New project from an example…"
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
M_ADD_UNIT = "Add device"
ADD_UNIT_PREFIX = "Add device:"
CONNECT_PREFIX = "Connect with"
GO_TO_UNIT = "Go to device"
GO_TO_INTERFACE = "Go to interface"
ZONE_NAME = "Zone name"
DELETE_TITLE = "Delete {}?"
DELETE_BODY = "<p>This will also remove:</p><ul><li>{n} interface{s}{ifs}</li><li>{c} connector(s) of the device</li></ul><p>You can undo this with Ctrl+Z.</p>"
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
RELEASE_DONE = "{0} released. Export the outputs again so they show the released status."
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
PANELS_HIDDEN = "The window is narrow, so the project panel and properties are hidden. Widen the window or use the View menu to show them."
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
ARRANGE_DONE = "Diagram arranged: devices stay in their lanes, ordered to shorten links. Undo restores the old positions."
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
WHY_SELECT_UNIT = "Select a device first."
WHY_IS_REDUNDANT = "This device is already a redundant copy."
WHY_HAS_REDUNDANT = "This device already has a redundant copy: {0}."
REDUNDANT_TIP = "Make a redundant copy of the selected device (the same as setting the number of these devices to 2 in the Devices tab)"
DELETE_TIP = "Delete the selected item (shows what it affects first)"
GEN_NO_INTERFACES = (
    "There is nothing to generate yet. Add devices and connect them with interfaces first."
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

CONNECTOR_AT_END = "Connector at the {} end, device {}"
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
UNIT_WORD = "device"
CONNECT_FIRST = "Click the first {} for {}."
CONNECT_NONE_FREE = (
    "No other device has a free {} connector. Pick another type, or add a device that supports it."
)
CONNECT_SECOND = "Now click the second {}. Valid ones are highlighted."
CLICK_CONNECTOR = "Click a connector (the small square) on the device."
PICK_TYPE_SHORT = "Pick a type"
PICK_TYPE_FIRST = "Pick an interface type first."
IF_ADDED = "Interface {} added."
IF_ADDED_AUTO = " Connectors were chosen for you and are marked Auto until you confirm them."
DELETED = "Deleted {}."
NOW_IN_ZONE = "{} is now in {}."
REDUNDANT_SKIPPED = " {} interface(s) could not be mirrored (no free connector): {}."
REDUNDANT_DONE = "Created {} and mirrored its interfaces (names end in -R).{}"
WAIVED_TOAST = "Waived. The justification will appear in the DRC report."
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
STEP_IMPORT = "Import {} interfaces"
# words on the device pictures and in the lists
TAG_FROM = "FROM"
TAG_NOMINAL = "NOMINAL"
TAG_REDUNDANT = "REDUNDANT"
NO_FREE_CONNECTOR = "No free {} connector"
NO_TYPE = "No type"
AND_MORE = "… and {} more"
PROGRESS_VERIFY = "Independent check"
FOLDER_UNUSABLE = "the folder cannot be used"
TABLE_FILES = "Tables (*.csv *.tsv *.json *.xlsx)"

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
STATUS_HASH = "Model hash"

# ---- diagram canvas: selection, navigation, search, menus (block appended for the canvas work) ----
READ_ONLY_REFUSAL = (
    "This project is read-only, so nothing was changed. Use Save as to make a copy you can edit."
)
STEP_DELETE_MANY = "Delete {} items"
DELETED_MANY = "Deleted {} items."
STEP_MOVE_MANY = "Move {} devices"
STEP_ALIGN = "Align devices"
STEP_DISTRIBUTE = "Space devices evenly"
STEP_DUPLICATE = "Duplicate {}"
STEP_DUPLICATE_MANY = "Duplicate {} devices"
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
WHY_NEED_TWO_UNITS = "Select at least two devices."
WHY_NEED_THREE_UNITS = "Select at least three devices."
WHY_NEED_UNIT_SELECTED = "Select a device first."
DUPLICATE_TIP = "Copy the selected devices with their connectors (Ctrl+D)"
SELECT_ALL_TIP = "Select every device and link in the diagram (Ctrl+A)"
FIND_TIP = "Find a device or link by ID, name, connector or type (Ctrl+F)"
FIT_TIP = "Show the whole diagram (F)"
ZOOM_100_TIP = "Real size, 100 % (Ctrl+0)"
ZOOM_SELECTION_TIP = "Fill the view with the selection (Shift+F)"
ARRANGE_TIP = "Tidy the diagram: order the devices to shorten and uncross links (Ctrl+Shift+L)"
ZOOM_LEVEL_NAME = "Zoom level"
ZOOM_LEVEL_TIP = "Zoom level of the diagram. Click to go back to 100 % (Ctrl+0)."
ZOOM_PERCENT = "{} %"
ARRANGING = "Arranging the diagram"
# find in diagram
SEARCH_NAME = "Find in diagram"
SEARCH_PLACEHOLDER = "Find device, link, connector or type"
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
    "No links yet. Press C to connect two devices, or use Connect in the bar above the diagram."
)
# context menu
CM_OPEN_PLAN = "Show in harness plans"
CM_CONNECT_FROM = "Connect from here with"
CM_ADD_HERE = "Add device here"
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
MULTI_UNITS = "{} devices"
MULTI_LINKS = "{} links"
MULTI_MIXED = "{} devices and {} links"
MULTI_HEAD = "Selection"
MULTI_HELP = "Fields shown here change every selected item at once. A field that reads (different) holds different values; leave it alone to keep them."
MULTI_DIFFERENT = "(different)"
MULTI_DELETE = "Delete selection"
SELECTED_MANY = "Selected: {} items"
EMPTY_HINT_NAME = "What to do next"
# ==== UX release / export / import wave (ux/rel): releases panel, release dialogs, export, import wizard, new project ====
# what a release locks / what a revision makes editable (gui/lock_tree.py)
LOCK_GROUP_WIRES = "Wires"
LOCK_GROUP_PINS = "Pins"
LOCK_GROUP_INTERFACES = "Interfaces"
LOCK_GROUP_CONNECTORS = "Connectors"
LOCK_GROUP_UNITS = "Devices"
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
LOCK_PIN_UNIT = "device connector"
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
REL_MARK_TIP = "Mark the devices, interfaces and harnesses that changed on the diagram"
REL_CLEAR_TIP = "Remove the marks from the diagram"
# export dialog (gui/export_dialog.py)
EXP_TITLE = "Export outputs"
EXP_ACCESSIBLE = "Export outputs"
EXP_FOLDER = "Output folder"
EXP_FOLDER_UNSAVED = "(none yet: the project has no folder)"
EXP_FOLDER_TIP = "The outputs always go to the outputs folder of the project; the full path is shown so you can copy it."
EXP_FULL_NOTE = (
    "Every export writes the complete set, so the outputs folder always matches the design and "
    "the independent check can verify it. The PDF and SVG drawings of the harnesses are written "
    "only when “Include the PDF drawings” is ticked. The tick marks choose what the result list "
    "shows and what “Copy selection to folder…” copies."
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
IMP_KIND_INTERFACES_TIP = "A table (CSV or XLSX) with one interface per row: ID, type, the two devices and the redundancy."
IMP_KIND_PARTS = "Approved parts"
IMP_KIND_PARTS_TIP = "A parts list (CSV or XLSX) with an approval status per part. You say what the status values mean; nothing is guessed."
IMP_KIND_LENGTHS = "Segment lengths"
IMP_KIND_LENGTHS_TIP = "Lengths from the mechanical design (CSV or XLSX). The columns are read by position: harness, segment, length."
IMP_KIND_VALUES = "Engineering values: ampacity table"
IMP_KIND_VALUES_TIP = "A CSV or XLSX with two columns: wire gauge (AWG) and the ampere value. It replaces the ampacity table of the derating values."
IMP_KIND_NETLIST = "KiCad netlist"
IMP_KIND_NETLIST_TIP = "The .net file exported from KiCad: creates or updates the connectors of one device, with fixed signals on their pins."
IMP_FILE_LABEL = "File"
IMP_FILE_NAME = "Import file"
IMP_FILE_BROWSE = "Choose file…"
IMP_FILE_BROWSE_TIP = "Choose the file to import"
IMP_FILE_NONE = "No file chosen yet."
IMP_FILE_READ = "Read {0}: {1}."
IMP_FILE_SHEET = "sheet “{0}”"
IMP_FILE_ROWS = "{0} data rows"
IMP_FILE_COMPONENTS = "{0} components"
IMP_FILTER_TABLES = "Tables (*.csv *.tsv *.json *.xlsx)"
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
IMP_NET_UNIT = "Device the connectors belong to"
IMP_NET_UNIT_NONE = "(choose a device)"
IMP_NET_PREFIX = "References that mark connectors"
IMP_NET_REFS = "Only these references"
IMP_NET_REFS_TIP = "Optional: references separated by commas, for example J1, J2. Empty means every component that starts with the prefix."
IMP_NET_IDS = "Connector IDs"
IMP_NET_IDS_TIP = "Optional: one REF=ID per line, for example J1=OBC1-J01. Otherwise the symbol field HarnessConnector, else the device and the reference."
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
IMP_NO_UNIT = "Choose the device these connectors belong to."
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
CONN_COUNT_TIP = "{} connectors on this device"
CONN_MORE = "+{}"
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
SHELL_LEFT_TABS = "Project, devices and interfaces"
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
EMPTY_VIEW_HARNESS = "Pick a harness in the project tree, or double-click a link in the diagram, to see its connectors, pins, wires and drawing. Generate harnesses first if there are none."
EMPTY_VIEW_LISTS = "The wire list, pinouts, bill of materials and test tables appear here once harnesses are generated."
EMPTY_VIEW_TREE = "The project tree lists devices, interfaces, harnesses, parts, interface types, configuration and imports."
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
A_IMPORT_PREFIX = "Import"
M_GO = "&Go"
UNDO_LABELLED = "Undo {}"
REDO_LABELLED = "Redo {}"
NO_HARNESS_FOR_ACTION = "Choose a harness first (there is more than one)."
NO_HARNESSES_FOR_ACTION = "There are no harnesses yet. Generate harnesses first."
VIEW_NOT_INSTALLED = "{} is not available in this version yet."
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
HV_WHY_NOT_RELEASED = "Only a released harness can be revised."
HV_WHY_RELEASE_NOT_DRAFT = "Only a draft or a harness in review can be released."
HV_EMPTY_TITLE = "No harnesses yet"
HV_EMPTY_NO_INTERFACES = "Add interfaces on the diagram or import a table (Ctrl+Shift+I). Then press Generate to build the harnesses. Or join two devices with Connect and press Create harness on the connection."
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
LP_EMPTY_NO_INTERFACES = "The lists are made from harnesses. Add interfaces on the diagram or import a table (Ctrl+Shift+I), then press Generate. Or join two devices with Connect and press Create harness on the connection."
LP_EMPTY_READY = "The lists are made from generated harnesses. Press Generate to build them; you see a preview first."
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
    "Devices, interfaces, harnesses, parts, interface types, configuration and imports. Arrow keys "
    "move, Enter selects, Ctrl+Enter opens, Right and Left open and close a group, typing jumps "
    "to a name, / filters."
)
TREE_ROOTS = {
    "units": "Devices",
    "interfaces": "Interfaces",
    "harnesses": "Harnesses",
    "parts": "Parts",
    "interface_types": "Interface types",
    "config": "Configuration",
    "imports": "Imports",
}
TREE_EMPTY = {
    "units": "No devices yet. Add one with the Add button.",
    "interfaces": "No interfaces yet. Add one with Ctrl+I or import a table.",
    "harnesses": "No harnesses yet. Generate them from the interfaces, or press Create harness on a connection.",
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
TREE_ADD = "Add"
TREE_ADD_TIP = "Add something to the project"
TREE_ADD_ENTRIES = {"unit": "Device…", "interface": "Interface…"}
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
TREE_TIP_UNIT = "Device {}: {}. Subsystem {}, zone {}, chain {}."
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
WHY_EMPTY = "Select a device, link, harness, wire, connector or pin to see why it is the way it is."
WHY_TITLE = "Why: {} {}"
WHY_KIND = {
    "unit": "device",
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
INS_USED_KINDS = {"interface": "Link", "harness": "Harness", "wire": "Wire", "unit": "Device"}
INS_USED_TIP = "Double-click or press Enter to show it on the diagram"
INS_FACTS_NAME = "Properties of {} {}"
INS_FACT_COLUMNS = ("Property", "Value", "Status")
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
TREE_FILTER_CLEAR = "Clear the filter"
LISTS_EXPORT_TITLE = "Export table"
LISTS_EXPORT_FILTER = {"csv": "CSV files (*.csv)", "xlsx": "Excel workbooks (*.xlsx)"}
LISTS_EXPORTED = "Saved {}."


# ---- Devices view (custom devices, docs/ux-custom-devices-audit.md) -------------------------------
TAB_DEVICES = "Devices"
A_GO_DEVICES = "Go to Devices"
DV_ACCESSIBLE = "Devices: connectors and pins of a device"
EMPTY_VIEW_DEVICES = "The connectors and pins of a device appear here: pick a device on the diagram or in the project tree."
DV_EMPTY_TITLE = "No devices yet"
DV_EMPTY_BODY = "A device is a box in your system (a computer, a battery, a wheel) with its connectors and pins. Add a device to see its pinout here."
DV_ADD = "Add a device…"
DV_ADD_TIP = "Add a device to the project"
DV_DEVICE = "Device"
DV_DEVICE_TIP = "The device whose connectors and pins are shown. A device picked on the diagram or in the project tree is shown here."
DV_CHAIN = {"nominal": "Nominal chain", "redundant": "Redundant chain", "none": "No chain"}
DV_STATE_DRAFT = "Draft"
DV_STATE_IN_USE = "In use"
DV_STATE_LOCKED = "Locked"
DV_STATE_READ_ONLY = "Read-only"
DV_DUPLICATE = "Duplicate"
DV_DUPLICATE_TIP = "Copy this device with its connectors and pins (not its links)"
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
DV_CONNECTORS_TIP = "The box connectors of this device"
DV_COL_CONNECTOR = "Connector"
DV_COL_PART = "Part"
DV_COL_PINS = "Pins"
DV_COL_STATE = "State"
DV_NO_CONNECTORS = "This device has no connectors yet."
DV_CARD_PART = "Part"
DV_CARD_GENDER = "Gender"
DV_CARD_KEYING = "Keying"
DV_CARD_CARRIES = "Carries"
DV_CARD_ALLOCATION = "Pin allocation"
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
DV_CONTACT_TIP = "Show the contact size, the termination and the cable contact of each pin"
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
DV_COL_FUNCTION = "Function"
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
    "These are the rows of system/box_pinouts.csv for this device: what you see is what you ship."
)
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
A_ADD_DEVICE_TIP = "Add a device: a box with its own connectors and pins, named in the Devices tab"
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
IMP_PIN_DEVICE_TIP = "The device whose connectors the table defines, or a new device"
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
    "Model: the diagram of devices and interfaces, and the devices with their connectors and pins"
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
TB_REVISION = "Revision {}"
TB_REVISION_TIP = "The revision of the released harnesses ({})"
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
HOME_SUMMARY = "{} devices, {} interfaces, {} harnesses"
SETTINGS_TITLE = "Settings"
SETTINGS_THEME = "Theme"
SETTINGS_THEME_SYSTEM = "Follow the system"
SETTINGS_THEME_LIGHT = "Light"
SETTINGS_THEME_DARK = "Dark"
SETTINGS_SCALE = "Interface size"
SETTINGS_MODE = "Mode"
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
OFFLINE_TEXT = "Offline"
OFFLINE_TIP = (
    "This program works offline: nothing leaves this computer, no account, no update check."
)
PROBLEMS_PANEL_TITLE = "Problems"
PROBLEMS_PANEL_NAME = "Problems of the project"
PROBLEMS_BUTTON = "Problems ({})"
PROBLEMS_EMPTY = "No problems. Every rule that could be checked passed."
PROBLEMS_COL_SEVERITY = "Severity"
PROBLEMS_COL_RULE = "Rule"
PROBLEMS_COL_OBJECT = "Object"
PROBLEMS_COL_MESSAGE = "Message"
PROBLEMS_FILTER_ALL = "All"

PANE_PROBLEMS = "Problems panel"
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
LOCK_BANNER_ONE = (
    "Harness {} is released (revision {}) and locked. To change it, start a new revision."
)
LOCK_BANNER_MANY = (
    "{} harnesses are released and locked. To change one, start a new revision of it."
)
LOCK_BANNER_ACTION = "Start new revision…"
HOME_RECENT = "Recent projects"
HOME_RECENT_NONE = "No recent projects yet. Create one or open an example below."
HOME_EXAMPLES = "Examples"
HOME_OPEN_BTN = "Open"
HOME_REMOVE = "Remove from the list"
HOME_MISSING = "The folder is gone: {}"
HOME_EXAMPLE_FLATSAT = "Try the flatsat example"
HOME_EXAMPLE_FLATSAT_TIP = "Open a copy of the 23-device flatsat example (example numbers, not engineering data) in your Documents folder"
HOME_EXAMPLE_OPEN = "Open this example"
HOME_COUNTS = "{} devices · {} interfaces · {} harnesses"
HOME_DRAFT = "{} draft"
HOME_IN_REVIEW = "{} in review"
HOME_RELEASED = "{} released"

# ---- UI overhaul M3: empty states ------------------------------------------------------------
EMPTY_FILTERED_TITLE = "No row matches"
EMPTY_FILTERED_HINT = "Change or clear the filter to see the rows again."
EMPTY_INTERFACES_TITLE = "No interfaces yet"
EMPTY_INTERFACES_HINT = "An interface is a pair of connectors with a signal between them. Add one, or import a table with File > Import."
EMPTY_INTERFACES_ACTION = "New interface"
EMPTY_LIST_TITLE = "Nothing to list yet"
EMPTY_LIST_HINT = "Generate the harnesses and the list fills in."

# ---- UI overhaul M4: model editors as sheets -------------------------------------------------
SHEET_PASTED = "{0} cell(s) pasted."
SHEET_PASTED_SKIPPED = " {0} left out (read-only column or past the end of the table)."
SHEET_COLUMNS_MENU = "Show columns"
TAB_UNITS = "Device list"
TAB_UNITS_TIP = (
    "Every device as a table: edit names and notes in place, paste from Excel (Ctrl+Shift+J)"
)
UNIT_TABLE = "Device list"
UNIT_COLUMNS = ["ID", "Name", "Subsystem", "Zone", "Chain", "Interfaces", "Connectors", "Notes"]
STEP_PASTE = "Paste {0} cell(s)"
EMPTY_UNITS_TITLE = "No devices yet"
EMPTY_UNITS_HINT = "Add a device with Add in the project panel (or Edit > Add device), or import a table with File > Import."
A_GO_UNITS = "Go to Device list"
UNIT_FILTER_PLACEHOLDER = "Filter by ID, name, subsystem, zone or notes"
NEW_UNIT = "New device"

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
    "unit": "{0} device(s)",
    "interface": "{0} link(s)",
    "box_connector": "{0} device connector(s)",
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
SETTINGS_SNAP = "Snap devices to the grid"
SETTINGS_SNAP_TIP = "Devices jump to the grid while you drag them (hold Alt to drag freely)"
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
    ("Diagram: place a device without snapping", "Alt while dragging"),
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
WIRE_NOTHING_CHANGED = "Nothing to change."

# ---- 1.4.0 M2: wires that a person draws ----------------------------------------------------------
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
WIRE_GROUP_KINDS = (
    ("twisted_pair", "Twisted pair (2 wires)"),
    ("shielded_pair", "Shielded pair (2 wires)"),
    ("quad", "Quad (4 wires)"),
    ("coax", "Coax (1 wire)"),
    ("overall_shield", "Overall shield (2 or more wires)"),
)
WIRE_GROUP = "Group"
WIRE_GROUP_KIND = "Kind of group"
WIRE_GROUP_KIND_TIP = "How the selected wires run together: twisted, shielded or both."
WIRE_GROUP_TIP = "Twist or shield the selected wires together. Generate keeps the group."
WIRE_UNGROUP = "Ungroup"
WIRE_UNGROUP_TIP = "Take apart the group of the selected wire that you made"
WIRE_IN_GROUP = "In {0} {1}"
STEP_GROUP_WIRES = "Group wires"
STEP_UNGROUP_WIRES = "Ungroup wires"

# ---- 1.4.0 M3: labels of connectors and of the harness -------------------------------------------
DV_CARD_LABEL = "Label"
DV_CARD_LABEL_TIP = (
    "Text for the label of this connector (labels.csv) instead of only its ID. The cable end "
    "that plugs into it prints the same text unless you give the cable end its own."
)
LABELS_TITLE = "Labels"
LABELS_HARNESS = "Harness label"
LABELS_HARNESS_TIP = "Text for the label of the harness (labels.csv)."
LABELS_CONNECTOR = "Cable connector"
LABELS_CONNECTOR_TIP = "A connector of the harness, the cable end of a device connector."
LABELS_CONNECTOR_LABEL = "Connector label"
LABELS_CONNECTOR_LABEL_TIP = "Text for the label of this cable connector (labels.csv)."
LABELS_APPLY = "Apply labels"
LABELS_APPLY_TIP = "Set the harness label and the label of the chosen cable connector"
STEP_SET_LABELS = "Set labels"

# ---- 1.4.0 M4: who made the last change ----------------------------------------------------------
REL_AUTHOR = "Last commit of the project folder: {author}, {when}, “{subject}” ({short}{branch})."
REL_AUTHOR_BRANCH = ", branch {}"
REL_AUTHOR_TIP = (
    "Read from the Git repository around the project folder, without starting Git and without a "
    "network. It is the last commit of the whole repository, not of this project alone, and "
    "changes made since that commit are not shown."
)
REL_AUTHOR_NAME = "Last commit of the project folder"

# ---- 1.4.0 M5: device library files --------------------------------------------------------------
DV_LIB_SAVE = "Save to library…"
DV_LIB_SAVE_TIP = (
    "Save this device with its connectors, pinouts, parts and interface types to a device library "
    "file, to use it in another project. A file that exists is added to; if it has a different "
    "device with the same ID you are asked before it is replaced."
)
DV_LIB_ADD = "Add from library…"
DV_LIB_ADD_TIP = (
    "Add devices from a device library file. A device in your project is never replaced."
)
DV_LIB_FILTER = "Device library files (*.json)"
DV_LIB_SAVE_TITLE = "Save device to a library file"
DV_LIB_OPEN_TITLE = "Add devices from a library file"
DV_LIB_SAVED = "Saved {0} to {1}"
DV_LIB_ADDED = "Added {0} device(s) from {1}"
DV_LIB_TITLE = "Add devices from a library file"
DV_LIB_LIST = "Devices in the file"
DV_LIB_LIST_TIP = "Tick the devices to add"
DV_LIB_ITEM = "{0}: {1}"
DV_LIB_NONE = "Tick at least one device."
DV_LIB_ADD_BUTTON = "Add devices"
DV_LIB_ROW_OK = "{0} will be added as {1} ({2} connectors, {3} pins)."
STEP_ADD_DEVICES = "Add devices from a library file"

# ---- 1.5.0: a harness from nothing (no interfaces behind it) -------------------------------------
A_NEW_HARNESS = "New harness…"
A_NEW_HARNESS_TIP = (
    "Make an empty harness by hand: no interface is needed. Then add its connectors and draw its "
    "wires in the Harness tab. Generate never changes it."
)
HV_NEW_HARNESS = "New harness…"
NEW_HARNESS_TITLE = "New harness"
NEW_HARNESS_NAME = "Name of the harness"
STEP_NEW_HARNESS = "New harness {0}"
HARNESS_CREATED = "{0} created. Add its connectors in the Connectors tab."
HV_EMPTY_BY_HAND = " Or make a harness by hand with New harness: no interface is needed."
HV_CONNECTORS_TAB = "Connectors"
CE_GENERATED = (
    "{0} is made by Generate, which gives it the connectors of the design. To add connectors "
    "yourself, make a harness with New harness."
)
CE_RELEASED = "{0} is released. Start a new revision to change its connectors."
CE_ADD_TITLE = "Add connector"
CE_PART = "Part"
CE_PART_TIP = "The connector part from the parts library. New parts are added in the Devices tab."
CE_PLUGS_INTO = "Plugs into"
CE_PLUGS_INTO_TIP = (
    "A connector of a device this connector plugs into: the mating part, the opposite gender, the "
    "keying and the pins are taken from it. Choose nothing for a free-standing connector."
)
CE_NOTHING = "nothing (free-standing)"
CE_NAME = "Name"
CE_NAME_TIP = "The name of the connector in the harness, for example P1. Left empty, the next free one is used."
CE_PINS = "Pins"
CE_PINS_TIP = (
    "The names of the pins, separated by commas, for example A1, A2, B1. Left empty, the pins are "
    "1 to the pin count of the part, or those of the device's connector it plugs into."
)
CE_ADD = "Add connector"
CE_ADD_TIP = "Add the connector to the harness. The pins are those of the part, or of the device's connector it plugs into."
CE_PIN_TITLE = "Pin of a connector"
CE_CONNECTOR = "Connector"
CE_CONNECTOR_TIP = "A connector of this harness"
CE_PIN = "Pin"
CE_FUNCTION = "Function"
CE_FUNCTION_TIP = "What the pin does, in your words, for example HEATER +. It is printed on the pinout and the labels."
CE_TERMINATION = "Termination"
CE_TERMINATION_TIP = "How the wire is joined to the pin: crimp, solder, or not said."
CE_CONTACT = "Contact size"
CE_CONTACT_TIP = "The size of the contact, for example 22."
CE_SET_PIN = "Set pin"
CE_SET_PIN_TIP = "Apply function, termination and contact size to this pin"
CE_DELETE = "Delete connector"
CE_DELETE_TIP = "Delete the selected connector. It must have no wires."
CE_TERMINATIONS = (("unspecified", "not said"), ("crimp", "crimp"), ("solder", "solder"))
STEP_ADD_HARNESS_CONNECTOR = "Add connector to {0}"
STEP_SET_HARNESS_PIN = "Set pin {0}"
STEP_DELETE_HARNESS_CONNECTOR = "Delete connector {0}"

# ---- 1.6.0: a blank project says where to start ---------------------------------------------------
EMPTY_ADD_DEVICE = "Add a device"
EMPTY_ADD_DEVICE_NAME = "Add a device to the empty diagram"

# ---- D-169: the build workbook is the main output, the drawings are optional ---------------------
EXP_DRAWINGS = "Include the PDF drawings"
EXP_DRAWINGS_TIP = (
    "Also write the PDF and SVG drawings of every harness. Without them the export writes the "
    "build workbook, the tables and the system documents. Unticking this removes the drawings "
    "an earlier export wrote to the folder."
)
EXP_DRAWINGS_NAME = "Include the PDF drawings in the export"

# ---- D-170: the build data (strip lengths, cable contact, accessories, crimp tool) ------------------
WIRE_STRIP_A = "Strip A (mm)"
WIRE_STRIP_A_TIP = (
    "How much insulation is stripped at the From end of the wire, in millimetres, for example 6. "
    "Empty clears it."
)
WIRE_STRIP_B = "Strip B (mm)"
WIRE_STRIP_B_TIP = (
    "How much insulation is stripped at the To end of the wire, in millimetres, for example 6. "
    "Empty clears it."
)
WIRE_STRIP_NOTE = (
    "Strip lengths do not lock the wire against Generate: they are always kept, like the note."
)
WIRE_STRIP_ALL = "Apply strip lengths to all wires of this harness"
WIRE_STRIP_ALL_TIP = (
    "Give every wire of this harness the strip lengths in the two fields above (a field that you "
    "emptied clears it). One undo step."
)
WIRE_STRIP_ALL_NONE = "Type a strip length in Strip A, Strip B or both first."
WIRE_STRIP_ALL_DONE = "Strip lengths changed on {0} of {1} wires of {2}."
WIRE_STRIP_ALL_SAME = "All {0} wires of {1} already have these strip lengths."
WIRE_STRIP_ALL_NO_HARNESS = "Choose a harness first."
STEP_SET_STRIP_ALL = "Set strip lengths of all wires of {0}"

DV_COL_CONTACT_PART = "Cable contact"
DV_COL_CONTACT_PART_TIP = (
    "The contact the cable side uses on this pin. Generate copies it to the cable connector."
)
DV_CONTACT_PART_NONE = "none"
DV_CONTACT_BULK = "Cable contact…"
DV_CONTACT_BULK_TIP = (
    "Cable contact: set it on the selected pins. Generate copies it to the cable connector."
)
DVD_CONTACT_TITLE = "Cable contact"
DVD_CONTACT_PINS = "Pins: {0}"
DVD_CONTACT_PART = "Contact"
DVD_CONTACT_PART_TIP = (
    "A part of category contact from the library. Choose none to clear the cable contact of "
    "these pins."
)
DVD_CONTACT_OK = "Set cable contact"
DVD_CONTACT_NO_PARTS = (
    "The library has no part of category contact yet. Import or add one first, then choose it here."
)
STEP_SET_CONTACTS = "Set cable contact of {0} on {1}"

CE_CONTACT_PART = "Contact"
CE_CONTACT_PART_TIP = (
    "The contact (a part of category contact from the library) the wire uses on this pin. Empty "
    "means none."
)
CE_CONTACT_ALL = "Contact for all pins of this connector"
CE_CONTACT_ALL_TIP = (
    "Give every pin of the selected connector the contact chosen in Contact (none clears them). "
    "One undo step."
)
CE_CONTACT_NONE = "none"
CE_CONTACT_GENERATED = (
    "The contact of a pin of a generated harness is set on the pin of the device, in the Devices "
    "tab (column Cable contact). Generate copies it to the cable connector."
)
STEP_SET_HARNESS_CONTACTS = "Set contact of all pins of {0}"

HV_ACCESSORIES_TAB = "Accessories"
ACC_TABLE_NAME = "Accessories of {0}"
ACC_COL_ID = "ID"
ACC_COL_KIND = "Kind"
ACC_COL_PART = "Part"
ACC_COL_ON = "On"
ACC_COL_POSITION = "Position"
ACC_COL_LENGTH = "Length (mm)"
ACC_COL_QUANTITY = "Quantity"
ACC_COL_NOTE = "Note"
ACC_KINDS = (
    ("sleeving", "sleeving"),
    ("heat_shrink", "heat shrink"),
    ("label", "label"),
    ("backshell", "backshell"),
    ("other", "other"),
)
ACC_ON_HARNESS = "the harness"
ACC_PART_NONE = "no part"
ACC_EMPTY_TITLE = "No accessories yet"
ACC_EMPTY_HINT = (
    "Accessories are the things that go on a harness besides its wires and connectors: sleeving, "
    "heat shrink, labels, backshells. List them here and the build sheets show them."
)
ACC_NO_HARNESS = "Choose a harness to list its accessories."
ACC_RELEASED = "{0} is released. Start a new revision to change its accessories."
ACC_ID = "ID"
ACC_ID_TIP = (
    "The name of the accessory in this harness, for example ACC-001. The next free one is "
    "offered. It cannot be changed once the accessory exists."
)
ACC_KIND = "Kind"
ACC_KIND_TIP = "What it is: sleeving, heat shrink, a label, a backshell or something else."
ACC_PART = "Part"
ACC_PART_TIP = (
    "The part from the library (optional). Parts come in with the parts import (import-parts)."
)
ACC_ON = "On"
ACC_ON_TIP = "What it goes on: a connector or a wire of this harness, or the harness itself."
ACC_POSITION = "Position"
ACC_POSITION_TIP = "Where it goes, in your words. Nothing is computed from it."
ACC_POSITION_PLACEHOLDER = "for example 50 mm from the P1 end"
ACC_LENGTH = "Length (mm)"
ACC_LENGTH_TIP = "The length of one piece in millimetres (optional), for example 120."
ACC_QUANTITY = "Quantity"
ACC_QUANTITY_TIP = "How many pieces, a whole number from 1 to 9999."
ACC_NOTE = "Note"
ACC_NOTE_TIP = "Your remark about the accessory. It appears in the build sheets."
ACC_ADD = "Add accessory"
ACC_ADD_TIP = (
    "Add the accessory in the form. When a row of the table is selected, the form is a copy of "
    "it and the new accessory gets the next free ID."
)
ACC_CHANGE = "Change accessory"
ACC_CHANGE_TIP = "Save the form into the selected accessory"
ACC_DELETE = "Delete accessory"
ACC_DELETE_TIP = "Delete the selected accessory from this harness"
ACC_NEW = "New accessory"
ACC_NEW_TIP = "Clear the form and the selection to describe a new accessory"
ACC_NONE_SELECTED = "Select an accessory in the table first."
ACC_ID_EXISTS = "{0} is already an accessory of this harness. Use Change accessory."
STEP_ADD_ACCESSORY = "Add accessory {0}"
STEP_CHANGE_ACCESSORY = "Change accessory {0}"
STEP_DELETE_ACCESSORY = "Delete accessory {0}"

INS_FACT_TOOL = "Crimp tool"
INS_PART_TOOL = "Crimp tool"
INS_PART_TOOL_TIP = (
    "The crimp tool, or its setting, for this contact, in your words, for example "
    "'Tool X, setting 4'. Empty clears it. The build sheets show it."
)
INS_PART_TOOL_SET = "Set tool"
INS_PART_TOOL_SET_TIP = "Save the crimp tool of this contact part"
STEP_SET_PART_TOOL = "Set tool of {0}"

# ---- 1.7.0 S1: the one next step (D-171) ---------------------------------------
AREA_NEXT = "Next step"
AREA_NEXT_TIP = "Next step: what to do now, in plain words, with one button"
NEXT_TITLE = "What to do next"
NEXT_STEPS_HEADING = "The steps"
NEXT_STEPS_NAME = "The steps of the work and where you are"
NEXT_STEP_ADD = "Add your devices"
NEXT_STEP_CONNECT = "Connect them"
NEXT_STEP_GENERATE = "Generate the harnesses"
NEXT_STEP_CHECK = "Check the design"
NEXT_STEP_SHEETS = "Get the build sheets"
NEXT_STEP_RELEASE = "Review and release"
NEXT_STATE_DONE = "done"
NEXT_STATE_NEXT = "next"
NEXT_STATE_TODO = "to do"
NEXT_STATE_BLOCKED = "not possible"
NEXT_STEP_LINE = "{0}: {1}"
NEXT_SHOW_EVERYTHING = "Show everything"
NEXT_SHOW_EVERYTHING_TIP = (
    "Switch to the role Electrical / AIT engineer, which shows every area, panel and tab. "
    "You can switch back in View > Role."
)
NEXT_LIBRARY = "Library…"
NEXT_LIBRARY_TIP = (
    "Open the library window (Ctrl+Shift+O): devices and subsystems your team has saved"
)
NEXT_BUSY_TITLE = "Working…"
NEXT_BUSY_WHY = "Please wait. This takes a moment."
NEXT_READ_ONLY_TITLE = "You can only look at this project"
NEXT_READ_ONLY_WHY = "It was saved by a newer version, or it is open in another window, so nothing can be changed here."
NEXT_ADD_TITLE = "Start with a device"
NEXT_ADD_WHY = "A device is a box in your design, such as a computer or a battery."
NEXT_ADD_BUTTON = "Add a device"
NEXT_ADD_ALTERNATIVE = "or make a harness by hand"
NEXT_ADD_ALTERNATIVE_BUTTON = "New harness…"
NEXT_CONNECT_TITLE = "Connect your devices"
NEXT_CONNECT_WHY = "Join a connector of one device to a connector of another. The program proposes the pairs of pins."
NEXT_CONNECT_BUTTON = "Connect two devices"
NEXT_GENERATE_TITLE = "Generate the harnesses"
NEXT_GENERATE_WHY = "The program makes the harnesses from your connections."
NEXT_GENERATE_AGAIN_TITLE = "Generate the harnesses again"
NEXT_GENERATE_AGAIN_WHY = "You changed the design, so the harness plans are out of date."
NEXT_GENERATE_BUTTON = "Generate the harnesses"
NEXT_CHECK_TITLE = "Check the design"
NEXT_CHECK_WHY = "The check looks for mistakes in the design and marks them."
NEXT_CHECK_BUTTON = "Check the design"
NEXT_FIX_TITLE = "Fix what is marked"
NEXT_FIX_WHY_ONE = "1 check failed. It is marked with what to do."
NEXT_FIX_WHY_MANY = "{0} checks failed. Each one is marked with what to do."
NEXT_FIX_BUTTON = "Show the problems"
NEXT_SHEETS_TITLE = "Get the build sheets"
NEXT_SHEETS_WHY = (
    "The workbook of every harness has the cut list, the connector blocks and the test sheet."
)
NEXT_SHEETS_WAIT = "Some checks wait for engineering values, and the sheets will say so."
NEXT_SHEETS_FOLDER = "Export first asks where to save the project."
NEXT_SHEETS_BUTTON = "Export the build sheets"
NEXT_RELEASE_TITLE = "Review and release"
NEXT_RELEASE_WHY = (
    "Release each harness when it is final. A released harness cannot be changed by accident."
)
NEXT_RELEASE_BUTTON = "Go to Releases"
NEXT_DONE_TITLE = "Everything is released"
NEXT_DONE_WHY = "Every harness is released and the files are up to date."
NEXT_DONE_BUTTON = "Open the Outputs"
NEXT_BUTTON_TIPS = {
    "add_device": "Add a device to the design and name it (Ctrl+Shift+N)",
    "new_harness": "Make a harness by hand, without devices or connections (Ctrl+Shift+H)",
    "connect": "Open the diagram with the Connect tool, then click two devices (C). A window then shows which pins go together",
    "generate": "Make the harnesses from the connections of the design (Ctrl+G)",
    "check": "Look for mistakes in the design (F5)",
    "fix": "Open the Checks, which list what failed and what to do",
    "build_sheets": "Write the build workbook and the other files of every harness (Ctrl+E)",
    "release": "Open the Revisions, where a harness is reviewed and released",
    "done": "Open the Outputs: the lists and the exported files",
}
# ---- The Systems engineer role (the Simple workspace of 1.7.0, stage S2): fewer things on screen (D-171, D-176) ----
A_SHOW_PANELS = "Show side panels"
SHOW_PANELS_BUTTON = "Show panels"
SHOW_PANELS_TIP = "Open or close the project tree and the properties together"
TOOL_ADD_DEVICE = "Add device"
TOOL_ADD_DEVICE_TIP = "Add a device to the design (Ctrl+Shift+N)"
TOOL_MORE = "More"
TOOL_MORE_TIP = "More tools: copy, delete, zoom, arrange and show only some connections"
TOOL_MORE_FILTER = "Show only"
PROPERTIES_CLOSED = "The properties are closed. Open them to see and change what you selected."

# ---- Workshop feedback M1 (D-172): a device asks for its name, problem notices on request, export in one step ----
NEWDEV_TITLE = "Add device"
NEWDEV_NAME = "Name"
NEWDEV_NAME_TIP = "What the device is called, for example Star tracker. The ID is made from it."
NEWDEV_NAME_HINT = "for example Star tracker"
NEWDEV_ID = "ID"
NEWDEV_ID_TIP = "The short ID of the device (letters and digits). It is made from the name; type another one to keep it."
NEWDEV_SUBSYSTEM = "Subsystem"
NEWDEV_SUBSYSTEM_TIP = "The subsystem of this device (optional): pick one or type a new one"
NEWDEV_NOTE = "You can change the name, the ID and the subsystem later in the Devices tab."
NEWDEV_OK = "Add device"
A_PROBLEM_NOTICES = "Show problem notices"
A_PROBLEM_NOTICES_TIP = (
    "Show or hide the notices that appear without being asked for: the Problems button and "
    "its count, the count on the inspector tab, the status chip of the top bar, the chip and "
    "the badges on the diagram, the pending-values link and the out-of-date banner. "
    "The Check button, the Checks, the Problems panel and the read-only, locked and sample "
    "banners always stay."
)
SETTINGS_PROBLEM_NOTICES = "Show problem notices"
SETTINGS_PROBLEM_NOTICES_TIP = (
    "Show the Problems count, the status chips, the badges on the diagram and the out-of-date "
    "banner without being asked. Off: they stay hidden; the Check button and the Checks still work. "
    "Each role remembers its own choice (the Systems engineer starts with them off)."
)
EXPORT_SAVE_AS_FOLDER = (
    "Choose an empty folder to save the project in. The files are then exported next to it"
)
EXP_DAMAGED_MORE = "and {} more"
HV_EXPORT_READ_ONLY = "Read-only: save a copy first"
HV_EXPORT_SAVES_FIRST = "Asks where to save first"
HV_EXPORT_SAVES_FIRST_TIP = "This project has no folder yet, so you first choose where to save it; the files are then exported next to it"
HV_EXPORT_REASON_NAME = "Why Export may not work"

# ---- Workshop feedback M2b (D-173): connections, the pinout first. Two connectors joined pin by pin ----
M_CONNECT_WITH_TYPE = "Connect with an interface type…"
M_CONNECTION = "Selected connection"
A_LINK = "Link connectors…"
A_LINK_EDIT = "Edit the pairs…"
A_LINK_RENAME = "Rename…"
A_LINK_HARNESS = "Create harness"
A_LINK_DELETE = "Delete connection"
A_CHECK_CONNECTIONS = "Check my connections"
CM_LINK_FROM = "Link connectors from here…"
STEP_ADD_LINK = "Link connectors {}"
STEP_EDIT_LINK = "Change connection {}"
STEP_RENAME_LINK = "Rename connection {}"
STEP_DELETE_LINK = "Delete connection {}"
STEP_LINK_HARNESS = "Create harness from connection {}"
LINK_ADDED = "Connection {} made between {}."
LINK_CHANGED = "Connection {} changed."
LINK_DELETED = "Connection {} deleted. A harness made from it stays."
LINK_HARNESS_MADE = (
    "Harness {} created from connection {}. Enter the lengths and wires' details in Edit wire."
)
LINK_NEED_TWO = "Add a second device first. A connection joins two devices."
LINK_PICK_ONE = "Pick a connection first (in the project tree or on the diagram)."
LINK_SAME_DEVICE = "Pick a device other than {}. A connection joins two different devices."
LINK_HINT_FIRST = "Click the first device. A window then shows which pins go together."
LINK_HINT_SECOND = "Now click the second device ({} is the first)."
LINK_NO_CONNECTOR_SHORT = "No connector yet"
LINK_NO_CONNECTOR = "Device {} has no connector yet. Add one in the Devices tab first."
LINK_NO_PAIRS = "Pair at least one pin of the first connector with a pin of the second."
LINK_NO_PAIRS_YET = "Nothing is paired yet. Pick a pin on each side and press Add pair."
LINK_TITLE = "Link connectors"
LINK_EDIT_TITLE = "Edit the pairs of a connection"
LINK_INTRO = (
    "Pick a connector on each device. The program proposes which pins go together from the "
    "signal names on the pins, never from their position. Look at the pairs and change what is wrong."
)
LINK_EDIT_INTRO = "The two connectors stay as they are. Change the pairs and the roles of the pins."
LINK_NAME = "Name"
LINK_NAME_TIP = (
    "A name for this connection (optional). Without one it is called after its two connectors."
)
LINK_NAME_HINT = "optional"
LINK_FIRST = "First device"
LINK_SECOND = "Second device"
LINK_JOINED = "joined to"
LINK_DEVICE = "Device"
LINK_DEVICE_TIP = "The device whose connector is joined"
LINK_CONNECTOR = "Connector"
LINK_CONNECTOR_TIP = (
    "The connector of the device. Every connector can be joined to a connector of another device."
)
LINK_ENDS_FIXED = (
    "The connectors of a connection cannot change. Delete it and link again to use others."
)
LINK_TABLE_NAME = "Pairs of pins"
LINK_COL_PIN_A = "Pin (first)"
LINK_COL_SIGNAL_A = "Signal (first)"
LINK_COL_ROLE_A = "Role (first)"
LINK_COL_PIN_B = "Pin (second)"
LINK_COL_SIGNAL_B = "Signal (second)"
LINK_COL_ROLE_B = "Role (second)"
LINK_NO_SIGNAL = "no signal"
LINK_PIN_A = "Pin of the first connector"
LINK_PIN_B = "Pin of the second connector"
LINK_PIN_TIP = "A pin of the connector with its signal name"
LINK_ROLE_A = "Role of that pin of the first connector"
LINK_ROLE_B = "Role of that pin of the second connector"
LINK_ROLE_TIP = "What the pin is for. Automatic takes it from the signal name."
LINK_ROLE_NAMES = {
    "": "Automatic",
    "power": "Power",
    "return": "Return",
    "ground": "Ground",
    "signal": "Signal",
    "shield": "Shield",
    "spare": "Spare",
}
LINK_ROLE_HELP = (
    "Roles: Power carries the supply. Return is the line the current of a signal comes back on. "
    "Ground is the common reference. Signal carries data. Shield is the screen of a cable. "
    "Spare is a pin nobody uses, so it is not asked about. Automatic takes the role from the signal name."
)
LINK_ADD_PAIR = "Add pair"
LINK_ADD_TIP = "Pair the two pins chosen above"
LINK_CHANGE_PAIR = "Change pair"
LINK_CHANGE_TIP = "Replace the pair picked in the table by the two pins chosen above"
LINK_REMOVE_PAIR = "Remove pair"
LINK_REMOVE_TIP = "Take the pair picked in the table out"
LINK_UNPAIRED_LINE = "Not paired on {}: {}."
LINK_ALL_PAIRED = "Every pin that has a signal is paired."
LINK_REVIEW_ERRORS = (
    "Something looks wrong. You can still make the connection; the check keeps asking."
)
LINK_REVIEW_WARNINGS = "Please have a look. You can still make the connection."
LINK_OK = "Link connectors"
LINK_SAVE = "Save the pairs"
LINK_OK_TIP = "Join the two connectors with these pairs (you can undo it)"
LINK_RENAME_TITLE = "Rename connection"
LINK_HARNESS_TITLE = "Create harness"
LINK_HARNESS_PREVIEW = (
    "This adds the harness {name} with {connectors} cable connectors and {wires} wires, "
    "one wire for each pair of {caption}."
)
LINK_HARNESS_NOTE = "Lengths, gauges and colours stay empty until you enter them. The program never makes a harness on its own, and you can undo this."
LINK_HARNESS_OK = "Create harness"
LINK_HARNESS_OK_TIP = "Make the harness now (you can undo it)"
LINK_CHECK_NONE = "There is no connection to check yet. Use Link connectors first."
LINK_CHECK_CLEAN = "Every connection looks fine."
LINK_CHECK_FOUND = (
    "1 thing to look at in your connections. It is listed under Problems.",
    "{} things to look at in your connections. They are listed under Problems.",
)
LINK_TIP_ENDS = "Joins"
LINK_TIP_PAIRS = "Pairs"
LINK_TIP_CARRIES = "Carries"
LINK_TIP_HARNESS = "Harness"
LINK_TIP_NO_HARNESS = "none yet (Create harness makes it)"
LINK_TIP_CHECKS = "Checks"
LINK_TIP_OPEN = "Double-click to change the pairs."
TREE_ROOTS["links"] = "Connections"
TREE_EMPTY["links"] = "No connections yet. Use Link connectors, or the Connect tool on the diagram."
TREE_ADD_LINK = "Link connectors…"
TREE_TIP_LINK = "Connection {}: {}, {} pairs."
TREE_TIP_LINK_HARNESS = "Harness {} was made from it."
TREE_TIP_LINK_NO_HARNESS = "No harness yet."
PROBLEMS_FILTER_LINKS = "Connections"
PROBLEMS_FILTER_LINKS_TIP = "Show only what the check says about connections"
NEXT_MAKE_TITLE = "Make the harness of your connection"
NEXT_MAKE_WHY = "Your connection says which pins go together. One button makes a harness with a wire for each pair."
NEXT_MAKE_BUTTON = "Create harness"
NEXT_BUTTON_TIPS["make_harness"] = (
    "Show what the harness will contain, then make it. Nothing is made before you agree"
)

# ---- Workshop feedback M3 (D-174): edit a connector, change a group, edit all wires, connectors on the connections ----
CE_EDIT_TITLE = "Edit connector"
CE_EDIT_PART_TIP = (
    "The part of this connector, from the parts library. The pins stay as they are; "
    "a part with another number of pins shows in the checks."
)
CE_GENDER = "Gender"
CE_GENDER_TIP = "Male or female, as the part says it. Not said: the checks cannot tell if it fits."
CE_GENDERS = (("unspecified", "not said"), ("male", "male"), ("female", "female"))
CE_KEYING = "Keying"
CE_KEYING_TIP = (
    "The key or coding of the connector, in words, for example A. It must match the device end."
)
CE_EDIT_NAME_TIP = "The name of the connector in the harness, for example P1"
CE_EDIT_NAME_FIXED = "The name of a connector of a generated harness comes from its ID."
CE_EDIT_APPLY = "Apply to connector"
CE_EDIT_APPLY_TIP = (
    "Set the part, gender, keying and name of the selected connector (you can undo it)"
)
CE_EDIT_NOTHING = "Nothing to change: the connector has these values already."
CE_EDIT_STATE_MINE = (
    "Edited by you: Generate keeps the part, gender, keying and pin details of this connector. "
    "Its pins and their contacts still follow the device."
)
CE_EDIT_STATE_GENERATED = (
    "Generate gives this connector the part, gender and keying of the device it plugs into. "
    "If you change them or a pin here, the connector becomes yours and Generate keeps them."
)
CE_RESET = "Give back to Generate"
CE_RESET_TIP = "Let Generate set the part, gender, keying and pins from the device again, the next time you generate"
CE_PIN_COUNT = "The part has {0} pins and the connector {1}."
CE_PIN_COUNT_ADD = " Add or delete pins below."
CE_SIGNAL = "Signal"
CE_SIGNAL_TIP = (
    "The name of what this pin carries, for example HEATER +. It is printed on the pinout."
)
CE_ROLE = "Role"
CE_ROLE_TIP = (
    "What the pin is for: power, return, ground, signal, shield or spare. Empty means not said."
)
CE_ROLES = (
    ("", "not said"),
    ("power", "power"),
    ("return", "return"),
    ("ground", "ground"),
    ("signal", "signal"),
    ("shield", "shield"),
    ("spare", "spare"),
)
CE_PIN_ID = "Pin ID"
CE_PIN_ID_TIP = "The ID of a pin: letters, digits, _ - . (up to 16). Add takes a list separated by commas; Rename takes one."
CE_PIN_ADD = "Add pin"
CE_PIN_ADD_TIP = "Add the pins in Pin ID to this connector"
CE_PIN_RENAME = "Rename pin"
CE_PIN_RENAME_TIP = "Give the selected pin the ID in Pin ID. The wires on it follow."
CE_PIN_DELETE = "Delete pin"
CE_PIN_DELETE_TIP = "Delete the selected pin. It must have no wires."
CE_PINS_FROM_DEVICE = (
    "The pins of a generated harness follow the device: add, rename or delete them on the "
    "device, in the Devices tab."
)
STEP_EDIT_CONNECTOR = "Edit connector {0}"
STEP_ADD_PINS = "Add pins to {0}"
CE_STEP_RENAME_PIN = "Rename pin {0}"
STEP_DELETE_PIN = "Delete pin {0}"
STEP_RESET_CONNECTOR = "Give {0} back to Generate"

WIRE_CHANGE_GROUP = "Change group…"
WIRE_CHANGE_GROUP_TIP = (
    "Change the kind, the wires or the shield ends of the group of the selected wire that you made"
)
STEP_CHANGE_GROUP = "Change group {0}"
GD_TITLE = "Change group {0}"
GD_INTRO = "A group that you made: change how the wires run together and how its shield ends. Generate keeps it while its wires exist."
GD_KIND = "Kind"
GD_KIND_TIP = (
    "How the wires run together: twisted pair, shielded pair, quad, coax or overall shield"
)
GD_END_A = "Shield end A"
GD_END_A_TIP = "How the shield ends at the From end of the wires"
GD_END_B = "Shield end B"
GD_END_B_TIP = "How the shield ends at the To end of the wires"
GD_ENDS = (
    ("backshell_360", "360 degree backshell"),
    ("pigtail", "pigtail"),
    ("floating", "floating"),
)
GD_WIRES = "Wires of the group"
GD_WIRES_TIP = "Tick the wires that belong to the group. A wire of another group is not offered."
GD_OK = "Change group"
GD_OK_TIP = "Change the group now (you can undo it)"
GD_READY = "{0} of {1} wires: this is a {2}."
GD_SAME = "The group has these values already, so nothing changes."

WIRE_BULK = "Edit all wires…"
WIRE_BULK_TIP = "Set the gauge, type, colour and length of all wires of this harness, the selected wires or the wires of one signal in one step"
A_BULK_WIRES = "Edit all wires of the harness…"
A_BULK_WIRES_TIP = "Set the gauge, type, colour and length of many wires of the open harness in one step (Harness tab)"
STEP_BULK_WIRES = "Edit {0} wires of {1}"
BULK_TITLE = "Edit all wires of {0}"
BULK_INTRO = "Fill in what the wires should have. A field left empty stays as it is. The wires become yours: Generate keeps their gauge, type, colour and length."
BULK_SCOPE = "Wires"
BULK_SCOPE_TIP = "Which wires get the values"
BULK_SCOPE_ALL = "All {0} wires of {1}"
BULK_SCOPE_SELECTED = "The {0} selected wires"
BULK_SCOPE_SIGNAL = "All wires of one signal"
BULK_SIGNAL = "Signal"
BULK_SIGNAL_TIP = "The signal name; every wire of this harness that carries it gets the values"
BULK_ONLY_EMPTY = "Only wires that have no value yet"
BULK_ONLY_EMPTY_TIP = "Leave a wire alone when it has its own gauge, type, colour or length: each field is filled in only where it is empty"
BULK_OK = "Apply to wires"
BULK_OK_TIP = "Set the values on the wires now (one undo step)"
BULK_NOTHING = "Fill in at least one of gauge, type, colour and length."
BULK_SAME = "The wires have these values already, so nothing changes."
BULK_READY = "{0} on {1} of {2} wires."
BULK_NO_HARNESS = "Open a harness first."

A_CONNECTION_ENDS = "Show connectors on connections"
A_CONNECTION_ENDS_TIP = "Draw the connector and its number of pins at both ends of every connection in the Diagram. The Expert mode always shows them."
SETTINGS_CONNECTION_ENDS = "Show connectors on connections"
SETTINGS_CONNECTION_ENDS_TIP = "Draw the connector and its number of pins at both ends of every connection in the Diagram. The Expert mode always shows them."
LINK_END_PINS = ("{0} of 1 pin", "{0} of {1} pins")
LINK_TIP_PATH = "Path"
A_LINK_SHOW_HARNESS = "Show the harness"
A_LINK_SHOW_HARNESS_TIP = "Open the harness that was made from this connection in the Harness tab"
A_LINK_SHOW_HARNESS_NONE = "No harness has been made from this connection yet"

# ---- the library (workshop M4, D-175) ----------------------------------------------------------
A_LIBRARY = "Library…"
A_LIBRARY_TIP = "Open the library window: the devices and subsystems in your team's library folder, to add to this project (Ctrl+Shift+O)"
A_LIBRARY_FOLDER = "Library folder…"
A_LIBRARY_FOLDER_TIP = "Choose the folder that holds your team's device and subsystem library files (a shared drive or a Git checkout)"
LIB_FOLDER_TITLE = "Choose the library folder"
LIB_TITLE = "Library"
LIB_FOLDER_LABEL = "Library folder"
LIB_FOLDER_NONE = "No folder chosen"
LIB_FOLDER_TIP = "The folder this window reads. It is only read, and written to only when you save to the library."
LIB_CHANGE = "Change…"
LIB_CHANGE_TIP = "Choose another library folder"
LIB_REFRESH = "Refresh"
LIB_REFRESH_TIP = "Read the folder again, for example after a colleague added to it"
LIB_SEARCH_NAME = "Search the library"
LIB_SEARCH_PLACEHOLDER = "Search by name, ID or description"
LIB_SEARCH_TIP = "Type words; only the entries that contain all of them stay (Ctrl+F)"
LIB_KIND_NAME = "Show"
LIB_KIND_TIP = "Show devices, subsystems or both"
LIB_KIND_ALL = "Devices and subsystems"
LIB_KIND_DEVICES = "Devices"
LIB_KIND_SUBSYSTEMS = "Subsystems"
LIB_LIST_NAME = "Library contents"
LIB_LIST_TIP = "The devices and subsystems of the library folder. Press Enter to add the chosen one to the project."
LIB_COLUMNS = ["Kind", "ID", "Name", "Contents"]
LIB_KIND_DEVICE = "Device"
LIB_KIND_SUBSYSTEM = "Subsystem"
LIB_N_CONNECTORS = ("{} connector", "{} connectors")
LIB_N_PINS = ("{} pin", "{} pins")
LIB_N_DEVICES = ("{} device", "{} devices")
LIB_N_CONNECTIONS = ("{} connection", "{} connections")
LIB_EMPTY_NO_FOLDER = "No library folder is chosen yet"
LIB_EMPTY_NO_FOLDER_HINT = "Choose the folder your team shares, for example on a shared drive or in a Git checkout. Until then the library is empty and your project is not touched."
LIB_EMPTY_CHOOSE = "Choose library folder…"
LIB_EMPTY_FOLDER = "This folder has no devices or subsystems yet"
LIB_EMPTY_FOLDER_HINT = "Select devices in your project and press Save selection to library…"
LIB_EMPTY_UNREADABLE = "The library cannot be read"
LIB_EMPTY_NOMATCH = "Nothing matches"
LIB_EMPTY_NOMATCH_HINT = "Clear the search, or show devices and subsystems."
LIB_DAMAGED = "{} files in the folder could not be used and are not listed."
LIB_PREVIEW_NAME = "Preview of the chosen entry"
LIB_PREVIEW_NONE = "Choose a device or a subsystem to see what is in it."
LIB_PREVIEW_PIN_COLUMNS = ["Connector", "Pin", "Signal", "Function"]
LIB_PREVIEW_SUB_COLUMNS = ["Kind", "Item", "Detail"]
LIB_PREVIEW_TABLE_PINS = "Connectors and pins of the chosen device"
LIB_PREVIEW_TABLE_SUB = "Devices and connections of the chosen subsystem"
LIB_FILE = "File: {}"
LIB_PREVIEW_ERROR = "This entry cannot be read: {}"
LIB_PREVIEW_LOADING = "Reading the file…"
LIB_NUMBER = "Number of these devices"
LIB_NUMBER_TIP = "How many of this device to add. 1 adds the device. 2 adds it and a copy named ID-R on the redundant chain, 3 a further copy ID-3, and so on."
LIB_NUMBER_SUBSYSTEM = "A subsystem is added once; set the number of a device after adding it"
LIB_ADD = "Add to project"
LIB_ADD_TIP = "Add the chosen device or subsystem to the open project in one step that you can undo. Nothing of the project is replaced. (Enter)"
LIB_ADD_NONE = "Choose a device or a subsystem first"
LIB_ADD_READ_ONLY = "This project is read-only, so nothing can be added to it"
LIB_SAVE = "Save selection to library…"
LIB_SAVE_TIP = "Save the devices that are selected in the project to the library folder, as devices or as a subsystem"
LIB_SAVE_NONE = "Select one or more devices in the diagram or in the project tree first"
LIB_SAVE_NO_FOLDER = "Choose a library folder first"
LIB_CLOSE = "Close"
LIB_CLOSE_TIP = "Close this window (Esc); your project stays as it is"
LIB_ADDED = "Added {}."
LIB_ADDED_SUBSYSTEM = "Added the subsystem {}: {}, {}."
STEP_LIB_ADD_DEVICE = "Add {} from the library"
STEP_LIB_ADD_SUBSYSTEM = "Add the subsystem {} from the library"
LIB_SAVE_TITLE = "Save to library"
LIB_SAVE_AS = "Save as"
LIB_SAVE_AS_DEVICES = "Devices (each one is added on its own)"
LIB_SAVE_AS_DEVICES_TIP = "Save every selected device with its connectors and pins in a device file; if that file has a different device with the same ID you are asked before it is replaced"
LIB_SAVE_AS_SUBSYSTEM = "A subsystem (the devices and the connections between them, added together)"
LIB_SAVE_AS_SUBSYSTEM_TIP = (
    "Save the selected devices and the connections between them as one subsystem file"
)
LIB_SAVE_NAME = "Subsystem name"
LIB_SAVE_NAME_TIP = "What the subsystem is called in the library; it becomes the subsystem of every device that is added"
LIB_SAVE_DESCRIPTION = "Description"
LIB_SAVE_DESCRIPTION_TIP = "One or two lines for whoever finds it in the library (optional)"
LIB_SAVE_SELECTED = "Selected devices: {}"
LIB_SAVE_KEPT = "{} saved with them."
LIB_SAVE_LEFT_OUT = "{} to devices that are not selected are left out."
LIB_SAVE_FILE = "File: {} in {}"
LIB_SAVE_NEEDS_NAME = "A subsystem needs a name."
LIB_SAVE_EXISTS = "The library has a subsystem file {} already. Choose another name, or delete that file if it is out of date."
LIB_SAVE_OK = "Save"
LIB_SAVE_OK_TIP = "Write the file into the library folder"
LIB_SAVED_DEVICES = "Saved {} to {}."
LIB_SAVED_SUBSYSTEM = "Saved the subsystem {} to {}."
SETTINGS_LIBRARY_FOLDER = "Library folder"
SETTINGS_LIBRARY_TEXT = "The folder that holds your team's device and subsystem library files, for example on a shared drive or in a Git checkout. The program only reads it, and writes into it only when you save to the library. It is kept for you on this computer."
SETTINGS_LIBRARY_CHOOSE = "Choose…"
SETTINGS_LIBRARY_CLEAR = "Clear"
SETTINGS_LIBRARY_CLEAR_TIP = "Stop using a library folder"
SETTINGS_LIBRARY_OPEN = "Open the library…"
SETTINGS_LIBRARY_NONE = "No folder chosen"
HOME_LIBRARY = "Library…"
HOME_LIBRARY_TIP = (
    "Open the library window (Ctrl+Shift+O): devices and subsystems your team has saved"
)
NEWDEV_NUMBER = "Number of these devices"
NEWDEV_NUMBER_TIP = "1 adds one device. 2 adds it and a copy named ID-R on the redundant chain, 3 a further copy ID-3, and so on."
DV_NUMBER = "Number of these devices"
DV_NUMBER_TIP = (
    "How many of this device the project has. Raise it and press Add copies to add the others."
)
DV_NUMBER_COPY = "This device is a copy; set the number on the device it was copied from"
DV_COPIES = "Add copies"
DV_COPIES_TIP = "Add the missing devices so that there are this many: the second is named ID-R, the next ID-3 and so on, with the same connectors and the links mirrored (one undo step; to have fewer, delete a copy)"
DV_COPIES_SAME = "Raise the number to add copies"
STEP_COPIES = "Make {} of {}"
COPIES_DONE = "Added {}.{}"

# ---- Workshop feedback M5 (D-176): the role replaces Simple and Full ----
ROLE_SYSTEMS = "Systems engineer"
ROLE_ELECTRICAL = "Electrical / AIT engineer"
ROLE_SYSTEMS_TIP = (
    "Systems engineer: devices, connections between devices, subsystems, the library and the "
    "checks. The project opens on the next step and the screen shows less"
)
ROLE_ELECTRICAL_TIP = (
    "Electrical / AIT engineer: connectors, pinouts, harnesses, wires, build sheets and tests. "
    "Every area, panel and tab is shown and the project opens on the diagram"
)
M_ROLE = "Role"
SETTINGS_ROLE = "Role"
SETTINGS_ROLE_HINT = (
    "Who you are working as. The Systems engineer sees less and starts on the next step; the "
    "Electrical / AIT engineer sees every area. It only changes what is shown: nothing is "
    "locked and nothing is stored in the project."
)
ROLE_DIALOG_TITLE = "Who are you working as?"
ROLE_DIALOG_TEXT = "Pick the one that fits your work. It decides what the screen shows first."
ROLE_DIALOG_SYSTEMS = "Systems engineer"
ROLE_DIALOG_SYSTEMS_TEXT = (
    "I think in devices, the connections between them, subsystems and the library."
)
ROLE_DIALOG_ELECTRICAL = "Electrical / AIT engineer"
ROLE_DIALOG_ELECTRICAL_TEXT = (
    "I work with connectors, pinouts, harnesses, wires, build sheets and tests."
)
ROLE_DIALOG_LATER = "You can change this later in View > Role."
ROLE_DIALOG_NAME = "Choose your role"

# ---- 1.8.1: the library never replaces a different device without asking (D4, D18) ----
LIB_DAMAGED_ONE = "1 file in the folder could not be used and is not listed."
LIB_COLUMN_FILE = "File"
LIB_EMPTY_UNREADABLE_HINT = "Check that the drive is connected and that you may open the folder, then press Refresh, or choose another folder."
LIB_CONFLICT_TITLE = "Already in the library"
LIB_CONFLICT_ONE = "{id} is in the library already (in {file}) and differs in {how}."
LIB_CONFLICT_MANY = "These devices are in the library already (in {file}) and differ: {what}."
LIB_CONFLICT_ASK = "Replace the library's version, keep both under a new ID, or cancel?"
LIB_CONFLICT_REPLACE = "Replace"
LIB_CONFLICT_REPLACE_TIP = "Overwrite the device in the library file with the one of this project"
LIB_CONFLICT_NEW_ONE = "Save as {}"
LIB_CONFLICT_NEW_MANY = "Save under new IDs"
LIB_CONFLICT_NEW_TIP = (
    "Keep the library's device as it is and add this one next to it with a new ID"
)
LIB_CONFLICT_DIALOG = "Library conflict"
LIB_SAVE_TARGET = "The devices are saved in the file {} in the library folder."
LIB_SAVED_AS_NEW = "Saved {} to {} as {}."

# 1.8.1 (G5): command-line and Outputs-list trust fixes
IMP_WILL_KEEP = "No change"
OUT_NOT_OPENED = (
    "That file is not one the program wrote, so it is not opened. Open the folder instead."
)

# ---- 1.8.1 trust fixes ----------------------------------------------------------------------------
SHEET_TAB_TIP = (
    "Tab moves to the next cell. Ctrl+Tab leaves the table for the next control, "
    "Ctrl+Shift+Tab for the one before. Ctrl+C copies the selected cells."
)

# ---- 1.8.1: wording that follows what the project has (connections first, or interfaces first) -----
HV_EMPTY_HAS_LINKS = (
    "The project has connections and no harness yet. Select a connection and press Create harness."
)
LP_EMPTY_HAS_LINKS = "The lists are made from harnesses. Select a connection and press Create harness, and its lists appear here. The connection list (which pin of which device joins which) does not need a harness: Export writes it now."
LP_EMPTY_EXPORT = "Export the connection list…"
LP_EMPTY_EXPORT_TIP = "Write the connection list (CSV and Excel) and the other outputs of this project to its outputs folder; harness lists come after Create harness"
TREE_EMPTY_HAS_LINKS = {
    "interfaces": "No interfaces. The connections are listed under Connections.",
    "harnesses": "No harnesses yet. Select a connection and press Create harness.",
}
CHIP_BY_HAND = "Made by hand"
CHIP_BY_HAND_TIP = (
    "The harnesses were made from connections or by hand. Nothing is generated from the diagram."
)
HV_MADE_BY_HAND = "Made by hand"

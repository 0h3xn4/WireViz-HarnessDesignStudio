# Layout of dialogs and windows: the base, the audit and the sweep

This page is for people who add or change a dialog, a window or a panel. It says why windows used to lie on top of themselves on a real screen, what to derive from, and how the layout tests work and what they cannot see. Requirement: REQ-GUI-23.

## What went wrong, and the rule that follows

A top-level window can be made as small as its layout's *minimum size*. That minimum counts a word-wrapped label as one line (or as one word wide), but the label needs more lines the narrower the window is. A window that is given its minimum height (a window manager that opens it small, a size that was remembered, a person dragging an edge) is then shorter than its content at that width, and the layout squeezes the rows into each other: the name field over the note under it, the banner over the buttons. The *Add device* window of the owner's first run on a real display (Ubuntu, Qt) showed exactly this, with the banner *A device needs a name.* already visible. The offscreen platform that the tests use opens a window at its size hint, which does count the wrapped lines, so it never showed.

**Rule: derive every dialog from `gui.dialog_base.Dialog` (a wizard from `Wizard`).** The base keeps the window's minimum height equal to what the layout needs at the window's width (and grows the window when it is shorter), keeps the minimum width at least what the layout needs even when the dialog set its own `setMinimumWidth`, and follows the page of a wizard. A window that is a plain `QWidget` (the library window) calls `dialog_base.refit_on(self, event)` from its `event()`. A test (`tests/test_ui_dialog_layout.py`) fails when a dialog or wizard of the `gui` package does not derive from the base.

Two more rules that come from the same cause:

- A word-wrapped label inside a splitter, a stacked widget or a scroll area (containers that do not ask for height for width) is a `gui.wrap_label.WrapLabel`, whose minimum height follows its width. Inside a box layout a plain `QLabel` with `setWordWrap(True)` is enough.
- A form that asks for something to be typed (`_PlannerDialog.quiet_at_open`) does not show why its button is off before the person has changed anything: it is not wrong yet, and the disabled button says what is needed. The reason shows from the first change on. A dialog that cannot be used whatever is typed says why at once.

Never raise a minimum size to hide a layout that is too small for its content, and never give a dialog a fixed height; the base makes both unnecessary.

## The audit and the sweep

`tests/layout_audit.py` has `audit(widget)` for a widget that is shown. It returns findings for: two visible siblings that cover each other (`overlap`; a widget meant to lie on top of another carries the property `overlay`), a child that reaches out of its parent (`outside`), a widget smaller than its own minimum size hint (`squeezed`), a wrapped label shorter than its text needs (`wrap-clipped`), a label or button narrower than its own text where cutting is not meant (`text-cut`; an elided label is left out) and a window shorter than its layout needs (`window-short`).

`tests/layout_cases.py` lists every dialog and window of the program, built as the program builds them (a flatsat project with 40-character names behind them). `tests/test_ui_layout_sweep.py` opens each one at eight settings (light and dark theme; interface size 100, 125, 150 and 200 %; the base font 2 pt and 4 pt larger than the design says, in both themes), with the opening state, 40-character text in every field and the reason banner shown, at the size it opens at and at the smallest size it allows, and audits it. It also walks the main window through every area, tab, inspector tab and settings section at two window sizes, with and without three long banners under the bar, at the six settings that do not make the font 4 pt larger, in the Electrical / AIT engineer role, and in the Systems engineer role, the AIT role and Quick mode at two of them. A new dialog is added to `layout_cases.py`; a test fails when one is missing. The sweep tests are marked `slow` (CI runs them on the master branch, not on pull requests); `tests/test_ui_dialog_layout.py` is fast and is the one that runs always.

The main window is held to `overlap`, `outside`, `wrap-clipped` and `window-short` only. The other two rules find things that are known and meant (the bars fold and cut text when the window is narrow) or a few pixels wide; run the sweep with `HARNESS_LAYOUT_STRICT=1` to see all of them.

Known and not fixed (the sweep does not gate on them; `HARNESS_LAYOUT_STRICT=1` lists them): the rail buttons *Next step*, *Revisions* and *Drawings* are 6 to 8 px narrower than their text needs, the Undo and Redo buttons 3 px, and the *Role* button of the bar is cut at 125 % and more in a 1440 px wide window (the bar folds by its own rule, `TopBar._fit`); in a window of 1100 px with both side panels open the Devices tab, the Checks summary (*Values pending*, *Not yet checked*) and the Releases panel (*Compare revision*, *Mark…*) have less width than their buttons and labels need and cut their text; with three long banners under the bar in a window 700 px high the central area is shorter than its minimum (the Devices and Harness tabs scroll then, the Checks, Releases and Lists tabs do not); with the base font 4 pt larger the status bar and the bar are too crowded for the width of the window (the progress bar of a running job lies over the *Cancel* button) and the wrapped text of a banner can be 5 px short of its last line.

## What the sweep cannot see

- **The fonts of another machine.** The tests use the bundled Inter (or the font the offscreen platform finds) and an application style sheet that sets every size in pixels. A person whose system has other metrics, a fractional screen scaling (Wayland at 125 %), hinting or a wider fallback font gets text widths that the offscreen platform does not produce. The sweep stands in for this with larger sizes and a larger base font; it does not reproduce any particular machine.
- **The window manager.** What size a window manager gives a new window, and whether it honours the minimum size, is not tested. The base makes the minimum size right, so a window manager that honours it cannot make the window too small; one that does not honour it still can.
- **What a widget paints itself.** Dock titles, the canvas, table cells and icons are not laid out by Qt's layouts, so the audit does not look at them.
- **Native dialogs.** The file chooser is the platform's own.
- **Text that is not in the test data.** Only the texts of the example project, 40-character names and the program's own strings are used.

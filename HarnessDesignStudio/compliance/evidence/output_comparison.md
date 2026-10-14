# Generated outputs before and after Phase 2

Method: the reference projects `mini3`, `sat15` (generated) and `sat15_full` were built with the baseline commit `f34cb9b` (before the audit) and with the audit branch head; every output file (drawings SVG and PDF, wire lists, pinouts, BOM, mass and length, tests, labels, WireViz YAML, XLSX, block diagrams, matrices, DRC report, change log, JSON model) was compared byte for byte (`diff -r`).

Result: 595 output files per side. **592 are identical. 3 differ**, all of them `system/drc_report.md`:

- `Rules run: 22` is now `Rules run: 33` (new rules that find nothing in these projects);
- findings of rules that serve a standard requirement end with `Requirement: <ID>` (connector look-alike: ECSS-Q-ST-30-11_0140054).

Drawings, wire lists, pinouts, BOMs, labels, mass and length tables, test tables, block diagrams and the model hash are unchanged. The EMC class column and label tag appear only in projects whose interface types define EMC classes; none of the reference projects does.

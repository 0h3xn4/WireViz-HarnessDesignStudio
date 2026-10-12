<!-- harness-design-studio 1.0.0 model ccc0cee5a01e -->
# Design rule check: mini3 (example data)

Model hash: `ccc0cee5a01e`. Rules run: 34.
Open: 0 error(s), 7 warning(s), 4 note(s). Waived: 0.

Placeholder configuration in use: derating, emc, generation, segmentation, segregation, titleblock. Results that depend on it are marked as not checked.

## Warnings (7)

- **Part EX-MICROD-15-F is not approved yet but is used (3 place(s))** (`part-unapproved.EX-MICROD-15-F`)  
  Only approved parts may be built into flight hardware. To fix it: Approve the part in the parts list, or choose an approved one. Requirement: ESCC3901-4.4.
- **Part EX-MICROD-15-M is not approved yet but is used (1 place(s))** (`part-unapproved.EX-MICROD-15-M`)  
  Only approved parts may be built into flight hardware. To fix it: Approve the part in the parts list, or choose an approved one. Requirement: ESCC3901-4.4.
- **Part EX-MICROD-25-F is not approved yet but is used (1 place(s))** (`part-unapproved.EX-MICROD-25-F`)  
  Only approved parts may be built into flight hardware. To fix it: Approve the part in the parts list, or choose an approved one. Requirement: ESCC3901-4.4.
- **Part EX-MICROD-25-M is not approved yet but is used (1 place(s))** (`part-unapproved.EX-MICROD-25-M`)  
  Only approved parts may be built into flight hardware. To fix it: Approve the part in the parts list, or choose an approved one. Requirement: ESCC3901-4.4.
- **Part EX-MICROD-9-F is not approved yet but is used (4 place(s))** (`part-unapproved.EX-MICROD-9-F`)  
  Only approved parts may be built into flight hardware. To fix it: Approve the part in the parts list, or choose an approved one. Requirement: ESCC3901-4.4.
- **Part EX-MICROD-9-M is not approved yet but is used (2 place(s))** (`part-unapproved.EX-MICROD-9-M`)  
  Only approved parts may be built into flight hardware. To fix it: Approve the part in the parts list, or choose an approved one. Requirement: ESCC3901-4.4.
- **Part EX-WIRE-TWISTED-SHIELDED is not approved yet but is used (4 place(s))** (`part-unapproved.EX-WIRE-TWISTED-SHIELDED`)  
  Only approved parts may be built into flight hardware. To fix it: Approve the part in the parts list, or choose an approved one. Requirement: ESCC3901-4.4.

## Not checked / note (4)

- **EMC class separation was not checked: the EMC rules are still a placeholder** (`unchecked-config.emc`)  
  A rule that needs a number nobody has entered, or an analysis outside the tool, cannot say anything, and silence must not look like a pass. To fix it: Fill in the missing value (see docs/PLACEHOLDERS.md), or do the analysis the note names and record it in the design review.
- **Shield grounding was not checked against a concept: it is still a placeholder** (`unchecked-config.grounding`)  
  A rule that needs a number nobody has entered, or an analysis outside the tool, cannot say anything, and silence must not look like a pass. To fix it: Fill in the missing value (see docs/PLACEHOLDERS.md), or do the analysis the note names and record it in the design review.
- **Power, signal and sensitive-analog separation was not checked: the category pairs are still a placeholder** (`unchecked-config.separation`)  
  A rule that needs a number nobody has entered, or an analysis outside the tool, cannot say anything, and silence must not look like a pass. To fix it: Fill in the missing value (see docs/PLACEHOLDERS.md), or do the analysis the note names and record it in the design review.
- **Spare pins were not checked: the required fraction is still a placeholder** (`unchecked-config.spare-pins`)  
  A rule that needs a number nobody has entered, or an analysis outside the tool, cannot say anything, and silence must not look like a pass. To fix it: Fill in the missing value (see docs/PLACEHOLDERS.md), or do the analysis the note names and record it in the design review.

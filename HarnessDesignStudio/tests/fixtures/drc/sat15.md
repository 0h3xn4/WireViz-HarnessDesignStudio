# Design rule check: sat15 (example data)

Model hash: `72ded2102aa8`. Rules run: 35.
Open: 0 error(s), 20 warning(s), 28 note(s). Waived: 0.

Placeholder configuration in use: derating, emc, generation, segmentation, segregation, titleblock. Results that depend on it are marked as not checked.

## Warnings (20)

- **HTR1-J01, HTR1-J02 on HTR1 are identical (EX-MICROD-9-F, same keying) and could be plugged in the wrong place** (`connector-lookalike.HTR1-J01`)  
  Identical connectors on one unit can be swapped by mistake. To fix it: Use different keying or a different insert on one of them. Requirement: ECSS-Q-ST-30-11_0140054.
- **MTQ1-J01, MTQ1-J02 on MTQ1 are identical (EX-MICROD-9-F, same keying) and could be plugged in the wrong place** (`connector-lookalike.MTQ1-J01`)  
  Identical connectors on one unit can be swapped by mistake. To fix it: Use different keying or a different insert on one of them. Requirement: ECSS-Q-ST-30-11_0140054.
- **OBC1-J02, OBC1-J03, OBC1-J04 and 8 more on OBC1 are identical (EX-MICROD-31-F, same keying) and could be plugged in the wrong place** (`connector-lookalike.OBC1-J02`)  
  Identical connectors on one unit can be swapped by mistake. To fix it: Use different keying or a different insert on one of them. Requirement: ECSS-Q-ST-30-11_0140054.
- **PCDU1-J01, PCDU1-J02, PCDU1-J03 and 8 more on PCDU1 are identical (EX-MICROD-9-F, same keying) and could be plugged in the wrong place** (`connector-lookalike.PCDU1-J01`)  
  Identical connectors on one unit can be swapped by mistake. To fix it: Use different keying or a different insert on one of them. Requirement: ECSS-Q-ST-30-11_0140054.
- **SA1-J01, SA1-J02 on SA1 are identical (EX-MICROD-9-F, same keying) and could be plugged in the wrong place** (`connector-lookalike.SA1-J01`)  
  Identical connectors on one unit can be swapped by mistake. To fix it: Use different keying or a different insert on one of them. Requirement: ECSS-Q-ST-30-11_0140054.
- **SS1-J01, SS1-J02 on SS1 are identical (EX-MICROD-9-F, same keying) and could be plugged in the wrong place** (`connector-lookalike.SS1-J01`)  
  Identical connectors on one unit can be swapped by mistake. To fix it: Use different keying or a different insert on one of them. Requirement: ECSS-Q-ST-30-11_0140054.
- **IF-012-R connects the nominal chain to the redundant chain** (`cross-strap.IF-012-R`)  
  One unit is nominal and the other redundant. A cross-strap like this means one failure could affect both chains, so reviewers will ask about it.
- **Part EX-MICROD-15-F is not approved yet but is used (5 place(s))** (`part-unapproved.EX-MICROD-15-F`)  
  Only approved parts may be built into flight hardware. To fix it: Approve the part in the parts list, or choose an approved one. Requirement: ESCC3901-4.4.
- **Part EX-MICROD-15-M is not approved yet but is used (5 place(s))** (`part-unapproved.EX-MICROD-15-M`)  
  Only approved parts may be built into flight hardware. To fix it: Approve the part in the parts list, or choose an approved one. Requirement: ESCC3901-4.4.
- **Part EX-MICROD-21-F is not approved yet but is used (3 place(s))** (`part-unapproved.EX-MICROD-21-F`)  
  Only approved parts may be built into flight hardware. To fix it: Approve the part in the parts list, or choose an approved one. Requirement: ESCC3901-4.4.
- **Part EX-MICROD-21-M is not approved yet but is used (2 place(s))** (`part-unapproved.EX-MICROD-21-M`)  
  Only approved parts may be built into flight hardware. To fix it: Approve the part in the parts list, or choose an approved one. Requirement: ESCC3901-4.4.
- **Part EX-MICROD-31-F is not approved yet but is used (22 place(s))** (`part-unapproved.EX-MICROD-31-F`)  
  Only approved parts may be built into flight hardware. To fix it: Approve the part in the parts list, or choose an approved one. Requirement: ESCC3901-4.4.
- **Part EX-MICROD-31-M is not approved yet but is used (11 place(s))** (`part-unapproved.EX-MICROD-31-M`)  
  Only approved parts may be built into flight hardware. To fix it: Approve the part in the parts list, or choose an approved one. Requirement: ESCC3901-4.4.
- **Part EX-MICROD-9-F is not approved yet but is used (38 place(s))** (`part-unapproved.EX-MICROD-9-F`)  
  Only approved parts may be built into flight hardware. To fix it: Approve the part in the parts list, or choose an approved one. Requirement: ESCC3901-4.4.
- **Part EX-MICROD-9-M is not approved yet but is used (28 place(s))** (`part-unapproved.EX-MICROD-9-M`)  
  Only approved parts may be built into flight hardware. To fix it: Approve the part in the parts list, or choose an approved one. Requirement: ESCC3901-4.4.
- **Part EX-RJ45-F is not approved yet but is used (5 place(s))** (`part-unapproved.EX-RJ45-F`)  
  Only approved parts may be built into flight hardware. To fix it: Approve the part in the parts list, or choose an approved one. Requirement: ESCC3901-4.4.
- **Part EX-RJ45-M is not approved yet but is used (2 place(s))** (`part-unapproved.EX-RJ45-M`)  
  Only approved parts may be built into flight hardware. To fix it: Approve the part in the parts list, or choose an approved one. Requirement: ESCC3901-4.4.
- **Part EX-SMA-F is not approved yet but is used (2 place(s))** (`part-unapproved.EX-SMA-F`)  
  Only approved parts may be built into flight hardware. To fix it: Approve the part in the parts list, or choose an approved one. Requirement: ESCC3901-4.4.
- **Part EX-WIRE-SINGLE is not approved yet but is used (30 place(s))** (`part-unapproved.EX-WIRE-SINGLE`)  
  Only approved parts may be built into flight hardware. To fix it: Approve the part in the parts list, or choose an approved one. Requirement: ESCC3901-4.4.
- **Part EX-WIRE-TWISTED-SHIELDED is not approved yet but is used (24 place(s))** (`part-unapproved.EX-WIRE-TWISTED-SHIELDED`)  
  Only approved parts may be built into flight hardware. To fix it: Approve the part in the parts list, or choose an approved one. Requirement: ESCC3901-4.4.

## Not checked / note (28)

- **EMC class separation was not checked: the EMC rules are still a placeholder** (`unchecked-config.emc`)  
  A rule that needs a number nobody has entered, or an analysis outside the tool, cannot say anything, and silence must not look like a pass. To fix it: Fill in the missing value (see docs/PLACEHOLDERS.md), or do the analysis the note names and record it in the design review.
- **Shield grounding was not checked against a concept: it is still a placeholder** (`unchecked-config.grounding`)  
  A rule that needs a number nobody has entered, or an analysis outside the tool, cannot say anything, and silence must not look like a pass. To fix it: Fill in the missing value (see docs/PLACEHOLDERS.md), or do the analysis the note names and record it in the design review.
- **Power, signal and sensitive-analog separation was not checked: the category pairs are still a placeholder** (`unchecked-config.separation`)  
  A rule that needs a number nobody has entered, or an analysis outside the tool, cannot say anything, and silence must not look like a pass. To fix it: Fill in the missing value (see docs/PLACEHOLDERS.md), or do the analysis the note names and record it in the design review.
- **Spare pins were not checked: the required fraction is still a placeholder** (`unchecked-config.spare-pins`)  
  A rule that needs a number nobody has entered, or an analysis outside the tool, cannot say anything, and silence must not look like a pass. To fix it: Fill in the missing value (see docs/PLACEHOLDERS.md), or do the analysis the note names and record it in the design review.
- **IF-001 uses connectors the tool chose for you** (`unconfirmed.IF-001`)  
  Auto-filled choices are marked until a person confirms them, so nobody assumes they were reviewed.
- **IF-001-R uses connectors the tool chose for you** (`unconfirmed.IF-001-R`)  
  Auto-filled choices are marked until a person confirms them, so nobody assumes they were reviewed.
- **IF-002 uses connectors the tool chose for you** (`unconfirmed.IF-002`)  
  Auto-filled choices are marked until a person confirms them, so nobody assumes they were reviewed.
- **IF-003 uses connectors the tool chose for you** (`unconfirmed.IF-003`)  
  Auto-filled choices are marked until a person confirms them, so nobody assumes they were reviewed.
- **IF-004 uses connectors the tool chose for you** (`unconfirmed.IF-004`)  
  Auto-filled choices are marked until a person confirms them, so nobody assumes they were reviewed.
- **IF-005 uses connectors the tool chose for you** (`unconfirmed.IF-005`)  
  Auto-filled choices are marked until a person confirms them, so nobody assumes they were reviewed.
- **IF-006 uses connectors the tool chose for you** (`unconfirmed.IF-006`)  
  Auto-filled choices are marked until a person confirms them, so nobody assumes they were reviewed.
- **IF-007 uses connectors the tool chose for you** (`unconfirmed.IF-007`)  
  Auto-filled choices are marked until a person confirms them, so nobody assumes they were reviewed.
- **IF-008 uses connectors the tool chose for you** (`unconfirmed.IF-008`)  
  Auto-filled choices are marked until a person confirms them, so nobody assumes they were reviewed.
- **IF-009 uses connectors the tool chose for you** (`unconfirmed.IF-009`)  
  Auto-filled choices are marked until a person confirms them, so nobody assumes they were reviewed.
- **IF-010 uses connectors the tool chose for you** (`unconfirmed.IF-010`)  
  Auto-filled choices are marked until a person confirms them, so nobody assumes they were reviewed.
- **IF-011 uses connectors the tool chose for you** (`unconfirmed.IF-011`)  
  Auto-filled choices are marked until a person confirms them, so nobody assumes they were reviewed.
- **IF-012 uses connectors the tool chose for you** (`unconfirmed.IF-012`)  
  Auto-filled choices are marked until a person confirms them, so nobody assumes they were reviewed.
- **IF-012-R uses connectors the tool chose for you** (`unconfirmed.IF-012-R`)  
  Auto-filled choices are marked until a person confirms them, so nobody assumes they were reviewed.
- **IF-013 uses connectors the tool chose for you** (`unconfirmed.IF-013`)  
  Auto-filled choices are marked until a person confirms them, so nobody assumes they were reviewed.
- **IF-014 uses connectors the tool chose for you** (`unconfirmed.IF-014`)  
  Auto-filled choices are marked until a person confirms them, so nobody assumes they were reviewed.
- **IF-015 uses connectors the tool chose for you** (`unconfirmed.IF-015`)  
  Auto-filled choices are marked until a person confirms them, so nobody assumes they were reviewed.
- **IF-016 uses connectors the tool chose for you** (`unconfirmed.IF-016`)  
  Auto-filled choices are marked until a person confirms them, so nobody assumes they were reviewed.
- **IF-017 uses connectors the tool chose for you** (`unconfirmed.IF-017`)  
  Auto-filled choices are marked until a person confirms them, so nobody assumes they were reviewed.
- **IF-018 uses connectors the tool chose for you** (`unconfirmed.IF-018`)  
  Auto-filled choices are marked until a person confirms them, so nobody assumes they were reviewed.
- **IF-019 uses connectors the tool chose for you** (`unconfirmed.IF-019`)  
  Auto-filled choices are marked until a person confirms them, so nobody assumes they were reviewed.
- **IF-020 uses connectors the tool chose for you** (`unconfirmed.IF-020`)  
  Auto-filled choices are marked until a person confirms them, so nobody assumes they were reviewed.
- **IF-021 uses connectors the tool chose for you** (`unconfirmed.IF-021`)  
  Auto-filled choices are marked until a person confirms them, so nobody assumes they were reviewed.
- **IF-022 uses connectors the tool chose for you** (`unconfirmed.IF-022`)  
  Auto-filled choices are marked until a person confirms them, so nobody assumes they were reviewed.

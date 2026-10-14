# M2 gate note: UX document and clickable prototype (awaiting owner review)

**Done**
- `docs/UX.md`: personas, ten journeys, information architecture, wireframes, design system, Qt mapping, usability test plan, my own UX review log, questions for you.
- `prototype/index.html`: single-file, offline, clickable prototype generated from `gui/tokens.py` (open it in any browser; add `?notour` to skip the first-run tour). Mock data throughout.
- `gui/tokens.py` design tokens with tests: WCAG 2.2 AA contrast on all surfaces in light and dark, and colour-blind separation of the seven signal categories (dE >= 20; an earlier hand-picked palette scored 2.2).
- 14 screenshots in `docs/ux/screens/`; 33 automated browser journey tests plus 2 build/offline tests.

**Tested**: 199 tests pass (1 skipped: needs a non-root user). Core coverage 97.6%. The journey tests fail on any console error or non-local network request.

**UX review**: rendering the screens found 5 high-severity issues (unit placed on top of another, unreadable pressed/primary buttons on hover, source unit greyed in connect mode, a cross-strap "fix" that defeated redundancy, unusable layout at 150 to 200% scale) and 3 medium/low ones. All are fixed and have regression tests; 3 are open and listed in UX.md section 10 (label overlap and auto-layout, hidden Properties hint, minimap and keyboard link drawing).

**Not done on purpose**: no Qt editor code until you approve the prototype (spec UX process step 2).

**Needs from you**: answers to the 8 questions at the end of UX.md; a decision on which open issues block approval; ideally a quick click-through yourself, because I can only test with scripts, not as a first-time user.

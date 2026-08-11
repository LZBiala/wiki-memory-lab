# milldale — session 04
MODE: ScriptedAgent — deterministic, zero API keys; write-backs are rule-driven

INDEX loaded: 9 notes / 159 tokens

## task s4t1 — "Is the pharmacy on Elm Street open this evening?"
RECALL: pharmacy-hours (1 note(s) / 48 tokens)
ANSWER: The note says 9am to 6pm weekdays, so it is closed this evening after 6pm. (from notes: pharmacy-hours)

## task s4t2 — "What time is the last route 4 bus and which streets does it cross?"
RECALL: bus-schedule, town-map (2 note(s) / 127 tokens)
ANSWER: Route 4 runs until 8pm from the square, along Main Street past Elm. An old-town leaflet was in the rack at the stop; the bakery window also had weekend hours posted. (from notes: bus-schedule, town-map)
WRITE-BACK: CREATE town-history — leaflet picked up at the bus stop; hook written lazily on purpose
WRITE-BACK: EXTEND bakery-hours — weekend hours posted in the bakery window

SESSION 04 TOTALS: index 159 + recalled 175 = 334 context tokens

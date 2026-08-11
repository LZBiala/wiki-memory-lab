# milldale — session 02
MODE: ScriptedAgent — deterministic, zero API keys; write-backs are rule-driven

INDEX loaded: 3 notes / 58 tokens

## task s2t1 — "When does the bakery open on Tuesday?"
RECALL: bakery-hours (1 note(s) / 50 tokens)
ANSWER: Weekday opening is 7am, so Tuesday it opens at 7am. (from notes: bakery-hours)

## task s2t2 — "Which bus goes to the library and how do I get a library card?"
RECALL: (none)
ANSWER: Route 4 stops by the library; bring one piece of mail to the counter to get a card. The Saturday market poster was up at the stop. (no notes recalled)
WRITE-BACK: CREATE library-card — asked at the library counter
WRITE-BACK: CREATE bus-schedule — timetable read at the stop
WRITE-BACK: CREATE farmers-market — poster seen at the bus stop

SESSION 02 TOTALS: index 58 + recalled 50 = 108 context tokens

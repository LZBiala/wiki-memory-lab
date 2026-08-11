# milldale — session 06
MODE: ScriptedAgent — deterministic, zero API keys; write-backs are rule-driven

INDEX loaded: 12 notes / 202 tokens

## task s6t1 — "How do I renew my library card this month?"
RECALL: library-card (1 note(s) / 52 tokens)
ANSWER: Renewal is free every two years — bring one piece of mail to the counter. (from notes: library-card)

## task s6t2 — "Which bus route runs past the riverside park?"
RECALL: riverside-park, bus-schedule, riverside-parking (3 note(s) / 168 tokens)
ANSWER: Route 4 from the square passes Elm Street near the river; the park entrance is a short walk from that stop. (from notes: riverside-park, bus-schedule, riverside-parking)

## task s6t3 — "Can I still catch the route 4 bus by the square tonight?"
RECALL: bus-schedule (1 note(s) / 53 tokens)
ANSWER: No — the town notice posted today says route 4 is discontinued; a new route 7 now runs from the square. The walk-in clinic sign by the stop listed Saturday hours too. (from notes: bus-schedule)
WRITE-BACK: CREATE walk-in-clinic-hours — same clinic as the existing note — a paraphrased title the exact matcher will miss, counted as false-CREATE [intended EXTEND — counted as false-CREATE]

CORRECTION: PRUNE bus-schedule — contradicted by session 6 town notice: route 4 discontinued
CORRECTION: CREATE bus-route-7 — replacement for pruned bus-schedule
DECAY: ARCHIVE school-play — not created or recalled inside the decay window

SESSION 06 TOTALS: index 202 + recalled 220 = 422 context tokens

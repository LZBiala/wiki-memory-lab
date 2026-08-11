# milldale — session 03
MODE: ScriptedAgent — deterministic, zero API keys; write-backs are rule-driven

INDEX loaded: 6 notes / 106 tokens

## task s3t1 — "What bus can I take to the farmers market on Saturday?"
RECALL: farmers-market, bus-schedule (2 note(s) / 107 tokens)
ANSWER: Route 4 runs hourly from the square; the market is on the square Saturdays 8am to noon, so any morning route 4 works. (from notes: farmers-market, bus-schedule)

## task s3t2 — "Where can I get my bike fixed and is there a pharmacy nearby?"
RECALL: (none)
ANSWER: The bike shop on Forge Alley does repairs with a two-day turnaround; the pharmacy is on Elm Street, open 9am to 6pm. The riverside park was worth the detour after. (no notes recalled)
WRITE-BACK: CREATE pharmacy-hours — sign read on the door
WRITE-BACK: CREATE bike-repair — asked in the shop
WRITE-BACK: CREATE riverside-park — visited after the errand

SESSION 03 TOTALS: index 106 + recalled 107 = 213 context tokens

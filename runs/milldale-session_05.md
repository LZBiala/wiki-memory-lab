# milldale — session 05
MODE: ScriptedAgent — deterministic, zero API keys; write-backs are rule-driven

INDEX loaded: 10 notes / 168 tokens

## task s5t1 — "When does the bakery open on Saturday?"
RECALL: bakery-hours (1 note(s) / 59 tokens)
ANSWER: Saturday hours are 8am to 1pm, per the extended note. (from notes: bakery-hours)

## task s5t2 — "Is the farmers market running this Saturday and where is it?"
RECALL: farmers-market (1 note(s) / 54 tokens)
ANSWER: Yes — Saturdays 8am to noon on the town square. (from notes: farmers-market)

## task s5t3 — "Where can I park near the river for a picnic?"
RECALL: riverside-park (1 note(s) / 56 tokens)
ANSWER: The picnic tables are in the riverside park; the gravel lot off River Road has free parking, forty spaces. (from notes: riverside-park)
WRITE-BACK: CREATE riverside-parking — found the lot on the picnic trip; distinct concept from the park itself
WRITE-BACK: CREATE clinic-hours — sign read while passing the clinic

SESSION 05 TOTALS: index 168 + recalled 169 = 337 context tokens

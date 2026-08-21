# milldale - session 08
MODE: ScriptedAgent - deterministic, zero API keys; write-backs are rule-driven

INDEX loaded: 14 notes / 246 tokens

## task s8t1 - "When does the bakery open today and is the hardware store open too?"
RECALL: bakery-hours (1 note(s) / 59 tokens)
ANSWER: The bakery opens 7am weekdays, 8am Saturday; the hardware store on Forge Alley turned out to be open 8am to 6pm. (from notes: bakery-hours)
WRITE-BACK: CREATE hardware-store - first visit to the hardware store

## task s8t2 - "Which route 7 bus gets me to the harvest festival?"
RECALL: bus-route-7, harvest-festival (2 note(s) / 122 tokens)
ANSWER: Route 7 runs hourly from the square, and the festival is on the square itself - any morning bus works. (from notes: bus-route-7, harvest-festival)

## task s8t3 - "Can the bike shop fix a flat tire before the clinic opens?"
RECALL: bike-repair, clinic-hours, walk-in-clinic-hours (3 note(s) / 144 tokens)
ANSWER: Tube work is same-day at the bike shop; the clinic opens at 9am on weekdays (both clinic notes describe the same clinic - the duplicate is the cost of the missed merge). (from notes: bike-repair, clinic-hours, walk-in-clinic-hours)

SESSION 08 TOTALS: index 246 + recalled 325 = 571 context tokens

# milldale — session 07
MODE: ScriptedAgent — deterministic, zero API keys; write-backs are rule-driven

INDEX loaded: 12 notes / 203 tokens

## task s7t1 — "When was the old mill by the river founded?"
RECALL: (none)
MISS: town-history (labeled relevant, not recalled — its hook gave the scorer nothing to match)
ANSWER: No note matched this question, so it cannot be answered from memory. (no notes recalled)

## task s7t2 — "Is the pharmacy on Elm Street still open until 6?"
RECALL: pharmacy-hours (1 note(s) / 48 tokens)
ANSWER: The note says 9am to 6pm — but the new owner posted new hours today: 8am to 8pm every day. The note is now wrong and gets pruned. (from notes: pharmacy-hours)

## task s7t3 — "What is happening at the harvest festival and where is the mayor's office?"
RECALL: (none)
ANSWER: The harvest festival runs the first weekend of the month on the square; the mayor's office is on the second floor of the town hall, open Monday to Thursday. (no notes recalled)
WRITE-BACK: CREATE harvest-festival — banner read on the square
WRITE-BACK: CREATE mayor-office — asked at the town hall

CORRECTION: PRUNE pharmacy-hours — new owner posted new hours in session 7; the old note is wrong
CORRECTION: CREATE pharmacy-hours — replacement for pruned pharmacy-hours

SESSION 07 TOTALS: index 203 + recalled 48 = 251 context tokens

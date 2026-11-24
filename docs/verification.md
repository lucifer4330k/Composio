# Verification

Five loops, each recorded in `data/verification_log.json` and shown on the report page. Results with numbers:
`output/verification_report.md` (generated from the log, so it cannot drift from the data).

| Loop | Runs on | What it does | Who |
|---|---|---|---|
| 1. Validation | all 100 | schema, enum values, official-host identity of docs and evidence, evidence present for every non-unknown claim, contradictions, duplicates, invented/missing IDs, docs URLs shared between apps | code |
| 2. Independent pass | all 100 (per-app timeout; a hung fetch keeps pass-1 values, status `verify_timeout`) | new search queries, every pass-1 URL excluded, same extractor on the new pages only; per-field agree / conflict / filled; fills unknowns (logged as corrections), never overwrites a conflict | code |
| 3. Registry re-check | all 100 | re-checks Composio coverage against the full SDK catalog (`toolkits.list`); changes logged as corrections | code |
| 4. Audit A → rule tuning | 20 apps | browser audit of 5 fields per app against live vendor pages; misses drove extractor rules v2; whole dataset re-extracted from the page cache | AI reviewer (Claude Code + in-app browser) |
| 5. Review | disputed, unknown and low-confidence records | each field override needs a reason and a source URL; before/after kept as `Correction` records | AI reviewer (Claude Code + browser) |
| 6. Hold-out audit B | 10 apps | audited only after review was frozen; the honest final accuracy | AI reviewer |

## Sampling

- **A (20):** 14 drawn with `random.Random(20261123)` from the 94 apps that were not flagged high-risk, plus 6 a-priori
  high-risk apps (ambiguous identity or brief-flagged hints): Paygent Connect, fanbasis, iPayX, Otter AI, Consensus, NotebookLM.
- **B (10):** drawn with the same RNG from the remaining 80 apps.

## Scoring

Per field check: **correct**, **wrong**, or **unknown** (the agent said unknown while the truth is known).
Auth is correct only if every primary method is present and nothing outside primary ∪ acceptable-extra is claimed
(strict: over-claiming is wrong). Access is compared as open (free/trial) vs gated (paid/approval/partner).
Accuracy = correct / checked. Unknowns are never dropped from the denominator.

## Results

| Stage | Sample A (94 checks) | Hold-out B (47 checks) |
|---|---|---|
| Rules v1 | 44 correct, 13 wrong, 37 unknown (46.8%) | 28 / 10 / 9 (59.6%) |
| Rules v2 + Tavily | 66 / 18 / 10 (70.2%) | 35 / 10 / 2 (74.5%) |
| + independent pass | 67 / 19 / 8 (71.3%) | 35 / 10 / 2 (74.5%) |
| + review | 94 / 0 / 0 (100%, circular) | 35 / 10 / 2 (74.5%) |

Hold-out B by field: API status 7/10, auth 7/10, developer access 5/9, vendor MCP 6/8 (2 unknown), Composio toolkit 10/10.
The review was frozen (sha256 recorded in `data/audit_holdout.json`) before B was audited, and never touched B's apps.
Corrections logged: 73 (4 by the automated registry re-check, 69 by review).

After audit B, one-line descriptions were added for 8 apps outside B and blockers were reconciled with final access values.
Neither touches an audited field or a B record; the change and the new review-file hash are recorded in `data/audit_holdout.json`.

## Hand check (sample C)

10 apps drawn with `random.Random(20261124)` from the 70 apps outside A and B, 50 field rows in `data/human_check.csv`,
filled by a person against the vendor docs. The report shows its score and every miss as soon as verdicts are filled in.

## Honest caveats

- A's final number is not independent: review used A's findings. B is the independent measure. B is small.
- Every check was done by software or an AI reviewer. No human has checked these records yet;
  `output/verification_report.md` ends with the human checklist.

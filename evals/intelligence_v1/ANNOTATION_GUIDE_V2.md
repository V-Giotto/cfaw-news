# G1-a annotation guide — g1a-guide-v2

This revision extends the original guide; its four 0–3 scales, graded relevance,
tier, relation, change and scope definitions remain applicable. The original v1
guide and packets remain historical artifacts. All five stories are synthetic.
No real participants or submissions are currently confirmed.

Only real people may supply human annotations. An administrator must confirm
their identity privately, record anonymous participant IDs and confirm independent
submission. Two IDs, AI calls and structural validation are not human evidence.

First pilot DEV-01, resolve guide ambiguity, then freeze a new version before
formal annotation. Give each participant only the current single-step v2 packet,
blank form and this guide. Do not distribute future packets before their prior
submission is frozen. Never distribute authored expectations, reference event IDs,
claims, model rankings, other people's initial labels or administrator probes.

The packet includes only visible documents, the historical Persona, time window,
delivery snapshots, exposure and coverage. Included/rendered/opened/acknowledged
are distinct signals; none establishes comprehension. Gaps are unknown coverage.

Use your own local event IDs and the exact visible document members. Extract
minimal claims with paragraph citations, semantic judgment supported/unsupported/
uncertain, scope and limitations. A cited paragraph existing is not support.
Score relevance/potential_value/novelty_to_persona/evidence_quality 0–3 and separately
graded_relevance 0–3. Use new/meaningful_update/no_change/correction/withdrawal/
insufficient and focus/radar/archive/hold with reasons and uncertainty. Publicity
is not evidence. Different domains copying one release are not independent tests.

Keep earlier packets after their submissions have frozen. Event grouping uses
the current packet's latest versions; claim citations may compare an earlier
version retained from the same story with its current correction. Every cited
version must have been available by the current as_of. Gold supporting versions
must belong to that same event. Future versions and other stories remain excluded.

| Dimension | 0 | 1 | 2 | 3 |
|---|---|---|---|---|
| relevance | unrelated | weak interest | clear work/interest link | directly affects an explicit goal/constraint |
| potential_value | no identifiable use | interesting, use unclear | plausible practical/research value | could materially alter an engineering/research choice |
| novelty_to_persona | already known, no increment | minor addition | new fact/update | new capability, critical constraint or major correction |
| evidence_quality | untraceable | one party's claim | direct official evidence or scoped independent test | substantively independent direct evidence, with explicit scope |

Graded relevance: 0=no recommendation value; 1=weak/reference; 2=worth knowing;
3=high priority. It is separately judged, not a computed average of dimensions.
Focus means important and checkable, radar means potentially useful but limited,
archive means ordinary/duplicate reference material, hold means unavailable,
unverifiable or too uncertain to recommend. Explain inconsistent tier/grade choices.
New means first visible event; meaningful_update requires a substantive new fact;
no_change means no substantive increment within observed coverage; correction
requires an evidenced correction; withdrawal requires an explicit withdrawal;
insufficient means the available evidence cannot determine change. Never use
missing coverage as no_change, popularity as verification, or a scoped result
as proof for all versions, platforms or tasks.

Retain raw submissions append-only. Hash each participant's canonical records in
(timeline_id, step_id, local_event_id, annotation_id) order. Record actual receipt,
submission and freeze times, packet SHA, guide SHA and annotation version.
Only after both initial submissions freeze may discussion or adjudication start.

Align events by visible document membership, never by local ID or list position.
Record split/merge/missing-event disagreements; do not force them into matches.
Compute raw agreement and confusion matrices before adjudication: quadratic
weighted Cohen kappa for ordinal scores, nominal kappa for tier/change, pairwise
relationship agreement and both directions of positive-pair precision/recall/F1.
Missing/degenerate denominators are null with a reason. Report matching coverage.
Kappa below the suggested .70 calls for a new guide and reannotation version;
never remove disagreements to increase a score.

Gold must trace to initial annotation IDs, an explicit event alignment and, for
disagreement, an adjudication with a reason and actual time. Preserve unresolved
and insufficient rather than invent certainty. Separate support-review records
must cite the original claim reviews, evidence and adjudication reason.

The review_session status remains not_started until actual people participate.
Human confirmation is a manual attestation, not a programmatic identity proof.
Without complete independently frozen submissions the total G1-a gate is NOT MET;
synthetic arithmetic/lineage tests are never counted as human submissions.

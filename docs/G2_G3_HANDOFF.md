# G2 → G3 offline handoff contract

PR6 exports immutable development artifacts. This document describes the interface;
it does not authorize G3 work or assert that final G2 acceptance has run.

## Required release and acceptance

Final acceptance requires a separately approved source commit, exact worktree/tree
bytes, a sealed full campaign, independently invoked post-prediction evaluation,
current checks/JUnit and output-bound AI development review. An uncommitted
worktree or CI smoke cannot produce final `g2_development PASS`.

The source release is an integration release of the actual PR1–PR6 files. Existing
PR1–PR5 local reports are historical evidence, not five merged commits. Prior failed
commands and later closing evidence remain separate. G0 is the historical baseline.

## Read-only objects

`pr6.handoff.views` emits `G3InputView` with unchanged event_key/event_revision,
EvidenceBundle, original rule Item, optional expression, snapshot/as_of, source
coverage, lineage IDs and trace pointer. There is no personalized rank. A mock
expression never replaces the original rule Item or becomes independent evidence.

Consumers must preserve source attribution, scope, unknown independence,
unsupported/uncertain states, historical lifecycle records and coverage gaps.
Alias resolution requires the requested time; current aliases cannot overwrite
past snapshots. Absence of new claims is not evidence of no change in the world.

G3 offline eligibility is a technical result only. Administrator acceptance and
authorization to plan G3 are separate, initially pending/false.

## Development and research scope

G1 five synthetic stories (26 steps), auxiliary nine steps and new synthetic
adversarial cases are reported separately. Reference labels are post-evaluation
inputs. AI initial labels/review/revisions are nonblind `ai_development`, not
independent validation. Human independent review, double annotation, user research
and real-world generalization are optional/not_evaluated. Real exploratory sources
are deferred pending separate network, rights and budget authorization.

R0 remains the unchanged G1 grouping baseline. R1 is the default; R2 supplementary.
Low/standard/high reading budgets are diagnostics, not G3 selection or deletion.
PR5 remains mock-only, with its frozen byte/call/token/timeout limits.

## Rollback and exclusions

PR6 rollback removes only the PR6 package, v6 schemas/config/fixtures/tests,
incremental CI and appended documentation. Preserve PR1–PR5, frozen G1, G0,
historical results and user data. Git rollback needs separate authorization.
There is no database migration or rollback. No UI, provider transport, keys,
external network, notification, training or autonomous action is added.

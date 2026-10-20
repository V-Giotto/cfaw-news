# PR1 synthetic contract fixture

Everything in the JSONL files is constructed for contract tests, not historical news,
human annotation or algorithm-quality evidence. Agent X is fictional. The GitHub Blog
registry entry describes only an existing repository configuration, not a licensed
document or a verified live source. All four document versions are synthetic.

Time zero is 2026-01-01T00:00:00Z. Agent X v1 is available at D0; its correction v2
is available at D6. A second document claims publication at D0 but is first observed
at D5. A far-future version is available in 2030. The three steps D1/D3/D6 must select
v1 / v1 / (v2 plus the late-observed document), respectively. Persona v2 starts at D6.

The history includes server inclusion at D1, an explicit open at D2, and an explicit
acknowledgement at D9. Earlier steps may not consume later history. These signals do
not mutate knowledge_known. Covered, unknown and service_offline intervals describe
only this synthetic source. No real collection or seven-day monitoring took place.

The minimal event/claim/gold records exercise references, version timestamps and
hashes. Every gold record is pending and uses synthetic-fixture-v1, without human
agreement, adjudication or semantic-support claims. The single family is dev only.

Fixture JSONL was prepared offline using the contract models and visible_versions;
candidate IDs were computed, then stored. There is no runtime generator or replay
engine. Editing frozen material requires a new dataset revision and retained prior
bytes. Tests mutate only independent temporary copies.

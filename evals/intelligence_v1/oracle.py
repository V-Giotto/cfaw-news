"""Explicit oracle experiment. Never imported by ordinary prediction rankers."""

from .contracts import EventGroup
from .exceptions import ContractError
from .grouping import event_group
from .loader import parse_model, read_entry, read_records, unique


def reference_events(bundle):
    rows = []
    for entry in bundle.manifest.file_hashes:
        if entry.role == "events":
            rows.extend(parse_model(EventGroup, r) for r in read_records(
                read_entry(bundle.root, entry), entry))
    unique(rows, lambda r: r.event_id)
    return rows


def visible_reference_mapping(events, candidate_ids, *, as_of):
    result = {}
    for event in events:
        if event.first_observed_at > as_of:
            continue
        for key in sorted(set(event.document_version_ids) & set(candidate_ids)):
            if key in result:
                raise ContractError("AMBIGUOUS_REFERENCE_EVENT", record_id=key)
            result[key] = event.event_id
    return result


def oracle_groups(bundle, candidates, *, as_of):
    ids = {d.doc_version_id for d in candidates}
    mapping = visible_reference_mapping(reference_events(bundle), ids, as_of=as_of)
    groups = {}
    for key in sorted(ids):
        # Unmapped candidates remain singleton; oracle cannot shrink its input pool.
        target = ("reference", mapping[key]) if key in mapping else ("unmapped", key)
        groups.setdefault(target, []).append(key)
    return tuple(sorted((event_group(members, ("oracle_reference",), "oracle-reference-v1",
                                    oracle=True) for members in groups.values()),
                        key=lambda g: g.doc_version_ids))

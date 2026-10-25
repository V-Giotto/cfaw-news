"""Export immutable evidence pointers, never a personalized ranking or new factual text."""

from evals.intelligence_g2.contracts import data

from .contracts import G3InputView


def views(record, trace_pointer):
    bundles = {b.event_key: b for b in record.evidence.bundles}
    snapshots = {s.event_key: s for s in record.rule.snapshots}
    presentations = {p.event_key: p for p in record.expression.presentations}
    return tuple(
        G3InputView(
            event_key=i.event_key,
            event_revision=i.event_revision,
            as_of=record.grouping.cursor.as_of.isoformat(),
            bundle=data(bundles[i.event_key]),
            rule_item=data(i),
            presentation=data(presentations[i.event_key]),
            snapshot=data(snapshots[i.event_key]),
            source_coverage=tuple(data(w) for w in i.source_coverage),
            lineage_ids=snapshots[i.event_key].lineage_ids,
            trace_pointer=trace_pointer,
        )
        for i in record.rule.items
    )

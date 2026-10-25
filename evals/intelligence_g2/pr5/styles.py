"""Closed expressions never paraphrase evidence or add facts."""

from .assets import strict_json
from .contracts import ClosedDraft, ModelRef, data, fail


def refs_for(request):
    return tuple(ModelRef(**{name: data(ref)[name] for name in ModelRef.model_fields})
                 for ref in request.citations)


def render(request, style_id, order, assets):
    catalog = {s["id"]: s for s in strict_json(assets.styles)["styles"]}
    style = catalog.get(style_id)
    expected = tuple(c.claim_key for c in request.claims)
    if (style_id not in request.style_ids or style is None or style["mode"] != request.mode
            or len(order) != len(set(order)) or set(order) != set(expected)
            or request.mode != "ordinary" and order != expected):
        fail("EXPRESSION_NOT_CLOSED", "expression", "style_order")
    claims = {c.claim_key: c for c in request.claims}
    source = request.claims[0].attribution.publisher_source_id
    headline = style["headline"].format(source=source)
    pieces = [style["quote"].format(source=claims[k].attribution.publisher_source_id,
                                   quote=claims[k].statement) for k in order]
    return headline, style["prefix"] + "；".join(pieces)


def closed_response(request, assets, style_id=None, order=None):
    style_id = style_id or request.style_ids[int(request.request_sha256, 16) % len(request.style_ids)]
    order = order or tuple(c.claim_key for c in request.claims)
    headline, body = render(request, style_id, order, assets)
    return ClosedDraft(kind="closed", style_id=style_id, claim_order=order, refs=refs_for(request),
                       headline=headline, body=body)

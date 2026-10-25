"""Small, auditable target-identifier grammar; never an entity or Claim oracle."""

import re
import unicodedata
from datetime import date
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from cfaw_news.retrieval import tokenize

from .contracts import DocumentEventFeatures, FeatureRef, digest

VERSION = r"(?:v(?=\d)|version\s+)(\d+(?:\.\d+)*(?:[-+][\w.]+)?)"
ACTION = (r"\b(?:v\d[\w.+-]*|version\s+\d|release|announcement|announces|introduces|adds|"
          r"independent|limited|measurement|test|benchmark|documentation|license|theme|"
          r"repost|reprint|republished|discussion|correction|research|safety)\b")


def normalize(value):
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def canonical_url(value):
    if not value:
        return None
    try:
        url = urlsplit(value)
        if url.scheme not in {"http", "https", "synthetic"} or not url.hostname or url.username:
            return None
        port = url.port
        host = url.hostname.casefold()
        if ":" in host:
            host = "[" + host + "]"
        if port and (url.scheme, port) not in {("https", 443), ("http", 80)}:
            host += ":" + str(port)
        query = [(k, v) for k, v in parse_qsl(url.query, keep_blank_values=True)
                 if not k.casefold().startswith("utm_") and k.casefold() not in {"gclid", "fbclid"}]
        return urlunsplit((url.scheme.casefold(), host, url.path, urlencode(sorted(query)),
                           url.fragment))
    except ValueError:
        return None


def token_hashes(text):
    # Unordered hashes retain Jaccard information without storing reconstructed historical prose.
    return tuple(sorted({digest(token) for token in tokenize(normalize(text))}))


def repository_subject(link):
    if not link:
        return None
    parts = urlsplit(link)
    path = parts.path.split("/")
    if "releases" in path:
        prefix = "/".join(path[:path.index("releases")])
        return "artifact:" + urlunsplit((parts.scheme, parts.netloc, prefix, "", ""))
    return None


def target_conflicts(a, b):
    reasons = []
    if a.ambiguous or b.ambiguous:
        return ()  # Ambiguity abstains; it is not proof of different subjects.
    left_names = {s for s in a.subject_candidates if not s.startswith("artifact:") and s.isascii()}
    right_names = {s for s in b.subject_candidates if not s.startswith("artifact:") and s.isascii()}
    if left_names and right_names and left_names.isdisjoint(right_names):
        reasons.append("different_subject")
    for field, reason in (("canonical_subject", "different_subject"),
                          ("target_version", "different_target_version"),
                          ("action", "different_action"),
                          ("action_object", "different_action_object"),
                          ("event_date", "different_target_date")):
        left, right = getattr(a, field), getattr(b, field)
        if left is not None and right is not None and left != right:
            reasons.append(reason)
    return tuple(dict.fromkeys(reasons))


def extract_features(*, replay_input, previous_state, config):
    del config
    history = {}
    if previous_state:
        for event in previous_state.registry:
            if event.status in {"active", "dormant"}:
                for feature in event.last_features:
                    old = history.get(feature.document_id)
                    if old is None or old.available_at < feature.available_at:
                        history[feature.document_id] = feature
    output = []
    for wrapped in replay_input.visible_documents:
        doc = wrapped.candidate
        title = normalize(doc.title)
        body = "\n".join(p.text for p in doc.paragraphs)
        text = normalize(body)
        own_url = canonical_url(doc.canonical_url)
        link_matches = re.findall(r"(?:target|release\s+url|发布目标)\s*:\s*"
                                  r"((?:https?|synthetic)://[^\s<>,]+)", body, re.I)
        links = {canonical_url(m.rstrip(".;")) for m in link_matches} - {None}
        link = next(iter(links)) if len(links) == 1 else None
        if not link and re.search(r"/releases/(?:tag/)?[^/]+", own_url or ""):
            link = own_url
        subject = re.split(ACTION, title, maxsplit=1)[0].strip(" :-–—")
        ambiguous = len(links) > 1 or bool(re.search(r"\b(?:and|vs|versus)\b|与|对比", subject))
        subject = subject if subject and subject != title and not ambiguous else None
        title_subject = subject
        # A repository/release anchor works across languages without guessing name translations.
        repo_subject = repository_subject(link or own_url)
        if repo_subject and not ambiguous:
            subject = repo_subject
        # Bind versions to the title's product phrase before repository canonicalization.
        # A comparison product's version is not a target identifier; conflicting explicit
        # target versions in title/body require abstention rather than title precedence.
        versions = set(re.findall(r"(?<!\w)" + re.escape(title_subject) + r"\s+" + VERSION,
                                  title + "\n" + text)) if title_subject else set()
        tag = re.search(r"/releases/tag/v(\d+(?:\.\d+)*(?:[-+][\w.]+)?)$", link or "")
        if tag:
            versions.add(tag.group(1))
        version = next(iter(versions)) if len(versions) == 1 else None
        ambiguous = ambiguous or len(versions) > 1
        copy_cue = bool(re.search(r"\breprint|\brepost|republish|reproduces|rewrite|"
                                  r"publicity repeats|转载|转发", title + "\n" + text))
        measurement = bool(re.search(r"\btest|\bmeasurement|\bmeasured|测试|实测", title)
                           or re.search(r"(?:^|[.!?]\s+)(?:we|i)\s+(?:independently\s+)?"
                                        r"(?:ran|tested|measured)\b", text))
        correction = bool(re.search(r"\bcorrection|\bcorrected|更正|纠正", title + "\n" + text))
        role = ("measurement" if measurement else "correction" if correction else
                "reprint" if copy_cue else "unknown")
        action, obj, event_type = None, None, "unknown"
        if re.search(r"\blicense|许可证", title):
            action, obj, event_type = "license", "license", "other"
        elif re.search(r"\bdocumentation|\btheme|文档|主题", title):
            action, obj, event_type = "documentation", "theme", "other"
        elif match := re.search(r"\b(?:adds|introduces|announces)\s+(.+)", title):
            action, obj, event_type = "capability", match.group(1), "capability"
        elif re.search(r"\bbenchmark", title):
            action, obj, event_type = "benchmark", title.split("benchmark", 1)[1].strip() or None, "benchmark"
        elif re.search(r"\brelease|\brepost|\breprint|\brepublished|发布", title) or link or (
                measurement and version):
            action, obj, event_type = "release", "release", "release"
        elif correction:
            action, event_type = "correction", "correction"
        if role == "unknown" and action:
            role = "announcement"
        if action == "release" and role in {"announcement", "correction"} and not link:
            link = own_url
        date_match = re.search(r"(?:release date|event date|发布日期)\s*:\s*(\d{4}-\d{2}-\d{2})", text)
        try:
            event_date = date.fromisoformat(date_match.group(1)) if date_match else None
        except ValueError:
            event_date = None
        refs = [FeatureRef(doc_version_id=doc.doc_version_id, field="title",
                           value_sha256=digest(doc.title), available_at=doc.available_at)]
        for field in ("canonical_url", "upstream_document_id"):
            if getattr(doc, field):
                refs.append(FeatureRef(doc_version_id=doc.doc_version_id, field=field,
                    value_sha256=digest(getattr(doc, field)), available_at=doc.available_at))
        refs.extend(FeatureRef(doc_version_id=doc.doc_version_id, field="paragraph",
            paragraph_id=p.paragraph_id, value_sha256=digest(p.text), available_at=doc.available_at)
            for p in doc.paragraphs)
        feature = DocumentEventFeatures(doc_version_id=doc.doc_version_id,
            document_id=doc.document_id, available_at=doc.available_at, published_at=doc.published_at,
            canonical_url=own_url, content_sha256=doc.content_sha256,
            upstream_document_id=doc.upstream_document_id, canonical_subject=subject,
            subject_candidates=tuple(sorted({s for s in (subject, title_subject) if s})), ambiguous=ambiguous,
            target_version=version, target_link=link, event_type=event_type, action=action,
            action_object=obj, material_role=role, event_date=event_date,
            title_tokens=token_hashes(doc.title), body_tokens=token_hashes(body),
            copy_cue=copy_cue, refs=tuple(refs))
        old = history.get(doc.document_id)
        if old and not ambiguous and not target_conflicts(old, feature):
            # A missing marker is not a correction. Inherit only same-document identity facts,
            # with their original visible refs; never old text tokens or citable paragraphs.
            fields = ("canonical_subject", "target_version", "target_link", "action",
                      "action_object", "event_date")
            updates = {f: getattr(old, f) for f in fields if getattr(feature, f) is None
                       and getattr(old, f) is not None}
            if feature.event_type == "unknown" and old.event_type != "unknown":
                updates["event_type"] = old.event_type
            if updates:
                updates["refs"] = tuple(sorted(set(feature.refs + old.refs),
                    key=lambda r: (r.doc_version_id, r.field, r.paragraph_id or "")))
                feature = feature.model_copy(update=updates)
        output.append(feature)
    # Explicit visible upstream may carry a target identifier, but never proves independence.
    # Propagation is constrained by subject/target compatibility and retains original refs.
    for _ in range(len(output)):
        upstreams = {f.document_id: f for f in output}
        changed = False
        for index, feature in enumerate(output):
            parent = upstreams.get(feature.upstream_document_id)
            if (parent is None or feature.ambiguous or parent.ambiguous
                    or not feature.canonical_subject
                    or feature.canonical_subject != parent.canonical_subject
                    or target_conflicts(feature, parent)
                    or feature.material_role not in {"reprint", "measurement", "correction"}):
                continue
            fields = ("target_version", "target_link", "action", "action_object", "event_date")
            updates = {f: getattr(parent, f) for f in fields if getattr(feature, f) is None
                       and getattr(parent, f) is not None}
            if feature.event_type == "unknown" and parent.event_type != "unknown":
                updates["event_type"] = parent.event_type
            if updates:
                updates["refs"] = tuple(sorted(set(feature.refs + parent.refs),
                    key=lambda r: (r.doc_version_id, r.field, r.paragraph_id or "")))
                output[index] = feature.model_copy(update=updates)
                changed = True
        if not changed:
            break
    return tuple(sorted(output, key=lambda f: f.doc_version_id))

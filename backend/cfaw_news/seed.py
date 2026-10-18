import json
from urllib.parse import urlsplit

from sqlalchemy import delete, select

from .database import Article, ArticleMedia, ArticleReading, Goal, Meta, fingerprint
from .following import retire_demo_goals

DEMO_GOALS = [
    {
        "name": "每周两小时，试一个省时的 AI 工具",
        "purpose": "我用 Mac 开会和做 PPT，想安排一次简单试用，确认是否真的省时间。",
        "scope": "会议转写、笔记、幻灯片",
        "constraints": "每周只有两小时；中文效果、设备与账号条件需要核实。",
        "keywords": ["Mac", "会议", "转写", "PPT", "试用"],
        "trial_requested": True,
    },
    {
        "name": "AI 笔记本：现在值得换吗？",
        "purpose": "预算约 6000 元，主要写文档和开视频会议，旧电脑仍可用。",
        "scope": "AI 笔记本的实际能力、国内配置和价格",
        "constraints": "不因发布会参数立即购买；需要国内价格和可用性证据。",
        "keywords": ["笔记本", "Surface", "价格", "国行"],
        "trial_requested": False,
    },
    {
        "name": "家人照片的隐私与存储变化",
        "purpose": "家人在国内用 Google Photos，关注隐私、存储、收费与账号条件。",
        "scope": "Google Photos、家庭分享、订阅及存储",
        "constraints": "先核实适用地区和套餐，不把新功能当作隐私政策变更。",
        "keywords": ["Google Photos", "照片", "隐私", "存储"],
        "trial_requested": False,
    },
]


def safe_url(url: str) -> str:
    parts = urlsplit(url)
    return url if parts.scheme in {"http", "https"} and parts.hostname else ""


def seed(database, root, *, demo=False, include_archive=False):
    """Goal and archive fixtures are opt-in for isolated tests/evals."""
    archive = (
        json.loads((root / "data/archive/articles.json").read_text(encoding="utf-8"))
        if include_archive else {"articles": []}
    )
    with database.session.begin() as session:
        if not demo:
            retire_demo_goals(session)
        if not include_archive:
            # Retire the legacy seed corpus, while leaving immutable run snapshots intact.
            legacy_ids = select(Article.id).where(
                Article.origin == "archive", Article.id.startswith("archive:")
            )
            session.execute(delete(ArticleMedia).where(ArticleMedia.article_id.in_(legacy_ids)))
            session.execute(delete(ArticleReading).where(ArticleReading.article_id.in_(legacy_ids)))
            session.execute(delete(Article).where(Article.id.in_(legacy_ids)))
        for raw in archive["articles"]:
            article_id = f"archive:{raw['key']}"
            if session.get(Article, article_id):
                continue
            row = {
                "id": article_id,
                "title": raw["title"],
                "original_title": raw.get("original_title", raw["title"]),
                "source": raw["source"],
                "source_url": safe_url(raw["url"]),
                "published_at": raw.get("published_date"),
                "captured_at": archive["captured_at"],
                "summary": raw["summary"],
                "paragraphs": [
                    {
                        "id": f"p{i + 1}",
                        "text": quote,
                        "kind": "curator_paraphrase"
                        if raw.get("curator_paraphrase")
                        else "archived_quote",
                    }
                    for i, quote in enumerate(raw.get("quotes", []))
                ],
                "coverage_note": raw.get("coverage_note", ""),
                "source_role": raw.get("source_role", ""),
                "same_event_as": raw.get("same_event_as"),
                "origin": "archive",
            }
            row["content_hash"] = fingerprint(row)
            session.add(
                Article(id=article_id, content_hash=row["content_hash"], origin="archive", data=row)
            )
        if demo and not session.get(Meta, "demo_goals_v1"):
            if not session.scalar(select(Goal.id).limit(1)):
                session.add_all(Goal(data=goal, is_demo=True) for goal in DEMO_GOALS)
            session.add(Meta(key="demo_goals_v1", value="loaded"))

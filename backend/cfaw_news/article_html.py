"""Publisher-specific article boundaries, shared by covers and reading."""

from urllib.parse import urlsplit

import lxml.html


def article_markup(markup, url) -> str | None:
    """Use China News' actual article body, excluding navigation and promotions.

    For a known publisher, a missing body fails closed instead of selecting a
    recommendation, navigation button or application download advertisement.
    None selects generic extraction; an empty string means a known body is missing.
    """
    if urlsplit(url).hostname not in {
        "www.chinanews.com.cn",
        "chinanews.com.cn",
        "www.chinanews.com",
        "chinanews.com",
    }:
        return None
    parser = lxml.html.HTMLParser(no_network=True, remove_comments=True, recover=True)
    tree = lxml.html.fromstring(markup or "<div/>", parser=parser)
    nodes = tree.xpath('//*[contains(concat(" ", normalize-space(@class), " "), " left_zw ")]')
    if nodes:
        return lxml.html.tostring(nodes[0], encoding="unicode")
    gallery = tree.xpath(
        '//*[contains(concat(" ", normalize-space(@class), " "), " tuji_current_img ")]'
    )
    if gallery:
        # Include this page's photograph and caption, excluding the neighboring
        # gallery thumbnails, previous/next controls and recommendations.
        article = lxml.html.Element("article")
        article.append(gallery[0])
        captions = tree.xpath(
            '//*[contains(concat(" ", normalize-space(@class), " "), " current_img_desc_wrapper ")]'
        )
        if captions:
            article.append(captions[0])
        return lxml.html.tostring(article, encoding="unicode")
    return ""

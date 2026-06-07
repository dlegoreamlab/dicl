"""
DICL 검증 스크립트
──────────────────
1) Offline: HTML 을 직접 주입해 Discovery 가 4종만 골라내는지 확인
2) Offline: 재귀 crawl 이 비미디어 URL 을 trash_records 로 분리하는지 확인
3) DFSS 기반 FileRecord 검증
"""

from __future__ import annotations

import json
import sys

from dicl import DICL, FileRecord
from dicl.core.budget import VisitBudget
from dicl.core.node import Payload
from dicl.engines.discovery import DiscoveryEngine
from dicl.engines.analysis import AnalysisEngine
from dicl.engines.relationship import RelationshipEngine
from dicl.engines.generator import FileRecordGenerator
from dicl.nodes.scout import ScoutNode


# ──────────────────────────────────────────────────────────
# 1) Offline 단위 검증
# ──────────────────────────────────────────────────────────
SAMPLE_HTML = """
<html lang="ko">
<head>
  <title>DICL Sample</title>
  <meta property="og:image" content="/static/cover.png">
  <script src="/_next/static/chunks/main.js"></script>
</head>
<body>
  <img src="/img/photo1.jpg">
  <img src="https://cdn.example.com/img/photo2.WebP">
  <video src="/media/movie.mp4"></video>
  <audio><source src="/sound/track.mp3"></audio>

  <!-- 미디어가 아닌 잡음 링크들 -->
  <a href="/about.html">About</a>
  <a href="https://example.com/login">Login</a>
  <a href="/docs/whitepaper.pdf">White Paper</a>
  <a href="/script.js">script</a>
  <a href="mailto:foo@bar.com">mail</a>
</body>
</html>
"""

RECURSIVE_HTML_ROOT = """
<html lang="ko">
<head><title>Root</title></head>
<body>
  <a href="/about.html">About</a>
  <a href="/assets/app.js">App JS</a>
  <img src="/img/root.jpg">
</body>
</html>
"""

RECURSIVE_HTML_ABOUT = """
<html lang="ko">
<head><title>About</title></head>
<body>
  <video src="/media/about.mp4"></video>
  <a href="/contact">Contact</a>
</body>
</html>
"""

RECURSIVE_HTML_CONTACT = """
<html lang="ko">
<head><title>Contact</title></head>
<body>
  <a href="/docs/company.pdf">Company PDF</a>
</body>
</html>
"""


class FakeResponse:
    def __init__(self, text: str, status_code: int = 200, headers: dict | None = None):
        self.text = text
        self.status_code = status_code
        self.headers = headers or {"Content-Type": "text/html", "Server": "test"}


def test_offline() -> None:
    print("── [Offline] Discovery + trash 분리 검증 ──")

    from bs4 import BeautifulSoup
    soup = BeautifulSoup(SAMPLE_HTML, "html.parser")

    scout = ScoutNode()
    candidates = scout._collect_candidates(soup, "https://example.com/page")

    payload = Payload(
        url="https://example.com/page",
        html=SAMPLE_HTML,
        candidates=candidates,
        status_code=200,
        headers={"Server": "nginx"},
    )

    discovery = DiscoveryEngine()
    discoveries = discovery.discover(payload)
    trash = discovery.discover_trash(payload, scope_domain="example.com")
    recursive_urls = discovery.discover_recursive(payload, scope_domain="example.com")
    analysis = AnalysisEngine().analyze(payload)

    rel = RelationshipEngine()
    rel.link(payload.url, discoveries)

    gen = FileRecordGenerator()
    site = gen.make_site_record(
        site_url=payload.url,
        analysis=analysis,
        discoveries=discoveries,
        relations=rel.relations(payload.url),
        observed_sitemap=rel.observed_sitemap(),
    )
    media_records = [gen.make_media_record(payload.url, d) for d in discoveries]
    trash_records = [gen.make_url_record(payload.url, t["url"]) for t in trash]

    print(f" candidates(raw) : {len(candidates)}")
    print(f" discoveries(4종): {len(discoveries)}")
    print(f" trash_urls      : {len(trash)}")
    for d in discoveries:
        print(f"   - [MEDIA:{d['media_type']:5s}] {d['url']}")
    for t in trash:
        print(f"   - [TRASH] {t['url']}")
    print()
    print(f" analysis        : framework={analysis['framework']!r}, "
          f"auth_type={analysis['auth_type']!r}, title={analysis['title']!r}")
    print()
    print(" Observed Sitemap:")
    print(json.dumps(rel.observed_sitemap(), indent=2, ensure_ascii=False))
    print()
    print(f" site_record   : {site}")
    print(f" media_records : {len(media_records)}개")
    print(f" trash_records : {len(trash_records)}개")

    types = sorted({d["media_type"] for d in discoveries})
    assert types == ["audio", "image", "pdf", "video"], types
    assert all(d["media_type"] in {"video", "image", "audio", "pdf"}
               for d in discoveries)
    assert not any(d["url"].endswith(".js") for d in discoveries)
    assert not any(d["url"].endswith(".html") for d in discoveries)
    assert not any(d["url"].startswith("mailto:") for d in discoveries)
    assert analysis["framework"] == "next.js"

    trash_urls = {t["url"] for t in trash}
    assert "https://example.com/about.html" in trash_urls
    assert "https://example.com/login" in trash_urls
    assert "https://example.com/script.js" in trash_urls
    assert "https://example.com/docs/whitepaper.pdf" not in trash_urls
    assert "https://example.com/script.js" not in recursive_urls
    assert "https://example.com/about.html" in recursive_urls

    assert isinstance(site, FileRecord)
    assert site.type == "site"
    assert site.validate() is True
    assert all(isinstance(r, FileRecord) for r in media_records)
    assert all(r.validate() is True for r in media_records)
    assert all(isinstance(r, FileRecord) for r in trash_records)
    assert all(r.type == "url" for r in trash_records)
    assert all(r.validate() is True for r in trash_records)

    print("\n ✅ Offline 검증 통과\n")


# ──────────────────────────────────────────────────────────
# 2) Offline 재귀 crawl 검증
# ──────────────────────────────────────────────────────────
def test_recursive_crawl() -> None:
    print("── [Offline] Recursive crawl 검증 ──")

    import requests

    html_map = {
        "https://example.com": RECURSIVE_HTML_ROOT,
        "https://example.com/about.html": RECURSIVE_HTML_ABOUT,
        "https://example.com/contact": RECURSIVE_HTML_CONTACT,
    }

    original_get = requests.get

    def fake_get(url, *args, **kwargs):  # noqa: ANN001, D401
        if url not in html_map:
            raise RuntimeError(f"Unexpected URL: {url}")
        return FakeResponse(html_map[url])

    requests.get = fake_get
    try:
        dicl = DICL(
            budget=VisitBudget(max_depth=2, max_visits=10, max_per_domain=10, max_seconds=10.0),
            use_heavy=False,
        )
        result = dicl.crawl("https://example.com")
    finally:
        requests.get = original_get

    print(f" pages_crawled  : {result.stats['pages_crawled']}")
    print(f" media_records  : {len(result.media_records)}개")
    print(f" trash_records  : {len(result.trash_records)}개")
    print(f" visited_pages  : {result.stats['visited_pages']}")

    media_paths = {r.path for r in result.media_records}
    trash_paths = {r.path for r in result.trash_records}

    assert result.site_record.validate() is True
    assert all(r.validate() is True for r in result.media_records)
    assert all(r.validate() is True for r in result.trash_records)

    assert "https://example.com/img/root.jpg" in media_paths
    assert "https://example.com/media/about.mp4" in media_paths
    assert "https://example.com/docs/company.pdf" in media_paths

    assert "https://example.com/about.html" in trash_paths
    assert "https://example.com/assets/app.js" in trash_paths
    assert "https://example.com/contact" in trash_paths

    assert result.stats["pages_crawled"] == 3
    assert result.stats["trash_found"] == 3
    assert set(result.stats["visited_pages"]) == {
        "https://example.com",
        "https://example.com/about.html",
        "https://example.com/contact",
    }

    print("\n ✅ Recursive crawl 검증 통과\n")


if __name__ == "__main__":
    test_offline()
    test_recursive_crawl()
    if len(sys.argv) > 1:
        target = sys.argv[1]
        print(f"(optionnel) online crawl: {target}")

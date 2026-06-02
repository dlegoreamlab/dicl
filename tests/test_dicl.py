"""
DICL 검증 스크립트
──────────────────
1) Offline: HTML 을 직접 주입해 Discovery 가 4종만 골라내는지 확인
2) Online : 실제 URL 을 크롤해 미디어가 발견되는지 확인 (네트워크 가능 시)
3) DFSS 기반 FileRecord 검증
"""

from __future__ import annotations

import sys

from dicl import DICL, FileRecord
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

  <!-- 미디어가 아닌 잡음 링크들 — 반드시 걸러져야 한다 -->
  <a href="/about.html">About</a>
  <a href="https://example.com/login">Login</a>
  <a href="/docs/whitepaper.pdf">White Paper</a>
  <a href="/script.js">script</a>
  <a href="mailto:foo@bar.com">mail</a>
</body>
</html>
"""


def test_offline() -> None:
    print("── [Offline] Discovery 4종 필터 검증 ──")

    # ScoutNode 내부 로직만 사용 (네트워크 호출 없음)
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

    discoveries = DiscoveryEngine().discover(payload)
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

    print(f" candidates(raw) : {len(candidates)}")
    print(f" discoveries(4종): {len(discoveries)}")
    for d in discoveries:
        print(f"   - [{d['media_type']:5s}] {d['url']}")
    print()
    print(f" analysis        : framework={analysis['framework']!r}, "
          f"auth_type={analysis['auth_type']!r}, title={analysis['title']!r}")
    print()
    print(" Observed Sitemap:")
    import json
    print(json.dumps(rel.observed_sitemap(), indent=2, ensure_ascii=False))
    print()
    print(f" site_record  : {site}")
    print(f" media_records: {len(media_records)}개")
    for r in media_records:
        print(f"   {r}")

    types = sorted({d["media_type"] for d in discoveries})
    assert types == ["audio", "image", "pdf", "video"], types
    assert all(d["media_type"] in {"video", "image", "audio", "pdf"}
               for d in discoveries)
    assert not any(d["url"].endswith(".js") for d in discoveries)
    assert not any(d["url"].endswith(".html") for d in discoveries)
    assert not any(d["url"].startswith("mailto:") for d in discoveries)
    assert analysis["framework"] == "next.js"

    assert isinstance(site, FileRecord)
    assert site.type == "site"
    assert site.validate() is True
    assert all(isinstance(r, FileRecord) for r in media_records)
    assert all(r.validate() is True for r in media_records)

    print("\n ✅ Offline 검증 통과\n")


# ──────────────────────────────────────────────────────────
# 2) Online 통합 검증 (네트워크 가능 시)
# ──────────────────────────────────────────────────────────
def test_online(url: str) -> None:
    print(f"── [Online] crawl {url} ──")
    try:
        dicl = DICL(use_heavy=False)
        result = dicl.crawl(url)
    except Exception as e:  # noqa: BLE001
        print(f"  (네트워크 실패: {e})")
        return

    print(f" site_record  : {result.site_record}")
    print(f" media_records: {len(result.media_records)}개")
    for r in result.media_records[:10]:
        print(f"   {r}")
    print(f" stats        : {result.stats}")
    print()

    assert result.site_record.validate() is True
    assert all(r.validate() is True for r in result.media_records)


if __name__ == "__main__":
    test_offline()
    target = sys.argv[1] if len(sys.argv) > 1 else "https://www.python.org"
    test_online(target)

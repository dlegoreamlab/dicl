# DICL — Dlegoream Intelligence Crawling Library

> Web Intelligence Discovery Framework · v2.1  
> _by **DLEGOREAM LABORATORY**_

DICL 은 단순 크롤러가 아니다. 웹사이트를 **정보 시스템**으로 간주하고
재귀적으로 구조를 순회하면서 **동영상 / 이미지 / 오디오 / PDF** 미디어 링크를 발견하며,
그 외 비미디어 URL 은 **trash list** 로 분리하여 DFSS 표준 `FileRecord` 로 반환하는
**노드 기반(Node-driven)** 지능형 Discovery Framework 이다.

---

## 핵심 아키텍처

```
        ┌────────────┐    ┌────────────┐    ┌──────────────┐
URL ──► │ Scout Node │──► │ Control    │──► │ Heavy        │
        │  (정적)    │    │  (우선순위)│    │  (Playwright)│
        └────────────┘    └────────────┘    └──────────────┘
                                                   │
       ┌────────────┬───────────────┬──────────────┘
       ▼            ▼               ▼
  Discovery     Analysis      Relationship
 (4종 필터 +    (기술스택)    (Observed Sitemap)
  trash 분리)
       └────────────┴───────────────┘
                    ▼
            DFSS FileRecord Generator
                    ▼
      site / media / trash FileRecord(s)
```

| 구성요소 | 백서 절 | 역할 |
|---|---|---|
| `ScoutNode` | §8 | HTML 정적 수집 · 링크/미디어 후보 추출 |
| `ControlNode` | §9 | 중요도 계산 · Heavy 호출 결정 |
| `HeavyAnalyzerNode` | §8 | Playwright 로 동적 콘텐츠 분석 |
| `DiscoveryEngine` | §5 | **video / image / audio / pdf 필터 + trash URL 분리** |
| `AnalysisEngine` | §6 | framework / auth / server 추정 |
| `RelationshipEngine` | §7, §11 | 관계 그래프 · Observed Sitemap |
| `FileRecordGenerator` | §12 | DFSS `FileRecord` 변환 |
| `VisitBudget` | §10 | 재귀 순회 깊이/방문 수 제어 |

---

## 설치

```bash
pip install -e .                # 기본 (DFSS commit hash 고정 설치)
pip install -e ".[heavy]"       # + Playwright (동적 분석)
pip install -e ".[telegram]"    # + Telethon (텔레그램 메시지 수집)
playwright install chromium     # heavy 옵션 시
```

기본 설치의 DFSS 의존성은 `46dcb2148bf4b52d3b7cabcaf9fd9cdf63c319a8` commit hash 로 고정되어
`main` 브랜치 변경에 영향받지 않는 재현 가능한 빌드를 보장한다.

또는 GitHub 에서 직접 설치:

```bash
pip install git+https://github.com/dlegoreamlab/dicl.git
```

---

## 사용 예

```python
from dicl import DICL

dicl = DICL()
result = dicl.crawl("https://example.com")

# 1) 사이트 자체 — DFSS FileRecord(type="site")
print(result.site_record)

# 2) 발견된 미디어 — DFSS FileRecord(type="video" | "image" | "audio" | "pdf")
for rec in result.media_records:
    print(rec.type, rec.path)

# 3) 재귀 crawl 중 수집된 비미디어 URL — DFSS FileRecord(type="url")
for rec in result.trash_records:
    print(rec.type, rec.path)

# 4) DFSS 검증
assert result.site_record.validate() is True
assert all(rec.validate() for rec in result.media_records)
assert all(rec.validate() for rec in result.trash_records)

# 5) 실패 URL 로그
print(result.stats["failed_url_logs"])

# 6) Observed Sitemap (백서 §11)
print(result.observed_sitemap)
```

### Telethon 기반 텔레그램 메시지 수집

```python
from dicl import DICL

dicl = DICL(use_heavy=False)
telegram = dicl.collect_telegram(
    api_id=123456,
    api_hash="YOUR_API_HASH",
    entity="public_channel_or_chat",
    limit=50,
)

for msg in telegram.normalized_messages:
    print(msg["message_id"], msg["record_type"], msg["file_name"])

for rec in telegram.media_records:
    # DFSS 의 telegram relation 표준(platform/chat_id/message_id)을 유지한다.
    print(rec.type, rec.path, rec.meta["relation"])
    assert rec.validate() is True
```

---

## 동작 원리

1. 시작 URL 을 방문한다.
2. 페이지에서 미디어/링크 후보를 수집한다.
3. **video / image / audio / pdf** 는 media discovery 로 확정한다.
4. 나머지 비미디어 URL 은 trash list 에 저장한다.
5. trash list 중 페이지성 URL 만 예산 범위 안에서 재귀 방문한다.
6. 최종적으로 `site_record`, `media_records`, `trash_records` 를 반환한다.

---

## DICL 이 다른 크롤러와 다른 점

1. **Discovery First** — 다운로드는 하지 않는다. 발견만 한다.
2. **Recursive Structure Aware** — 단일 페이지가 아니라 재귀적 웹 구조를 본다.
3. **Unified Record** — 결과가 DFSS `FileRecord` 형식으로 통일된다.
4. **Node 기반 조립** — `Scout/Control/Heavy` 노드를 자유롭게 교체 가능.
5. **Noise Separation** — 미디어와 잡 URL 을 섞지 않고 분리 반환한다.

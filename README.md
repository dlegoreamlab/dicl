# DICL — Dlegoream Intelligence Crawling Library

> Web Intelligence Discovery Framework · v2.0
> _by **DLEGOREAM LABORATORY**_

DICL 은 단순 크롤러가 아니다. 웹사이트를 **정보 시스템**으로 간주하고
**동영상 / 이미지 / 오디오 / PDF** 네 가지 미디어 링크만을 발견하여
표준화된 `FileRecord` 로 변환하는 **노드 기반(Node-driven)** 지능형
Discovery Framework 이다.

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
  (4종 필터)    (기술스택)    (Observed Sitemap)
       └────────────┴───────────────┘
                    ▼
            FileRecord Generator
                    ▼
            FileRecord(s)
```

| 구성요소 | 백서 절 | 역할 |
|---|---|---|
| `ScoutNode` | §8 | HTML 정적 수집 · 미디어 후보 추출 |
| `ControlNode` | §9 | 중요도 계산 · Heavy 호출 결정 |
| `HeavyAnalyzerNode` | §8 | Playwright 로 동적 콘텐츠 분석 |
| `DiscoveryEngine` | §5 | **video / image / audio / pdf 만 통과** |
| `AnalysisEngine` | §6 | framework / auth / server 추정 |
| `RelationshipEngine` | §7, §11 | 관계 그래프 · Observed Sitemap |
| `FileRecordGenerator` | §12 | 통일 `FileRecord` 변환 |
| `VisitBudget` | §10 | 무한 탐색 방지 |

---

## 설치

```bash
pip install -e .                # 기본
pip install -e ".[heavy]"       # + Playwright (동적 분석)
playwright install chromium     # heavy 옵션 시
```

---

## 사용 예

```python
from dicl import DICL

dicl = DICL()
result = dicl.crawl("https://example.com")

# 1) 사이트 자체 — FileRecord(type="site")
print(result.site_record)

# 2) 발견된 미디어 — FileRecord(type="video" | "image" | "audio" | "pdf")
for rec in result.media_records:
    print(rec.type, rec.path)

# 3) Observed Sitemap (백서 §11)
print(result.observed_sitemap)
```

---

## DICL 이 다른 크롤러와 다른 점

1. **Discovery First** — 다운로드는 하지 않는다. 발견만 한다.
2. **Structure Aware** — 페이지가 아니라 *웹 구조* 를 본다.
3. **Unified Record** — 모든 결과가 `FileRecord` 한 형식으로 통일된다.
4. **Node 기반 조립** — `Scout/Control/Heavy` 노드를 자유롭게 교체 가능.
5. **미디어 4종 전용** — 잡음을 만들지 않는다. 영상/이미지/오디오/PDF 만.

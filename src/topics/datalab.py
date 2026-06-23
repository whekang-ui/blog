"""네이버 데이터랩 검색어 트렌드 API 래퍼.

검색어 그룹들의 '상대적' 검색량 추이를 반환한다(절대 검색수는 제공되지 않음).
키워드 후보들의 최근 평균 상대지수를 구해, 수요가 높은 키워드를 가려내는 데 쓴다.

키가 없으면(.env 미설정) 비활성 상태로 동작하며 빈 결과를 반환한다.
API 문서: https://developers.naver.com/docs/serviceapi/datalab/search/search.md
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

try:
    import requests
except ImportError:
    requests = None  # type: ignore

from ..config import Config

API_URL = "https://openapi.naver.com/v1/datalab/search"


@dataclass
class TrendResult:
    keyword: str
    avg_ratio: float  # 기간 평균 상대지수 (0~100)


class DataLab:
    def __init__(self, config: Config) -> None:
        self._secrets = config.secrets
        self.enabled = config.secrets.has_datalab and requests is not None

    def keyword_demand(
        self, keywords: list[str], *, days: int = 90
    ) -> list[TrendResult]:
        """키워드별 최근 평균 상대 검색지수를 구해 내림차순 정렬해 반환.

        데이터랩은 요청당 최대 5개 키워드 그룹만 받으므로 5개씩 끊어 호출한다.
        """
        if not self.enabled or not keywords:
            return []

        end = date.today()
        start = end - timedelta(days=days)
        headers = {
            "X-Naver-Client-Id": self._secrets.naver_datalab_client_id,
            "X-Naver-Client-Secret": self._secrets.naver_datalab_client_secret,
            "Content-Type": "application/json",
        }

        results: list[TrendResult] = []
        for chunk in _chunks(keywords, 5):
            body = {
                "startDate": start.isoformat(),
                "endDate": end.isoformat(),
                "timeUnit": "week",
                "keywordGroups": [
                    {"groupName": kw, "keywords": [kw]} for kw in chunk
                ],
            }
            try:
                resp = requests.post(API_URL, headers=headers, json=body, timeout=15)
                resp.raise_for_status()
                payload = resp.json()
            except Exception:  # noqa: BLE001 - 트렌드는 보조 신호이므로 실패해도 진행
                continue
            results.extend(_parse(payload))

        results.sort(key=lambda r: r.avg_ratio, reverse=True)
        return results


def _parse(payload: dict[str, Any]) -> list[TrendResult]:
    out: list[TrendResult] = []
    for group in payload.get("results", []):
        ratios = [point.get("ratio", 0.0) for point in group.get("data", [])]
        avg = sum(ratios) / len(ratios) if ratios else 0.0
        out.append(TrendResult(keyword=group.get("title", ""), avg_ratio=round(avg, 2)))
    return out


def _chunks(items: list[str], size: int) -> list[list[str]]:
    return [items[i : i + size] for i in range(0, len(items), size)]

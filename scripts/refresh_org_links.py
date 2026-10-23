#!/usr/bin/env python3
"""Refresh cached institution pages when old ALIO hash links remain.

This is a local-only recovery path: no API calls, secrets, or social publishing.
The normal ALIO collector already regenerates institution pages on success.
"""
import json
import re
from datetime import datetime

import history
import orgs

LEGACY = re.compile(r'href=["\']\./#job=a[0-9]+["\']')


def main():
    pages = list(history.ROOT.glob("org-*.html"))
    stale = [page for page in pages if LEGACY.search(page.read_text(encoding="utf-8"))]
    if not stale:
        print("기관 링크: 기존 해시 링크 없음, 추가 생성 생략")
        return 0
    try:
        state = history.load()
        forecast = json.loads(history.FORECAST.read_text(encoding="utf-8"))
        if not isinstance(state.get("items"), dict) or not state["items"]:
            raise ValueError("채용 이력 데이터 없음")
        rows, skipped = forecast.get("rows"), forecast.get("skipped")
        if not isinstance(rows, list) or not isinstance(skipped, list):
            raise ValueError("예상 공고 데이터 형식 오류")
    except (OSError, ValueError, TypeError) as exc:
        print(f"기관 링크 재생성 보류: 저장된 데이터 확인 필요 ({type(exc).__name__})")
        return 1

    orgs.generate(state, [], rows, skipped, datetime.now(history.KST))
    remaining = sum(bool(LEGACY.search(page.read_text(encoding="utf-8")))
                    for page in history.ROOT.glob("org-*.html"))
    print(f"기관 링크 재생성: 기존 오류 페이지 {len(stale)}개, 잔여 {remaining}개")
    return 1 if remaining else 0


if __name__ == "__main__":
    raise SystemExit(main())

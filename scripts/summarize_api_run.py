#!/usr/bin/env python3
"""Summarize ALIO/QNet run outcomes from existing collector messages.

This reads logs only, never credentials or network responses. No output JSON is published.
"""
import sys
from pathlib import Path


def classify(log):
    if "ALIO_KEY 가 없어" in log:
        alio = "SKIPPED (ALIO_KEY missing)"
    elif "잡알리오 요청 실패:" in log or "잡알리오 연동 오류(" in log:
        alio = "ERROR (request or processing failed; check logs)"
    elif "가져온 공고가 없어 기존 alio.json" in log:
        alio = "WARNING (no active records; snapshot retained)"
    elif "잡알리오 변경 없음" in log:
        alio = "SUCCESS (API returned; no changes)"
    elif "alio.json 갱신:" in log:
        alio = "SUCCESS (snapshot updated)"
    else:
        alio = "UNKNOWN (inspect collector logs)"

    if "큐넷 시험일정 오류(무시하고 계속):" in log or "큐넷 시험일정을 받지 못해" in log:
        qnet = "ERROR (no usable schedule; snapshot retained)"
    elif "큐넷 " in log and "요청 실패:" in log:
        qnet = "WARNING (some QNet requests failed; snapshot may be partial)"
    elif "qnet.json 갱신:" in log:
        qnet = "SUCCESS (snapshot updated)"
    else:
        qnet = "SKIPPED/UNKNOWN (daily cache or no credentials; not proof of success)"
    return alio, qnet


def main(path):
    if not path.is_file():
        print("## API 호출 실행 결과\n\n수집 로그가 없어 결과를 확인할 수 없습니다.")
        return
    log = path.read_text(encoding="utf-8", errors="replace")
    alio, qnet = classify(log)
    print("## API 호출 실행 결과")
    print()
    print("이 상태는 해당 실행의 수집 로그에서 판별하며, 저장된 데이터의 최신성과 별개입니다.")
    print()
    print(f"- ALIO: {alio}")
    print(f"- 큐넷: {qnet}")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/tmp/careerpick-api-run.log"))

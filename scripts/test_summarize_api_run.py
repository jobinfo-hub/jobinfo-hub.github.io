#!/usr/bin/env python3
from summarize_api_run import classify

def main():
    assert classify("ALIO_KEY 가 없어 잡알리오 연동을 건너뜁니다.")[0].startswith("SKIPPED")
    assert classify("잡알리오 요청 실패: timeout\n잡알리오 변경 없음")[0].startswith("ERROR")
    assert classify("잡알리오 변경 없음")[0].startswith("SUCCESS")
    assert classify("alio.json 갱신: 모집 중 공식 공고 4건")[0].startswith("SUCCESS")
    assert classify("가져온 공고가 없어 기존 alio.json 을 유지합니다.")[0].startswith("WARNING")
    assert classify("qnet.json 갱신: 시험 회차 30건")[1].startswith("SUCCESS")
    assert classify("큐넷 시험일정을 받지 못해 기존 파일을 유지합니다.")[1].startswith("ERROR")
    assert classify("잡알리오 변경 없음")[1].startswith("SKIPPED")
    print("API run classifier tests: PASS")

if __name__ == "__main__":
    main()

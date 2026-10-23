"""Check ALIO organization alias suggestions without conflating distinct names."""
from audit_org_alio_coverage import normalized_org_name

def main():
    examples = {
        " (재)우체국물류지원단 ": "우체국물류지원단",
        "한전KPS(주)": "한전KPS",
        "(주)강원랜드": "강원랜드",
        "㈜코레일테크": "코레일테크",
        "한국남부발전(주)": "한국남부발전",
        "국민건강보험공단 일산병원": "국민건강보험공단일산병원",
    }
    for name, expected in examples.items():
        actual = normalized_org_name(name)
        assert actual == expected, (name, actual, expected)
    assert normalized_org_name("한국수력원자력") != normalized_org_name("한국남부발전")
    print("ALIO institution name normalization PASS")

if __name__ == "__main__":
    main()

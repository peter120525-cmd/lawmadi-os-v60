#!/usr/bin/env python3
"""
추가 Target 조사
DRF API 문서에서 언급될 수 있는 다른 target들 테스트
"""
import os
import sys
import requests
from dotenv import load_dotenv

load_dotenv()

def test_target(target, query):
    """특정 target 테스트"""
    api_key = os.getenv("LAWGO_DRF_OC", "")
    url = "https://www.law.go.kr/DRF/lawSearch.do"
    params = {
        "OC": api_key,
        "target": target,
        "type": "JSON",
        "query": query
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        content_type = response.headers.get("Content-Type", "")

        if response.status_code == 200 and "json" in content_type.lower():
            data = response.json()
            # 유효한 응답인지 확인 (키가 있고 빈 응답이 아닌지)
            if data and len(str(data)) > 50:
                return True, data
        return False, None
    except:
        return False, None

def main():
    print("🔍 추가 Target 조사\n")

    # 가능성 있는 target들 (DRF API 추정)
    targets = [
        # 자치법규 관련
        ("ordin", "자치법규", "조례"),
        ("ordinlaw", "자치법규2", "조례"),
        ("locallaw", "자치법규3", "조례"),

        # 행정심판 관련
        ("admprec", "행정심판례", "행정심판"),
        ("admdec", "행정심판례2", "행정심판"),
        ("adjud", "행정심판례3", "심판"),

        # 조약 관련
        ("treaty", "조약", "조약"),
        ("inter", "조약2", "조약"),
        ("intlaw", "조약3", "조약"),

        # 학칙/공단 관련
        ("edulaw", "학칙공단", "학칙"),
        ("schrule", "학칙공단2", "학칙"),
        ("regulation", "학칙공단3", "규정"),

        # 기타 가능성
        ("lword", "법령용어", "민법"),
        ("eflaw", "영문법령", "constitution"),
    ]

    results = {}

    for target, name, query in targets:
        success, data = test_target(target, query)

        if success:
            print(f"✅ {target:15} | {name:12} | 작동")
            # 응답 구조 출력
            print(f"   응답 키: {list(data.keys())}")

            # totalCnt 찾기
            for key, value in data.items():
                if isinstance(value, dict):
                    total = value.get('totalCnt', 0)
                    if total:
                        print(f"   검색 결과: {total}건")
            results[target] = {"name": name, "success": True, "data": data}
        else:
            print(f"❌ {target:15} | {name:12} | 미지원")
            results[target] = {"name": name, "success": False}

    # 요약
    print(f"\n{'='*60}")
    print("📊 작동하는 Target 목록:")
    print(f"{'='*60}")

    working = [t for t, info in results.items() if info["success"]]

    for target in working:
        info = results[target]
        print(f"  ✅ target={target:12} - {info['name']}")

    print(f"\n총 {len(working)}개 target 작동 확인")

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
법령 응답 구조 분석
법령용어가 법령 데이터 내에 포함되어 있는지 확인
"""
import os
import sys
import json
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from connectors.drf_client import DRFConnector

def analyze_law_structure():
    """법령 응답의 상세 구조 분석"""
    print("🔍 법령 응답 구조 분석\n")

    api_key = os.getenv("LAWGO_DRF_OC", "")
    if not api_key:
        print("❌ LAWGO_DRF_OC 환경변수 미설정")
        sys.exit(1)

    drf = DRFConnector(api_key=api_key)

    # 민법 조회
    print("="*60)
    print("테스트: 민법 조회 (법령용어 포함 여부 확인)")
    print("="*60)

    result = drf.search_by_target("민법", target="law")

    if not result:
        print("❌ 응답 없음")
        return

    print(f"\n✅ 응답 성공")

    # 전체 키 구조 출력
    print(f"\n1단계 키: {list(result.keys())}")

    # LawSearch 하위 분석
    if "LawSearch" in result:
        law_search = result["LawSearch"]
        print(f"\nLawSearch 키: {list(law_search.keys())}")

        # law 배열 분석
        if "law" in law_search and isinstance(law_search["law"], list):
            laws = law_search["law"]
            print(f"\n법령 개수: {len(laws)}개")

            if laws:
                first_law = laws[0]
                print(f"\n첫 번째 법령의 키:")

                # 모든 키를 계층적으로 출력
                def print_keys(obj, indent=0):
                    """재귀적으로 모든 키 출력"""
                    prefix = "  " * indent
                    if isinstance(obj, dict):
                        for key, value in obj.items():
                            if isinstance(value, dict):
                                print(f"{prefix}📁 {key}:")
                                print_keys(value, indent + 1)
                            elif isinstance(value, list):
                                print(f"{prefix}📋 {key}: [{len(value)}개 항목]")
                                if value and isinstance(value[0], dict):
                                    print(f"{prefix}   첫 항목 키: {list(value[0].keys())}")
                            else:
                                # 값이 너무 길면 앞부분만
                                val_str = str(value)
                                if len(val_str) > 50:
                                    val_str = val_str[:50] + "..."
                                print(f"{prefix}📄 {key}: {val_str}")

                print_keys(first_law, indent=1)

                # 용어 관련 키 찾기
                print("\n" + "="*60)
                print("용어 관련 키 검색:")
                print("="*60)

                def find_term_keys(obj, path=""):
                    """용어 관련 키 찾기"""
                    found = []
                    if isinstance(obj, dict):
                        for key, value in obj.items():
                            current_path = f"{path}.{key}" if path else key
                            # 용어 관련 키워드
                            if any(keyword in key.lower() for keyword in ["term", "word", "용어", "dict", "glossary"]):
                                found.append(f"✅ {current_path}: {type(value).__name__}")
                            found.extend(find_term_keys(value, current_path))
                    elif isinstance(obj, list):
                        for i, item in enumerate(obj[:3]):  # 처음 3개만
                            found.extend(find_term_keys(item, f"{path}[{i}]"))
                    return found

                term_keys = find_term_keys(first_law)

                if term_keys:
                    print("\n발견된 용어 관련 키:")
                    for key in term_keys:
                        print(f"  {key}")
                else:
                    print("\n❌ 용어 관련 키 없음")

                # JSON 전체 저장 (분석용)
                output_file = "law_response_sample.json"
                with open(output_file, "w", encoding="utf-8") as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)
                print(f"\n💾 전체 응답 저장: {output_file}")

    print("\n" + "="*60)
    print("💡 결론:")
    print("="*60)
    print("법령 응답 구조를 분석하여 용어 관련 필드를 확인합니다.")
    print("만약 용어가 별도 필드로 없다면, DRF API에서 법령용어는 미지원입니다.")

if __name__ == "__main__":
    analyze_law_structure()

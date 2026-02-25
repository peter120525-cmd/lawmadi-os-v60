"""
Lawmadi OS v60 — 사용자 관점 100회 사용 테스트
실제 사용자가 홈페이지에서 물어볼 법률 질문 100건
"""
import requests
import time
import json
import re
import sys
from datetime import datetime

# 사용자 환경과 동일: 프론트엔드(app.js)의 fetch('/ask') 호출 방식 그대로 재현
# - 인증 헤더 없음 (무료 사용자)
# - Content-Type: application/json 만 사용
# - body: { query: "질문" }
API = "https://lawmadi-os-v60-938146962157.asia-northeast3.run.app"
TIMEOUT = 120

# 실제 사용자가 물어볼 100개 질문 (다양한 법률 분야)
QUESTIONS = [
    # === 민사·계약 (L01) ===
    "친구한테 500만원 빌려줬는데 안 갚아요. 어떻게 해야 하나요?",
    "계약서 없이 돈 빌려줬는데 받을 수 있나요?",
    "중고거래에서 사기 당했어요. 돈 돌려받을 수 있나요?",
    "내용증명 보내는 방법 알려주세요",
    "소멸시효가 뭔가요? 빌려준 돈 3년 지났으면 못 받나요?",
    "지급명령 신청하려는데 어떻게 하나요?",
    "손해배상 청구소송 절차가 궁금합니다",
    "보증금 돌려달라고 했는데 안 줘요",
    "물건 샀는데 하자가 있어요. 환불 받을 수 있나요?",
    "계약 해제하고 싶은데 위약금 내야 하나요?",

    # === 부동산 (L02) ===
    "아파트 매매 계약했는데 취소할 수 있나요?",
    "부동산 중개사가 허위 정보를 줬어요",
    "등기부등본 확인 방법 알려주세요",
    "전세 계약 만료인데 집주인이 보증금 안 돌려줘요",
    "부동산 사기 당한 것 같아요. 어떻게 하죠?",

    # === 재건축·재개발 (L04) ===
    "재개발 구역 지정되면 어떻게 되나요?",
    "재건축 조합원 자격 조건이 뭔가요?",

    # === 의료 (L05) ===
    "수술 후 부작용이 생겼는데 의료사고인가요?",
    "의료과실로 손해배상 청구할 수 있나요?",
    "병원에서 설명 없이 시술했어요",

    # === 손해배상 (L06) ===
    "이웃집 누수로 우리집 피해 봤어요. 배상 받을 수 있나요?",
    "개에게 물렸는데 주인한테 치료비 청구할 수 있나요?",
    "위자료는 얼마나 받을 수 있나요?",

    # === 교통사고 (L07) ===
    "교통사고 났는데 보험회사가 적게 줘요",
    "뺑소니 당했어요. 어떻게 해야 하나요?",
    "교통사고 합의금 적정 금액이 궁금해요",
    "음주운전 사고 피해자인데 보상 어떻게 받나요?",

    # === 임대차 (L08) ===
    "월세 밀렸는데 쫓겨나나요?",
    "임대차 3법이 뭔가요?",
    "전세사기 예방하려면 어떻게 해야 하나요?",
    "상가 권리금 보호받을 수 있나요?",
    "집주인이 갑자기 나가라고 해요",

    # === 건설 (L09) ===
    "아파트 하자보수 청구 기간이 언제까지인가요?",
    "인테리어 공사 하자가 있는데 어떻게 하나요?",

    # === 회사·M&A (L14) ===
    "주주총회 소집 절차가 궁금합니다",
    "이사의 충실의무가 뭔가요?",
    "소수주주권 행사 방법 알려주세요",

    # === 보험 (L16) ===
    "보험금 청구했는데 거절당했어요",
    "보험사가 면책이라고 하는데 맞나요?",

    # === 금융·증권 (L18) ===
    "주식 투자 사기 당했어요. 구제 방법 있나요?",
    "불법 대출 중개 피해 구제 방법이 뭔가요?",

    # === 조세 (L20) ===
    "양도소득세 비과세 조건이 뭔가요?",
    "증여세 면제 한도가 얼마인가요?",
    "종합소득세 신고 방법 알려주세요",

    # === 형사 (L22) ===
    "사기죄로 고소하려면 어떻게 하나요?",
    "명예훼손으로 고소당했어요. 어떡하죠?",
    "폭행당했는데 고소 절차 알려주세요",
    "성범죄 피해자 보호 제도가 있나요?",
    "형사 합의금 적정 금액이 궁금해요",

    # === 지식재산 (L26) ===
    "상표권 등록 절차가 궁금합니다",
    "특허 침해 당했는데 어떻게 하나요?",
    "디자인권 보호 방법 알려주세요",

    # === 노동 (L30) ===
    "부당해고 당했어요. 어떻게 구제받나요?",
    "퇴직금 안 줘요. 어디에 신고하나요?",
    "야근 수당 안 받았는데 청구할 수 있나요?",
    "직장 내 괴롭힘 당하고 있어요",
    "최저임금보다 적게 받고 있어요",
    "해고예고 없이 잘렸어요",
    "연차 사용 거부당했어요",

    # === 행정 (L31) ===
    "영업정지 처분 받았는데 취소할 수 있나요?",
    "건축허가 반려됐는데 이의신청 하고 싶어요",
    "행정심판 청구 방법 알려주세요",

    # === 개인정보 (L34) ===
    "개인정보 유출됐는데 손해배상 받을 수 있나요?",
    "스팸 문자 계속 와요. 신고할 수 있나요?",
    "CCTV 동의 없이 촬영당했어요",

    # === 헌법·기본권 (L35) ===
    "표현의 자유는 어디까지 보호되나요?",
    "헌법소원 청구 절차가 궁금합니다",
    "기본권 침해 구제 방법이 뭔가요?",

    # === 환경 (L37) ===
    "공장 소음으로 피해 보고 있어요",
    "환경오염 피해 배상 청구할 수 있나요?",

    # === 이혼·가족 (L41) ===
    "협의이혼 절차가 어떻게 되나요?",
    "양육권 다툼에서 유리하려면 어떻게 해야 하나요?",
    "재산분할 비율은 어떻게 정해지나요?",
    "위자료 청구 조건이 뭔가요?",
    "면접교섭권이 뭔가요?",

    # === 저작권 (L42) ===
    "유튜브 영상 도용당했어요. 어떻게 하나요?",
    "저작권 침해 기준이 뭔가요?",
    "AI가 만든 콘텐츠도 저작권 있나요?",

    # === 산업재해 (L43) ===
    "산재 신청 방법 알려주세요",
    "출퇴근 중 다쳤는데 산재 되나요?",
    "직업병 산재 인정 기준이 뭔가요?",

    # === 소비자 (L45) ===
    "인터넷 쇼핑 환불 거부당했어요",
    "제조물 결함으로 다쳤어요. 보상받을 수 있나요?",

    # === 상속 (L57) ===
    "유언장 작성 방법 알려주세요",
    "상속포기 절차가 어떻게 되나요?",
    "법정상속분이 어떻게 계산되나요?",
    "유류분 반환 청구할 수 있나요?",

    # === 국제 (L52) ===
    "해외에서 물건 샀는데 하자가 있어요",
    "외국인 체류자격 변경 방법 알려주세요",

    # === 스포츠·엔터 (L50) ===
    "연예인 전속계약 해지 조건이 뭔가요?",
    "초상권 침해 기준이 궁금해요",

    # === 실생활 복합 질문 ===
    "집 전세 살고 있는데 집주인이 바뀌었어요. 보증금 괜찮나요?",
    "온라인에서 악플 달린 거 고소할 수 있나요?",
    "회사에서 부당전보 당했는데 어떻게 하나요?",
    "학교폭력 가해자 처벌이 궁금해요",
    "층간소음 분쟁 해결 방법이 뭔가요?",
    "이웃이 불법 증축했어요. 신고할 수 있나요?",
    "자동차 리스 중도해지 위약금이 너무 높아요",
    "프리랜서인데 계약금 안 줘요",
    "공동명의 부동산 매각하려면 어떻게 하나요?",
]

assert len(QUESTIONS) == 100, f"질문 수: {len(QUESTIONS)} (100개 필요)"

def analyze_response(resp_data):
    """응답 품질 분석"""
    text = resp_data.get("response", "")
    status = resp_data.get("status", "UNKNOWN")
    leader = resp_data.get("leader_name", "")
    leader_id = resp_data.get("leader_id", "")

    # 법조문 수
    law_refs = re.findall(r'제\d+조', text)
    # 판례 수
    prec_refs = re.findall(r'\d{2,4}[가-힣]+\d{2,6}', text)
    # 응답 길이
    length = len(text)

    # 품질 점수 (5점 만점)
    score = 0
    if length >= 2000:
        score += 2
    elif length >= 1000:
        score += 1
    if len(law_refs) >= 2:
        score += 1
    if len(law_refs) >= 5:
        score += 1
    if "법률 근거" in text or "관련 법률" in text or "법적 근거" in text or "법률 조문" in text:
        score += 1

    return {
        "status": status,
        "leader": leader,
        "leader_id": leader_id,
        "length": length,
        "law_refs": len(law_refs),
        "prec_refs": len(set(prec_refs)),
        "score": score,
    }


def run_test(idx, question):
    """단일 질문 테스트"""
    try:
        start = time.time()
        resp = requests.post(
            f"{API}/ask",
            json={"query": question},
            headers={"Content-Type": "application/json"},
            timeout=TIMEOUT,
        )
        elapsed = time.time() - start

        if resp.status_code != 200:
            return {
                "idx": idx + 1,
                "question": question[:30],
                "status": f"HTTP_{resp.status_code}",
                "leader": "",
                "leader_id": "",
                "length": 0,
                "law_refs": 0,
                "prec_refs": 0,
                "score": 0,
                "latency": round(elapsed, 1),
                "error": resp.text[:100],
            }

        data = resp.json()
        analysis = analyze_response(data)
        analysis["idx"] = idx + 1
        analysis["question"] = question[:30]
        analysis["latency"] = round(elapsed, 1)
        analysis["error"] = ""

        return analysis

    except requests.exceptions.Timeout:
        return {
            "idx": idx + 1,
            "question": question[:30],
            "status": "TIMEOUT",
            "leader": "",
            "leader_id": "",
            "length": 0,
            "law_refs": 0,
            "prec_refs": 0,
            "score": 0,
            "latency": TIMEOUT,
            "error": "TIMEOUT",
        }
    except Exception as e:
        return {
            "idx": idx + 1,
            "question": question[:30],
            "status": "ERROR",
            "leader": "",
            "leader_id": "",
            "length": 0,
            "law_refs": 0,
            "prec_refs": 0,
            "score": 0,
            "latency": 0,
            "error": str(e)[:100],
        }


def main():
    print("=" * 70)
    print(f"사용자 관점 100회 사용 테스트")
    print(f"시작: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    # 서버 상태 확인
    try:
        health = requests.get(f"{API}/health", timeout=10).json()
        print(f"서버: {health.get('status')} | 버전: {health.get('os_version')}")
    except:
        print("서버 상태 확인 실패")
        return

    print()
    results = []
    success = 0
    fail_closed = 0
    errors = 0
    total_latency = 0

    # 순차 실행 (Gemini API 할당량 보호)
    for i in range(100):
        r = run_test(i, QUESTIONS[i])
        results.append(r)
        total_latency += r["latency"]

        status_icon = "✅" if r["status"] == "SUCCESS" else "⚠️" if r["status"] == "FAIL_CLOSED" else "❌"
        if r["status"] == "SUCCESS":
            success += 1
        elif r["status"] == "FAIL_CLOSED":
            fail_closed += 1
        else:
            errors += 1

        print(
            f"  [{r['idx']:3d}/100] {status_icon} {r['question']:<32s} "
            f"| {r['leader']:4s} | {r['length']:5d}자 | "
            f"법:{r['law_refs']:2d} 례:{r['prec_refs']:2d} | "
            f"{r['latency']:5.1f}s | Q:{r['score']}/5"
        )

        # 10건마다 중간 리포트
        done = len(results)
        if done % 10 == 0:
            pct = success / done * 100
            avg_lat = total_latency / done
            print(f"  --- {done}/100 완료 | 성공:{success} FAIL_CLOSED:{fail_closed} 오류:{errors} | 성공률:{pct:.0f}% | 평균:{avg_lat:.1f}s ---")
            print()

    # === 최종 리포트 ===
    print()
    print("=" * 70)
    print("최종 결과")
    print("=" * 70)
    print()

    avg_latency = total_latency / 100
    avg_length = sum(r["length"] for r in results) / 100
    avg_score = sum(r["score"] for r in results) / 100
    avg_laws = sum(r["law_refs"] for r in results) / 100
    avg_precs = sum(r["prec_refs"] for r in results) / 100

    success_results = [r for r in results if r["status"] == "SUCCESS"]
    if success_results:
        avg_success_length = sum(r["length"] for r in success_results) / len(success_results)
        avg_success_latency = sum(r["latency"] for r in success_results) / len(success_results)
    else:
        avg_success_length = 0
        avg_success_latency = 0

    print(f"  총 테스트: 100건")
    print(f"  SUCCESS:     {success}/100 ({success}%)")
    print(f"  FAIL_CLOSED: {fail_closed}/100")
    print(f"  ERROR:       {errors}/100")
    print()
    print(f"  평균 레이턴시:  {avg_latency:.1f}s (성공만: {avg_success_latency:.1f}s)")
    print(f"  평균 응답 길이: {avg_length:.0f}자 (성공만: {avg_success_length:.0f}자)")
    print(f"  평균 품질:     {avg_score:.1f}/5")
    print(f"  평균 법조문:   {avg_laws:.1f}개")
    print(f"  평균 판례:     {avg_precs:.1f}개")
    print()

    # 길이 분포
    len_ranges = {
        "0~999자": 0,
        "1000~1999자": 0,
        "2000~2999자": 0,
        "3000자+": 0,
    }
    for r in success_results:
        l = r["length"]
        if l < 1000:
            len_ranges["0~999자"] += 1
        elif l < 2000:
            len_ranges["1000~1999자"] += 1
        elif l < 3000:
            len_ranges["2000~2999자"] += 1
        else:
            len_ranges["3000자+"] += 1

    print("  응답 길이 분포 (SUCCESS):")
    for label, cnt in len_ranges.items():
        bar = "█" * (cnt // 2)
        print(f"    {label:12s}: {cnt:3d}건 {bar}")
    print()

    # 레이턴시 분포
    lat_ranges = {
        "0~15초": 0,
        "15~30초": 0,
        "30~60초": 0,
        "60~90초": 0,
        "90초+": 0,
    }
    for r in success_results:
        t = r["latency"]
        if t < 15:
            lat_ranges["0~15초"] += 1
        elif t < 30:
            lat_ranges["15~30초"] += 1
        elif t < 60:
            lat_ranges["30~60초"] += 1
        elif t < 90:
            lat_ranges["60~90초"] += 1
        else:
            lat_ranges["90초+"] += 1

    print("  레이턴시 분포 (SUCCESS):")
    for label, cnt in lat_ranges.items():
        bar = "█" * (cnt // 2)
        print(f"    {label:8s}: {cnt:3d}건 {bar}")
    print()

    # 리더 분포
    leader_stats = {}
    for r in results:
        lid = r.get("leader_id", "") or r.get("leader", "") or "unknown"
        if lid not in leader_stats:
            leader_stats[lid] = {"count": 0, "success": 0, "name": r.get("leader", "")}
        leader_stats[lid]["count"] += 1
        if r["status"] == "SUCCESS":
            leader_stats[lid]["success"] += 1

    sorted_leaders = sorted(leader_stats.items(), key=lambda x: x[1]["count"], reverse=True)
    print("  리더 배정 분포 (TOP 15):")
    for lid, s in sorted_leaders[:15]:
        print(f"    {lid:6s} {s['name']:6s}: {s['count']:3d}건 (성공 {s['success']}건)")
    print()

    # 실패 목록
    failures = [r for r in results if r["status"] not in ("SUCCESS",)]
    if failures:
        print(f"  실패/제한 상세 ({len(failures)}건):")
        for r in failures:
            print(f"    [{r['idx']:3d}] {r['status']:12s} | {r['question']} | {r.get('error', '')[:60]}")
    print()

    # 품질 분포
    score_dist = {0: 0, 1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    for r in success_results:
        score_dist[r["score"]] = score_dist.get(r["score"], 0) + 1

    print("  품질 점수 분포 (SUCCESS):")
    for s in range(6):
        cnt = score_dist.get(s, 0)
        bar = "█" * cnt
        print(f"    {s}/5: {cnt:3d}건 {bar}")
    print()

    print(f"  종료: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    # 결과 저장
    save_data = {
        "test_date": datetime.now().isoformat(),
        "total": 100,
        "success": success,
        "fail_closed": fail_closed,
        "errors": errors,
        "avg_latency": round(avg_latency, 1),
        "avg_length": round(avg_length, 0),
        "avg_score": round(avg_score, 1),
        "results": results,
    }
    with open("tests/test_user_100_results.json", "w", encoding="utf-8") as f:
        json.dump(save_data, f, ensure_ascii=False, indent=2)
    print(f"\n결과 저장: tests/test_user_100_results.json")


if __name__ == "__main__":
    main()

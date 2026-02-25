"""1건씩 테스트 - 5점 연속 10회 달성 시 중지"""
import requests, re, sys, time

API = "https://lawmadi-os-v60-938146962157.asia-northeast3.run.app"

QUESTIONS = [
    "친구한테 500만원 빌려줬는데 안 갚아요. 어떻게 해야 하나요?",
    "전세 계약 만료인데 집주인이 보증금 안 돌려줘요",
    "수술 후 부작용이 생겼는데 의료사고인가요?",
    "이웃집 누수로 우리집 피해 봤어요. 배상 받을 수 있나요?",
    "교통사고 났는데 보험회사가 적게 줘요",
    "직장에서 부당해고 당했어요",
    "아파트 층간소음 때문에 미치겠어요",
    "이혼할 때 재산분할 어떻게 하나요?",
    "상속 포기하고 싶은데 방법이 뭔가요?",
    "건물주가 갑자기 임대료를 올렸어요",
    "회사가 월급을 안 줘요",
    "온라인 쇼핑몰에서 환불 거부당했어요",
    "명예훼손으로 고소하려면 어떻게 하나요?",
    "개인정보 유출 피해 보상 받을 수 있나요?",
    "중고차 사고 이력 숨기고 팔면 어떻게 되나요?",
    "특허 침해 소송 절차가 궁금합니다",
    "임금체불로 노동청에 신고하려면?",
    "재개발 구역 지정되면 어떻게 되나요?",
    "음주운전 처벌 기준이 어떻게 되나요?",
    "공무원 징계에 불복하려면 어떻게 하나요?",
    "저작권 침해 신고하려면?",
    "프랜차이즈 계약 해지 위약금이 너무 높아요",
    "소비자 보호법에 따라 환불받을 수 있나요?",
    "연예인 초상권 침해 기준이 뭔가요?",
    "세금 체납하면 어떤 불이익이 있나요?",
    "부동산 중개사가 허위 정보를 줬어요",
    "아파트 매매 계약했는데 취소할 수 있나요?",
    "유언장 작성 방법이 궁금합니다",
    "채무 정리 방법 알려주세요",
    "보험금 청구했는데 거절당했어요",
]

# 질문별 관련 법률 키워드 (무관 조문 감지용)
Q_TOPIC = {
    "빌려": ["민법", "민사소송", "민사집행", "채권", "이자", "소액"],
    "보증금": ["주택임대차", "임대차", "민법", "민사소송", "민사집행"],
    "의료사고": ["의료법", "민법", "형법", "의료사고"],
    "누수": ["민법", "집합건물", "주택법", "건축법", "손해배상"],
    "교통사고": ["자동차손해배상", "도로교통", "민법", "교통사고", "보험"],
    "부당해고": ["근로기준법", "노동", "근로", "고용"],
    "층간소음": ["주택법", "공동주택", "민법", "환경", "소음", "층간", "이웃", "경범죄"],
    "이혼": ["민법", "가사소송", "가정폭력"],
    "상속": ["민법", "상속세", "가사"],
    "임대료": ["상가건물", "임대차", "민법"],
    "월급": ["근로기준법", "임금", "노동", "민사소송", "소액사건", "인지법"],
    "환불": ["전자상거래", "소비자", "민법", "약관"],
    "명예훼손": ["형법", "정보통신", "민법", "명예"],
    "개인정보": ["개인정보", "정보통신"],
    "중고차": ["자동차관리", "민법", "소비자"],
    "특허": ["특허법", "지식재산", "민사소송"],
    "임금체불": ["근로기준법", "임금", "노동", "민사소송", "소액사건", "인지법"],
    "재개발": ["도시정비", "재개발", "재건축", "주택", "도시", "주거환경", "정비"],
    "음주운전": ["도로교통", "형법", "특정범죄"],
    "공무원": ["국가공무원", "행정소송", "행정심판", "행정절차", "국가배상"],
    "저작권": ["저작권", "정보통신"],
    "프랜차이즈": ["가맹사업", "가맹", "민법", "상법"],
    "소비자": ["소비자", "전자상거래", "약관", "민법"],
    "초상권": ["민법", "언론", "정보통신", "초상"],
    "세금": ["국세", "조세", "세법", "소득세", "부가가치세", "징수", "체납"],
    "중개사": ["공인중개사", "부동산", "민법"],
    "매매": ["민법", "부동산", "주택"],
    "유언장": ["민법", "상속", "유언"],
    "채무": ["채무자", "민법", "파산", "회생", "민사집행"],
    "보험금": ["보험", "상법", "민법", "보험업"],
}

def find_irrelevant(question, text):
    """법률 근거 섹션에서 질문과 무관한 법률 인용 탐지"""
    section_match = re.search(r'##\s*법률\s*근거(.*)', text, re.DOTALL)
    if not section_match:
        return []
    section = section_match.group(1)
    raw = re.findall(r'([가-힣]+(?:법|시행령|규칙|조례))', section)
    fp = {"대법", "위법", "불법", "합법", "사법", "입법", "탈법", "준법", "적법", "공법",
          "대한법", "방법", "가정법", "보장법", "특별법", "기본법", "절차법", "실체법",
          "일반법", "특례법", "보호법", "국가법", "취업규칙",
          "공익법", "현행법", "관계법", "관련법", "소송법",
          "지방법", "노무법", "자연법", "표시방법", "관습법", "국가재정법"}
    cited_laws = [l for l in raw if l not in fp and len(l) >= 3]

    related = set()
    for keyword, laws in Q_TOPIC.items():
        if keyword in question:
            for law in laws:
                related.add(law)
    if not related:
        return []

    common = {"민법", "헌법", "민사소송법", "형법", "형사소송법"}
    irrelevant = []
    for law in cited_laws:
        is_rel = any(r in law or law in r for r in related)
        is_com = any(c in law for c in common)
        if not is_rel and not is_com:
            irrelevant.append(law)
    return irrelevant


def score(question, text, drf_pass):
    """5점 만점 (cap)
    +1 길이2000자+ | +1 법조문있음 | +1 핵심만/-2 무관 | +1 근거섹션 | +1 판례 | +2 DRF통과
    """
    law_refs = re.findall(r'제\d+조', text)
    prec1 = re.findall(r'\d{2,4}[가-힣]+\d{2,6}', text)
    prec2 = re.findall(r'(?:대법원|헌법재판소|고등법원|지방법원).{0,10}\d{4}\.\s*\d{1,2}\.\s*\d{1,2}\.?\s*선고', text)
    pc = len(set(prec1)) + len(prec2)
    has_sec = any(k in text for k in ["법률 근거", "관련 법률", "법적 근거", "법률 조문"])
    irrelevant = find_irrelevant(question, text)

    s = 0
    if len(text) >= 2000: s += 1
    if len(law_refs) >= 1: s += 1
    if not irrelevant: s += 1
    else: s -= 2
    if has_sec: s += 1
    if pc >= 1: s += 1
    if drf_pass: s += 2                    # +2: DRF 검증 통과
    s = max(0, min(5, s))
    return s, len(text), len(law_refs), pc, has_sec, irrelevant

consecutive = 0
total = 0

for i, q in enumerate(QUESTIONS):
    total += 1
    t0 = time.time()
    try:
        r = requests.post(f"{API}/ask", json={"query": q}, timeout=120)
        data = r.json()
        ans = data.get("response", data.get("answer", ""))
        status = data.get("status", "")
        leader = data.get("leader_name", data.get("leader", ""))
        meta = data.get("meta", {})
        drf_pass = meta.get("ssot_verified", False)
        elapsed = time.time() - t0
    except Exception as e:
        print(f"[{i+1:02d}] ERROR: {e}")
        consecutive = 0
        continue

    if status != "SUCCESS" or not ans or len(ans) < 50:
        print(f"[{i+1:02d}] FAIL ({status}) {q[:20]}... | {elapsed:.1f}s")
        consecutive = 0
        continue

    sc, length, refs, precs, has_sec, irrel = score(q, ans, drf_pass)

    if sc == 5:
        consecutive += 1
        mark = "★"
    else:
        consecutive = 0
        mark = "✗"

    missing = []
    if length < 2000: missing.append(f"길이{length}")
    if refs < 1: missing.append("법조문X")
    if not has_sec: missing.append("근거섹션X")
    if precs < 1: missing.append("판례X")
    if irrel: missing.append(f"무관:{irrel}")
    if not drf_pass: missing.append("DRF미통과")

    miss_str = f" 부족:{missing}" if missing else ""
    drf_mark = "DRF✓" if drf_pass else "DRF✗"
    print(f"[{i+1:02d}] {mark} {sc}/5 | 연속:{consecutive}/10 | {length}자 법{refs} 판례{precs} {drf_mark} | {elapsed:.1f}s | {leader} | {q[:20]}...{miss_str}")
    sys.stdout.flush()

    if consecutive >= 10:
        print(f"\n🎉 5점 만점 10회 연속 달성! (총 {total}건)")
        break

    time.sleep(1)

if consecutive < 10:
    print(f"\n⚠️ {total}건 완료, 최종 연속 5점: {consecutive}회")

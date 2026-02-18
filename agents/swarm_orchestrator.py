#!/usr/bin/env python3
"""
Lawmadi OS Swarm Orchestrator
진정한 60 Leader 협업 아키텍처

Chapter 3 구현:
- 여러 Leader가 동시에 문제 분석
- 각 Leader의 전문 분야 사고방식 적용
- 결과를 조합하여 최종 판단 흐름 구성
"""
import json
import os
import logging
from typing import Dict, List, Tuple, Optional
from google import genai
from google.genai import types as genai_types
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger("LawmadiOS.SwarmOrchestrator")


class SwarmOrchestrator:
    """
    60 Leader Swarm 오케스트레이터

    역할:
    1. Query 분석 → 관련 법률 도메인 탐지
    2. 도메인별 전문 Leader 자동 선택
    3. 다중 Leader 병렬 분석 실행
    4. 결과 통합 → 종합 판단 흐름 생성
    """

    def __init__(self, leaders_registry: Dict, config: Dict = None, genai_client=None):
        self.leaders = leaders_registry
        self.config = config or {}
        self.genai_client = genai_client

        # Leader별 도메인 키워드 매핑
        self._build_domain_index()

        # Swarm 모드 설정
        self.swarm_enabled = os.getenv("SWARM_ENABLED", "true").lower() == "true"
        self.max_leaders = int(os.getenv("SWARM_MAX_LEADERS", "3"))
        self.min_leaders = int(os.getenv("SWARM_MIN_LEADERS", "1"))

        logger.info(f"✅ SwarmOrchestrator initialized: {len(self.leaders)} leaders, swarm={self.swarm_enabled}")

    def _build_domain_index(self):
        """각 Leader의 specialty를 기반으로 도메인 키워드 인덱스 구축"""
        self.domain_keywords = {
            "L01": ["민사", "계약", "손해배상", "부당이득", "민법", "채무", "불법행위"],  # 민사법
            "L02": ["부동산", "등기", "소유권", "지분", "매매", "토지", "건물"],  # 부동산법
            "L03": ["건설", "공사", "하자", "설계", "시공"],  # 건설법
            "L04": ["재개발", "재건축", "조합", "분양", "정비사업"],  # 재개발·재건축
            "L05": ["의료", "진료", "수술", "병원", "의사", "환자", "의료과실"],  # 의료법
            "L06": ["손해배상", "과실", "배상", "보상", "위자료"],  # 손해배상
            "L07": ["교통사고", "사고", "과실", "보험", "자동차"],  # 교통사고
            "L08": ["임대차", "전세", "월세", "보증금", "임차", "임대", "집주인"],  # 임대차
            "L09": ["국가계약", "입찰", "계약", "공공계약"],  # 국가계약
            "L10": ["민사집행", "경매", "압류", "배당", "강제집행", "집행"],  # 민사집행
            "L11": ["채권", "추심", "변제", "채무", "빚"],  # 채권추심
            "L12": ["등기", "경매", "낙찰", "배당", "부동산등기"],  # 등기·경매
            "L13": ["상사", "회사", "주주", "이사", "상법", "상행위"],  # 상사법
            "L14": ["회사법", "M&A", "인수합병", "주식", "법인"],  # 회사법·M&A
            "L15": ["스타트업", "투자", "벤처", "스톡옵션", "창업"],  # 스타트업
            "L16": ["보험", "보험금", "피보험자", "약관", "보험사"],  # 보험
            "L17": ["국제거래", "무역", "중재", "외국", "국제"],  # 국제거래
            "L18": ["에너지", "자원", "전력", "광업", "전기"],  # 에너지·자원
            "L19": ["해상", "항공", "선박", "운송", "물류"],  # 해상·항공
            "L20": ["조세", "금융", "세금", "과세", "은행", "국세", "지방세"],  # 조세·금융
            "L21": ["IT", "보안", "해킹", "데이터", "정보보호", "개인정보", "사이버"],  # IT·보안
            "L22": ["형사", "고소", "처벌", "범죄", "기소", "형법", "사기", "횡령", "폭행", "절도", "구속", "수사", "검찰"],  # 형사법
            "L23": ["엔터테인먼트", "연예", "계약", "방송", "영화"],  # 엔터테인먼트
            "L24": ["조세불복", "심판", "이의신청", "과세전적부심사"],  # 조세불복
            "L25": ["군형법", "군대", "군사", "군인"],  # 군형법
            "L26": ["지식재산권", "특허", "상표", "저작권", "IP", "디자인권"],  # 지식재산권
            "L27": ["환경", "오염", "배출", "환경법", "폐기물"],  # 환경법
            "L28": ["무역", "관세", "수입", "수출", "FTA"],  # 무역·관세
            "L29": ["게임", "콘텐츠", "아이템", "게임물"],  # 게임·콘텐츠
            "L30": ["노동", "해고", "임금", "근로", "퇴직", "근로기준법", "부당해고", "노동조합"],  # 노동법
            "L31": ["행정", "행정처분", "취소", "허가", "행정소송", "행정청"],  # 행정법
            "L32": ["공정거래", "독점", "담합", "불공정", "경쟁제한"],  # 공정거래
            "L33": ["우주항공", "위성", "발사체", "항공우주"],  # 우주항공
            "L34": ["개인정보", "GDPR", "정보주체", "개인정보보호"],  # 개인정보
            "L35": ["헌법", "위헌", "기본권", "헌재", "헌법재판소", "위헌법률"],  # 헌법
            "L36": ["문화", "종교", "문화재", "문화유산"],  # 문화·종교
            "L37": ["소년법", "청소년", "미성년", "소년범"],  # 소년법
            "L38": ["소비자", "피해", "환불", "약관", "소비자보호"],  # 소비자
            "L39": ["정보통신", "통신", "망", "전기통신"],  # 정보통신
            "L40": ["인권", "차별", "평등", "인권침해"],  # 인권
            "L41": ["이혼", "가족", "양육", "위자료", "혼인", "친권", "상속"],  # 이혼·가족
            "L42": ["저작권", "표절", "침해", "저작물"],  # 저작권
            "L43": ["산업재해", "산재", "업무상", "산업안전"],  # 산업재해
            "L44": ["사회복지", "복지", "사회보장"],  # 사회복지
            "L45": ["교육", "학교", "청소년", "학생"],  # 교육·청소년
            "L46": ["보험", "연금", "국민연금", "4대보험"],  # 보험·연금
            "L47": ["벤처", "신산업", "규제샌드박스", "혁신"],  # 벤처·신산업
            "L48": ["문화예술", "예술", "미술", "문화"],  # 문화예술
            "L49": ["식품", "보건", "위생", "식품안전"],  # 식품·보건
            "L50": ["다문화", "이주", "외국인", "이민"],  # 다문화·이주
            "L51": ["종교", "전통", "종교법인", "사찰"],  # 종교·전통
            "L52": ["광고", "언론", "명예훼손", "언론중재", "명예", "출판"],  # 광고·언론
            "L53": ["농림", "축산", "농지", "농업", "축산업"],  # 농림·축산
            "L54": ["해양", "수산", "어업", "어선", "수산물"],  # 해양·수산
            "L55": ["과학기술", "R&D", "연구", "기술개발"],  # 과학기술
            "L56": ["장애인", "복지", "편의시설", "장애", "장애인차별금지"],  # 장애인·복지
            "L57": ["상속", "신탁", "유언", "유산", "명의신탁", "상속세", "증여"],  # 상속·신탁
            "L58": ["스포츠", "레저", "체육", "운동"],  # 스포츠·레저
            "L59": ["데이터", "AI윤리", "알고리즘", "인공지능", "AI"],  # 데이터·AI윤리
            # L60(마디)은 도메인 매칭에서 제외 — 기본 응답은 유나(CCO)가 담당
        }

    def detect_name_call(self, query: str) -> Optional[str]:
        """
        Query에서 리더 이름 직접 호출 감지

        "휘율아 계약 해지 방법" → "L01"
        "무결아 사기죄 질문" → "L22"

        Returns:
            매칭된 leader_id 또는 None
        """
        # 모든 매칭 후보를 수집한 뒤, 긴 이름 우선 + 같은 길이면 앞쪽 위치 우선
        matches = []
        for leader_id, info in self.leaders.items():
            name = info.get("name", "")
            if not name:
                continue
            pos = query.find(name)
            if pos >= 0:
                matches.append((leader_id, name, pos))

        if not matches:
            return None

        # 정렬: ① 이름 길이 내림차순 ② 출현 위치 오름차순
        matches.sort(key=lambda x: (-len(x[1]), x[2]))
        best_id, best_name, _ = matches[0]
        logger.info(f"🎯 이름 호출 감지: '{best_name}' → {best_id}")
        return best_id

    def detect_domains(self, query: str) -> List[Tuple[str, int]]:
        """
        Query에서 관련 법률 도메인 탐지

        Returns:
            List[Tuple[leader_id, score]] - 점수 순으로 정렬
        """
        domain_scores = {}

        query_lower = query.lower()

        for leader_id, keywords in self.domain_keywords.items():
            # 해당 leader_id가 실제 registry에 있는지 확인
            if leader_id not in self.leaders:
                continue

            score = 0
            matched_keywords = []

            for keyword in keywords:
                if keyword in query_lower:
                    score += 10
                    matched_keywords.append(keyword)

            if score > 0:
                domain_scores[leader_id] = score
                leader_name = self.leaders[leader_id].get('name', '?')
                logger.debug(f"🎯 {leader_id} ({leader_name}): score={score}, matched={matched_keywords}")

        # 점수순 정렬
        sorted_domains = sorted(domain_scores.items(), key=lambda x: x[1], reverse=True)

        return sorted_domains

    def select_leaders(self, query: str, detected_domains: List[Tuple[str, int]] = None) -> List[Dict]:
        """
        Query에 적합한 Leader 선택

        Returns:
            List[Dict] - 선택된 Leader 정보 리스트
        """
        if not self.swarm_enabled:
            # Swarm 비활성화 시 기본 리더(L60)만 반환
            return [self.leaders.get("L60", {"name": "마디", "role": "시스템 총괄", "specialty": "통합"})]

        # 이름 호출 감지 (도메인 매칭보다 우선)
        named_leader_id = self.detect_name_call(query)
        if named_leader_id:
            leader_info = self.leaders.get(named_leader_id, {})
            leader_info["_id"] = named_leader_id
            leader_info["_score"] = 100  # 이름 호출은 최고 우선순위
            logger.info(f"✅ 이름 호출 리더 단독 선택: {leader_info.get('name', '?')}({named_leader_id})")
            return [leader_info]

        if detected_domains is None:
            detected_domains = self.detect_domains(query)

        if not detected_domains:
            # 도메인 미탐지 → 유나(CCO)가 따뜻하게 맞이
            logger.info("🎯 도메인 미탐지 → 유나(CCO) 응대")
            return [{"name": "유나", "role": "Chief Content Officer", "specialty": "콘텐츠 설계", "_clevel": "CCO"}]

        # 상위 N개 도메인의 Leader 선택
        selected_leaders = []
        for leader_id, score in detected_domains[:self.max_leaders]:
            leader_info = self.leaders.get(leader_id, {})
            leader_info["_id"] = leader_id
            leader_info["_score"] = score
            selected_leaders.append(leader_info)

        # 최소 리더 수 보장
        if len(selected_leaders) < self.min_leaders:
            default_leader = {"name": "유나", "role": "Chief Content Officer", "specialty": "콘텐츠 설계", "_clevel": "CCO"}
            default_leader["_id"] = "CCO"
            default_leader["_score"] = 5
            selected_leaders.append(default_leader)

        leader_names = [f"{l.get('name', '?')}({l.get('specialty', '?')})" for l in selected_leaders]
        logger.info(f"✅ {len(selected_leaders)}명 리더 선택: {', '.join(leader_names)}")

        return selected_leaders

    def analyze_with_leader(
        self,
        leader: Dict,
        query: str,
        tools: List = None,
        system_instruction_base: str = "",
        model_name: str = "gemini-3-flash-preview"
    ) -> Dict:
        """
        단일 Leader로 분석 실행

        Returns:
            Dict: {"leader": str, "specialty": str, "analysis": str, "success": bool}
        """
        leader_name = leader.get("name", "Unknown")
        leader_role = leader.get("role", "Unknown")
        leader_specialty = leader.get("specialty", "Unknown")

        try:
            # C-Level 여부 확인
            clevel_id = leader.get("_clevel")

            if clevel_id == "CCO":
                # 유나(CCO) 전용: 따뜻하고 친근한 톤
                system_instruction = (
                    f"{system_instruction_base}\n\n"
                    f"🎯 당신의 역할: 유나 (CCO, Chief Content Officer)\n"
                    f"🎯 전문 분야: 콘텐츠 설계 · 사용자 경험\n"
                    f"🎯 톤: 따뜻하고 친근하며, 사용자의 불안을 공감하고 행동으로 바꿔주는 스타일\n\n"
                    f"사용자가 질문하면:\n"
                    f"1. 먼저 공감과 격려로 시작하세요\n"
                    f"2. 법률 관련이면 핵심 쟁점을 쉬운 말로 설명하세요\n"
                    f"3. 구체적인 행동 계획을 안내하세요\n"
                    f"4. 비법률 질문이면 친절하게 안내하되, 법률 상담도 가능함을 알려주세요\n\n"
                    f"반드시 [유나 (CCO) 콘텐츠 설계]로 시작하세요."
                )
            elif clevel_id == "CSO":
                # 서연(CSO) 전용: 전략적 접근
                system_instruction = (
                    f"{system_instruction_base}\n\n"
                    f"🎯 당신의 역할: 서연 (CSO, Chief Strategy Officer)\n"
                    f"🎯 전문 분야: 전략 기획 · 법률 전략\n"
                    f"🎯 톤: 전략적이고 체계적이며, 큰 그림을 그려주는 스타일\n\n"
                    f"반드시 [서연 (CSO) 전략 분석]으로 시작하세요."
                )
            elif clevel_id == "CTO":
                # 지유(CTO) 전용
                system_instruction = (
                    f"{system_instruction_base}\n\n"
                    f"🎯 당신의 역할: 지유 (CTO, Chief Technology Officer)\n"
                    f"🎯 전문 분야: 기술 검증 · AI 무결성\n"
                    f"🎯 톤: 정확하고 논리적이며, 기술적 관점을 제공하는 스타일\n\n"
                    f"반드시 [지유 (CTO) 기술 분석]으로 시작하세요."
                )
            else:
                # 일반 리더: 기존 로직
                system_instruction = (
                    f"{system_instruction_base}\n\n"
                    f"🎯 당신의 역할: {leader_name} ({leader_role})\n"
                    f"🎯 전문 분야: {leader_specialty}\n"
                    f"🎯 관점: {leader_specialty} 전문가 관점에서 이 사안을 분석하세요.\n\n"
                    f"특히 다음에 집중하세요:\n"
                    f"1. {leader_specialty} 관련 법령 및 규정\n"
                    f"2. {leader_specialty} 관련 판례 및 해석례\n"
                    f"3. {leader_specialty} 관점에서의 쟁점 및 위험\n"
                    f"4. {leader_specialty} 관련 절차 및 대응 방안\n\n"
                    f"반드시 [{leader_name} ({leader_specialty}) 분석]으로 시작하세요."
                )

            # 분석 실행 (Function Calling 활성화)
            logger.info(f"🔄 {leader_name} ({leader_specialty}) 분석 시작...")

            gc = self.genai_client
            chat = gc.chats.create(
                model=model_name,
                config=genai_types.GenerateContentConfig(
                    tools=tools or [],
                    system_instruction=system_instruction,
                    max_output_tokens=4096,
                    automatic_function_calling=genai_types.AutomaticFunctionCallingConfig(disable=False),
                ),
            )
            response = chat.send_message(query)

            # 응답 텍스트 추출
            try:
                analysis_text = response.text
            except ValueError as e:
                # function_call이 포함되어 text 변환 실패 시
                logger.warning(f"⚠️ {leader_name} response.text 추출 실패: {e}")
                # 채팅 히스토리에서 마지막 텍스트 응답 찾기
                analysis_text = ""
                for part in response.parts:
                    if hasattr(part, 'text') and part.text:
                        analysis_text += part.text

                if not analysis_text:
                    analysis_text = f"[{leader_specialty} 분석 결과를 텍스트로 변환하지 못했습니다]"

            # 응답이 너무 짧으면 1회 재시도
            if len(analysis_text.strip()) < 50:
                logger.warning(f"⚠️ {leader_name} 응답 너무 짧음 ({len(analysis_text)}자), 재시도...")
                retry_response = chat.send_message(
                    f"이전 응답이 너무 짧습니다. 다음 질문에 대해 상세하게 분석해주세요:\n{query}"
                )
                try:
                    retry_text = retry_response.text
                except ValueError:
                    retry_text = ""
                    for part in retry_response.parts:
                        if hasattr(part, 'text') and part.text:
                            retry_text += part.text
                if len(retry_text.strip()) > len(analysis_text.strip()):
                    analysis_text = retry_text
                    logger.info(f"✅ {leader_name} 재시도 성공 ({len(analysis_text)} chars)")

            logger.info(f"✅ {leader_name} 분석 완료 ({len(analysis_text)} chars)")

            # chat.history에서 tool 호출 메타데이터 수집
            tools_used = []
            tool_results = []
            try:
                if hasattr(chat, 'history'):
                    for turn in chat.history:
                        if hasattr(turn, 'parts'):
                            for part in turn.parts:
                                if hasattr(part, 'function_call') and part.function_call:
                                    fc = part.function_call
                                    tools_used.append({
                                        "name": fc.name,
                                        "args": dict(fc.args) if fc.args else {}
                                    })
                                if hasattr(part, 'function_response') and part.function_response:
                                    fr = part.function_response
                                    response_data = dict(fr.response) if fr.response else {}
                                    tool_results.append(response_data)
            except Exception as te:
                logger.warning(f"⚠️ {leader_name} tool 메타데이터 수집 실패 (무시): {te}")

            return {
                "leader": leader_name,
                "specialty": leader_specialty,
                "role": leader_role,
                "analysis": analysis_text,
                "success": True,
                "tools_used": tools_used,
                "tool_results": tool_results
            }

        except Exception as e:
            logger.error(f"❌ {leader_name} 분석 실패: {e}")
            return {
                "leader": leader_name,
                "specialty": leader_specialty,
                "role": leader_role,
                "analysis": f"[{leader_specialty} 분석 실패: {str(e)}]",
                "success": False
            }

    def parallel_swarm_analysis(
        self,
        query: str,
        selected_leaders: List[Dict],
        tools: List = None,
        system_instruction_base: str = "",
        model_name: str = "gemini-3-flash-preview"
    ) -> List[Dict]:
        """
        여러 Leader로 병렬 분석 실행

        Returns:
            List[Dict] - 각 Leader의 분석 결과
        """
        results = []

        # 병렬 실행
        with ThreadPoolExecutor(max_workers=len(selected_leaders)) as executor:
            future_to_leader = {
                executor.submit(
                    self.analyze_with_leader,
                    leader,
                    query,
                    tools,
                    system_instruction_base,
                    model_name
                ): leader for leader in selected_leaders
            }

            for future in as_completed(future_to_leader):
                leader = future_to_leader[future]
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    logger.error(f"❌ {leader.get('name', '?')} 병렬 실행 오류: {e}")
                    results.append({
                        "leader": leader.get("name", "Unknown"),
                        "specialty": leader.get("specialty", "Unknown"),
                        "analysis": f"[실행 오류: {str(e)}]",
                        "success": False
                    })

        # 원래 순서 복원 (specialty 순서 유지)
        results_map = {r["leader"]: r for r in results}
        ordered_results = [results_map.get(l["name"], results_map[l["name"]]) for l in selected_leaders if l["name"] in results_map]

        return ordered_results

    def synthesize_swarm_results(
        self,
        query: str,
        swarm_results: List[Dict],
        model_name: str = "gemini-3-flash-preview"
    ) -> str:
        """
        여러 Leader의 분석 결과를 통합하여 최종 판단 흐름 생성

        Args:
            query: 원본 질문
            swarm_results: 각 Leader의 분석 결과

        Returns:
            str: 통합된 최종 응답
        """
        # 성공한 분석만 필터링
        successful_analyses = [r for r in swarm_results if r.get("success", False)]

        if not successful_analyses:
            logger.warning("⚠️ 모든 Leader 분석 실패 - Fallback 응답 생성")
            return self._fallback_response(query)

        # 통합 프롬프트 생성
        synthesis_prompt = f"""
당신은 Lawmadi OS의 유나 (CCO, Chief Content Officer)입니다.
여러 전문 분야 리더들이 분석한 결과를 따뜻하고 이해하기 쉽게 통합하여 최종 판단 흐름을 생성하세요.
사용자의 불안에 공감하고, 구체적인 행동으로 바꿔주는 톤을 유지하세요.

[사용자 질문]
{query}

[전문 리더 분석 결과]
"""

        for idx, result in enumerate(successful_analyses, 1):
            synthesis_prompt += f"\n[{idx}. {result['leader']} ({result['specialty']})]\n"
            synthesis_prompt += result['analysis']
            synthesis_prompt += "\n"

        # 참여 리더 목록 생성
        leader_names = [f"{a['leader']} ({a['specialty']})" for a in successful_analyses]
        leader_list_str = ", ".join(leader_names)

        synthesis_prompt += f"""

[통합 지침]
1. 모든 전문 리더의 분석을 고려하여 종합적인 답변을 작성하세요
2. 반드시 아래 헤더로 시작하세요:
   [유나 (CCO) 종합 판단]
   참여 전문가: {leader_list_str}

3. 반드시 다음 5단계 계층 구조를 유지하세요:

   1. 핵심 요약
      1.1 상황 진단 — 공감과 현황 파악
      1.2 결론 및 전략 방향 — 서연 CSO의 법률 전략 관점을 최우선으로 반영

   2. 법률 근거 분석
      — 리더별로 배지형 구분 사용:
      👤 [리더명] 리더 ([전문분야] 전문)
      2.1, 2.2... 순서로 분야별 법률 근거 정리
      ⚠️ 법률 전략 관련 내용은 서연(CSO)의 분석을 가장 먼저 배치하세요

   3. 시간축 전략
      3.1 과거 (상황 정리)
      3.2 현재 (골든타임) — 시효/기한 강조
      3.3 미래 (대응 시나리오)

   4. 실행 계획
      4.1 즉시 조치 (24시간 내)
      4.2 단계별 가이드
      4.3 체크리스트 — □ 기호로 확인 항목 나열

   5. 추가 정보
      5.1 무료 법률 지원 (기관명 + 전화번호)
      5.2 관련 법령 요약

4. 여러 전문 분야가 교차하는 복합 사안임을 명시하세요
5. 전문가 간 의견이 다를 경우 양측 관점을 모두 제시하세요
6. 마무리에 재질문 유도 + 간결한 면책 포함

🚨 **CRITICAL**: 절대로 마크다운 표(table) 형식을 사용하지 마세요!
❌ 금지: | 구분 | 내용 | 형식
✅ 사용: • **항목** - 설명 형식 또는 번호 목록

[응답 형식]
반드시 "[유나 (CCO) 종합 판단]"으로 시작하세요.
"""

        try:
            # 통합 모델 실행
            logger.info(f"🔄 통합 분석 시작 ({len(successful_analyses)}개 리더 결과 통합)...")

            gc = self.genai_client
            response = gc.models.generate_content(
                model=model_name,
                contents=synthesis_prompt,
                config=genai_types.GenerateContentConfig(
                    temperature=0.3,
                    top_p=0.95,
                    max_output_tokens=4096,
                ),
            )
            final_response = response.text

            logger.info(f"✅ 통합 분석 완료 ({len(final_response)} chars)")

            return final_response

        except Exception as e:
            logger.error(f"❌ 통합 분석 실패: {e}")
            return self._fallback_response_with_analyses(query, successful_analyses)

    def _fallback_response(self, query: str) -> str:
        """Fallback 응답 생성"""
        return f"""[유나 (CCO) 종합 판단]

1. 핵심 요약
   1.1 상황 진단
   분석 중 시스템 오류가 발생하여 일부 기능이 제한되었습니다.

   1.2 결론 및 전략 방향
   아래 지원 기관을 통해 직접 상담을 받으시길 권장합니다.

2. 법률 근거 분석
   현재 법률 데이터 검색이 제한되어 있습니다.
   질문: {query[:100]}...

3. 시간축 전략
   3.1 현재 (골든타임)
   • 아래 무료 상담 기관에 즉시 연락하세요.

4. 실행 계획
   4.1 즉시 조치
   • 대한법률구조공단 ☎ 132 — 무료 법률 상담
   • 관할 법원/기관에 문의

   4.3 체크리스트
   □ 관련 서류 정리
   □ 상담 기관 연락

5. 추가 정보
   5.1 무료 법률 지원
   • 대한법률구조공단 ☎ 132 (klac.or.kr)
   • 국민권익위원회 ☎ 110 (epeople.go.kr)

> ℹ️ 본 시스템은 법률 자문이 아닌 정보 제공 시스템입니다.
"""

    def _fallback_response_with_analyses(self, query: str, analyses: List[Dict]) -> str:
        """분석 결과 포함 Fallback 응답"""
        leader_names = [f"{a['leader']} ({a['specialty']})" for a in analyses]
        leader_list_str = ", ".join(leader_names)

        response = "[유나 (CCO) 종합 판단]\n\n"
        response += f"참여 전문가: {leader_list_str}\n\n"

        response += "1. 핵심 요약\n"
        response += f"   1.1 상황 진단\n"
        response += f"   본 사안은 {', '.join([a['specialty'] for a in analyses])} 등 복합 법률 영역에 관한 질문입니다.\n\n"

        response += "2. 법률 근거 분석\n\n"
        for idx, analysis in enumerate(analyses, 1):
            response += f"   👤 {analysis['leader']} 리더 ({analysis['specialty']} 전문)\n\n"
            response += f"   2.{idx} {analysis['specialty']} 검토\n"
            response += analysis['analysis']
            response += "\n\n"

        response += "5. 추가 정보\n"
        response += "   5.1 무료 법률 지원\n"
        response += "   • 대한법률구조공단 ☎ 132 (klac.or.kr)\n"
        response += "   • 국민권익위원회 ☎ 110 (epeople.go.kr)\n\n"
        response += "여러 전문 분야의 분석이 제공되었습니다. 종합적인 판단을 위해 전문가 상담을 권장합니다.\n"

        return response

    def orchestrate(
        self,
        query: str,
        tools: List = None,
        system_instruction_base: str = "",
        model_name: str = "gemini-3-flash-preview",
        force_single: bool = False
    ) -> Dict:
        """
        Swarm 전체 오케스트레이션

        Args:
            query: 사용자 질문
            tools: Function calling tools
            system_instruction_base: 기본 시스템 지시
            model_name: Gemini 모델명
            force_single: True면 단일 리더만 사용 (테스트용)

        Returns:
            Dict: {
                "response": str,
                "leaders": List[str],
                "domains": List[str],
                "swarm_mode": bool
            }
        """
        # 1. 도메인 탐지
        detected_domains = self.detect_domains(query)

        # 2. Leader 선택
        selected_leaders = self.select_leaders(query, detected_domains)

        # 3. 단일 vs 다중 모드 결정
        use_swarm = (
            self.swarm_enabled
            and not force_single
            and len(selected_leaders) > 1
        )

        if not use_swarm:
            # 단일 리더 모드
            logger.info(f"🔄 단일 리더 모드: {selected_leaders[0]['name']}")
            result = self.analyze_with_leader(
                selected_leaders[0],
                query,
                tools,
                system_instruction_base,
                model_name
            )

            return {
                "response": result["analysis"],
                "leaders": [result["leader"]],
                "domains": [result["specialty"]],
                "swarm_mode": False,
                "leader_count": 1,
                "tools_used": result.get("tools_used", []),
                "tool_results": result.get("tool_results", [])
            }

        # 4. Swarm 모드: 병렬 분석
        logger.info(f"🔄 Swarm 모드: {len(selected_leaders)}명 리더 병렬 분석")
        swarm_results = self.parallel_swarm_analysis(
            query,
            selected_leaders,
            tools,
            system_instruction_base,
            model_name
        )

        # 5. 결과 통합 (성공한 리더가 1명뿐이면 synthesis 스킵 → ~8초 절약)
        successful = [r for r in swarm_results if r.get("success", False)]

        if len(successful) == 1:
            logger.info(f"⚡ 성공 리더 1명 — synthesis 스킵 ({successful[0]['leader']})")
            final_response = successful[0]["analysis"]
        else:
            final_response = self.synthesize_swarm_results(
                query,
                swarm_results,
                model_name
            )

        # 모든 리더의 tool 메타데이터 합산
        all_tools_used = []
        all_tool_results = []
        for r in swarm_results:
            all_tools_used.extend(r.get("tools_used", []))
            all_tool_results.extend(r.get("tool_results", []))

        return {
            "response": final_response,
            "leaders": [r["leader"] for r in swarm_results],
            "domains": [r["specialty"] for r in swarm_results],
            "swarm_mode": len(successful) > 1,
            "leader_count": len(swarm_results),
            "detailed_results": swarm_results,
            "tools_used": all_tools_used,
            "tool_results": all_tool_results
        }

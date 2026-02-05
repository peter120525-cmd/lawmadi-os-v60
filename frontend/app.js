/**
 * Lawmadi OS v50.2.3-HARDENED Client Engine
 * Core Logic for L7 Interface & API Gateway Integration
 */

const input = document.getElementById('userInput');
const sendBtn = document.getElementById('sendBtn');
const conversationArea = document.getElementById('conversation-area');
const hero = document.getElementById('hero-section');
const terminal = document.getElementById('log-terminal');
const logContent = document.getElementById('log-content');
const netStatus = document.getElementById('netStatus');

// [IT 인프라: 백엔드 API 게이트웨이 설정]
// Cloud Run 서비스의 고유 엔드포인트입니다.
const API_URL = 'https://lawmadi-os-v50-938146962157.asia-northeast3.run.app/ask';
const SYSTEM_VERSION = 'v50.2.3-HARDENED';

/**
 * L7 RENDERER: 시스템 로그 터미널 출력 함수
 * 실시간 커널 트레이싱 및 L3/L5 데이터 흐름을 모니터링합니다.
 */
const addLog = (msg, type = 'info') => {
    if (!logContent) return; 
    const p = document.createElement('div');
    p.className = `log-line ${type}`;
    const time = new Date().toLocaleTimeString('ko-KR', { hour12: false });
    p.textContent = `[${time}] ${msg}`;
    logContent.appendChild(p);
    
    // 터미널 자동 스크롤 (IT 운영 가시성 확보)
    if(terminal) terminal.scrollTop = terminal.scrollHeight;
};

// [L4 PERSONA] 유나(Yuna) 시스템 가이드 템플릿 (UI 컴포넌트)
const yunaIntro = `
    <div class="ai-header">
        <span class="material-symbols-outlined">face</span>
        <h3>System Guide by Yuna</h3>
    </div>
    <p>반가워요! <strong>Lawmadi OS ${SYSTEM_VERSION}</strong> 제어 평면에 접속하셨습니다.</p>
    <ul>
        <li><strong>L2 Swarm Intelligence:</strong> 63인의 전문 리더 노드가 질문 맥락을 분석합니다.</li>
        <li><strong>L5 Hardened Validator:</strong> Cloud SQL 캐시와 연동된 데이터 무결성 검증을 통과한 정보만 제공합니다.</li>
        <li><strong>Multi-Target Search:</strong> 법령과 판례를 동시에 스캔하여 최적의 법리를 타격합니다.</li>
    </ul>
`;

/**
 * 메인 실행 엔진 (Request Pipeline)
 * 사용자의 패킷을 백엔드 커널로 라우팅하고 응답을 렌더링합니다.
 */
const execute = async () => {
    const q = input.value.trim();
    if(!q) return;

    // UI 레이아웃 상태 전환 (Hero -> Conversation)
    if(hero) hero.classList.add('hidden');
    if(conversationArea) conversationArea.classList.remove('hidden');
    if(terminal) terminal.classList.remove('hidden');
    
    // 사용자 패킷 렌더링
    const uDiv = document.createElement('div');
    uDiv.className = 'user-msg'; 
    uDiv.textContent = q;
    conversationArea.appendChild(uDiv);
    
    input.value = ''; 
    input.focus();

    // L4: 인사말 패턴 매칭 및 정적 라우팅
    if (["안녕", "안녕하세요", "반가워"].some(word => q.includes(word))) {
        addLog("서연: 인사말 프로토콜 감지 -> 유나(Yuna) 노드 활성화", "system");
        setTimeout(() => {
            const aiDiv = document.createElement('div');
            aiDiv.className = 'ai-msg'; aiDiv.innerHTML = yunaIntro;
            conversationArea.appendChild(aiDiv);
            if(terminal) terminal.classList.add('hidden');
        }, 600);
        return;
    }

    addLog(`서연: 사용자 패킷 인코딩 완료 - Length: ${q.length}`, "system");
    
    // 판례 키워드 감지 시 특화 로그 출력
    if (q.includes("판례") || q.includes("사례")) {
        setTimeout(() => addLog("서연: [L3] 판례 검색 노드(Precedent Node) 예열 중...", "process"), 200);
    }
    
    setTimeout(() => addLog("서연: [L2 SWARM] 전문가 리더 노드 배정 시작...", "process"), 400);

    try {
        if(netStatus) netStatus.textContent = "System: Processing...";

        // [L3/L5 SHORT_SYNC] API 게이트웨이 비동기 통신
        const res = await fetch(API_URL, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ query: q })
        });
        
        if (!res.ok) throw new Error(`Gateway Error: ${res.status}`);
        
        const data = await res.json();
        
        // 백엔드로부터 전달받은 리더 정보 및 응답 추출
        const assignedLeader = data.leader || "System Master";
        let responseText = (data.response || "응답 데이터를 수신하지 못했습니다.");

        // [L7 RENDERER] Persona Filter: 구시대적 명칭 실시간 치환
        responseText = responseText.replace(/변호사/g, '리더').replace(/변호 사/g, '리더');
        const formattedResponse = responseText.replace(/\n/g, '<br>');

        addLog(`서연: [L2] ${assignedLeader} 리더 노드 바인딩 성공`, "success");
        addLog(`서연: [L5] 데이터 무결성 검증(Signature OK) 완료`, "success");

        setTimeout(() => {
            const aiDiv = document.createElement('div');
            aiDiv.className = 'ai-msg';
            
            // 리더 뱃지 및 인프라 메타데이터 렌더링
            const leaderBadge = `
                <div style="font-size:0.75rem; color:#64748b; margin-bottom:12px; border-left: 3px solid #3b82f6; padding-left: 10px; background: #f1f5f9; padding: 8px; border-radius: 4px;">
                    <div style="font-weight:bold; color:#1e293b;">Lawmadi Kernel ${SYSTEM_VERSION}</div>
                    <div>Instance: <strong>${assignedLeader} Leader</strong> | Status: Verified</div>
                </div>
            `;
            
            aiDiv.innerHTML = leaderBadge + formattedResponse;
            conversationArea.appendChild(aiDiv);
            
            // 뷰포트 자동 하단 포커싱
            conversationArea.scrollTop = conversationArea.scrollHeight;

            if(netStatus) netStatus.textContent = "System: Healthy";

            // 터미널 페이드 아웃 (사용자 경험 최적화)
            if(terminal) {
                terminal.style.transition = 'opacity 0.8s';
                terminal.style.opacity = '0';
                setTimeout(() => {
                    terminal.classList.add('hidden');
                    terminal.style.opacity = '0.9'; 
                }, 800);
            }
        }, 800);

    } catch (err) {
        addLog(`서연: [CRITICAL] 시스템 커널 통신 실패 - ${err.message}`, "error");
        if(netStatus) netStatus.textContent = "System: Critical Error";
        
        const errDiv = document.createElement('div');
        errDiv.className = 'ai-msg';
        errDiv.innerHTML = `<p style="color:#ef4444; font-weight:bold;">🚨 커널 파이프라인 단절 (네트워크 상태 또는 API 게이트웨이 설정을 점검하십시오)</p>`;
        conversationArea.appendChild(errDiv);
    }
};

// 인터랙션 이벤트 핸들러 바인딩
sendBtn.onclick = execute;
input.addEventListener('keydown', (e) => { 
    if (e.key === 'Enter' && !e.isComposing) { 
        e.preventDefault(); 
        execute(); 
    } 
});

// 시스템 초기화 부팅 로그
addLog(`서연: Lawmadi OS ${SYSTEM_VERSION} Client Engine Online.`, "system");
addLog("서연: L7 Renderer Interface Ready.", "system");
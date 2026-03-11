// XSS sanitizer helper — all API responses pass through this
function _sanitize(html) { if (typeof DOMPurify !== 'undefined') return DOMPurify.sanitize(html, {ADD_ATTR: ['target','data-tooltip']}); var d = document.createElement('div'); d.textContent = html; return d.innerHTML; }

// Mobile & In-app browser viewport fix (모바일 전체 + 인앱 브라우저)
(function() {
    var ua = navigator.userAgent || '';
    var isInApp = /KAKAOTALK|FBAN|FBAV|Instagram|Line\/|NAVER|Snapchat|Twitter|SamsungBrowser|Whale|DaumApps|MicroMessenger|Telegram/i.test(ua);
    var isMobile = /Android|iPhone|iPad|iPod/i.test(ua) || window.innerWidth <= 768;

    if (isInApp) document.body.classList.add('is-inapp-browser');

    if (isInApp || isMobile) {
        // visualViewport 우선, 없으면 innerHeight 폴백
        function setAppHeight() {
            var h = window.visualViewport ? window.visualViewport.height : window.innerHeight;
            document.documentElement.style.setProperty('--app-height', h + 'px');
            document.body.style.height = h + 'px';
        }
        setAppHeight();
        window.addEventListener('resize', setAppHeight);
        window.addEventListener('orientationchange', function() {
            setTimeout(setAppHeight, 150);
        });

        // Virtual keyboard detection & auto-scroll
        if (window.visualViewport) {
            var baseHeight = window.innerHeight;
            window.visualViewport.addEventListener('resize', function() {
                setAppHeight();
                var kbOpen = window.visualViewport.height < baseHeight * 0.75;
                document.body.classList.toggle('keyboard-open', kbOpen);
                if (kbOpen) {
                    var cv = document.querySelector('.conversation-viewport');
                    if (cv) cv.scrollTop = cv.scrollHeight;
                }
            });
        }
    }
})();

    // 리더/C-Level 프로필 이미지 매핑 (이름 → 경로)
    const leaderProfileImages = {
        '휘율': 'images/leaders/L01-hwiyul.jpg',
        '보늬': 'images/leaders/L02-bonui.jpg',
        '담슬': 'images/leaders/L03-damseul.jpg',
        '아키': 'images/leaders/L04-aki.jpg',
        '연우': 'images/leaders/L05-yeonwoo.jpg',
        '벼리': 'images/leaders/L06-byeori.jpg',
        '하늬': 'images/leaders/L07-hanui.jpg',
        '온유': 'images/leaders/L08-onyu.jpg',
        '한울': 'images/leaders/L09-hanul.jpg',
        '결휘': 'images/leaders/L10-gyeolhwi.jpg',
        '오름': 'images/leaders/L11-oreum.jpg',
        '아슬': 'images/leaders/L12-aseul.jpg',
        '누리': 'images/leaders/L13-nuri.jpg',
        '다솜': 'images/leaders/L14-dasom.jpg',
        '별하': 'images/leaders/L15-byeolha.jpg',
        '슬아': 'images/leaders/L16-seula.jpg',
        '미르': 'images/leaders/L17-mir.jpg',
        '다온': 'images/leaders/L18-daon.jpg',
        '슬옹': 'images/leaders/L19-selong.jpg',
        '찬솔': 'images/leaders/L20-chansol.jpg',
        '휘윤': 'images/leaders/L21-sebin.jpg',
        '무결': 'images/leaders/L22-gaon.jpg',
        '가비': 'images/leaders/L23-seoun.jpg',
        '도울': 'images/leaders/L24-doul.jpg',
        '강무': 'images/leaders/L25-damwoo.jpg',
        '루다': 'images/leaders/L26-jinu.jpg',
        '수림': 'images/leaders/L27-ruda.jpg',
        '해슬': 'images/leaders/L28-haeseul.jpg',
        '라온': 'images/leaders/L29-raon.jpg',
        '담우': 'images/leaders/L30-damwoo.jpg',
        '로운': 'images/leaders/L31-roun.jpg',
        '바름': 'images/leaders/L32-bareum.jpg',
        '별이': 'images/leaders/L33-byeoli.jpg',
        '지누': 'images/leaders/L34-jinu.jpg',
        '마루': 'images/leaders/L35-maru.jpg',
        '단아': 'images/leaders/L36-dana.jpg',
        '예솔': 'images/leaders/L37-yesol.jpg',
        '슬비': 'images/leaders/L38-seulbi.jpg',
        '가온': 'images/leaders/L39-gaon.jpg',
        '한결': 'images/leaders/L40-hangyeol.jpg',
        '산들': 'images/leaders/L41-sandeul.jpg',
        '하람': 'images/leaders/L42-haram.jpg',
        '해나': 'images/leaders/L43-haena.jpg',
        '보람': 'images/leaders/L44-boram.jpg',
        '이룸': 'images/leaders/L45-ireum.jpg',
        '다올': 'images/leaders/L46-daol.jpg',
        '새론': 'images/leaders/L47-saeron.jpg',
        '나래': 'images/leaders/L48-narae.jpg',
        '가람': 'images/leaders/L49-garam.jpg',
        '빛나': 'images/leaders/L50-bitna.jpg',
        '소울': 'images/leaders/L51-soul.jpg',
        '미소': 'images/leaders/L52-miso.jpg',
        '늘솔': 'images/leaders/L53-neulsol.jpg',
        '이서': 'images/leaders/L54-iseo.jpg',
        '윤빛': 'images/leaders/L55-yunbit.jpg',
        '다인': 'images/leaders/L56-dain.jpg',
        '세움': 'images/leaders/L57-seum.jpg',
        '예온': 'images/leaders/L58-yeon.jpg',
        '한빛': 'images/leaders/L59-hanbit.jpg',
        '마디': 'images/leaders/L60-madi.jpg',
        '서연': 'images/clevel/cso-seoyeon.jpg',
        '지유': 'images/clevel/cto-jiyu.jpg',
        '유나': 'images/clevel/cco-yuna.jpg',
    };

    // 리더별 전문분야 매핑
    const leaderSpecialties = {
        '휘율': '민사법', '보늬': '부동산법', '담슬': '건설법', '아키': '재개발·재건축',
        '연우': '의료법', '벼리': '손해배상', '하늬': '교통사고', '온유': '임대차',
        '한울': '국가계약', '결휘': '민사집행', '오름': '채권추심', '아슬': '등기·경매',
        '누리': '상사법', '다솜': '회사법·M&A', '별하': '스타트업', '슬아': '보험',
        '미르': '국제거래', '다온': '에너지·자원', '슬옹': '해상·항공', '찬솔': '조세·금융',
        '휘윤': 'IT·보안', '무결': '형사법', '가비': '엔터테인먼트', '도울': '조세불복',
        '강무': '군형법', '루다': '지식재산권', '수림': '환경법', '해슬': '무역·관세',
        '라온': '게임·콘텐츠', '담우': '노동법', '로운': '행정법', '바름': '공정거래',
        '별이': '우주항공', '지누': '개인정보', '마루': '헌법', '단아': '문화·종교',
        '예솔': '소년법', '슬비': '소비자', '가온': '정보통신', '한결': '인권',
        '산들': '이혼·가족', '하람': '저작권', '해나': '산업재해', '보람': '사회복지',
        '이룸': '교육·청소년', '다올': '보험·연금', '새론': '벤처·신산업', '나래': '문화예술',
        '가람': '식품·보건', '빛나': '다문화·이주', '소울': '종교·전통', '미소': '광고·언론',
        '늘솔': '농림·축산', '이서': '해양·수산', '윤빛': '과학기술', '다인': '장애인·복지',
        '세움': '상속·신탁', '예온': '스포츠·레저', '한빛': '데이터·AI윤리', '마디': '시스템 총괄',
        '서연': '전략 기획', '지유': '기술 검증', '유나': '콘텐츠 설계',
    };

    const _el = (id) => document.getElementById(id);
    const UI = {
        sidebar: _el('sidebar'),
        overlay: _el('overlay'),
        menuToggle: _el('menuToggle'),
        userInput: _el('userInput'),
        sendBtn: _el('sendBtn'),
        startChatBtn: _el('startChatBtn'),
        landingContent: _el('landing-content'),
        convArea: _el('conversation-area'),
        uploadBtn: _el('uploadBtn'),
        fileInput: _el('fileInput'),
        uploadedFilePreview: _el('uploadedFilePreview'),
        uploadedFileName: _el('uploadedFileName'),
        uploadedFileSize: _el('uploadedFileSize'),
        removeFileBtn: _el('removeFileBtn'),
        favoritesPanel: _el('favoritesPanel'),
        favoritesList: _el('favoritesList'),
        scrollBottomBtn: _el('scrollBottomBtn'),
        charCounter: _el('charCounter'),
        newChatBtn: _el('newChatBtn'),
        API_URL: '/ask',
        STREAM_URL: '/ask-stream',
        BASE_URL: '',
        USE_STREAMING: true,
        USE_TYPING_EFFECT: false,
        uploadedFile: null,
        conversationHistory: [],
        lastQuery: null,
        lastRawResponse: null,
        darkMode: false,
        MAX_RETRY: 2,
        DAILY_FREE: 2,
        _getQueryCount() { try { var d=new Date(),k='lq_'+d.getFullYear()+(d.getMonth()+1)+d.getDate(); return parseInt(sessionStorage.getItem(k)||'0',10); } catch(e){return 0;} },
        _incQueryCount() { try { var d=new Date(),k='lq_'+d.getFullYear()+(d.getMonth()+1)+d.getDate(); sessionStorage.setItem(k,String(this._getQueryCount()+1)); } catch(e){} },
        currentAbortController: null,  // AbortController (항목 #12)
        currentLeader: null,  // {name, specialty} — 현재 담당 리더
        isFirstQuestion: true,  // 첫 질문 여부

        init() {
            // 필수 DOM 요소 존재 확인
            if (!this.convArea || !this.userInput || !this.sendBtn) {
                console.error('[Lawmadi] 필수 DOM 요소 누락 — 페이지 구조를 확인하세요.');
                return;
            }
            this.menuToggle.onclick = (e) => {
                e.stopPropagation();
                const isMobile = window.innerWidth <= 768;
                if (isMobile) {
                    this.toggleSidebar(!this.sidebar.classList.contains('active'));
                } else {
                    this.sidebar.classList.toggle('collapsed');
                }
            };
            this.overlay.onclick = () => this.toggleSidebar(false);

            this.userInput.addEventListener('input', () => {
                this.userInput.style.height = 'auto';
                this.userInput.style.height = this.userInput.scrollHeight + 'px';
                // 글자 수 카운터 업데이트
                this.updateCharCounter();
                // 전송 버튼 상태 업데이트
                this.updateSendBtnState();
            });

            this._isSending = false;
            this.sendBtn.onclick = () => this.dispatchPacket();
            this.userInput.onkeydown = (e) => {
                if(e.key === 'Enter' && !e.shiftKey && !e.isComposing) {
                    e.preventDefault();
                    this.dispatchPacket();
                }
            };

            this.startChatBtn.onclick = () => this.switchToChatMode();

            document.querySelectorAll('.example-card').forEach(card => {
                const handler = () => {
                    const question = card.getAttribute('data-question');
                    this.userInput.value = question;
                    this.switchToChatMode();
                    this.dispatchPacket();
                };
                card.onclick = handler;
                card.onkeydown = (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); handler(); } };
            });

            // C-Level 임원 클릭/키보드 → 해당 임원에게 인사 질문 전송
            document.querySelectorAll('.clevel-card').forEach(card => {
                const handler = () => {
                    const name = card.getAttribute('data-clevel');
                    this.userInput.value = `${name}아, 안녕하세요. 자기소개 부탁드려요.`;
                    this.switchToChatMode();
                    this.dispatchPacket();
                };
                card.onclick = handler;
                card.onkeydown = (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); handler(); } };
            });

            this.initVisitorTracking();

            // v60: 파일 업로드 (서비스 예정)
            this.uploadBtn.onclick = () => this.showUploadComingSoon();
            this.fileInput.onchange = (e) => this.handleFileSelect(e);
            this.removeFileBtn.onclick = () => this.clearUploadedFile();

            // 다크모드 초기화 (기본값: 다크모드 ON)
            const darkToggle = document.getElementById('darkToggle');
            if (darkToggle) darkToggle.onclick = () => this.toggleDarkMode();
            const savedDarkMode = localStorage.getItem('lawmadi-dark-mode');
            if (savedDarkMode === 'true') {
                this.darkMode = true;
                document.body.classList.add('dark-mode');
                if (darkToggle) {
                    darkToggle.querySelector('.material-symbols-outlined').textContent = 'light_mode';
                    const label = darkToggle.querySelectorAll('span')[1];
                    if (label) label.textContent = '라이트모드';
                    darkToggle.setAttribute('aria-pressed', 'true');
                }
            }

            // 3-dot 더보기 메뉴
            const moreMenuBtn = document.getElementById('moreMenuBtn');
            const moreMenuDropdown = document.getElementById('moreMenuDropdown');
            if (moreMenuBtn && moreMenuDropdown) {
                moreMenuBtn.onclick = (e) => {
                    e.stopPropagation();
                    const open = moreMenuDropdown.style.display !== 'none';
                    moreMenuDropdown.style.display = open ? 'none' : 'block';
                    moreMenuBtn.setAttribute('aria-expanded', !open);
                };
                if (!window._lawmadiMoreMenuListenerAdded) {
                    document.addEventListener('click', (e) => {
                        if (!moreMenuDropdown.contains(e.target) && e.target !== moreMenuBtn) {
                            moreMenuDropdown.style.display = 'none';
                            moreMenuBtn.setAttribute('aria-expanded', 'false');
                        }
                    });
                    window._lawmadiMoreMenuListenerAdded = true;
                }
            }

            // 대화 이력 복원 (항목 #13)
            try {
                const saved = localStorage.getItem('lawmadi-chat-history');
                if (saved) this.conversationHistory = JSON.parse(saved);
            } catch(e) {}

            // 현재 리더 상태 복원
            try {
                const savedLeader = localStorage.getItem('lawmadi-current-leader');
                if (savedLeader) {
                    this.currentLeader = JSON.parse(savedLeader);
                    this.isFirstQuestion = false;
                }
            } catch(e) {}

            // 즐겨찾기 초기화
            const favToggle = document.getElementById('favToggle');
            if (favToggle) favToggle.onclick = () => this.toggleFavorites();

            // 새 대화 버튼
            if (this.newChatBtn) this.newChatBtn.onclick = () => this.resetConversation();

            // 스크롤 투 바텀 버튼
            if (this.scrollBottomBtn) {
                this.scrollBottomBtn.onclick = () => this._smartScroll(true);
                this._scrollHandler = () => {
                    const show = !this._isNearBottom() && !this.convArea.classList.contains('hidden');
                    this.scrollBottomBtn.classList.toggle('visible', show);
                };
                this.convArea.addEventListener('scroll', this._scrollHandler);
            }

            // retry 버튼 이벤트 위임 (CSP: inline onclick 제거)
            this.convArea.addEventListener('click', (e) => {
                const btn = e.target.closest('[data-action="retry"]');
                if (btn) UI.retryLastQuery();
            });

            // 전송 버튼 초기 상태
            this.updateSendBtnState();

            // CSP 호환 이벤트 리스너 (inline handler 대체)
            var favCloseBtn = document.getElementById('favoritesCloseBtn');
            if (favCloseBtn) favCloseBtn.addEventListener('click', () => this.toggleFavorites());
            var premiumCta = document.getElementById('premiumCta');
            if (premiumCta) premiumCta.addEventListener('click', () => alert('프리미엄 서비스 준비 중입니다. 곧 오픈 예정입니다!'));
            var lawyerCta = document.getElementById('lawyerCtaLanding');
            if (lawyerCta) lawyerCta.addEventListener('click', () => UI.openLawyerModal('', ''));
            var modalClose = document.getElementById('modalCloseBtn');
            if (modalClose) modalClose.addEventListener('click', () => this.closeLawyerModal());
            var lawyerForm = document.getElementById('lawyerForm');
            if (lawyerForm) lawyerForm.addEventListener('submit', (e) => this.submitLawyerInquiry(e));
            var successClose = document.getElementById('lawyerSuccessCloseBtn');
            if (successClose) successClose.addEventListener('click', () => this.closeLawyerModal());
            var moreOverlay = document.getElementById('moreSheetOverlay');
            if (moreOverlay) moreOverlay.addEventListener('click', function() { this.classList.remove('active'); var sheet = document.getElementById('moreSheet'); if (sheet) sheet.classList.remove('active'); });

            // Hover effects for menu toggle
            this.menuToggle.onmouseenter = () => {
                this.menuToggle.style.background = 'rgba(0,0,0,0.05)';
            };
            this.menuToggle.onmouseleave = () => {
                this.menuToggle.style.background = 'none';
            };

            // URL 파라미터로 리더 자동 질문 (leaders.html에서 카드 클릭 시)
            const urlParams = new URLSearchParams(window.location.search);
            const leaderParam = urlParams.get('leader');
            if (leaderParam) {
                history.replaceState(null, '', window.location.pathname);
                // 화이트리스트 검증: 등록된 리더 이름만 허용
                const allowedLeaders = new Set(['서연','지유','유나','휘율','보늬','담슬','아키','연우','벼리','하늬','온유','한울','결휘','오름','아슬','누리','다솜','별하','슬아','미르','다온','슬옹','찬솔','휘윤','무결','가비','도울','강무','루다','수림','해슬','라온','담우','로운','바름','별이','지누','마루','단아','예솔','슬비','가온','한결','산들','하람','해나','보람','이룸','다올','새론','나래','가람','빛나','소울','미소','늘솔','이서','윤빛','다인','세움','예온','한빛','마디']);
                if (!allowedLeaders.has(leaderParam)) return;
                const clevelTitles = { '서연': 'CSO', '지유': 'CTO', '유나': 'CCO' };
                const title = clevelTitles[leaderParam];
                const honorific = title ? `${leaderParam} ${title}님` : `${leaderParam} 리더님`;
                // 페이지 로드 완료 후 실행 (네트워크 안정화 대기)
                setTimeout(() => {
                    this.userInput.value = `${honorific}, 안녕하세요. 자기소개 부탁드려요.`;
                    this.switchToChatMode();
                    // convArea가 표시된 후 디스패치
                    setTimeout(() => this.dispatchPacket(), 400);
                }, 100);
            }
        },

        // ═══ 다크모드 ═══
        toggleDarkMode() {
            this.darkMode = !this.darkMode;
            document.body.classList.toggle('dark-mode', this.darkMode);
            try { localStorage.setItem('lawmadi-dark-mode', this.darkMode); } catch(e) {}
            const darkToggle = document.getElementById('darkToggle');
            if (darkToggle) darkToggle.setAttribute('aria-pressed', this.darkMode);
            const icon = document.querySelector('#darkToggle .material-symbols-outlined');
            if (icon) icon.textContent = this.darkMode ? 'light_mode' : 'dark_mode';
            const label = darkToggle ? darkToggle.querySelectorAll('span')[1] : null;
            if (label) label.textContent = this.darkMode ? '라이트모드' : '다크모드';
        },

        // ═══ 즐겨찾기 ═══
        toggleFavorites() {
            const panel = this.favoritesPanel;
            if (!panel) return;
            const isActive = panel.classList.toggle('active');
            if (isActive) this.renderFavorites();
        },

        // ─── 변호사 상담 모달 ───
        openLawyerModal(querySummary, leaderName) {
            const overlay = document.getElementById('lawyerModalOverlay');
            if (!overlay) return;
            overlay.classList.add('active');
            document.body.style.overflow = 'hidden';
            // Pre-fill fields
            const summaryField = document.getElementById('lawyerSummary');
            const leaderField = document.getElementById('lawyerLeader');
            if (summaryField && querySummary) summaryField.value = querySummary.substring(0, 500);
            if (leaderField && leaderName) leaderField.value = leaderName;
            // Pre-fill user info if logged in
            const user = window.__lawmadiAuth && window.__lawmadiAuth.user;
            if (user && user.email) {
                const nameField = document.getElementById('lawyerName');
                if (nameField && !nameField.value) nameField.value = user.email.split('@')[0];
            }
        },

        closeLawyerModal() {
            const overlay = document.getElementById('lawyerModalOverlay');
            if (overlay) {
                overlay.classList.remove('active');
                document.body.style.overflow = '';
            }
            // Reset to form view
            const formView = document.getElementById('lawyerFormView');
            const successView = document.getElementById('lawyerSuccessView');
            if (formView) formView.style.display = 'block';
            if (successView) successView.style.display = 'none';
        },

        async submitLawyerInquiry(e) {
            e.preventDefault();
            const name = document.getElementById('lawyerName')?.value?.trim();
            const phone = document.getElementById('lawyerPhone')?.value?.trim();
            const summary = document.getElementById('lawyerSummary')?.value?.trim();
            const leader = document.getElementById('lawyerLeader')?.value?.trim() || '';

            if (!name || !phone) {
                alert('이름과 연락처를 입력해 주세요.');
                return false;
            }
            if (!summary) {
                alert('상담 내용을 입력해 주세요.');
                return false;
            }
            // Phone validation (Korean format)
            const phoneClean = phone.replace(/[^0-9]/g, '');
            if (phoneClean.length < 10 || phoneClean.length > 11) {
                alert('올바른 전화번호를 입력해 주세요.');
                return false;
            }

            const consent = document.getElementById('lawyerPrivacyConsent');
            if (!consent || !consent.checked) {
                alert('개인정보 수집·이용에 동의해 주세요.');
                return false;
            }

            const submitBtn = document.querySelector('#lawyerFormView button[type="submit"], #lawyerFormView .lawyer-submit-btn');
            if (submitBtn) {
                submitBtn.disabled = true;
                submitBtn.textContent = '접수 중...';
            }

            try {
                const res = await fetch('/api/lawyer-inquiry', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    credentials: 'include',
                    body: JSON.stringify({ name, phone: phoneClean, query_summary: summary, leader })
                });
                if (!res.ok) throw new Error('접수 실패');

                // Switch to success view
                const formView = document.getElementById('lawyerFormView');
                const successView = document.getElementById('lawyerSuccessView');
                if (formView) formView.style.display = 'none';
                if (successView) successView.style.display = 'block';
            } catch (err) {
                alert('상담 신청 접수에 실패했습니다. 잠시 후 다시 시도해 주세요.');
                console.error('Lawyer inquiry failed:', err);
            } finally {
                if (submitBtn) {
                    submitBtn.disabled = false;
                    submitBtn.textContent = '상담 신청';
                }
            }
            return false;
        },

        saveFavorite(query, response) {
            const favs = JSON.parse(localStorage.getItem('lawmadi-favorites') || '[]');
            favs.unshift({
                id: Date.now(),
                query: query,
                response: response,
                date: new Date().toLocaleDateString('ko-KR')
            });
            if (favs.length > 50) favs.pop();
            try { localStorage.setItem('lawmadi-favorites', JSON.stringify(favs)); } catch(e) {}
        },

        deleteFavorite(id) {
            let favs = JSON.parse(localStorage.getItem('lawmadi-favorites') || '[]');
            favs = favs.filter(f => f.id !== id);
            try { localStorage.setItem('lawmadi-favorites', JSON.stringify(favs)); } catch(e) {}
            this.renderFavorites();
        },

        renderFavorites() {
            const list = this.favoritesList;
            if (!list) return;
            const favs = JSON.parse(localStorage.getItem('lawmadi-favorites') || '[]');
            if (favs.length === 0) {
                list.innerHTML = '<div class="fav-empty">저장된 답변이 없습니다.</div>';
                return;
            }
            list.innerHTML = favs.map(f => `
                <div class="fav-item" data-id="${this.escapeHtml(f.id)}">
                    <button class="fav-delete" data-fav-id="${this.escapeHtml(f.id)}" aria-label="삭제: ${this.escapeHtml(f.query).substring(0, 30)}">삭제</button>
                    <div class="fav-query">${this.escapeHtml(f.query)}</div>
                    <div class="fav-preview">${this.escapeHtml(f.response).substring(0, 100)}...</div>
                    <div class="fav-date">${this.escapeHtml(f.date || '')}</div>
                </div>
            `).join('');

            if (!list._favDeleteDelegated) {
                list.addEventListener('click', (e) => {
                    const btn = e.target.closest('.fav-delete');
                    if (btn) { e.stopPropagation(); UI.deleteFavorite(parseInt(btn.dataset.favId)); }
                });
                list._favDeleteDelegated = true;
            }

            list.querySelectorAll('.fav-item').forEach(item => {
                item.onclick = () => {
                    const fav = favs.find(f => f.id === parseInt(item.dataset.id));
                    if (fav) {
                        this.switchToChatMode();
                        this.appendMessage('user', this.escapeHtml(fav.query));
                        this.appendMessage('ai', this.formatReport(fav.response));
                        this.toggleFavorites();
                    }
                };
            });
        },

        escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text || '';
            return div.innerHTML;
        },

        handleFileSelect(event) {
            const file = event.target.files[0];
            if (!file) return;

            const maxSize = 10 * 1024 * 1024;
            if (file.size > maxSize) {
                alert(`파일 크기가 너무 큽니다. 최대 ${maxSize / 1024 / 1024}MB까지 업로드 가능합니다.`);
                return;
            }

            const allowedTypes = ['image/jpeg', 'image/jpg', 'image/png', 'image/webp', 'application/pdf'];
            if (!allowedTypes.includes(file.type)) {
                alert('지원하지 않는 파일 형식입니다. JPG, PNG, WEBP, PDF 파일만 업로드 가능합니다.');
                return;
            }

            this.uploadedFile = file;
            this.uploadedFileName.textContent = file.name;
            this.uploadedFileSize.textContent = this.formatFileSize(file.size);
            this.uploadedFilePreview.style.display = 'block';
        },

        clearUploadedFile() {
            this.uploadedFile = null;
            this.fileInput.value = '';
            this.uploadedFilePreview.style.display = 'none';
        },

        showUploadComingSoon() {
            const existing = document.getElementById('upload-coming-soon');
            if (existing) existing.remove();
            const toast = document.createElement('div');
            toast.id = 'upload-coming-soon';
            toast.style.cssText = 'position:fixed;bottom:100px;left:50%;transform:translateX(-50%);background:linear-gradient(135deg,#1A2E22,#2D4038);color:#E4EDE8;padding:16px 28px;border-radius:14px;border:1px solid rgba(109,187,143,0.4);box-shadow:0 8px 32px rgba(0,0,0,0.3);z-index:9999;display:flex;align-items:center;gap:12px;font-size:0.95rem;font-weight:600;animation:expertFadeIn 0.3s ease;max-width:90vw;';
            toast.innerHTML = '<span class="material-symbols-outlined" style="color:#6DBB8F;font-size:1.5rem;">upload_file</span><div><div>파일 업로드 — <span style="color:#B8922D;">서비스 예정</span></div><div style="font-size:0.8rem;font-weight:400;color:#7A9A88;margin-top:4px;">업로드 파일 1MB 제한 · JPG, PNG, WEBP, PDF 지원</div></div>';
            document.body.appendChild(toast);
            setTimeout(() => {
                toast.style.transition = 'opacity 0.4s';
                toast.style.opacity = '0';
                setTimeout(() => toast.remove(), 400);
            }, 3000);
        },

        formatFileSize(bytes) {
            if (bytes === 0) return '0 Bytes';
            const k = 1024;
            const sizes = ['Bytes', 'KB', 'MB'];
            const i = Math.floor(Math.log(bytes) / Math.log(k));
            return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
        },

        async initVisitorTracking() {
            try {
                await fetch(`${this.BASE_URL}/api/visit`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({})
                });
            } catch (error) {
                console.error('방문자 추적 실패:', error);
            }
            this.loadVisitorStats();
        },

        async loadVisitorStats() {
            const todayEl = document.getElementById('todayVisitors');
            const totalEl = document.getElementById('totalVisitors');
            try {
                const response = await fetch(`${this.BASE_URL}/api/visitor-stats`);
                const data = await response.json();

                if (data.ok) {
                    if (todayEl) this.animateNumber(todayEl, data.today_visitors || 0);
                    if (totalEl) this.animateNumber(totalEl, data.total_visitors || 0);
                } else {
                    if (todayEl) todayEl.textContent = '준비중';
                    if (totalEl) totalEl.textContent = '준비중';
                }
            } catch (error) {
                console.error('통계 로드 실패:', error);
                if (todayEl) todayEl.textContent = '준비중';
                if (totalEl) totalEl.textContent = '준비중';
            }
        },

        animateNumber(element, target) {
            if (target === 0) {
                element.textContent = '0';
                return;
            }
            if (this._animTimers) this._animTimers.forEach(t => clearInterval(t));
            this._animTimers = this._animTimers || [];
            let current = 0;
            const increment = target / 50;
            const timer = setInterval(() => {
                if (!element.parentNode) { clearInterval(timer); return; }
                current += increment;
                if (current >= target) {
                    element.textContent = target.toLocaleString();
                    clearInterval(timer);
                } else {
                    element.textContent = Math.floor(current).toLocaleString();
                }
            }, 20);
            this._animTimers.push(timer);
        },

        toggleSidebar(state) {
            this.sidebar.classList.toggle('active', state);
            this.overlay.classList.toggle('active', state);
            this.menuToggle.setAttribute('aria-expanded', state ? 'true' : 'false');
        },

        switchToChatMode() {
            if (!this.landingContent.classList.contains('hidden')) {
                // 랜딩 → 채팅 전환 애니메이션
                this.landingContent.classList.add('slide-out');
                setTimeout(() => {
                    this.landingContent.classList.add('hidden');
                    this.landingContent.classList.remove('slide-out');
                    this.convArea.classList.remove('hidden');
                    this.convArea.classList.add('slide-in');
                    if (window.innerWidth > 768) this.userInput.focus();
                    // 애니메이션 후 클래스 제거
                    setTimeout(() => this.convArea.classList.remove('slide-in'), 350);
                }, 300);
            } else {
                this.convArea.classList.remove('hidden');
                if (window.innerWidth > 768) this.userInput.focus();
            }
        },

        // ═══ 메인 디스패치 (대화 이력 + 에러 재시도) ═══
        async dispatchPacket(retryCount = 0) {
            if (this._isSending) return;
            const query = retryCount > 0 ? this.lastQuery : this.userInput.value.trim();
            const hasFile = this.uploadedFile !== null;

            if (!query && !hasFile) return;
            this._isSending = true;

            this.switchToChatMode();

            if (hasFile) {
                await this.handleFileUploadAndAnalysis(query);
                return;
            }

            if (retryCount === 0) {
                this.appendMessage('user', this.escapeHtml(query));
                this.userInput.value = "";
                this.userInput.style.height = 'auto';
                this.lastQuery = query;
                this.updateCharCounter();
                this.updateSendBtnState();
            }

            // AbortController: 이전 요청 취소 + 120초 타임아웃
            if (this.currentAbortController) {
                this.currentAbortController.abort();
                this.currentAbortController = null;
            }
            if (this._requestTimeoutId) {
                clearTimeout(this._requestTimeoutId);
                this._requestTimeoutId = null;
            }
            this.currentAbortController = new AbortController();
            const timeoutId = setTimeout(() => {
                if (this.currentAbortController) this.currentAbortController.abort();
            }, 120000);
            this._requestTimeoutId = timeoutId;

            const _startTime = performance.now();
            this._showSimpleWaiting();

            try {
                if (this.USE_STREAMING) {
                    await this._dispatchStreaming(query, _startTime, timeoutId);
                } else {
                    await this._dispatchClassic(query, _startTime, timeoutId);
                }

                clearTimeout(timeoutId);

                // GA4 이벤트 추적
                if (typeof gtag === 'function') {
                    gtag('event', 'query_sent', { query_length: query.length });
                }

            } catch (error) {
                clearTimeout(timeoutId);
                this._requestTimeoutId = null;
                this.hideTypingIndicator();
                // 스트리밍 중 생성된 부분 메시지 제거 (고유 ID prefix 매칭)
                document.querySelectorAll('[id^="streaming-msg-"]').forEach(el => el.remove());

                // 사용자 취소 또는 타임아웃 (AbortError)
                if (error.name === 'AbortError') {
                    // 요청이 취소되었습니다
                    return;
                }

                // 서버 에러 (event: error)는 재시도 없이 바로 표시
                if (error._serverError) {
                    this.appendMessage('ai', `
                        <div style="color: #C45454;">
                            <p><strong>${this.escapeHtml(error.message)}</strong></p>
                            <button class="retry-btn" data-action="retry">
                                <span class="material-symbols-outlined" style="font-size: 16px;">refresh</span>
                                다시 시도
                            </button>
                        </div>
                    `);
                    return;
                }

                // 네트워크 오류만 자동 재시도
                if (retryCount < this.MAX_RETRY) {
                    const waitSec = (retryCount + 1) * 2;
                    this.appendMessage('ai', `<p style="color: #B8922D;">네트워크 오류 발생. ${waitSec}초 후 자동 재시도합니다... (${retryCount + 1}/${this.MAX_RETRY})</p>`);
                    await new Promise(r => setTimeout(r, waitSec * 1000));
                    // 재시도 메시지 제거
                    const lastMsg = this.convArea.lastElementChild;
                    if (lastMsg && lastMsg.classList.contains('ai-msg')) lastMsg.remove();
                    return this.dispatchPacket(retryCount + 1);
                }

                // 최종 실패: 사용자 친화적 에러 메시지 + 재시도 버튼
                const friendlyMsg = this._friendlyError(error);
                this.appendMessage('ai', `
                    <div style="color: #C45454;">
                        <p><strong>${this.escapeHtml(friendlyMsg)}</strong></p>
                        <button class="retry-btn" data-action="retry">
                            <span class="material-symbols-outlined" style="font-size: 16px;">refresh</span>
                            다시 시도
                        </button>
                    </div>
                `);
            } finally {
                this._isSending = false;
            }
        },

        retryLastQuery() {
            if (!this.lastQuery) return;
            // 에러 메시지 제거
            const lastMsg = this.convArea.lastElementChild;
            if (lastMsg && lastMsg.classList.contains('ai-msg')) lastMsg.remove();
            this.dispatchPacket(0);
        },

        // ═══ 클래식(비스트리밍) 디스패치 ═══
        async _dispatchClassic(query, _startTime, timeoutId) {
            const response = await fetch(this.API_URL, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify({
                    query: query,
                    history: this.conversationHistory.slice(-10),
                    current_leader: this.currentLeader,
                    is_first_question: this.isFirstQuestion,
                }),
                signal: this.currentAbortController.signal
            });

            clearTimeout(timeoutId);
            if (response.status === 429) {
                this.hideTypingIndicator();
                var limitMsg = '<p>일일 무료 이용 한도에 도달했습니다.</p>'
                    + '<p style="margin-top:8px;"><a href="/pricing" style="color:#3D8B5E;font-weight:700;text-decoration:underline;">크레딧 구매</a>하시면 계속 이용 가능합니다.</p>';
                if (window.__lawmadiAuth && !window.__lawmadiAuth.authenticated) {
                    limitMsg += '<p style="margin-top:4px;font-size:0.9em;color:#5D7D6D;">이미 크레딧을 구매하셨다면 헤더의 <strong>Login</strong> 버튼으로 로그인하세요.</p>';
                }
                try {
                    const errData = await response.json();
                    if (errData.error) limitMsg = `<p>${this.escapeHtml(errData.error)}</p>`;
                } catch {}
                this.appendMessage('ai', limitMsg);
                return;
            }
            if (!response.ok) throw new Error(`서버 오류 (${response.status})`);
            const data = await response.json();

            this.hideTypingIndicator();

            // 협의/인수인계 렌더링
            if (data.deliberation) this._renderDeliberation(data.deliberation);
            if (data.handoff) this._renderHandoff(data.handoff);

            // 현재 리더 상태 업데이트
            if (data.current_leader) {
                this.currentLeader = data.current_leader;
                this.isFirstQuestion = false;
                try { localStorage.setItem('lawmadi-current-leader', JSON.stringify(data.current_leader)); } catch(e) {}
            }

            this.conversationHistory.push(
                { role: 'user', content: query },
                { role: 'assistant', content: data.response || '' }
            );
            if (this.conversationHistory.length > 20) {
                this.conversationHistory = this.conversationHistory.slice(-20);
            }
            try { localStorage.setItem('lawmadi-chat-history', JSON.stringify(this.conversationHistory)); } catch(e) {}

            this.lastRawResponse = data.response;
            const _elapsed = ((performance.now() - _startTime) / 1000).toFixed(1);
            const formattedHtml = this.formatReport(data.response);
            this.appendMessage('ai', formattedHtml, null, query, data.response, data.leader, data.leader_specialty, _elapsed);
        },

        // ═══ SSE 스트리밍 디스패치 ═══
        async _dispatchStreaming(query, _startTime, timeoutId) {
            const response = await fetch(this.STREAM_URL, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify({
                    query: query,
                    history: this.conversationHistory.slice(-10),
                    current_leader: this.currentLeader,
                    is_first_question: this.isFirstQuestion,
                }),
                signal: this.currentAbortController.signal
            });

            clearTimeout(timeoutId);
            if (response.status === 429) {
                this.hideTypingIndicator();
                var limitMsg = '<p>일일 무료 이용 한도에 도달했습니다.</p>'
                    + '<p style="margin-top:8px;"><a href="/pricing" style="color:#3D8B5E;font-weight:700;text-decoration:underline;">크레딧 구매</a>하시면 계속 이용 가능합니다.</p>';
                if (window.__lawmadiAuth && !window.__lawmadiAuth.authenticated) {
                    limitMsg += '<p style="margin-top:4px;font-size:0.9em;color:#5D7D6D;">이미 크레딧을 구매하셨다면 헤더의 <strong>Login</strong> 버튼으로 로그인하세요.</p>';
                }
                try {
                    const errData = await response.json();
                    if (errData.error) limitMsg = `<p>${this.escapeHtml(errData.error)}</p>`;
                } catch {}
                this.appendMessage('ai', limitMsg);
                return;
            }
            if (!response.ok) throw new Error(`서버 오류 (${response.status})`);

            // 회의 채팅 컨테이너 (speaking/message 이벤트용)
            this._meetingContainer = null;

            // 답변 스트리밍 컨테이너 (answer_start → answer_chunk → answer_done)
            const streamId = 'streaming-msg-' + Date.now();
            const streamDiv = document.createElement('div');
            streamDiv.className = 'ai-msg';
            streamDiv.id = streamId;
            const streamContent = document.createElement('div');
            streamContent.className = 'stream-content';
            streamDiv.appendChild(streamContent);
            let streamDivAttached = false;

            let accumulatedText = '';
            let leaderName = '';
            let leaderSpecialty = '';
            let fullTextFromServer = '';

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';

            // SSE 이벤트 파싱 헬퍼 (multi-line data 지원)
            const _parseSSE = (rawEvent) => {
                let eventType = 'message';
                const dataLines = [];
                for (const line of rawEvent.split('\n')) {
                    if (line.startsWith('event: ')) {
                        eventType = line.slice(7).trim();
                    } else if (line.startsWith('data: ')) {
                        dataLines.push(line.slice(6));
                    } else if (line.startsWith('data:')) {
                        dataLines.push(line.slice(5));
                    }
                }
                return { eventType, eventData: dataLines.join('\n') };
            };

            const _handleEvent = (eventType, payload) => {
                if (eventType === 'progress') {
                    this._updateProgress(payload);
                    return;
                }
                if (eventType === 'speaking') {
                    // 회의 컨테이너 없으면 생성
                    if (!this._meetingContainer) {
                        this._hideSimpleWaiting();
                        this._meetingContainer = document.createElement('div');
                        this._meetingContainer.className = 'chat-flow-container';
                        this.convArea.appendChild(this._meetingContainer);
                    }
                    const status = payload.status || 'typing';
                    if (status === 'entering') {
                        // "X(역할) 님이 회의에 참가했습니다" 시스템 메시지
                        this._removeChatTypingBubble(this._meetingContainer);
                        const sysMsg = document.createElement('div');
                        sysMsg.className = 'chat-flow-status';
                        sysMsg.textContent = (payload.speaker || '') + '(' + (payload.role || '') + ') 님이 회의에 참가했습니다';
                        this._meetingContainer.appendChild(sysMsg);
                        this._smartScroll(false);
                    } else if (status === 'typing') {
                        this._removeChatTypingBubble(this._meetingContainer);
                        this._appendChatTypingBubble(this._meetingContainer, payload.speaker || '', payload.role || '');
                        this._smartScroll(false);
                    }

                } else if (eventType === 'message') {
                    // 타이핑 버블 → 메시지 버블로 교체
                    if (this._meetingContainer) {
                        this._removeChatTypingBubble(this._meetingContainer);
                    } else {
                        this._hideSimpleWaiting();
                        this._meetingContainer = document.createElement('div');
                        this._meetingContainer.className = 'chat-flow-container';
                        this.convArea.appendChild(this._meetingContainer);
                    }
                    const bubble = document.createElement('div');
                    const isMod = (payload.role === 'CSO');
                    bubble.className = 'chat-msg-bubble' + (isMod ? ' moderator' : '');
                    bubble.style.opacity = '0';
                    const _avatarHtml = this._buildAvatarHTML(payload.speaker || '');
                    bubble.innerHTML = _avatarHtml + this._buildBubbleBody(payload.speaker || '', payload.role || '', payload.content || payload.text || '');
                    this._meetingContainer.appendChild(bubble);
                    requestAnimationFrame(() => { bubble.style.transition = 'opacity 0.3s'; bubble.style.opacity = '1'; });
                    this._smartScroll(false);

                } else if (eventType === 'answer_start') {
                    // 회의 완료 표시 + 답변 작성 상태
                    this._removeChatTypingBubbleAll();
                    if (this._meetingContainer) {
                        const doneStatus = document.createElement('div');
                        doneStatus.className = 'chat-flow-status';
                        doneStatus.textContent = '회의 완료';
                        this._meetingContainer.appendChild(doneStatus);
                    }
                    this._hideSimpleWaiting();
                    leaderName = payload.speaker || '';
                    leaderSpecialty = payload.role || '';
                    // "X(역할) 리더가 답변을 작성하고 있습니다" 표시
                    this._showMiniWaiting((leaderName ? leaderName + '(' + leaderSpecialty + ') ' : '') + '리더가 답변을 작성하고 있습니다');

                } else if (eventType === 'answer_chunk') {
                    accumulatedText += (payload.text || '');
                    if (!streamDivAttached) {
                        this._hideMiniWaiting();
                        this._removeChatTypingBubbleAll();
                        this.convArea.appendChild(streamDiv);
                        streamDivAttached = true;
                    }
                    streamContent.innerHTML = this._renderStreamingText(accumulatedText);
                    this._smartScroll(false);

                } else if (eventType === 'answer_done') {
                    leaderName = payload.leader || leaderName;
                    leaderSpecialty = payload.leader_specialty || payload.specialty || leaderSpecialty;
                    fullTextFromServer = payload.response || payload.full_text || accumulatedText;
                    if (payload.current_leader) {
                        this.currentLeader = payload.current_leader;
                        this.isFirstQuestion = false;
                        try { localStorage.setItem('lawmadi-current-leader', JSON.stringify(payload.current_leader)); } catch(e) {}
                    }

                } else if (eventType === 'error') {
                    this.hideTypingIndicator();
                    streamDiv.remove();
                    const serverErr = new Error(payload.message || '스트리밍 오류');
                    serverErr._serverError = true;
                    throw serverErr;
                }
            };

            try {
                while (true) {
                    const { done, value } = await reader.read();
                    if (done) break;

                    buffer += decoder.decode(value, { stream: true });
                    const events = buffer.split('\n\n');
                    buffer = events.pop() || '';

                    for (const rawEvent of events) {
                        if (!rawEvent.trim()) continue;
                        const { eventType, eventData } = _parseSSE(rawEvent);
                        if (!eventData) continue;
                        let payload;
                        try { payload = JSON.parse(eventData); } catch(e) {
                            console.warn('[SSE] JSON 파싱 실패:', eventData.slice(0, 100));
                            continue;
                        }
                        _handleEvent(eventType, payload);
                    }
                }
                // 스트림 종료 후 버퍼에 남은 이벤트 처리
                if (buffer.trim()) {
                    const { eventType, eventData } = _parseSSE(buffer);
                    if (eventData) {
                        try {
                            const payload = JSON.parse(eventData);
                            _handleEvent(eventType, payload);
                        } catch(e) { /* 무시 */ }
                    }
                }
            } catch (streamError) {
                try { reader.cancel(); } catch(e) { /* 무시 */ }
                const el = document.getElementById(streamId);
                if (el) el.remove();
                throw streamError;
            }

            // 스트리밍 완료 → 최종 포맷 렌더링
            this.hideTypingIndicator();
            const finalText = fullTextFromServer || accumulatedText;
            streamDiv.remove();

            if (!finalText.trim()) {
                throw new Error('서버에서 응답을 받지 못했습니다.');
            }

            this.conversationHistory.push(
                { role: 'user', content: query },
                { role: 'assistant', content: finalText }
            );
            if (this.conversationHistory.length > 20) {
                this.conversationHistory = this.conversationHistory.slice(-20);
            }
            try { localStorage.setItem('lawmadi-chat-history', JSON.stringify(this.conversationHistory)); } catch(e) {}

            this.lastRawResponse = finalText;
            const _elapsed = ((performance.now() - _startTime) / 1000).toFixed(1);
            const formattedHtml = this.formatReport(finalText);
            this.appendMessage('ai', formattedHtml, null, query, finalText, leaderName, leaderSpecialty, _elapsed);
        },

        // ═══ 스트리밍 텍스트 실시간 렌더링 (경량) ═══
        _renderStreamingText(text) {
            // think 블록 제거
            text = text.replace(/<think>[\s\S]*?<\/think>/g, '');
            text = text.replace(/^think\n(?:[A-Za-z*].*\n)*/gm, '');
            // ## 헤더 → 볼드
            text = text.replace(/^#{1,4}\s+(.+)$/gm, '**$1**');
            // 기본 마크다운 변환 (볼드, 줄바꿈)
            return text
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;')
                .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
                .replace(/\n/g, '<br>');
        },

        // ═══ 관련 질문 추천 로드 ═══
        async _loadSuggestions(container, query, leader, specialty) {
            try {
                const res = await fetch(`${this.BASE_URL}/suggest-questions`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ query, leader: leader || '', specialty: specialty || '' })
                });
                if (!res.ok) return;
                const data = await res.json();
                if (!data.suggestions || !data.suggestions.length) return;
                container.innerHTML = _sanitize(data.suggestions.map(q =>
                    `<button class="suggest-chip">${this.escapeHtml(q)}</button>`
                ).join(''));
                container.querySelectorAll('.suggest-chip').forEach(chip => {
                    chip.onclick = () => {
                        this.userInput.value = chip.textContent;
                        this.updateCharCounter();
                        this.updateSendBtnState();
                        this.dispatchPacket();
                    };
                });
            } catch(e) { /* 무시 */ }
        },

        // ═══ 서버 이벤트 기반 step 진행 ═══
        _advanceTypingStep(targetStepId) {
            const stepOrder = ['step-1', 'step-2', 'step-3', 'step-4', 'step-5', 'step-6'];
            const targetIdx = stepOrder.indexOf(targetStepId);
            if (targetIdx < 0) return;
            // 타겟까지의 모든 이전 step을 done으로, 타겟을 active로
            stepOrder.forEach((sid, idx) => {
                const el = document.getElementById(sid);
                if (!el) return;
                if (idx < targetIdx) {
                    el.classList.remove('active');
                    el.classList.add('done');
                    const icon = el.querySelector('.step-icon');
                    if (icon) icon.textContent = '✓';
                } else if (idx === targetIdx) {
                    el.classList.remove('done');
                    el.classList.add('active');
                }
            });
        },

        // ═══ 타이핑 인디케이터 상태 텍스트 업데이트 ═══
        _updateTypingStatus(statusText) {
            const steps = document.querySelectorAll('.typing-step');
            if (steps.length > 0) {
                // 모든 step의 active 제거
                steps.forEach(s => { s.classList.remove('active'); s.classList.add('done'); });
                // 마지막 step을 현재 상태로 업데이트
                const lastStep = steps[steps.length - 1];
                lastStep.classList.remove('done');
                lastStep.classList.add('active');
                const icon = lastStep.querySelector('.step-icon');
                if (icon) {
                    icon.nextSibling ? icon.nextSibling.textContent = ' ' + statusText : lastStep.appendChild(document.createTextNode(' ' + statusText));
                } else {
                    lastStep.innerHTML = '<span class="step-icon">⏳</span> ' + statusText;
                }
            }
        },

        async handleFileUploadAndAnalysis(additionalQuery) {
            const file = this.uploadedFile;

            const userMsg = additionalQuery
                ? `📄 ${this.escapeHtml(file.name)} (${this.formatFileSize(file.size)})<br>${this.escapeHtml(additionalQuery)}`
                : `📄 ${this.escapeHtml(file.name)} (${this.formatFileSize(file.size)})`;

            this.appendMessage('user', userMsg);
            this.userInput.value = "";
            this.userInput.style.height = 'auto';

            const statusId = 'upload-status-' + Date.now();
            const statusDiv = document.createElement('div');
            statusDiv.id = statusId;
            statusDiv.className = 'ai-msg';
            statusDiv.innerHTML = '<p>📤 <b>파일 업로드 중...</b> (1/2)</p>';
            this.convArea.appendChild(statusDiv);
            this._smartScroll(true);

            try {
                const formData = new FormData();
                formData.append('file', file);

                const uploadResponse = await fetch(`${this.BASE_URL}/upload`, {
                    method: 'POST',
                    body: formData
                });

                if (!uploadResponse.ok) {
                    let errorData = {};
                    try { errorData = await uploadResponse.json(); } catch(_) {}
                    throw new Error(errorData.detail || '파일 업로드 실패');
                }

                const uploadData = await uploadResponse.json();

                this.updateMessage(statusId, '<p>🔍 <b>문서 분석 중...</b> (2/2)</p><p>문서를 법률적 관점에서 분석하고 있습니다...</p>');

                const analysisType = this.detectAnalysisType(file.name, additionalQuery);

                const analyzeResponse = await fetch(`${this.BASE_URL}/analyze-document/${uploadData.file_id}?analysis_type=${analysisType}`, {
                    method: 'POST'
                });

                if (!analyzeResponse.ok) {
                    let errorData = {};
                    try { errorData = await analyzeResponse.json(); } catch(_) {}
                    throw new Error(errorData.detail || '문서 분석 실패');
                }

                const analyzeData = await analyzeResponse.json();

                const resultHtml = this.formatDocumentAnalysis(analyzeData.analysis, file.name);
                this.updateMessage(statusId, resultHtml);
                this.clearUploadedFile();

            } catch (error) {
                console.error('파일 처리 오류:', error);
                this.updateMessage(statusId, `<div style='color:red;'>파일 처리 중 오류 발생: ${this.escapeHtml(error.message)}</div>`);
                this.clearUploadedFile();
            }
        },

        detectAnalysisType(filename, query) {
            const lowerFilename = filename.toLowerCase();
            const lowerQuery = (query || '').toLowerCase();

            if (lowerFilename.includes('contract') || lowerFilename.includes('계약') || lowerQuery.includes('계약')) {
                return 'contract';
            }
            if (lowerQuery.includes('위험') || lowerQuery.includes('리스크') || lowerQuery.includes('risk')) {
                return 'risk_assessment';
            }
            return 'general';
        },

        formatDocumentAnalysis(analysis, filename) {
            const esc = (s) => this.escapeHtml(String(s || ''));
            let html = `<h3>📄 문서 분석 결과: ${esc(filename)}</h3>`;

            if (analysis.summary) {
                html += `<h3>요약</h3><p>${esc(analysis.summary)}</p>`;
            }

            if (analysis.document_type || analysis.contract_type) {
                const docType = analysis.document_type || analysis.contract_type;
                html += `<p><strong>📋 문서 종류:</strong> ${esc(docType)}</p>`;
            }

            if (analysis.risk_level) {
                const riskEmoji = { 'low': '🟢', 'medium': '🟡', 'high': '🟠', 'critical': '🔴' }[analysis.risk_level] || '⚪';
                const riskText = { 'low': '낮음', 'medium': '중간', 'high': '높음', 'critical': '매우 높음' }[analysis.risk_level] || esc(analysis.risk_level);
                html += `<p><strong>위험도:</strong> ${riskEmoji} ${riskText}</p>`;
            }

            if (analysis.legal_category) {
                html += `<p><strong>법률 분야:</strong> ${esc(analysis.legal_category)}</p>`;
            }

            if (analysis.legal_issues && analysis.legal_issues.length > 0) {
                html += `<h3>법률적 쟁점</h3><ul>`;
                analysis.legal_issues.forEach(issue => { html += `<li>${esc(issue)}</li>`; });
                html += `</ul>`;
            }

            if (analysis.key_terms && analysis.key_terms.length > 0) {
                html += `<h3>📋 주요 조항</h3>`;
                analysis.key_terms.forEach((term, idx) => {
                    html += `<p><strong>${idx + 1}. ${esc(term.term)}</strong></p><p>${esc(term.content)}</p>`;
                    if (term.issue) html += `<p style="color: #B8922D;">${esc(term.issue)}</p>`;
                });
            }

            if (analysis.key_points && analysis.key_points.length > 0) {
                html += `<h3>핵심 내용</h3><ul>`;
                analysis.key_points.forEach(point => { html += `<li>${esc(point)}</li>`; });
                html += `</ul>`;
            }

            if (analysis.recommendations && analysis.recommendations.length > 0) {
                html += `<h3>권고사항</h3><ul>`;
                analysis.recommendations.forEach(rec => { html += `<li>${esc(rec)}</li>`; });
                html += `</ul>`;
            }

            html += `<p style="margin-top: 24px; padding-top: 16px; border-top: 2px solid var(--border); color: var(--text-muted); font-size: 0.9rem;">
                이 분석 결과는 Lawmadi OS에 의해 자동 생성되었습니다. 최종 결정은 반드시 법률 전문가와 상의하시기 바랍니다.
            </p>`;

            return html;
        },

        // ═══ 마크다운 렌더링 (코드블록 지원 추가) ═══
        formatReport(text) {
            if (!text) return "응답 데이터를 수신하지 못했습니다.";

            // 전처리: Gemini가 ## 대신 **N. 제목** 패턴을 쓴 경우 → ## 헤더로 정규화
            text = text.replace(/^\*\*(\d+\.\d+\.?\s+.+?)\s*\*\*\s*$/gm, '### $1');
            text = text.replace(/^\*\*(\d+\.\s+.+?)\s*\*\*\s*$/gm, '## $1');

            // 코드블록 사전 처리: ```로 감싼 블록을 플레이스홀더로 치환
            const codeBlocks = [];
            let processed = text.replace(/```(\w*)\n([\s\S]*?)```/g, (match, lang, code) => {
                const idx = codeBlocks.length;
                codeBlocks.push({ lang, code: code.trimEnd() });
                return `%%CODEBLOCK_${idx}%%`;
            });

            let lines = processed.split('\n');
            let html = [];
            let inList = false;
            let inOrderedList = false;
            let lastWasH2 = false;

            for (let i = 0; i < lines.length; i++) {
                let line = lines[i];
                let trimmed = line.trim();

                // 코드블록 플레이스홀더 복원
                if (/^%%CODEBLOCK_\d+%%$/.test(trimmed)) {
                    if (inList) { html.push('</ul>'); inList = false; }
                    if (inOrderedList) { html.push('</ol>'); inOrderedList = false; }
                    const idx = parseInt(trimmed.match(/\d+/)[0]);
                    const block = codeBlocks[idx];
                    const escapedCode = this.escapeHtml(block.code);
                    html.push(`<pre><code>${escapedCode}</code></pre>`);
                    lastWasH2 = false;
                    continue;
                }

                if (!trimmed) {
                    if (inList) { html.push('</ul>'); inList = false; }
                    if (inOrderedList) { html.push('</ol>'); inOrderedList = false; }
                    html.push('<p></p>');
                    lastWasH2 = false;
                    continue;
                }

                if (/^\[마디/.test(trimmed)) {
                    if (inList) { html.push('</ul>'); inList = false; }
                    if (inOrderedList) { html.push('</ol>'); inOrderedList = false; }
                    const tagEnd = trimmed.indexOf(']');
                    const tagText = tagEnd > 0 ? trimmed.substring(1, tagEnd) : '마디 분석';
                    const rest = tagEnd > 0 ? trimmed.substring(tagEnd + 1).replace(/^[\s:：]+/, '') : '';
                    if (rest) {
                        html.push(`<div class="madi-analysis-header"><span class="madi-tag">${tagText}</span><span class="madi-content">${this.formatInline(rest)}</span></div>`);
                    } else {
                        html.push(`<div class="madi-analysis-header"><span class="madi-tag">${tagText}</span></div>`);
                    }
                    lastWasH2 = false;
                    continue;
                }

                if (trimmed.startsWith('#### ')) {
                    if (inList) { html.push('</ul>'); inList = false; }
                    if (inOrderedList) { html.push('</ol>'); inOrderedList = false; }
                    let raw = trimmed.substring(5).trim();
                    const hasArrow = raw.startsWith('▶');
                    const arrowIcon = hasArrow ? '▶' : '▸';
                    const content = raw.replace(/^▶\s*/, '').trim();
                    html.push(`<div class="arrow-section-box"><span class="arrow-icon">${arrowIcon}</span><span class="arrow-text">${this.formatInline(content)}</span></div>`);
                    lastWasH2 = false;
                    continue;
                }

                if (/^(-{3,}|\*{3,}|_{3,})$/.test(trimmed)) {
                    if (inList) { html.push('</ul>'); inList = false; }
                    if (inOrderedList) { html.push('</ol>'); inOrderedList = false; }
                    html.push('<hr>');
                    lastWasH2 = false;
                    continue;
                }

                if (trimmed.startsWith('## ')) {
                    if (inList) { html.push('</ul>'); inList = false; }
                    if (inOrderedList) { html.push('</ol>'); inOrderedList = false; }
                    if (html.length > 0 && !lastWasH2) html.push('<hr>');
                    html.push('<p><strong class="section-title">' + this.formatInline(trimmed.substring(3)) + '</strong></p>');
                    lastWasH2 = true;
                }
                else if (trimmed.startsWith('### ')) {
                    if (inList) { html.push('</ul>'); inList = false; }
                    if (inOrderedList) { html.push('</ol>'); inOrderedList = false; }
                    html.push('<p><strong class="subsection-title">' + this.formatInline(trimmed.substring(4)) + '</strong></p>');
                    lastWasH2 = false;
                }
                else if (/^\d+\.\s+/.test(trimmed)) {
                    if (inList) { html.push('</ul>'); inList = false; }
                    const num = trimmed.match(/^(\d+)\./)[1];
                    if (!inOrderedList) { html.push(`<ol start="${num}">`); inOrderedList = true; }
                    let content = trimmed.replace(/^\d+\.\s+/, '');
                    html.push('<li>' + this.formatInline(content) + '</li>');
                    lastWasH2 = false;
                }
                else if (/^[-•*✓✅▪◦]\s+/.test(trimmed)) {
                    if (inOrderedList) { html.push('</ol>'); inOrderedList = false; }
                    if (!inList) { html.push('<ul>'); inList = true; }
                    let content = trimmed.replace(/^[-•*✓✅▪◦]\s+/, '');
                    html.push('<li>' + this.formatInline(content) + '</li>');
                    lastWasH2 = false;
                }
                else {
                    if (inList) { html.push('</ul>'); inList = false; }
                    if (inOrderedList) { html.push('</ol>'); inOrderedList = false; }
                    html.push('<p>' + this.formatInline(trimmed) + '</p>');
                    lastWasH2 = false;
                }
            }

            if (inList) html.push('</ul>');
            if (inOrderedList) html.push('</ol>');

            // 섹션 래핑: section-title 기준으로 ai-section 래퍼 생성
            let joined = html.join('\n');
            const sectionMarker = '<strong class="section-title">';
            const sectionParts = joined.split(/(?=<p><strong class="section-title">)/);
            if (sectionParts.length > 1) {
                let secIdx = 0;
                const wrapped = sectionParts.map((part, i) => {
                    if (part.startsWith('<p><strong class="section-title">')) {
                        secIdx++;
                        const titleMatch = part.match(/<strong class="section-title">(.*?)<\/strong>/);
                        const title = titleMatch ? titleMatch[1].replace(/<[^>]+>/g, '') : '';
                        const headerEnd = part.indexOf('</p>') + 4;
                        const headerTag = part.substring(0, headerEnd);
                        const body = part.substring(headerEnd);
                        return `<div class="ai-section" id="sec-${secIdx}" data-section-title="${this.escapeHtml(title)}"><div class="ai-section-header">${headerTag}<span class="material-symbols-outlined toggle-icon">expand_less</span></div><div class="ai-section-body">${body}</div></div>`;
                    }
                    return part;
                });
                joined = wrapped.join('\n');
            }

            return joined;
        },

        formatInline(text) {
            // XSS 방어: 마크다운 변환 전 HTML 이스케이프 적용
            let result = this.escapeHtml(text);
            result = result.replace(/`([^`]+?)`/g, '<code>$1</code>');
            result = result.replace(/\*\*\*([^*]+?)\*\*\*/g, '<strong><em>$1</em></strong>');
            result = result.replace(/\*\*([^*\n]+?)\*\*/g, '<strong>$1</strong>');
            result = result.replace(/\*([^*\n]+?)\*/g, '<em>$1</em>');
            // 법령 인용 하이라이트: "민법 제750조", "형법 제123조의2 제1항" 등
            result = result.replace(/((?:[가-힣]+\s)?제\d+조(?:의\d+)?(?:\s제\d+항)?(?:\s제\d+호)?)/g, '<span class="law-cite-chip">$1</span>');
            return result;
        },

        // ═══ 스마트 스크롤 (하단 근처일 때만 자동 스크롤) ═══
        _isNearBottom() {
            const el = this.convArea;
            return el.scrollHeight - el.scrollTop - el.clientHeight < 150;
        },
        _smartScroll(force = false) {
            if (force || this._isNearBottom()) {
                this.convArea.scrollTo({ top: this.convArea.scrollHeight, behavior: 'smooth' });
            }
        },

        // ═══ 메시지 렌더링 (즐겨찾기 + PDF 버튼 추가) ═══
        appendMessage(sender, text, id = null, originalQuery = null, rawResponse = null, leaderName = null, leaderSpecialtyFromServer = null, elapsedTime = null) {
            const msgDiv = document.createElement('div');
            msgDiv.className = sender === 'user' ? 'user-msg' : 'ai-msg';
            if (id) msgDiv.id = id;
            msgDiv.innerHTML = _sanitize(text);

            if (sender === 'ai' && leaderName) {
                const clevelTitles = { '서연': 'CSO', '지유': 'CTO', '유나': 'CCO' };
                const names = leaderName.split(',').map(n => n.trim()).filter(Boolean);
                const serverSpecialties = leaderSpecialtyFromServer ? leaderSpecialtyFromServer.split(',').map(s => s.trim()) : [];
                const avatarItems = names.map((name, idx) => {
                    const imgPath = leaderProfileImages[name];
                    const safeName = this.escapeHtml(name);
                    const displayName = clevelTitles[name] ? `${clevelTitles[name]} ${safeName}` : `${safeName} 리더`;
                    const specialty = serverSpecialties[idx] || leaderSpecialties[name] || '';
                    const specialtyHtml = specialty ? `<span class="leader-specialty">${this.escapeHtml(specialty)}</span>` : '';
                    const infoHtml = `<div class="leader-info"><span class="leader-name">${displayName}</span>${specialtyHtml}</div>`;
                    if (imgPath) {
                        return `<div class="leader-avatar-item"><img src="${imgPath}" alt="${safeName}">${infoHtml}</div>`;
                    }
                    return `<div class="leader-avatar-item">${infoHtml}</div>`;
                }).join('');
                if (avatarItems) {
                    const header = document.createElement('div');
                    header.className = 'leader-response-header';
                    header.innerHTML = `<div class="leader-avatars">${avatarItems}</div>`;
                    msgDiv.insertBefore(header, msgDiv.firstChild);
                }
            }

            if (sender === 'ai' && !id) {
                this.addCopyButton(msgDiv);

                // ── 응답 요약 카드 ──
                if (leaderName && originalQuery) {
                    const sections = msgDiv.querySelectorAll('.ai-section');
                    const firstH2 = msgDiv.querySelector('h2');
                    const topicText = firstH2 ? firstH2.textContent.replace(/[^\w가-힣\s]/g, '').trim().substring(0, 20) : '';
                    const summaryCard = document.createElement('div');
                    summaryCard.className = 'response-summary-card';
                    let summaryHtml = `<span class="summary-badge"><span class="material-symbols-outlined">person</span>${this.escapeHtml(leaderName)}</span>`;
                    if (leaderSpecialtyFromServer) summaryHtml += `<span class="summary-badge"><span class="material-symbols-outlined">category</span>${this.escapeHtml(leaderSpecialtyFromServer.split(',')[0].trim())}</span>`;
                    if (topicText) summaryHtml += `<span class="summary-badge"><span class="material-symbols-outlined">topic</span>${this.escapeHtml(topicText)}</span>`;
                    if (elapsedTime) summaryHtml += `<span class="summary-badge"><span class="material-symbols-outlined">timer</span>${elapsedTime}초</span>`;
                    summaryCard.innerHTML = _sanitize(summaryHtml);
                    const headerEl = msgDiv.querySelector('.leader-response-header');
                    if (headerEl && headerEl.nextSibling) {
                        msgDiv.insertBefore(summaryCard, headerEl.nextSibling);
                    } else {
                        msgDiv.insertBefore(summaryCard, msgDiv.firstChild);
                    }
                }

                // ── TOC 네비게이션 (섹션 3개 초과 시) ──
                const aiSections = msgDiv.querySelectorAll('.ai-section');
                if (aiSections.length > 3) {
                    const tocNav = document.createElement('div');
                    tocNav.className = 'ai-toc';
                    aiSections.forEach((sec) => {
                        const title = sec.getAttribute('data-section-title') || '';
                        if (!title) return;
                        const chip = document.createElement('span');
                        chip.className = 'ai-toc-item';
                        chip.textContent = title.substring(0, 15);
                        chip.onclick = () => {
                            sec.scrollIntoView({ behavior: 'smooth', block: 'start' });
                            sec.classList.add('toc-highlight');
                            setTimeout(() => sec.classList.remove('toc-highlight'), 1500);
                        };
                        tocNav.appendChild(chip);
                    });
                    const summaryEl = msgDiv.querySelector('.response-summary-card');
                    const insertRef = summaryEl ? summaryEl.nextSibling : (msgDiv.querySelector('.leader-response-header')?.nextSibling || msgDiv.firstChild);
                    msgDiv.insertBefore(tocNav, insertRef);
                }

                // ── 섹션 접기/펼치기 바인딩 ──
                msgDiv.querySelectorAll('.ai-section-header').forEach(header => {
                    header.addEventListener('click', () => {
                        header.parentElement.classList.toggle('collapsed');
                    });
                });

                // ── 키워드 하이라이트 ──
                if (originalQuery) {
                    /* 키워드 하이라이트 제거 — 불필요한 단어까지 노란색 강조되는 문제 */
                }

                // ── 액션 버튼 툴바 ──
                if (originalQuery && rawResponse) {
                    const toolbar = document.createElement('div');
                    toolbar.className = 'ai-action-toolbar';

                    // 그룹1: 저장, 공유, 내보내기
                    const g1 = document.createElement('div');
                    g1.className = 'toolbar-group';

                    const favBtn = this._createToolbarBtn('bookmark_add', '저장', () => {
                        this.saveFavorite(originalQuery, rawResponse);
                        favBtn.querySelector('.material-symbols-outlined').textContent = 'bookmark_added';
                        favBtn.classList.add('active');
                    });
                    g1.appendChild(favBtn);

                    const shareBtn = this._createToolbarBtn('share', '공유', async () => {
                        const shareText = rawResponse.substring(0, 500) + (rawResponse.length > 500 ? '...' : '');
                        try {
                            if (navigator.share) {
                                await navigator.share({ title: 'Lawmadi OS', text: shareText, url: location.origin });
                            } else {
                                await navigator.clipboard.writeText(shareText + '\n\n' + location.origin);
                                shareBtn.querySelector('.material-symbols-outlined').textContent = 'check';
                                setTimeout(() => { shareBtn.querySelector('.material-symbols-outlined').textContent = 'share'; }, 2000);
                            }
                        } catch(e) { if (e.name !== 'AbortError') console.warn('Share failed:', e); }
                    });
                    g1.appendChild(shareBtn);

                    const exportBtn = this._createToolbarBtn('picture_as_pdf', 'PDF 저장', async () => {
                        const icon = exportBtn.querySelector('.material-symbols-outlined');
                        icon.textContent = 'hourglass_top';
                        exportBtn.disabled = true;
                        try {
                            let pdfTitle = '법률 분석';
                            if (leaderName) pdfTitle = `${leaderName} 분석`;
                            let pdfContent = `[질문]\n${originalQuery}\n\n`;
                            if (leaderName) pdfContent += `[담당] ${leaderName}${leaderSpecialtyFromServer ? ' (' + leaderSpecialtyFromServer + ')' : ''}\n\n`;
                            pdfContent += `[답변]\n${rawResponse}`;
                            const pdfRes = await fetch(`${this.BASE_URL}/export-pdf`, {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                credentials: 'include',
                                body: JSON.stringify({ title: pdfTitle, content: pdfContent, doc_type: 'analysis', lang: 'ko' })
                            });
                            if (!pdfRes.ok) throw new Error('PDF 생성 실패');
                            const blob = await pdfRes.blob();
                            const url = URL.createObjectURL(blob);
                            const now = new Date();
                            const pad = n => String(n).padStart(2, '0');
                            const fname = `lawmadi-분석-${now.getFullYear()}${pad(now.getMonth()+1)}${pad(now.getDate())}-${pad(now.getHours())}${pad(now.getMinutes())}.pdf`;
                            const a = document.createElement('a'); a.href = url; a.download = fname; a.click();
                            URL.revokeObjectURL(url);
                            icon.textContent = 'check';
                            setTimeout(() => { icon.textContent = 'picture_as_pdf'; exportBtn.disabled = false; }, 2000);
                        } catch (e) {
                            icon.textContent = 'error';
                            setTimeout(() => { icon.textContent = 'picture_as_pdf'; exportBtn.disabled = false; }, 2000);
                        }
                    });
                    g1.appendChild(exportBtn);

                    // 문서 작성 버튼
                    const docBtn = this._createToolbarBtn('description', '문서 작성', () => {
                        this._showDocGenModal(originalQuery, rawResponse, leaderName);
                    });
                    g1.appendChild(docBtn);
                    toolbar.appendChild(g1);

                    msgDiv.appendChild(toolbar);

                    // ── 피드백 섹션 ──
                    const fbSection = document.createElement('div');
                    fbSection.className = 'feedback-section';
                    fbSection.innerHTML = _sanitize(
                        '<span class="fb-prompt">이 답변이 도움이 되셨나요?</span>'
                        + '<button class="fb-btn fb-up"><span class="material-symbols-outlined">thumb_up</span> 좋아요</button>'
                        + '<button class="fb-btn fb-down"><span class="material-symbols-outlined">thumb_down</span> 아쉬워요</button>'
                    );
                    const _fbUp = fbSection.querySelector('.fb-up');
                    const _fbDown = fbSection.querySelector('.fb-down');
                    const _sendFb = async (rating) => {
                        try {
                            await fetch(`${this.BASE_URL}/feedback`, {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({ rating, query: originalQuery, leader: leaderName || '' })
                            });
                        } catch(e) { /* 무시 */ }
                        if (rating === 'up') { _fbUp.classList.add('selected'); } else { _fbDown.classList.add('selected'); }
                        _fbUp.disabled = true; _fbDown.disabled = true;
                        fbSection.querySelector('.fb-prompt').textContent = '피드백을 보내주셔서 감사합니다!';
                    };
                    _fbUp.onclick = () => _sendFb('up');
                    _fbDown.onclick = () => _sendFb('down');
                    msgDiv.appendChild(fbSection);

                    // ── 면책 안내 ──
                    const disclaimerDiv = document.createElement('div');
                    disclaimerDiv.className = 'ai-disclaimer';
                    disclaimerDiv.textContent = '본 서비스는 AI 기반 법률 정보 제공 시스템이며, 변호사의 법률 자문을 대체하지 않습니다.';
                    msgDiv.appendChild(disclaimerDiv);

                    // ── 로그인 유도 배너 (비로그인 사용자) ──
                    this._incQueryCount();
                    const _qc = this._getQueryCount();
                    const _isLoggedIn = window.__lawmadiAuth && window.__lawmadiAuth.user;
                    if (!_isLoggedIn && _qc >= 1) {
                        const loginBanner = document.createElement('div');
                        loginBanner.className = 'login-nudge-banner';
                        if (_qc >= this.DAILY_FREE) {
                            loginBanner.innerHTML = _sanitize(
                                '<span class="material-symbols-outlined">lock</span>'
                                + '<div><strong>무료 이용 한도에 가까워지고 있습니다</strong>'
                                + '<p>로그인하면 크레딧으로 전문가 검증, 리더 1:1 채팅 등 추가 기능을 이용할 수 있습니다.</p></div>'
                                + '<button class="login-nudge-btn">로그인</button>'
                            );
                        } else {
                            loginBanner.innerHTML = _sanitize(
                                '<span class="material-symbols-outlined">person</span>'
                                + '<div><strong>로그인하면 더 많은 기능을 이용할 수 있습니다</strong>'
                                + '<p>전문가 검증, 리더 1:1 채팅, PDF 내보내기, 답변 저장 등</p></div>'
                                + '<button class="login-nudge-btn">로그인</button>'
                            );
                        }
                        loginBanner.querySelector('.login-nudge-btn').onclick = () => {
                            if (typeof UI !== 'undefined' && UI.openAuthModal) UI.openAuthModal();
                            else { const snLogin = document.getElementById('siteNavAuth'); if (snLogin) snLogin.click(); }
                        };
                        msgDiv.appendChild(loginBanner);
                    }

                    // ── 전문가 검증 + 변호사 상담 CTA (답변 맨 아래) ──
                    const ctaBar = document.createElement('div');
                    ctaBar.className = 'ai-bottom-cta';

                    const expertCta = document.createElement('button');
                    expertCta.className = 'bottom-cta-btn expert';
                    // 크레딧 부족 시 비활성화
                    const _authUser = window.__lawmadiAuth && window.__lawmadiAuth.user;
                    const _userBal = _authUser ? (_authUser.credit_balance || 0) : -1;
                    const _isFreeNoCredit = _authUser && _userBal === 0 && _authUser.current_plan === 'free';
                    if (_isFreeNoCredit || (_authUser && _userBal >= 0 && _userBal < 2)) {
                        expertCta.innerHTML = '<span class="material-symbols-outlined">verified</span> 전문가용 답변 받기 <span style="font-size:0.75em;background:rgba(196,84,84,0.15);color:#C45454;padding:2px 8px;border-radius:6px;margin-left:4px;">크레딧 부족</span>';
                        expertCta.disabled = true;
                        expertCta.title = '크레딧을 충전하면 이용할 수 있습니다 (2 Credit 필요)';
                    } else {
                        expertCta.innerHTML = '<span class="material-symbols-outlined">verified</span> 전문가용 답변 받기 <span style="font-size:0.75em;background:rgba(109,187,143,0.15);padding:2px 8px;border-radius:6px;margin-left:4px;">2 Credit</span>';
                    }
                    expertCta.onclick = async () => {
                        // 로그인 확인
                        const _authU = window.__lawmadiAuth && window.__lawmadiAuth.user;
                        if (!_authU) {
                            const _goLogin = confirm('전문가용 답변을 받으려면 로그인이 필요합니다.\n\n로그인하시겠습니까?');
                            if (_goLogin && typeof UI !== 'undefined' && UI.openAuthModal) { UI.openAuthModal(); }
                            return;
                        }
                        // 크레딧 차감 확인 모달
                        const _bal = _authU.credit_balance || 0;
                        if (_bal < 2) {
                            const _goPrice = confirm('크레딧이 부족합니다.\n\n크레딧을 충전하시겠습니까?');
                            if (_goPrice) location.href = '/pricing';
                            return;
                        }
                        if (!confirm('전문가용 답변을 받으시겠습니까?\n\n2 Credit이 차감됩니다.\n현재 잔액: ' + _bal + ' Credit')) return;
                        expertCta.disabled = true;
                        expertCta.innerHTML = '<span class="material-symbols-outlined">hourglass_top</span> 검증 중...';

                        // ── 대기 문구 표시 ──
                        const waitingDiv = document.createElement('div');
                        waitingDiv.className = 'expert-waiting-indicator';
                        waitingDiv.innerHTML = `
                            <div class="expert-waiting-title">
                                <span class="material-symbols-outlined">sync</span>
                                전문가 검증 진행 중
                            </div>
                            <div class="expert-waiting-steps">
                                <div class="expert-wait-step active" data-ew="1"><span class="ew-icon">🔍</span> 원본 답변 분석 중...</div>
                                <div class="expert-wait-step" data-ew="2"><span class="ew-icon">📖</span> DRF 법조문 전수검증 중...</div>
                                <div class="expert-wait-step" data-ew="3"><span class="ew-icon">⚖️</span> 시행령·시행규칙 교차 검증 중...</div>
                                <div class="expert-wait-step" data-ew="4"><span class="ew-icon">📋</span> 검증 보고서 작성 중...</div>
                            </div>
                            <div class="expert-wait-elapsed">0초 경과</div>
                        `;
                        msgDiv.insertBefore(waitingDiv, ctaBar);
                        this._smartScroll(true);

                        const ewSteps = [
                            { ew: '1', delay: 0 },
                            { ew: '2', delay: 2000 },
                            { ew: '3', delay: 5000 },
                            { ew: '4', delay: 9000 }
                        ];
                        const ewTimers = [];
                        ewSteps.forEach((s, idx) => {
                            const t = setTimeout(() => {
                                const el = waitingDiv.querySelector(`[data-ew="${s.ew}"]`);
                                if (el) { el.classList.add('active'); }
                                if (idx > 0) {
                                    const prev = waitingDiv.querySelector(`[data-ew="${ewSteps[idx-1].ew}"]`);
                                    if (prev) { prev.classList.remove('active'); prev.classList.add('done'); }
                                }
                            }, s.delay);
                            ewTimers.push(t);
                        });
                        let ewSec = 0;
                        const ewElapsed = setInterval(() => {
                            ewSec++;
                            const el = waitingDiv.querySelector('.expert-wait-elapsed');
                            if (el) el.textContent = `${ewSec}초 경과`;
                        }, 1000);

                        try {
                            const expertRes = await fetch(`${this.BASE_URL}/ask-expert`, {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                credentials: 'include',
                                body: JSON.stringify({ query: originalQuery, original_response: rawResponse })
                            });
                            if (!expertRes.ok) throw new Error('전문가 검증 실패');
                            const expertData = await expertRes.json();
                            ewTimers.forEach(t => clearTimeout(t));
                            clearInterval(ewElapsed);
                            waitingDiv.remove();

                            if (expertData.status === 'SUCCESS' && expertData.response) {
                                const panel = document.createElement('div');
                                panel.className = 'expert-response-panel';
                                panel.innerHTML = _sanitize(this.formatReport(expertData.response));
                                msgDiv.insertBefore(panel, ctaBar);
                                const vScore = Number(expertData.verification?.ssot_compliance_score) || 0;
                                if (vScore > 0) {
                                    const barDiv = document.createElement('div');
                                    barDiv.className = 'ssot-confidence-bar';
                                    const level = vScore >= 80 ? 'high' : vScore >= 50 ? 'medium' : 'low';
                                    barDiv.innerHTML = `<span class="bar-label">SSOT 신뢰도</span><div class="bar-track"><div class="bar-fill ${level}" style="width: ${vScore}%"></div></div><span class="bar-score ${level}">${vScore}점</span>`;
                                    msgDiv.insertBefore(barDiv, ctaBar);
                                }
                                expertCta.innerHTML = '<span class="material-symbols-outlined">check_circle</span> 검증 완료';
                                expertCta.classList.add('done');
                                // 전문가 패널 상단으로 스크롤
                                requestAnimationFrame(() => {
                                    panel.scrollIntoView({ behavior: 'smooth', block: 'start' });
                                });
                            } else { throw new Error('검증 실패'); }
                        } catch (e) {
                            ewTimers.forEach(t => clearTimeout(t));
                            clearInterval(ewElapsed);
                            waitingDiv.remove();
                            expertCta.disabled = false;
                            expertCta.innerHTML = '<span class="material-symbols-outlined">verified</span> 전문가용 답변 받기 <span style="font-size:0.75em;background:rgba(109,187,143,0.15);padding:2px 8px;border-radius:6px;margin-left:4px;">2 Credit</span>';
                            // 크레딧 부족 에러인 경우
                            if (e.message && e.message.includes('402')) {
                                expertCta.innerHTML = '<span class="material-symbols-outlined">verified</span> 전문가용 답변 받기 <span style="font-size:0.75em;background:rgba(196,84,84,0.15);color:#C45454;padding:2px 8px;border-radius:6px;margin-left:4px;">크레딧 부족</span>';
                                expertCta.disabled = true;
                            }
                            console.error('Expert verification failed:', e);
                        }
                    };
                    ctaBar.appendChild(expertCta);

                    // 리더 1:1 채팅 CTA
                    if (leaderName && this.currentLeader && this.currentLeader.leader_id) {
                        const chatCta = document.createElement('button');
                        chatCta.className = 'bottom-cta-btn leader-chat';
                        chatCta.innerHTML = '<span class="material-symbols-outlined">chat</span> ' + this.escapeHtml(leaderName) + '에게 질문하기';
                        chatCta.onclick = () => {
                            location.href = '/leader-chat?id=' + encodeURIComponent(this.currentLeader.leader_id);
                        };
                        ctaBar.appendChild(chatCta);
                    }

                    if (leaderName) {
                        const clevelOnly = ['서연','지유','유나'];
                        const lNames = leaderName.split(',').map(n => n.trim()).filter(Boolean);
                        if (!lNames.every(n => clevelOnly.includes(n))) {
                            const lawyerCta = document.createElement('button');
                            lawyerCta.className = 'bottom-cta-btn lawyer';
                            lawyerCta.innerHTML = '<span class="material-symbols-outlined">gavel</span> 변호사 상담 안내';
                            lawyerCta.onclick = () => UI.openLawyerModal(originalQuery, leaderName);
                            ctaBar.appendChild(lawyerCta);
                        }
                    }
                    msgDiv.appendChild(ctaBar);

                    // 관련 질문 추천 (비동기 로드)
                    const suggestArea = document.createElement('div');
                    suggestArea.className = 'suggest-area';
                    msgDiv.appendChild(suggestArea);
                    this._loadSuggestions(suggestArea, originalQuery, leaderName, leaderSpecialtyFromServer);
                }

                // PDF 다운로드 버튼 (법률문서 코드블록 감지)
                if (rawResponse) {
                    const docKeywords = ['고소장', '소장', '답변서', '내용증명', '고소취하서'];
                    const hasCodeBlock = rawResponse.includes('```');
                    const hasDocKeyword = docKeywords.some(kw => rawResponse.includes(kw));

                    if (hasCodeBlock && hasDocKeyword) {
                        const codeMatch = rawResponse.match(/```[\s\S]*?\n([\s\S]*?)```/);
                        if (codeMatch) {
                            const docContent = codeMatch[1].trim();
                            const titleMatch = docContent.match(/^(고\s*소\s*장|소\s+장|답\s*변\s*서|내\s*용\s*증\s*명|고소취하서)/m);
                            const docTitle = titleMatch ? titleMatch[1].replace(/\s+/g, '') : '법률문서';

                            const pdfBtn = document.createElement('button');
                            pdfBtn.className = 'pdf-download-btn';
                            pdfBtn.innerHTML = '<span class="material-symbols-outlined" style="font-size: 18px;">picture_as_pdf</span> PDF 다운로드';
                            pdfBtn.onclick = async () => {
                                pdfBtn.innerHTML = '<span class="material-symbols-outlined" style="font-size: 18px;">hourglass_top</span> 생성 중...';
                                pdfBtn.disabled = true;
                                try {
                                    const pdfRes = await fetch(`${this.BASE_URL}/export-pdf`, {
                                        method: 'POST',
                                        headers: { 'Content-Type': 'application/json' },
                                        body: JSON.stringify({ title: docTitle, content: docContent })
                                    });
                                    if (!pdfRes.ok) throw new Error('PDF 생성 실패');
                                    const blob = await pdfRes.blob();
                                    const url = URL.createObjectURL(blob);
                                    const a = document.createElement('a'); a.href = url; a.download = `${docTitle}.pdf`; a.click();
                                    URL.revokeObjectURL(url);
                                    pdfBtn.innerHTML = '<span class="material-symbols-outlined" style="font-size: 18px;">check_circle</span> 완료';
                                    setTimeout(() => { pdfBtn.innerHTML = '<span class="material-symbols-outlined" style="font-size: 18px;">picture_as_pdf</span> PDF 다운로드'; pdfBtn.disabled = false; }, 2000);
                                } catch (e) {
                                    pdfBtn.innerHTML = '<span class="material-symbols-outlined" style="font-size: 18px;">error</span> 실패 - 재시도';
                                    pdfBtn.disabled = false;
                                }
                            };
                            msgDiv.appendChild(pdfBtn);
                        }
                    }
                }
            }

            // 타임스탬프 추가
            const tsDiv = document.createElement('div');
            tsDiv.className = 'msg-timestamp';
            let tsText = this._formatTime();
            if (sender === 'ai' && elapsedTime) {
                tsText += ` · ⏱ ${elapsedTime}초`;
            }
            tsDiv.textContent = tsText;
            msgDiv.appendChild(tsDiv);

            // 협의/인수인계 컨테이너를 AI 메시지 안으로 이동 (응답 후에도 항상 보이도록)
            // leader-response-header(sticky) 바로 아래에 삽입하여 덮이지 않도록 함
            if (sender === 'ai') {
                const delibEls = Array.from(this.convArea.querySelectorAll(':scope > .deliberation-container, :scope > .handoff-container, :scope > .chat-flow-container'));
                if (delibEls.length) {
                    const headerEl = msgDiv.querySelector('.leader-response-header');
                    const summaryEl = msgDiv.querySelector('.response-summary-card');
                    const insertRef = summaryEl ? summaryEl.nextSibling : (headerEl ? headerEl.nextSibling : msgDiv.firstChild);
                    for (let i = delibEls.length - 1; i >= 0; i--) {
                        msgDiv.insertBefore(delibEls[i], insertRef);
                    }
                }
            }

            this.convArea.appendChild(msgDiv);
            this._smartScroll(sender === 'user');
        },

        updateMessage(id, html) {
            const msgDiv = document.getElementById(id);
            if (msgDiv) {
                msgDiv.innerHTML = _sanitize(html);
                this.addCopyButton(msgDiv);
                this._smartScroll();
            }
        },

        _createToolbarBtn(icon, tooltip, onClick) {
            const btn = document.createElement('button');
            btn.className = 'toolbar-btn';
            btn.setAttribute('data-tooltip', tooltip);
            btn.innerHTML = `<span class="material-symbols-outlined">${icon}</span>`;
            btn.onclick = onClick;
            return btn;
        },

        // ═══ 고급 문서 작성 모달 ═══
        _showDocGenModal(originalQuery, rawResponse, leaderName) {
            // Remove existing modal if any
            const existing = document.getElementById('doc-gen-modal');
            if (existing) existing.remove();

            const docTypes = [
                { key: 'complaint', label: '고소장', desc: '형사 고소장 초안' },
                { key: 'petition', label: '소장', desc: '민사 소장 초안' },
                { key: 'notice', label: '내용증명', desc: '내용증명 우편 초안' },
                { key: 'answer', label: '답변서', desc: '민사 답변서 초안' },
                { key: 'appeal', label: '탄원서', desc: '탄원서/선처 요청' },
                { key: 'demand', label: '최고서', desc: '이행 최고/독촉장' },
                { key: 'agreement', label: '합의서', desc: '합의서/화해계약' },
                { key: 'opinion', label: '법률의견서', desc: '법률 검토 의견서' },
            ];

            const overlay = document.createElement('div');
            overlay.id = 'doc-gen-modal';
            overlay.style.cssText = 'position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.5);z-index:9999;display:flex;align-items:center;justify-content:center;padding:16px;';
            overlay.onclick = (e) => { if (e.target === overlay) overlay.remove(); };

            const modal = document.createElement('div');
            modal.style.cssText = 'background:#fff;border-radius:16px;max-width:520px;width:100%;max-height:85vh;overflow-y:auto;padding:28px;box-shadow:0 20px 60px rgba(0,0,0,0.25);';

            // Header
            modal.innerHTML = '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;">'
                + '<h3 style="margin:0;font-size:1.2rem;color:#2D4A37;">법률 문서 작성</h3>'
                + '<button id="doc-gen-close" style="background:none;border:none;cursor:pointer;font-size:1.5rem;color:#999;">&times;</button>'
                + '</div>';

            // Document type grid
            let gridHtml = '<div style="display:grid;grid-template-columns:repeat(2,1fr);gap:10px;margin-bottom:20px;">';
            docTypes.forEach(dt => {
                gridHtml += `<button class="doc-type-btn" data-type="${dt.key}" style="padding:14px 12px;border:2px solid #E8F0EB;border-radius:12px;background:#FAFCFB;cursor:pointer;text-align:left;transition:all 0.2s;">`
                    + `<div style="font-weight:600;color:#2D4A37;font-size:0.95rem;">${_sanitize(dt.label)}</div>`
                    + `<div style="font-size:0.78rem;color:#7A9A88;margin-top:3px;">${_sanitize(dt.desc)}</div>`
                    + `</button>`;
            });
            gridHtml += '</div>';
            modal.innerHTML += gridHtml;

            // Extra instructions
            modal.innerHTML += '<div style="margin-bottom:16px;">'
                + '<label style="font-size:0.85rem;color:#5A7A68;font-weight:500;">추가 지시사항 (선택)</label>'
                + '<textarea id="doc-gen-extra" placeholder="예: 피해 금액 500만원, 피고소인 주소 서울시 강남구..." '
                + 'style="width:100%;min-height:70px;margin-top:6px;padding:12px;border:1.5px solid #D4E4DA;border-radius:10px;font-size:0.9rem;resize:vertical;box-sizing:border-box;font-family:inherit;"></textarea>'
                + '</div>';

            // Context info
            const contextPreview = originalQuery ? originalQuery.substring(0, 80) + (originalQuery.length > 80 ? '...' : '') : '';
            if (contextPreview) {
                modal.innerHTML += '<div style="padding:10px 14px;background:#F0F7F3;border-radius:10px;margin-bottom:16px;font-size:0.82rem;color:#5A7A68;">'
                    + '<span class="material-symbols-outlined" style="font-size:14px;vertical-align:middle;margin-right:4px;">info</span>'
                    + '이전 질문/답변을 기반으로 문서가 작성됩니다.'
                    + '</div>';
            }

            // Generate button
            modal.innerHTML += '<button id="doc-gen-submit" disabled style="width:100%;padding:14px;background:#B8922D;color:#fff;border:none;border-radius:12px;font-size:1rem;font-weight:600;cursor:pointer;opacity:0.5;transition:all 0.2s;">'
                + '<span class="material-symbols-outlined" style="font-size:18px;vertical-align:middle;margin-right:6px;">edit_document</span>'
                + '문서 생성 (2 Credit)'
                + '</button>';

            // Status area
            modal.innerHTML += '<div id="doc-gen-status" style="margin-top:12px;text-align:center;font-size:0.85rem;color:#7A9A88;"></div>';

            overlay.appendChild(modal);
            document.body.appendChild(overlay);

            // Event handlers
            document.getElementById('doc-gen-close').onclick = () => overlay.remove();

            let selectedType = null;
            modal.querySelectorAll('.doc-type-btn').forEach(btn => {
                btn.onmouseover = () => { if (btn.dataset.type !== selectedType) btn.style.borderColor = '#B8922D'; };
                btn.onmouseout = () => { if (btn.dataset.type !== selectedType) btn.style.borderColor = '#E8F0EB'; };
                btn.onclick = () => {
                    modal.querySelectorAll('.doc-type-btn').forEach(b => {
                        b.style.borderColor = '#E8F0EB';
                        b.style.background = '#FAFCFB';
                    });
                    btn.style.borderColor = '#B8922D';
                    btn.style.background = '#FDF8EE';
                    selectedType = btn.dataset.type;
                    const submitBtn = document.getElementById('doc-gen-submit');
                    submitBtn.disabled = false;
                    submitBtn.style.opacity = '1';
                };
            });

            // Submit handler
            document.getElementById('doc-gen-submit').onclick = async () => {
                if (!selectedType) return;
                const submitBtn = document.getElementById('doc-gen-submit');
                const statusEl = document.getElementById('doc-gen-status');
                submitBtn.disabled = true;
                submitBtn.innerHTML = '<span class="material-symbols-outlined" style="font-size:18px;vertical-align:middle;margin-right:6px;animation:spin 1s linear infinite;">progress_activity</span> 문서 생성 중...';
                statusEl.textContent = 'Gemini가 법률 문서를 작성하고 있습니다...';

                try {
                    const extra = (document.getElementById('doc-gen-extra') || {}).value || '';
                    let context = '';
                    if (originalQuery) context += `[상황/질문]\n${originalQuery}\n\n`;
                    if (rawResponse) context += `[분석 결과]\n${rawResponse}\n\n`;
                    if (leaderName) context += `[담당 리더] ${leaderName}\n`;

                    const res = await fetch(`${this.BASE_URL}/generate-document`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        credentials: 'include',
                        body: JSON.stringify({
                            doc_type: selectedType,
                            context: context,
                            lang: 'ko',
                            extra_instructions: extra
                        })
                    });

                    if (!res.ok) {
                        const err = await res.json().catch(() => ({}));
                        throw new Error(err.detail || '문서 생성 실패');
                    }

                    const result = await res.json();
                    statusEl.innerHTML = '<span style="color:#6DBB8F;">문서 생성 완료! PDF를 다운로드합니다...</span>';

                    // Auto-download PDF
                    const pdfRes = await fetch(`${this.BASE_URL}/export-pdf`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        credentials: 'include',
                        body: JSON.stringify({
                            title: result.title,
                            content: result.content,
                            doc_type: selectedType,
                            lang: 'ko',
                            sections: result.sections
                        })
                    });

                    if (!pdfRes.ok) throw new Error('PDF 변환 실패');
                    const blob = await pdfRes.blob();
                    const url = URL.createObjectURL(blob);
                    const now = new Date();
                    const pad = n => String(n).padStart(2, '0');
                    const fname = `${result.title}-${now.getFullYear()}${pad(now.getMonth()+1)}${pad(now.getDate())}.pdf`;
                    const a = document.createElement('a'); a.href = url; a.download = fname; a.click();
                    URL.revokeObjectURL(url);

                    statusEl.innerHTML = '<span style="color:#6DBB8F;">PDF 다운로드 완료</span>';
                    submitBtn.innerHTML = '<span class="material-symbols-outlined" style="font-size:18px;vertical-align:middle;margin-right:6px;">check_circle</span> 완료';

                    // Also display the document content in chat
                    if (result.content) {
                        const docMsg = '```\n' + result.content + '\n```';
                        this.addMessage(docMsg, 'ai');
                    }

                    setTimeout(() => overlay.remove(), 2000);
                } catch (e) {
                    statusEl.innerHTML = `<span style="color:#E74C3C;">${_sanitize(e.message)}</span>`;
                    submitBtn.disabled = false;
                    submitBtn.innerHTML = '<span class="material-symbols-outlined" style="font-size:18px;vertical-align:middle;margin-right:6px;">edit_document</span> 재시도';
                    submitBtn.style.opacity = '1';
                }
            };
        },

        addCopyButton(msgDiv) {
            const existingBtn = msgDiv.querySelector('.copy-btn');
            if (existingBtn) existingBtn.remove();

            const copyBtn = document.createElement('button');
            copyBtn.className = 'copy-btn';
            copyBtn.innerHTML = '<span class="material-symbols-outlined" style="font-size: 18px;">content_copy</span>';
            copyBtn.style.cssText = `
                position: absolute; top: 12px; right: 12px;
                background: rgba(255, 255, 255, 0.9); backdrop-filter: blur(8px);
                border: 1px solid #D4E4DA; border-radius: 8px; padding: 8px;
                cursor: pointer; display: flex; align-items: center; justify-content: center;
                opacity: 0.7; transition: all 0.2s ease;
                box-shadow: 0 2px 8px rgba(0,0,0,0.1); z-index: 10;
            `;

            copyBtn.onmouseenter = () => { copyBtn.style.opacity = '1'; copyBtn.style.background = 'rgba(61, 139, 94, 0.1)'; copyBtn.style.borderColor = '#3D8B5E'; };
            copyBtn.onmouseleave = () => { copyBtn.style.opacity = '0.7'; copyBtn.style.background = 'rgba(255, 255, 255, 0.9)'; copyBtn.style.borderColor = '#D4E4DA'; };

            copyBtn.onclick = async () => {
                try {
                    await navigator.clipboard.writeText(msgDiv.innerText);
                    copyBtn.innerHTML = '<span class="material-symbols-outlined" style="font-size: 18px; color: #3D8B5E;">check</span>';
                    copyBtn.style.opacity = '1';
                    setTimeout(() => { copyBtn.innerHTML = '<span class="material-symbols-outlined" style="font-size: 18px;">content_copy</span>'; copyBtn.style.opacity = '0.7'; }, 2000);
                } catch (err) { console.error('복사 실패:', err); }
            };

            msgDiv.style.position = 'relative';
            msgDiv.appendChild(copyBtn);
        },

        // ═══ 향상된 로딩 애니메이션 ═══
        showTypingIndicator() {
            const typingId = 'typing-indicator';
            if (document.getElementById(typingId)) return typingId;

            const typingDiv = document.createElement('div');
            typingDiv.id = typingId;
            typingDiv.className = 'typing-indicator';
            typingDiv.innerHTML = `
                <div class="typing-dots">
                    <span></span><span></span><span></span>
                </div>
                <div class="typing-progress">
                    <div class="typing-step active" id="step-1">
                        <span class="step-icon">🔍</span> 질문 분석 중...
                    </div>
                    <div class="typing-step" id="step-2">
                        <span class="step-icon">👥</span> AI 전문 리더 배정 중...
                    </div>
                    <div class="typing-step" id="step-3">
                        <span class="step-icon">⚖️</span> 법령·판례 검색 중...
                    </div>
                    <div class="typing-step" id="step-4">
                        <span class="step-icon">✍️</span> 답변 생성 중...
                    </div>
                    <div class="typing-step" id="step-5">
                        <span class="step-icon">🔎</span> 교차 검증 중...
                    </div>
                    <div class="typing-step" id="step-6">
                        <span class="step-icon">📋</span> 최종 정리 중...
                    </div>
                    <div class="typing-elapsed" id="typing-elapsed" style="margin-top:6px;font-size:0.7rem;color:var(--text-muted);opacity:0.7;">0초 경과</div>
                </div>
            `;
            this.convArea.appendChild(typingDiv);
            this._smartScroll(true);

            // 단계별 진행 애니메이션
            this._typingStepTimers = [];
            const steps = [
                { id: 'step-1', delay: 0 },
                { id: 'step-2', delay: 1500 },
                { id: 'step-3', delay: 3500 },
                { id: 'step-4', delay: 6000 },
                { id: 'step-5', delay: 12000 },
                { id: 'step-6', delay: 20000 }
            ];
            steps.forEach((step, idx) => {
                const timer = setTimeout(() => {
                    const el = document.getElementById(step.id);
                    if (el) {
                        el.classList.add('active');
                        if (idx > 0) {
                            const prev = document.getElementById(steps[idx - 1].id);
                            if (prev) {
                                prev.classList.remove('active'); prev.classList.add('done');
                                const icon = prev.querySelector('.step-icon');
                                if (icon) icon.textContent = '✓';
                            }
                        }
                    }
                }, step.delay);
                this._typingStepTimers.push(timer);
            });

            // 경과 시간 카운터
            let elapsed = 0;
            this._elapsedTimer = setInterval(() => {
                elapsed++;
                const el = document.getElementById('typing-elapsed');
                if (el) el.textContent = `${elapsed}초 경과`;
            }, 1000);

            return typingId;
        },

        // ═══ 리더 협의(Deliberation) 렌더링 — Premium UI ═══
        _getLeaderAvatar(name) {
            return leaderProfileImages[name] || 'images/leaders/L60-madi.jpg';
        },

        _getTimeStamp(turnOffset) {
            const now = new Date();
            // 턴별 타임스탬프 오프셋: 각 턴마다 30~50초씩 증가하여 자연스러운 시간 흐름
            if (typeof turnOffset === 'number' && turnOffset > 0) {
                now.setSeconds(now.getSeconds() + turnOffset * 40);
            }
            return String(now.getHours()).padStart(2,'0') + ':' + String(now.getMinutes()).padStart(2,'0');
        },

        _buildAvatarHTML(name, context) {
            const cls = context === 'handoff' ? '' : '';
            return `<div class="delib-avatar-wrap"><img class="delib-avatar" src="${this._getLeaderAvatar(name)}" alt="${this.escapeHtml(name)}"></div>`;
        },

        _buildBubbleBody(name, role, text, turnIndex) {
            const ts = this._getTimeStamp(turnIndex || 0);
            return `<div class="chat-msg-body">` +
                `<div class="chat-msg-meta"><span class="chat-msg-name">${this.escapeHtml(name)}</span>` +
                `<span class="chat-msg-role">${this.escapeHtml(role)}</span>` +
                `<span class="chat-msg-time">${ts}</span></div>` +
                `<div class="chat-msg-text">${this.escapeHtml(text)}</div></div>`;
        },

        _buildHandoffArrow() {
            return '<div class="handoff-arrow">' +
                '<div class="handoff-arrow-line"></div>' +
                '<svg class="handoff-arrow-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14"/><path d="m12 5 7 7-7 7"/></svg>' +
                '<div class="handoff-arrow-line"></div>' +
                '</div>';
        },

        // 스트리밍: deliberation_start 이벤트
        _renderDeliberationStart(payload) {
            const container = document.createElement('div');
            container.className = 'chat-flow-container';
            container.id = 'delib-live-' + Date.now();
            // 컨테이너 헤더 없음 — 자연스러운 채팅 흐름
            this._appendChatTypingBubble(container, '서연', 'CSO');
            this.convArea.appendChild(container);
            this._smartScroll(false);
            this._delibContainer = container;
            this._delibTurnIndex = 0;
        },

        // ─── 턴 큐잉 시스템: 턴이 동시 도착해도 순차 재생 ───
        _turnQueue: [],
        _turnPlaying: false,
        _turnFlushed: false,

        _enqueueTurn(type, payload) {
            // 이미 flush됨 → 즉시 무시
            if (this._turnFlushed) return;
            this._turnQueue.push({ type, payload });
            if (!this._turnPlaying) this._playNextTurn();
        },

        // chunk 도착 시 호출: 남은 턴 즉시 표시 (애니메이션 없이)
        _flushTurnQueue() {
            this._turnFlushed = true;
            this._turnPlaying = false;
            const remaining = this._turnQueue.splice(0);
            for (const { type, payload } of remaining) {
                if (type === 'deliberation_turn') {
                    this._doTurnInstant(payload, this._delibContainer, 'deliberation');
                } else if (type === 'handoff') {
                    this._doTurnInstant(payload, this._handoffContainer, 'handoff');
                } else if (type === 'deliberation_end') {
                    this._doDeliberationEnd(payload);
                }
            }
            // 모든 타이핑 버블 제거
            this._removeChatTypingBubbleAll();
        },

        // 즉시 렌더링 (타자 효과/딜레이 없음)
        _doTurnInstant(payload, container, mode) {
            if (!container) return;
            const name = payload.speaker || '?';
            const role = payload.role || '';
            const text = payload.text || '';
            const isMod = (name === '서연');
            this._removeChatTypingBubble(container);
            const bubble = document.createElement('div');
            bubble.className = 'chat-msg-bubble' + (isMod ? ' moderator' : '');
            const idx = (mode === 'handoff' ? this._handoffTurnIndex : this._delibTurnIndex) || 0;
            bubble.innerHTML = _sanitize(
                this._buildAvatarHTML(name, mode) +
                '<div class="chat-msg-body">' +
                '<div class="chat-msg-meta"><span class="chat-msg-name">' + this.escapeHtml(name) + '</span>' +
                '<span class="chat-msg-role">' + this.escapeHtml(role) + '</span>' +
                '<span class="chat-msg-time">' + this._getTimeStamp(idx) + '</span></div>' +
                '<div class="chat-msg-text">' + this.escapeHtml(text) + '</div></div>'
            );
            container.appendChild(bubble);
            if (mode === 'handoff') this._handoffTurnIndex = idx + 1;
            else this._delibTurnIndex = idx + 1;
            if (payload.is_final) {
                const endMsg = document.createElement('div');
                endMsg.className = 'chat-flow-status';
                endMsg.textContent = '회의 완료';
                container.appendChild(endMsg);
            }
        },

        _playNextTurn() {
            if (this._turnFlushed || !this._turnQueue.length) { this._turnPlaying = false; return; }
            this._turnPlaying = true;
            const { type, payload } = this._turnQueue.shift();

            if (type === 'deliberation_turn') {
                this._doDeliberationTurn(payload, () => this._playNextTurn());
            } else if (type === 'handoff') {
                this._doHandoffTurn(payload, () => this._playNextTurn());
            } else if (type === 'deliberation_end') {
                this._doDeliberationEnd(payload);
                this._playNextTurn();
            } else {
                this._playNextTurn();
            }
        },

        // 실제 deliberation 턴 렌더링 (콜백 기반)
        _doDeliberationTurn(payload, onDone) {
            const container = this._delibContainer;
            if (!container) { onDone(); return; }
            const name = payload.speaker || '?';
            const role = payload.role || '';
            const text = payload.text || '';
            const isFinal = payload.is_final || false;
            const isMod = (name === '서연');

            this._removeChatTypingBubble(container);

            const bubble = document.createElement('div');
            bubble.className = 'chat-msg-bubble' + (isMod ? ' moderator' : '');
            const turnIdx = this._delibTurnIndex || 0;
            const ts = this._getTimeStamp(turnIdx);
            bubble.innerHTML = _sanitize(
                this._buildAvatarHTML(name, 'deliberation') +
                '<div class="chat-msg-body">' +
                '<div class="chat-msg-meta"><span class="chat-msg-name">' + this.escapeHtml(name) + '</span>' +
                '<span class="chat-msg-role">' + this.escapeHtml(role) + '</span>' +
                '<span class="chat-msg-time">' + ts + '</span></div>' +
                '<div class="chat-msg-text"></div></div>'
            );
            container.appendChild(bubble);
            this._delibTurnIndex = turnIdx + 1;
            this._smartScroll(false);

            const textEl = bubble.querySelector('.chat-msg-text');
            if (textEl) {
                this._typewriterReveal(textEl, text, () => {
                    if (!isFinal) {
                        const nextName = isMod ? '' : '서연';
                        const nextRole = isMod ? '' : 'CSO';
                        this._appendChatTypingBubble(container, nextName, nextRole);
                    }
                    this._smartScroll(false);
                    // 다음 턴 전 1초 대기 (타이핑 느낌)
                    setTimeout(onDone, 1000);
                });
            } else { onDone(); }
        },

        // 실제 deliberation_end 렌더링
        _doDeliberationEnd(payload) {
            const container = this._delibContainer;
            if (!container) return;
            this._removeChatTypingBubble(container);
            const selected = payload.selected_leader || '?';
            const specialty = payload.selected_leader_specialty || '';
            const endMsg = document.createElement('div');
            endMsg.className = 'chat-flow-status';
            endMsg.textContent = '회의 완료';
            container.appendChild(endMsg);
            this._smartScroll(false);
            this._delibContainer = null;
            this._showMiniWaiting(`${selected}(${specialty}) 리더가 답변을 작성합니다`);
        },

        // SSE에서 호출하는 래퍼 (큐에 넣기만)
        _renderDeliberationTurn(payload) { this._enqueueTurn('deliberation_turn', payload); },
        _renderDeliberationEnd(payload) { this._enqueueTurn('deliberation_end', payload); },

        // 스트리밍: deliberation_start
        _renderDeliberationStart(payload) {
            const container = document.createElement('div');
            container.className = 'chat-flow-container';
            container.id = 'delib-live-' + Date.now();
            this._appendChatTypingBubble(container, '서연', 'CSO');
            this.convArea.appendChild(container);
            this._smartScroll(false);
            this._delibContainer = container;
            this._delibTurnIndex = 0;
            this._turnQueue = [];
            this._turnPlaying = false;
            this._turnFlushed = false;
        },

        // 스트리밍: handoff_start
        _renderHandoffStart(payload) {
            if (this._handoffContainer) return;
            const container = document.createElement('div');
            container.className = 'chat-flow-container';
            this._appendChatTypingBubble(container, '서연', 'CSO');
            this.convArea.appendChild(container);
            this._handoffContainer = container;
            this._handoffTurnIndex = 0;
            this._turnQueue = [];
            this._turnPlaying = false;
            this._turnFlushed = false;
            this._smartScroll(false);
        },

        // SSE에서 호출하는 handoff 래퍼 (큐에 넣기만)
        _renderHandoffTurn(payload) { this._enqueueTurn('handoff', payload); },

        // 실제 handoff 턴 렌더링 (콜백 기반)
        _doHandoffTurn(payload, onDone) {
            if (!this._handoffContainer) {
                const container = document.createElement('div');
                container.className = 'chat-flow-container';
                this.convArea.appendChild(container);
                this._handoffContainer = container;
                this._handoffTurnIndex = 0;
            }
            const container = this._handoffContainer;
            const name = payload.speaker || '?';
            const role = payload.role || '';
            const text = payload.text || '';
            const isFinal = payload.is_final || false;
            const isMod = (name === '서연');

            this._removeChatTypingBubble(container);

            const bubble = document.createElement('div');
            bubble.className = 'chat-msg-bubble' + (isMod ? ' moderator' : '');
            const hoTurnIdx = this._handoffTurnIndex || 0;
            const ts = this._getTimeStamp(hoTurnIdx);
            bubble.innerHTML = _sanitize(
                this._buildAvatarHTML(name, 'handoff') +
                '<div class="chat-msg-body">' +
                '<div class="chat-msg-meta"><span class="chat-msg-name">' + this.escapeHtml(name) + '</span>' +
                '<span class="chat-msg-role">' + this.escapeHtml(role) + '</span>' +
                '<span class="chat-msg-time">' + ts + '</span></div>' +
                '<div class="chat-msg-text"></div></div>'
            );
            container.appendChild(bubble);
            this._handoffTurnIndex = hoTurnIdx + 1;
            this._smartScroll(false);

            const textEl = bubble.querySelector('.chat-msg-text');
            if (textEl) {
                this._typewriterReveal(textEl, text, () => {
                    if (!isFinal) {
                        this._appendChatTypingBubble(container, '', '');
                    } else {
                        const endMsg = document.createElement('div');
                        endMsg.className = 'chat-flow-status';
                        endMsg.textContent = '회의 완료';
                        container.appendChild(endMsg);
                        this._showMiniWaiting('답변을 작성합니다');
                    }
                    this._smartScroll(false);
                    setTimeout(onDone, 1000);
                });
            } else { onDone(); }
        },

        // Classic (/ask) 응답의 deliberation 렌더링
        _renderDeliberation(turns) {
            if (!turns || !turns.length) return;
            const container = document.createElement('div');
            container.className = 'chat-flow-container';
            turns.forEach((turn, idx) => {
                const isMod = (turn.speaker === '서연');
                const bubble = document.createElement('div');
                bubble.className = 'chat-msg-bubble' + (isMod ? ' moderator' : '');
                bubble.style.animationDelay = (idx * 0.25) + 's';
                bubble.innerHTML = _sanitize(
                    this._buildAvatarHTML(turn.speaker, 'deliberation') +
                    this._buildBubbleBody(turn.speaker, turn.role || '', turn.text || '', idx)
                );
                container.appendChild(bubble);
            });
            const endMsg = document.createElement('div');
            endMsg.className = 'chat-flow-status';
            endMsg.textContent = '회의 완료';
            container.appendChild(endMsg);
            this.convArea.appendChild(container);
            this._smartScroll(false);
        },

        // Classic (/ask) 응답의 handoff 렌더링
        _renderHandoff(turns) {
            if (!turns || !turns.length) return;
            const container = document.createElement('div');
            container.className = 'chat-flow-container';
            turns.forEach((turn, idx) => {
                const isMod = (turn.speaker === '서연');
                const bubble = document.createElement('div');
                bubble.className = 'chat-msg-bubble' + (isMod ? ' moderator' : '');
                bubble.style.animationDelay = (idx * 0.25) + 's';
                bubble.innerHTML = _sanitize(
                    this._buildAvatarHTML(turn.speaker, 'handoff') +
                    this._buildBubbleBody(turn.speaker, turn.role || '', turn.text || '', idx)
                );
                container.appendChild(bubble);
            });
            const endMsg = document.createElement('div');
            endMsg.className = 'chat-flow-status';
            endMsg.textContent = '회의 완료';
            container.appendChild(endMsg);
            this.convArea.appendChild(container);
            this._smartScroll(false);
        },

        // 채팅 흐름 타이핑 버블 ("이름(역할) 입력 중...")
        _appendChatTypingBubble(container, speakerName, speakerRole) {
            this._removeChatTypingBubble(container);
            const bubble = document.createElement('div');
            bubble.className = 'chat-typing-bubble';
            const label = speakerName ? `${speakerName}${speakerRole ? '(' + speakerRole + ')' : ''} 입력 중` : '입력 중';
            bubble.innerHTML = _sanitize(
                '<div class="chat-typing-dots"><span></span><span></span><span></span></div>' +
                '<span class="chat-typing-label">' + this.escapeHtml(label) + '</span>'
            );
            container.appendChild(bubble);
            this._smartScroll(false);
        },
        _removeChatTypingBubble(container) {
            const el = container.querySelector('.chat-typing-bubble');
            if (el) el.remove();
        },
        _removeChatTypingBubbleAll() {
            document.querySelectorAll('.chat-typing-bubble').forEach(el => el.remove());
        },

        // ═══ 새 대화 시작 ═══
        resetConversation() {
            if (this._scrollHandler) {
                this.convArea.removeEventListener('scroll', this._scrollHandler);
            }
            this.conversationHistory = [];
            this.convArea.innerHTML = '';
            this.lastQuery = null;
            this.lastRawResponse = null;
            this.currentLeader = null;
            this.isFirstQuestion = true;
            try { localStorage.removeItem('lawmadi-chat-history'); } catch(e) {}
            try { localStorage.removeItem('lawmadi-current-leader'); } catch(e) {}
            // 랜딩 화면으로 복귀
            this.convArea.classList.add('hidden');
            this.landingContent.classList.remove('hidden');
            this.userInput.value = '';
            this.userInput.style.height = 'auto';
            this.updateCharCounter();
            this.updateSendBtnState();
            if (this.scrollBottomBtn) {
                this.scrollBottomBtn.classList.remove('visible');
                if (this._scrollHandler) this.convArea.addEventListener('scroll', this._scrollHandler);
            }
        },

        // ═══ 글자 수 카운터 ═══
        updateCharCounter() {
            if (!this.charCounter) return;
            const len = this.userInput.value.length;
            this.charCounter.textContent = `${len}/2000`;
            this.charCounter.classList.toggle('over-limit', len > 2000);
        },

        // ═══ 전송 버튼 상태 ═══
        updateSendBtnState() {
            const empty = this.userInput.value.trim().length === 0 && !this.uploadedFile;
            this.sendBtn.classList.toggle('disabled', empty);
        },

        // ═══ 현재 시각 포맷 ═══
        _formatTime() {
            const now = new Date();
            return now.toLocaleTimeString('ko-KR', { hour: 'numeric', minute: '2-digit', hour12: true });
        },

        // ═══ 사용자 친화적 에러 메시지 ═══
        _friendlyError(error) {
            const msg = error.message || '';
            if (error.name === 'AbortError' || msg.includes('timeout') || msg.includes('abort')) {
                return '응답 시간이 초과되었습니다. 잠시 후 다시 시도해주세요.';
            }
            if (msg.includes('NetworkError') || msg.includes('Failed to fetch') || msg.includes('network')) {
                return '인터넷 연결을 확인해주세요.';
            }
            if (msg.includes('5') && msg.includes('서버')) {
                return '서버가 바쁩니다. 잠시 후 다시 시도해주세요.';
            }
            return msg || '알 수 없는 오류가 발생했습니다.';
        },

        // 대기 메신저 (질문 전송 즉시 서연 CSO 타이핑 버블)
        _showSimpleWaiting() {
            this._hideSimpleWaiting();
            const isLeaderChat = !!this.currentLeader;
            const container = document.createElement('div');
            container.id = 'simple-waiting';
            container.className = 'progress-indicator-container';

            // 리더 1:1 채팅: 담당 리더 아바타 + 타이핑 표시
            if (isLeaderChat) {
                const leaderName = (this.currentLeader && this.currentLeader.name) || '';
                const leaderSpec = (this.currentLeader && this.currentLeader.specialty) || '';
                const avatarSrc = leaderProfileImages[leaderName] || 'images/leaders/L60-madi.jpg';
                container.innerHTML = _sanitize(
                    '<div class="progress-avatar-row">' +
                        '<img class="progress-avatar" src="' + this.escapeHtml(avatarSrc) + '" alt="' + this.escapeHtml(leaderName) + '">' +
                        '<div class="progress-info">' +
                            '<div class="progress-leader-name">' + this.escapeHtml(leaderName) + ' <span class="progress-leader-spec">' + this.escapeHtml(leaderSpec) + '</span></div>' +
                            '<div class="progress-typing-row"><div class="chat-typing-dots"><span></span><span></span><span></span></div><span class="progress-typing-label">입력 중...</span></div>' +
                            '<div class="progress-elapsed" id="progress-elapsed">0초</div>' +
                        '</div>' +
                    '</div>'
                );
            } else {
                // 일반 질문: 유나(CCO) 아바타 + 파이프라인 단계 표시
                container.innerHTML = _sanitize(
                    '<div class="progress-avatar-row">' +
                        '<img class="progress-avatar" src="images/clevel/cco-yuna.jpg" alt="유나">' +
                        '<div class="progress-info">' +
                            '<div class="progress-leader-name">유나 <span class="progress-leader-spec">진행 안내</span></div>' +
                            '<div class="progress-steps" id="progress-steps">' +
                                '<div class="progress-step active" data-step="0"><span class="progress-step-icon">🔍</span> 질문 분석 중...</div>' +
                            '</div>' +
                            '<div class="progress-elapsed" id="progress-elapsed">0초</div>' +
                        '</div>' +
                    '</div>'
                );
            }
            this.convArea.appendChild(container);
            this._smartScroll(true);

            // 경과 시간 카운터
            this._progressStartTime = Date.now();
            this._progressTimer = setInterval(() => {
                const sec = Math.floor((Date.now() - this._progressStartTime) / 1000);
                const el = document.getElementById('progress-elapsed');
                if (el) el.textContent = sec + '초';
            }, 1000);
        },
        _hideSimpleWaiting() {
            if (this._progressTimer) {
                clearInterval(this._progressTimer);
                this._progressTimer = null;
            }
            const el = document.getElementById('simple-waiting');
            if (el) el.remove();
        },

        // progress SSE 이벤트 처리: 실시간 파이프라인 단계 업데이트
        _updateProgress(payload) {
            const stepsEl = document.getElementById('progress-steps');
            if (!stepsEl) return;  // 리더 1:1 채팅 모드에서는 스킵

            const step = payload.step;
            const message = payload.message || '';

            // 기존 active 단계를 done으로 전환
            stepsEl.querySelectorAll('.progress-step.active').forEach(el => {
                el.classList.remove('active');
                el.classList.add('done');
                const icon = el.querySelector('.progress-step-icon');
                if (icon) icon.textContent = '✓';
            });

            // step 0.5: 리더 배정 시 유나 아바타→리더 아바타 교체
            if (step === 0.5 && payload.leader) {
                const avatarEl = document.querySelector('#simple-waiting .progress-avatar');
                const nameEl = document.querySelector('#simple-waiting .progress-leader-name');
                if (avatarEl) {
                    const newSrc = leaderProfileImages[payload.leader] || 'images/leaders/L60-madi.jpg';
                    avatarEl.src = newSrc;
                    avatarEl.alt = payload.leader;
                }
                if (nameEl) {
                    nameEl.innerHTML = _sanitize(this.escapeHtml(payload.leader) + ' <span class="progress-leader-spec">' + this.escapeHtml(payload.leader_specialty || '') + '</span>');
                }
            }

            // 아이콘 매핑
            const icons = { 0: '🔍', 0.5: '👤', 1: '⚖️', 2: '📚', 3: '✍️', 4: '🔎', 5: '📋' };
            const icon = icons[step] || '⏳';

            // 새 단계 추가
            const newStep = document.createElement('div');
            newStep.className = 'progress-step active';
            newStep.dataset.step = step;
            newStep.innerHTML = _sanitize('<span class="progress-step-icon">' + icon + '</span> ' + this.escapeHtml(message));
            stepsEl.appendChild(newStep);
        },

        // 협의 종료 후 답변 대기 미니 인디케이터
        _showMiniWaiting(leaderHint) {
            this._hideMiniWaiting();
            const mini = document.createElement('div');
            mini.id = 'mini-waiting';
            mini.className = 'chat-flow-status writing';
            mini.innerHTML = _sanitize(
                '<div class="chat-typing-dots"><span></span><span></span><span></span></div>' +
                '<span>' + this.escapeHtml(leaderHint || '답변 작성 중...') + '</span>'
            );
            this.convArea.appendChild(mini);
            this._smartScroll(false);
        },
        _hideMiniWaiting() {
            const el = document.getElementById('mini-waiting');
            if (el) el.remove();
        },

        // 타자 효과 (타이핑 느낌)
        _typewriterReveal(element, text, onComplete) {
            element.innerHTML = '';
            element.textContent = '';
            let i = 0;
            const len = text.length;
            const chunkSize = Math.max(1, Math.ceil(len / 30));
            const timer = setInterval(() => {
                i = Math.min(i + chunkSize, len);
                element.textContent = text.substring(0, i);
                this._smartScroll(false);
                if (i >= len) {
                    clearInterval(timer);
                    if (onComplete) onComplete();
                }
            }, 30);
        },

        hideTypingIndicator() {
            this._flushTurnQueue();
            this._hideSimpleWaiting();
            this._hideMiniWaiting();
            this._removeChatTypingBubbleAll();
            const typingDiv = document.getElementById('typing-indicator');
            if (typingDiv) typingDiv.remove();
        },

        // 하위호환: showTypingIndicator → _showSimpleWaiting
        showTypingIndicator() {
            this._showSimpleWaiting();
            return 'simple-waiting';
        }
    };

    // ── 탭 닫기 시 스트림 정리 ──
    window.addEventListener('beforeunload', () => {
        if (UI.currentAbortController) {
            UI.currentAbortController.abort();
            UI.currentAbortController = null;
        }
    });

    window.onload = () => {
        UI.init();


        // ── Mobile Tab Bar ──
        const tabItems = document.querySelectorAll('.tab-item');
        const updateTabAria = (activeTab) => {
            tabItems.forEach(t => { t.classList.remove('active'); t.setAttribute('aria-selected', 'false'); });
            activeTab.classList.add('active');
            activeTab.setAttribute('aria-selected', 'true');
        };
        tabItems.forEach(tab => {
            tab.addEventListener('click', () => {
                const action = tab.dataset.tab;
                // 활성 탭 업데이트
                updateTabAria(tab);

                if (action === 'chat') {
                    window.location.href = '/';
                } else if (action === 'leaders') {
                    window.location.href = '/leaders';
                } else if (action === 'clevel') {
                    window.location.href = '/clevel';
                } else if (action === 'more') {
                    const sheet = document.getElementById('moreSheet');
                    const sheetOverlay = document.getElementById('moreSheetOverlay');
                    if (sheet) {
                        sheet.classList.toggle('active');
                        sheetOverlay.classList.toggle('active');
                    }
                    updateTabAria(document.getElementById('tabChat'));
                    return;
                } else if (action === 'favorites') {
                    UI.toggleFavorites();
                    // 저장 탭은 토글이므로 chat 활성 유지
                    updateTabAria(document.getElementById('tabChat'));
                }
            });
        });
    };

    // Service Worker 정리 (PWA → 홈화면 바로가기 전환)
    // 기존 설치된 SW 캐시 정리 후 해제
    if ('serviceWorker' in navigator) {
        navigator.serviceWorker.getRegistrations().then(function(regs) {
            regs.forEach(function(reg) { reg.unregister(); });
        });
        if (caches) {
            caches.keys().then(function(keys) {
                keys.forEach(function(k) { caches.delete(k); });
            });
        }
    }

// ═══ 랜딩 스크롤 애니메이션 + 카운터 ═══
(function() {
    // IntersectionObserver 스크롤 애니메이션
    const animElements = document.querySelectorAll('.landing-animate');
    if (animElements.length > 0 && 'IntersectionObserver' in window) {
        const obs = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.classList.add('visible');
                    obs.unobserve(entry.target);
                }
            });
        }, { threshold: 0.15 });
        animElements.forEach(el => obs.observe(el));
    } else {
        animElements.forEach(el => el.classList.add('visible'));
    }

    // Hero 숫자 카운트업 애니메이션
    const counters = document.querySelectorAll('.hero-stat-number[data-count]');
    const animateCounter = (el) => {
        const target = parseInt(el.getAttribute('data-count'));
        const suffix = el.getAttribute('data-suffix') || '';
        const duration = 1200;
        const start = performance.now();
        const step = (now) => {
            const progress = Math.min((now - start) / duration, 1);
            const eased = 1 - Math.pow(1 - progress, 3);
            el.textContent = Math.floor(target * eased) + suffix;
            if (progress < 1) requestAnimationFrame(step);
        };
        requestAnimationFrame(step);
    };
    if (counters.length > 0 && 'IntersectionObserver' in window) {
        const counterObs = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    animateCounter(entry.target);
                    counterObs.unobserve(entry.target);
                }
            });
        }, { threshold: 0.5 });
        counters.forEach(el => counterObs.observe(el));
    } else {
        counters.forEach(el => {
            el.textContent = el.getAttribute('data-count') + (el.getAttribute('data-suffix') || '');
        });
    }
})();

// ═══ 홈화면 바로가기 안내 ═══
(function() {
    var promptEl = document.getElementById('installPrompt');
    var dismissBtn = document.getElementById('installDismiss');
    var guideText = document.getElementById('shortcutGuideText');
    if (!promptEl || !dismissBtn) return;

    // 이미 홈화면에서 열린 경우 표시 안 함
    var isStandalone = window.matchMedia('(display-mode: standalone)').matches || navigator.standalone;
    if (isStandalone) return;

    // beforeinstallprompt 차단 (앱 설치 방지)
    window.addEventListener('beforeinstallprompt', function(e) { e.preventDefault(); });

    // 플랫폼별 안내 메시지
    var ua = navigator.userAgent || '';
    var isIOS = /iPad|iPhone|iPod/.test(ua);
    var isAndroid = /Android/i.test(ua);
    var isSamsung = /SamsungBrowser/i.test(ua);
    var isInApp = /KAKAOTALK|FBAN|FBAV|Instagram|Line\/|NAVER|Snapchat|Twitter|SamsungBrowser|Whale|DaumApps|MicroMessenger|Telegram/i.test(ua);

    if (isInApp) {
        // 인앱 브라우저: 외부 브라우저로 열기 안내
        var titleEl = promptEl.querySelector('.install-prompt-title');
        if (titleEl) titleEl.textContent = '외부 브라우저에서 열기';
        if (isIOS) {
            guideText.innerHTML = '우측 하단 <b>···</b> 또는 <b>Safari로 열기</b>를 눌러주세요';
        } else {
            guideText.innerHTML = '우측 상단 <b>⋮</b> → <b>"다른 브라우저로 열기"</b>를 눌러주세요';
        }
        // 인앱에서는 확인 버튼 옆에 "링크 복사" 버튼 추가
        var actionsEl = promptEl.querySelector('.install-prompt-actions');
        if (actionsEl && !document.getElementById('copyLinkBtn')) {
            var copyBtn = document.createElement('button');
            copyBtn.id = 'copyLinkBtn';
            copyBtn.className = 'install-btn install-btn-dismiss';
            copyBtn.textContent = '링크 복사';
            copyBtn.setAttribute('aria-label', '링크 복사');
            actionsEl.insertBefore(copyBtn, dismissBtn);
            copyBtn.addEventListener('click', function() {
                navigator.clipboard.writeText(window.location.href).then(function() {
                    copyBtn.textContent = '복사됨!';
                    setTimeout(function() { copyBtn.textContent = '링크 복사'; }, 2000);
                }).catch(function() {
                    // clipboard API 미지원 시 fallback
                    var ta = document.createElement('textarea');
                    ta.value = window.location.href;
                    ta.style.cssText = 'position:fixed;opacity:0';
                    document.body.appendChild(ta);
                    ta.select();
                    document.execCommand('copy');
                    document.body.removeChild(ta);
                    copyBtn.textContent = '복사됨!';
                    setTimeout(function() { copyBtn.textContent = '링크 복사'; }, 2000);
                });
            });
        }
    } else if (isIOS) {
        guideText.textContent = '하단 공유 버튼(□↑) → "홈 화면에 추가"를 눌러주세요';
    } else if (isSamsung) {
        guideText.textContent = '우측 하단 ≡ 메뉴 → "홈 화면에 추가"를 눌러주세요';
    } else if (isAndroid) {
        guideText.textContent = '우측 상단 ⋮ 메뉴 → "홈 화면에 추가"를 눌러주세요';
    }

    // 이전에 닫은 적이 있으면 7일 후에만 다시 표시 (인앱은 3일)
    var dismissed = localStorage.getItem('shortcut-dismissed');
    var cooldown = isInApp ? 259200000 : 604800000; // 인앱 3일, 일반 7일
    if (dismissed && Date.now() - parseInt(dismissed) < cooldown) return;

    setTimeout(function() { promptEl.classList.add('show'); }, isInApp ? 2000 : 4000);

    dismissBtn.addEventListener('click', function() {
        promptEl.classList.remove('show');
        try { localStorage.setItem('shortcut-dismissed', Date.now().toString()); } catch(e) {}
    });
})();

document.addEventListener('contextmenu', function(e) { e.preventDefault(); });

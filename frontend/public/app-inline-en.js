// XSS sanitizer helper — all API responses pass through this
function _sanitize(html) { if (typeof DOMPurify !== 'undefined') return DOMPurify.sanitize(html, {ADD_ATTR: ['target','data-tooltip']}); var d = document.createElement('div'); d.textContent = html; return d.innerHTML; }

// Mobile & In-app browser viewport fix (모바일 전체 + 인앱 브라우저)
(function() {
    var ua = navigator.userAgent || '';
    var isInApp = /KAKAOTALK|FBAN|FBAV|Instagram|Line\/|NAVER|Snapchat|Twitter|SamsungBrowser|Whale|DaumApps|MicroMessenger|Telegram/i.test(ua);
    var isMobile = /Android|iPhone|iPad|iPod/i.test(ua) || window.innerWidth <= 768;

    if (isInApp) document.body.classList.add('is-inapp-browser');

    if (isInApp || isMobile) {
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

    // Leader Korean → Romanized name mapping (for foreigner-friendly display)
    const leaderRomanNames = {
        '휘율': 'Hwiyul', '보늬': 'Bonui', '담슬': 'Damseul', '아키': 'Aki',
        '연우': 'Yeonwoo', '벼리': 'Byeori', '하늬': 'Hanui', '온유': 'Onyu',
        '한울': 'Hanul', '결휘': 'Gyeolhwi', '오름': 'Oreum', '아슬': 'Aseul',
        '누리': 'Nuri', '다솜': 'Dasom', '별하': 'Byeolha', '슬아': 'Seula',
        '미르': 'Mir', '다온': 'Daon', '슬옹': 'Selong', '찬솔': 'Chansol',
        '휘윤': 'Hwiyun', '무결': 'Mugyeol', '가비': 'Gabi', '도울': 'Doul',
        '강무': 'Gangmu', '루다': 'Ruda', '수림': 'Surim', '해슬': 'Haeseul',
        '라온': 'Raon', '담우': 'Damwoo', '로운': 'Roun', '바름': 'Bareum',
        '별이': 'Byeoli', '지누': 'Jinu', '마루': 'Maru', '단아': 'Dana',
        '예솔': 'Yesol', '슬비': 'Seulbi', '가온': 'Gaon', '한결': 'Hangyeol',
        '산들': 'Sandeul', '하람': 'Haram', '해나': 'Haena', '보람': 'Boram',
        '이룸': 'Ireum', '다올': 'Daol', '새론': 'Saeron', '나래': 'Narae',
        '가람': 'Garam', '빛나': 'Bitna', '소울': 'Soul', '미소': 'Miso',
        '늘솔': 'Neulsol', '이서': 'Iseo', '윤빛': 'Yunbit', '다인': 'Dain',
        '세움': 'Seum', '예온': 'Yeon', '한빛': 'Hanbit', '마디': 'Madi',
        '서연': 'Seoyeon', '지유': 'Jiyu', '유나': 'Yuna',
    };

    // Leader specialty mapping
    const leaderSpecialties = {
        '휘율': 'Civil Law', '보늬': 'Real Estate Law', '담슬': 'Construction Law', '아키': 'Redevelopment',
        '연우': 'Medical Law', '벼리': 'Damages', '하늬': 'Traffic Accidents', '온유': 'Lease',
        '한울': 'Government Contracts', '결휘': 'Civil Enforcement', '오름': 'Debt Collection', '아슬': 'Registration & Auction',
        '누리': 'Commercial Law', '다솜': 'Corporate & M&A', '별하': 'Startups', '슬아': 'Insurance',
        '미르': 'International Trade', '다온': 'Energy & Resources', '슬옹': 'Maritime & Aviation', '찬솔': 'Tax & Finance',
        '휘윤': 'IT & Security', '무결': 'Criminal Law', '가비': 'Entertainment', '도울': 'Tax Disputes',
        '강무': 'Military Law', '루다': 'Intellectual Property', '수림': 'Environmental Law', '해슬': 'Trade & Customs',
        '라온': 'Gaming & Content', '담우': 'Labor Law', '로운': 'Administrative Law', '바름': 'Fair Trade',
        '별이': 'Aerospace', '지누': 'Privacy', '마루': 'Constitutional Law', '단아': 'Culture & Religion',
        '예솔': 'Juvenile Law', '슬비': 'Consumer', '가온': 'Telecommunications', '한결': 'Human Rights',
        '산들': 'Divorce & Family', '하람': 'Copyright', '해나': 'Industrial Accidents', '보람': 'Social Welfare',
        '이룸': 'Education & Youth', '다올': 'Insurance & Pension', '새론': 'Venture & Innovation', '나래': 'Culture & Arts',
        '가람': 'Food & Health', '빛나': 'Multicultural & Immigration', '소울': 'Religion & Tradition', '미소': 'Advertising & Media',
        '늘솔': 'Agriculture & Livestock', '이서': 'Maritime & Fisheries', '윤빛': 'Science & Tech', '다인': 'Disability & Welfare',
        '세움': 'Inheritance & Trust', '예온': 'Sports & Leisure', '한빛': 'Data & Tech Ethics', '마디': 'System Director',
        '서연': 'Strategic Planning', '지유': 'Technical Verification', '유나': 'Content Design',
    };

    const UI = {
        sidebar: document.getElementById('sidebar'),
        overlay: document.getElementById('overlay'),
        menuToggle: document.getElementById('menuToggle'),
        userInput: document.getElementById('userInput'),
        sendBtn: document.getElementById('sendBtn'),
        startChatBtn: document.getElementById('startChatBtn'),
        landingContent: document.getElementById('landing-content'),
        convArea: document.getElementById('conversation-area'),
        uploadBtn: document.getElementById('uploadBtn'),
        fileInput: document.getElementById('fileInput'),
        uploadedFilePreview: document.getElementById('uploadedFilePreview'),
        uploadedFileName: document.getElementById('uploadedFileName'),
        uploadedFileSize: document.getElementById('uploadedFileSize'),
        removeFileBtn: document.getElementById('removeFileBtn'),
        favoritesPanel: document.getElementById('favoritesPanel'),
        favoritesList: document.getElementById('favoritesList'),
        scrollBottomBtn: document.getElementById('scrollBottomBtn'),
        charCounter: document.getElementById('charCounter'),
        newChatBtn: document.getElementById('newChatBtn'),
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
        currentAbortController: null,  // AbortController (항목 #12)
        currentLeader: null,  // {name, specialty} — current assigned leader
        isFirstQuestion: true,  // first question flag

        init() {
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

            this.sendBtn.onclick = () => this.dispatchPacket();
            this.userInput.onkeydown = (e) => {
                if(e.key === 'Enter' && !e.shiftKey) {
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
                    this.userInput.value = `Hello ${name}, please introduce yourself.`;
                    this.switchToChatMode();
                    this.dispatchPacket();
                };
                card.onclick = handler;
                card.onkeydown = (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); handler(); } };
            });

            this.initVisitorTracking();

            // v60: File upload (coming soon)
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
                    if (label) label.textContent = 'Light Mode';
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
                document.addEventListener('click', (e) => {
                    if (!moreMenuDropdown.contains(e.target) && e.target !== moreMenuBtn) {
                        moreMenuDropdown.style.display = 'none';
                        moreMenuBtn.setAttribute('aria-expanded', 'false');
                    }
                });
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
                this.convArea.addEventListener('scroll', () => {
                    const show = !this._isNearBottom() && !this.convArea.classList.contains('hidden');
                    this.scrollBottomBtn.classList.toggle('visible', show);
                });
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
            if (premiumCta) premiumCta.addEventListener('click', () => alert('Premium service is coming soon!'));
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
                // Whitelist validation: only allow registered leader names
                const allowedLeaders = new Set(['서연','지유','유나','휘율','보늬','담슬','아키','연우','벼리','하늬','온유','한울','결휘','오름','아슬','누리','다솜','별하','슬아','미르','다온','슬옹','찬솔','휘윤','무결','가비','도울','강무','루다','수림','해슬','라온','담우','로운','바름','별이','지누','마루','단아','예솔','슬비','가온','한결','산들','하람','해나','보람','이룸','다올','새론','나래','가람','빛나','소울','미소','늘솔','이서','윤빛','다인','세움','예온','한빛','마디']);
                if (!allowedLeaders.has(leaderParam)) return;
                const clevelTitles = { '서연': 'CSO', '지유': 'CTO', '유나': 'CCO' };
                const title = clevelTitles[leaderParam];
                const romanName = leaderRomanNames[leaderParam] || leaderParam;
                const honorific = title ? `${romanName} (${title})` : romanName;
                // 페이지 로드 완료 후 실행 (네트워크 안정화 대기)
                setTimeout(() => {
                    this.userInput.value = `Hello ${honorific}, please introduce yourself.`;
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
            localStorage.setItem('lawmadi-dark-mode', this.darkMode);
            const darkToggle = document.getElementById('darkToggle');
            if (darkToggle) darkToggle.setAttribute('aria-pressed', this.darkMode);
            const icon = document.querySelector('#darkToggle .material-symbols-outlined');
            if (icon) icon.textContent = this.darkMode ? 'light_mode' : 'dark_mode';
            const label = darkToggle ? darkToggle.querySelectorAll('span')[1] : null;
            if (label) label.textContent = this.darkMode ? 'Light Mode' : 'Dark Mode';
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
                alert('Please enter your name and contact.');
                return false;
            }
            if (!summary) {
                alert('Please enter consultation details.');
                return false;
            }
            // Phone validation
            const phoneClean = phone.replace(/[^0-9]/g, '');
            if (phoneClean.length < 10 || phoneClean.length > 11) {
                alert('Please enter a valid phone number.');
                return false;
            }

            const consent = document.getElementById('lawyerPrivacyConsent');
            if (!consent || !consent.checked) {
                alert('Please consent to the collection and use of personal information.');
                return false;
            }

            const submitBtn = document.querySelector('#lawyerFormView button[type="submit"], #lawyerFormView .lawyer-submit-btn');
            if (submitBtn) {
                submitBtn.disabled = true;
                submitBtn.textContent = 'Submitting...';
            }

            try {
                const res = await fetch('/api/lawyer-inquiry', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    credentials: 'include',
                    body: JSON.stringify({ name, phone: phoneClean, query_summary: summary, leader })
                });
                if (!res.ok) throw new Error('Submission failed');

                // Switch to success view
                const formView = document.getElementById('lawyerFormView');
                const successView = document.getElementById('lawyerSuccessView');
                if (formView) formView.style.display = 'none';
                if (successView) successView.style.display = 'block';
            } catch (err) {
                alert('Failed to submit. Please try again.');
                console.error('Lawyer inquiry failed:', err);
            } finally {
                if (submitBtn) {
                    submitBtn.disabled = false;
                    submitBtn.textContent = 'Submit';
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
                date: new Date().toLocaleDateString('en-US')
            });
            if (favs.length > 50) favs.pop();
            localStorage.setItem('lawmadi-favorites', JSON.stringify(favs));
        },

        deleteFavorite(id) {
            let favs = JSON.parse(localStorage.getItem('lawmadi-favorites') || '[]');
            favs = favs.filter(f => f.id !== id);
            localStorage.setItem('lawmadi-favorites', JSON.stringify(favs));
            this.renderFavorites();
        },

        renderFavorites() {
            const list = this.favoritesList;
            if (!list) return;
            const favs = JSON.parse(localStorage.getItem('lawmadi-favorites') || '[]');
            if (favs.length === 0) {
                list.innerHTML = '<div class="fav-empty">No saved answers yet.</div>';
                return;
            }
            list.innerHTML = favs.map(f => `
                <div class="fav-item" data-id="${this.escapeHtml(f.id)}">
                    <button class="fav-delete" data-fav-id="${this.escapeHtml(f.id)}" aria-label="Delete: ${this.escapeHtml(f.query).substring(0, 30)}">Delete</button>
                    <div class="fav-query">${this.escapeHtml(f.query)}</div>
                    <div class="fav-preview">${this.escapeHtml(f.response).substring(0, 100)}...</div>
                    <div class="fav-date">${this.escapeHtml(f.date || '')}</div>
                </div>
            `).join('');

            list.querySelectorAll('.fav-delete').forEach(btn => {
                btn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    UI.deleteFavorite(parseInt(btn.dataset.favId));
                });
            });

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
                alert(`File size is too large. Maximum ${maxSize / 1024 / 1024}MB allowed.`);
                return;
            }

            const allowedTypes = ['image/jpeg', 'image/jpg', 'image/png', 'image/webp', 'application/pdf'];
            if (!allowedTypes.includes(file.type)) {
                alert('Unsupported file format. Only JPG, PNG, WEBP, and PDF files are allowed.');
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
            toast.style.cssText = 'position:fixed;bottom:100px;left:50%;transform:translateX(-50%);background:linear-gradient(135deg,#1e293b,#334155);color:#f1f5f9;padding:16px 28px;border-radius:14px;border:1px solid rgba(139,92,246,0.4);box-shadow:0 8px 32px rgba(0,0,0,0.3);z-index:9999;display:flex;align-items:center;gap:12px;font-size:0.95rem;font-weight:600;animation:expertFadeIn 0.3s ease;max-width:90vw;';
            toast.innerHTML = '<span class="material-symbols-outlined" style="color:#8b5cf6;font-size:1.5rem;">upload_file</span><div><div>File Upload — <span style="color:#f59e0b;">Coming Soon</span></div><div style="font-size:0.8rem;font-weight:400;color:#94a3b8;margin-top:4px;">Max 1MB · JPG, PNG, WEBP, PDF supported</div></div>';
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
                console.error('Visitor tracking failed:', error);
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
                    if (todayEl) todayEl.textContent = 'Loading';
                    if (totalEl) totalEl.textContent = 'Loading';
                }
            } catch (error) {
                console.error('Stats loading failed:', error);
                if (todayEl) todayEl.textContent = 'Loading';
                if (totalEl) totalEl.textContent = 'Loading';
            }
        },

        animateNumber(element, target) {
            if (target === 0) {
                element.textContent = '0';
                return;
            }
            let current = 0;
            const increment = target / 50;
            const timer = setInterval(() => {
                current += increment;
                if (current >= target) {
                    element.textContent = target.toLocaleString();
                    clearInterval(timer);
                } else {
                    element.textContent = Math.floor(current).toLocaleString();
                }
            }, 20);
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
            const query = retryCount > 0 ? this.lastQuery : this.userInput.value.trim();
            const hasFile = this.uploadedFile !== null;

            if (!query && !hasFile) return;

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
            this.showTypingIndicator();

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
                    // Request was cancelled
                    return;
                }

                // 서버 에러 (event: error)는 재시도 없이 바로 표시
                if (error._serverError) {
                    this.appendMessage('ai', `
                        <div style="color: #ef4444;">
                            <p><strong>${this.escapeHtml(error.message)}</strong></p>
                            <button class="retry-btn" data-action="retry">
                                <span class="material-symbols-outlined" style="font-size: 16px;">refresh</span>
                                Retry
                            </button>
                        </div>
                    `);
                    return;
                }

                // Network errors only - auto retry
                if (retryCount < this.MAX_RETRY) {
                    const waitSec = (retryCount + 1) * 2;
                    this.appendMessage('ai', `<p style="color: #f59e0b;">Network error. Auto-retrying in ${waitSec} seconds... (${retryCount + 1}/${this.MAX_RETRY})</p>`);
                    await new Promise(r => setTimeout(r, waitSec * 1000));
                    // Remove retry message
                    const lastMsg = this.convArea.lastElementChild;
                    if (lastMsg && lastMsg.classList.contains('ai-msg')) lastMsg.remove();
                    return this.dispatchPacket(retryCount + 1);
                }

                // Final failure: user-friendly error message + retry button
                const friendlyMsg = this._friendlyError(error);
                this.appendMessage('ai', `
                    <div style="color: #ef4444;">
                        <p><strong>${this.escapeHtml(friendlyMsg)}</strong></p>
                        <button class="retry-btn" data-action="retry">
                            <span class="material-symbols-outlined" style="font-size: 16px;">refresh</span>
                            Retry
                        </button>
                    </div>
                `);
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
                    lang: 'en',
                    current_leader: this.currentLeader,
                    is_first_question: this.isFirstQuestion
                }),
                signal: this.currentAbortController.signal
            });

            clearTimeout(timeoutId);
            if (response.status === 429) {
                this.hideTypingIndicator();
                var limitMsg = '<p>Daily free limit reached.</p>'
                    + '<p style="margin-top:8px;"><a href="/pricing-en" style="color:#2563eb;font-weight:700;text-decoration:underline;">Buy credits</a> to continue using Lawmadi OS.</p>';
                if (window.__lawmadiAuth && !window.__lawmadiAuth.authenticated) {
                    limitMsg += '<p style="margin-top:4px;font-size:0.9em;color:#64748b;">Already purchased? Click <strong>Login</strong> in the header.</p>';
                }
                try {
                    const errData = await response.json();
                    if (errData.error) limitMsg = `<p>${this.escapeHtml(errData.error)}</p>`;
                } catch {}
                this.appendMessage('ai', limitMsg);
                return;
            }
            if (!response.ok) throw new Error(`Server error (${response.status})`);
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
                    lang: 'en',
                    current_leader: this.currentLeader,
                    is_first_question: this.isFirstQuestion
                }),
                signal: this.currentAbortController.signal
            });

            clearTimeout(timeoutId);
            if (response.status === 429) {
                this.hideTypingIndicator();
                var limitMsg = '<p>Daily free limit reached.</p>'
                    + '<p style="margin-top:8px;"><a href="/pricing-en" style="color:#2563eb;font-weight:700;text-decoration:underline;">Buy credits</a> to continue using Lawmadi OS.</p>';
                if (window.__lawmadiAuth && !window.__lawmadiAuth.authenticated) {
                    limitMsg += '<p style="margin-top:4px;font-size:0.9em;color:#64748b;">Already purchased? Click <strong>Login</strong> in the header.</p>';
                }
                try {
                    const errData = await response.json();
                    if (errData.error) limitMsg = `<p>${this.escapeHtml(errData.error)}</p>`;
                } catch {}
                this.appendMessage('ai', limitMsg);
                return;
            }
            if (!response.ok) throw new Error(`Server error (${response.status})`);

            // 협의/인수인계 임시 상태 초기화
            this._delibContainer = null;
            this._delibTurnIndex = 0;
            this._handoffContainer = null;
            this._handoffTurnIndex = 0;

            // Streaming message container (고유 ID로 충돌 방지)
            // 첫 chunk 도착 시에만 DOM에 추가하여 이중 박스 방지
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

            const _statusLabels = {
                'detecting_domain': '🔍 Analyzing question...',
                'searching_laws': '⚖️ Searching laws & precedents...',
                'analyzing': '✍️ Generating response...',
                'parallel_analysis': '👥 Multi-leader parallel analysis...',
                'verifying': '🔎 Cross-verifying...',
                'synthesizing': '📝 Generating comprehensive response...'
            };

            const _statusToStep = {
                'searching_laws': 'step-3',
                'analyzing': 'step-4',
                'verifying': 'step-5',
            };

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

            try {
                while (true) {
                    const { done, value } = await reader.read();
                    if (done) break;

                    buffer += decoder.decode(value, { stream: true });

                    // SSE 파싱: 이벤트는 빈 줄(\n\n)로 구분
                    const events = buffer.split('\n\n');
                    buffer = events.pop() || ''; // 마지막 불완전 이벤트는 버퍼에 유지

                    for (const rawEvent of events) {
                        if (!rawEvent.trim()) continue;

                        const { eventType, eventData } = _parseSSE(rawEvent);
                        if (!eventData) continue;

                        let payload;
                        try { payload = JSON.parse(eventData); } catch(e) {
                            console.warn('[SSE] JSON parse failed:', eventData.slice(0, 100));
                            continue;
                        }

                        if (eventType === 'deliberation_start') {
                            this._renderDeliberationStart(payload);

                        } else if (eventType === 'deliberation_turn') {
                            this._renderDeliberationTurn(payload);

                        } else if (eventType === 'deliberation_end') {
                            this._renderDeliberationEnd(payload);

                        } else if (eventType === 'handoff') {
                            this._renderHandoffTurn(payload);

                        } else if (eventType === 'status') {
                            const stepKey = payload.step || '';
                            const statusText = _statusLabels[stepKey] || stepKey;
                            const leaderInfo = payload.leader ? ` (${leaderRomanNames[payload.leader] || payload.leader})` : '';
                            const targetStepId = _statusToStep[stepKey];
                            if (targetStepId) {
                                this._advanceTypingStep(targetStepId);
                            }
                            this._updateTypingStatus(statusText + leaderInfo);

                        } else if (eventType === 'chunk') {
                            if (!accumulatedText) {
                                this.hideTypingIndicator();
                                if (!streamDivAttached) {
                                    this.convArea.appendChild(streamDiv);
                                    streamDivAttached = true;
                                }
                            }
                            accumulatedText += (payload.text || '');
                            if (!this._chunkRafPending) {
                                this._chunkRafPending = true;
                                requestAnimationFrame(() => {
                                    streamContent.innerHTML = _sanitize(this._renderStreamingText(accumulatedText));
                                    this._smartScroll(false);
                                    this._chunkRafPending = false;
                                });
                            }

                        } else if (eventType === 'done') {
                            leaderName = payload.leader || '';
                            leaderSpecialty = payload.leader_specialty || payload.specialty || '';
                            fullTextFromServer = payload.response || payload.full_text || accumulatedText;
                            if (payload.current_leader) {
                                this.currentLeader = payload.current_leader;
                                this.isFirstQuestion = false;
                                try { localStorage.setItem('lawmadi-current-leader', JSON.stringify(payload.current_leader)); } catch(e) {}
                            }

                        } else if (eventType === 'error') {
                            this.hideTypingIndicator();
                            streamDiv.remove();
                            const serverErr = new Error(payload.message || 'Streaming error');
                            serverErr._serverError = true;
                            throw serverErr;
                        }
                    }
                }

                // 스트림 종료 후 버퍼에 남은 이벤트 처리
                if (buffer.trim()) {
                    const { eventType, eventData } = _parseSSE(buffer);
                    if (eventData) {
                        try {
                            const payload = JSON.parse(eventData);
                            if (eventType === 'chunk') {
                                accumulatedText += (payload.text || '');
                            } else if (eventType === 'done') {
                                leaderName = payload.leader || '';
                                leaderSpecialty = payload.leader_specialty || payload.specialty || '';
                                fullTextFromServer = payload.response || payload.full_text || accumulatedText;
                            }
                        } catch(e) { /* 무시 */ }
                    }
                }
            } catch (streamError) {
                // reader 리소스 정리
                try { reader.cancel(); } catch(e) { /* 무시 */ }
                // 스트리밍 div 정리 (아직 DOM에 있으면)
                const el = document.getElementById(streamId);
                if (el) el.remove();
                throw streamError;  // 상위 catch에서 처리
            }

            // 스트리밍 완료 → 최종 포맷 렌더링
            this.hideTypingIndicator();
            const finalText = fullTextFromServer || accumulatedText;
            streamDiv.remove();

            // 빈 응답 방어
            if (!finalText.trim()) {
                throw new Error('No response received from server.');
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

        // ═══ Leader Deliberation Rendering — Premium UI ═══
        _getLeaderAvatar(name) {
            return leaderProfileImages[name] || 'images/leaders/L60-madi.jpg';
        },

        _getTimeStamp() {
            const now = new Date();
            return String(now.getHours()).padStart(2,'0') + ':' + String(now.getMinutes()).padStart(2,'0');
        },

        _buildAvatarHTML(name, context) {
            return `<div class="delib-avatar-wrap"><img class="delib-avatar" src="${this._getLeaderAvatar(name)}" alt="${this.escapeHtml(name)}"></div>`;
        },

        _buildBubbleBody(name, role, text) {
            const ts = this._getTimeStamp();
            return `<div class="delib-body">` +
                `<div class="delib-meta-row"><span class="delib-name">${this.escapeHtml(name)}</span>` +
                `<span class="delib-role">${this.escapeHtml(role)}</span>` +
                `<span class="delib-time">${ts}</span></div>` +
                `<div class="delib-text">${this.escapeHtml(text)}</div></div>`;
        },

        _buildHandoffArrow() {
            return '<div class="handoff-arrow">' +
                '<div class="handoff-arrow-line"></div>' +
                '<svg class="handoff-arrow-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14"/><path d="m12 5 7 7-7 7"/></svg>' +
                '<div class="handoff-arrow-line"></div>' +
                '</div>';
        },

        // Streaming: deliberation_start event
        _renderDeliberationStart(payload) {
            const container = document.createElement('div');
            container.className = 'deliberation-container';
            container.id = 'delib-live-' + Date.now();
            const leaders = payload.leaders || [];
            const count = leaders.filter(l => l.name !== 'Seoyeon' && l.name !== '서연').length;
            container.innerHTML = _sanitize(
                `<div class="delib-header">` +
                `<span class="delib-header-dot"></span>` +
                `<span>Meeting in progress — Seoyeon (CSO) presiding</span>` +
                (count > 1 ? `<span class="delib-header-count">${count} attending</span>` : ``) +
                `</div>`
            );
            this._appendDelibTypingIndicator(container, 'Seoyeon');
            this.convArea.appendChild(container);
            this._smartScroll(false);
            this._delibContainer = container;
            this._delibTurnIndex = 0;
        },

        // Streaming: deliberation_turn event
        _renderDeliberationTurn(payload) {
            const container = this._delibContainer;
            if (!container) return;
            const name = payload.speaker || '?';
            const role = payload.role || '';
            const text = payload.text || '';
            const isFinal = payload.is_final || false;
            const isMod = (name === 'Seoyeon' || name === '서연');

            this._removeDelibTypingIndicator(container);

            const bubble = document.createElement('div');
            bubble.className = 'deliberation-bubble' + (isMod ? ' moderator' : '') + (isFinal ? ' final-selection' : '');
            bubble.innerHTML = _sanitize(
                this._buildAvatarHTML(name, 'deliberation') +
                this._buildBubbleBody(name, role, text)
            );
            container.appendChild(bubble);
            this._delibTurnIndex = (this._delibTurnIndex || 0) + 1;

            if (!isFinal) {
                const nextSpeaker = isMod ? '' : 'Seoyeon';
                this._appendDelibTypingIndicator(container, nextSpeaker);
            }
            this._smartScroll(false);
        },

        // Streaming: deliberation_end event
        _renderDeliberationEnd(payload) {
            const container = this._delibContainer;
            if (!container) return;
            this._removeDelibTypingIndicator(container);
            const selected = payload.selected_leader || '?';
            const specialty = payload.selected_leader_specialty || '';
            const summary = document.createElement('div');
            summary.className = 'delib-conclusion';
            summary.textContent = `${selected} (${specialty}) has been assigned as your leader`;
            container.appendChild(summary);
            this._smartScroll(false);
            this._delibContainer = null;
        },

        // Streaming: handoff event (per turn, 6-turn CSO-moderated)
        _renderHandoffTurn(payload) {
            if (!this._handoffContainer) {
                const container = document.createElement('div');
                container.className = 'handoff-container';
                container.innerHTML = _sanitize(
                    '<div class="handoff-header">' +
                    '<span class="delib-header-dot"></span>' +
                    '<span>Leader Handoff — Seoyeon (CSO) presiding</span>' +
                    '</div>'
                );
                this.convArea.appendChild(container);
                this._handoffContainer = container;
                this._handoffTurnIndex = 0;
            }
            const container = this._handoffContainer;
            const name = payload.speaker || '?';
            const role = payload.role || '';
            const text = payload.text || '';
            const isFinal = payload.is_final || false;
            const isMod = (name === 'Seoyeon' || name === '서연');

            this._removeDelibTypingIndicator(container);

            const bubble = document.createElement('div');
            bubble.className = 'handoff-bubble' + (isMod ? ' moderator' : '') + (isFinal ? ' final-selection' : '');
            bubble.innerHTML = _sanitize(
                this._buildAvatarHTML(name, 'handoff') +
                this._buildBubbleBody(name, role, text)
            );
            container.appendChild(bubble);
            this._handoffTurnIndex = (this._handoffTurnIndex || 0) + 1;

            if (!isFinal) {
                this._appendDelibTypingIndicator(container, '');
            }
            this._smartScroll(false);
        },

        // Classic (/ask) deliberation rendering
        _renderDeliberation(turns) {
            if (!turns || !turns.length) return;
            const container = document.createElement('div');
            container.className = 'deliberation-container';
            const names = [...new Set(turns.map(t => t.speaker))].filter(n => n !== 'Seoyeon' && n !== '서연');
            container.innerHTML = _sanitize(
                `<div class="delib-header">` +
                `<span class="delib-header-dot"></span>` +
                `<span>Meeting in progress — Seoyeon (CSO) presiding</span>` +
                (names.length > 1 ? `<span class="delib-header-count">${names.length} attending</span>` : ``) +
                `</div>`
            );
            turns.forEach((turn, idx) => {
                const isMod = (turn.speaker === 'Seoyeon' || turn.speaker === '서연');
                const isFinal = turn.is_final || false;
                const bubble = document.createElement('div');
                bubble.className = 'deliberation-bubble' + (isMod ? ' moderator' : '') + (isFinal ? ' final-selection' : '');
                bubble.style.animationDelay = (idx * 0.25) + 's';
                bubble.innerHTML = _sanitize(
                    this._buildAvatarHTML(turn.speaker, 'deliberation') +
                    this._buildBubbleBody(turn.speaker, turn.role || '', turn.text || '')
                );
                container.appendChild(bubble);
            });
            this.convArea.appendChild(container);
            this._smartScroll(false);
        },

        // Classic (/ask) handoff rendering (6-turn CSO-moderated)
        _renderHandoff(turns) {
            if (!turns || !turns.length) return;
            const container = document.createElement('div');
            container.className = 'handoff-container';
            container.innerHTML = _sanitize(
                '<div class="handoff-header">' +
                '<span class="delib-header-dot"></span>' +
                '<span>Leader Handoff — Seoyeon (CSO) presiding</span>' +
                '</div>'
            );
            turns.forEach((turn, idx) => {
                const isMod = (turn.speaker === 'Seoyeon' || turn.speaker === '서연');
                const isFinal = turn.is_final || false;
                const bubble = document.createElement('div');
                bubble.className = 'handoff-bubble' + (isMod ? ' moderator' : '') + (isFinal ? ' final-selection' : '');
                bubble.style.animationDelay = (idx * 0.25) + 's';
                bubble.innerHTML = _sanitize(
                    this._buildAvatarHTML(turn.speaker, 'handoff') +
                    this._buildBubbleBody(turn.speaker, turn.role || '', turn.text || '')
                );
                container.appendChild(bubble);
            });
            this.convArea.appendChild(container);
            this._smartScroll(false);
        },

        // Deliberation typing indicator helpers
        _appendDelibTypingIndicator(container, speakerHint) {
            const indicator = document.createElement('div');
            indicator.className = 'delib-typing-indicator';
            const label = speakerHint ? `${speakerHint} is typing` : 'typing';
            indicator.innerHTML = _sanitize(
                `<div class="delib-typing-dots"><span></span><span></span><span></span></div>` +
                `<span>${label}</span>`
            );
            container.appendChild(indicator);
            this._smartScroll(false);
        },
        _removeDelibTypingIndicator(container) {
            const existing = container.querySelector('.delib-typing-indicator');
            if (existing) existing.remove();
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
            statusDiv.innerHTML = '<p>📤 <b>Uploading file...</b> (1/2)</p>';
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
                    const errorData = await uploadResponse.json();
                    throw new Error(errorData.detail || 'File upload failed');
                }

                const uploadData = await uploadResponse.json();

                this.updateMessage(statusId, '<p>🔍 <b>Analyzing document...</b> (2/2)</p><p>Analyzing the document from a legal perspective...</p>');

                const analysisType = this.detectAnalysisType(file.name, additionalQuery);

                const analyzeResponse = await fetch(`${this.BASE_URL}/analyze-document/${uploadData.file_id}?analysis_type=${analysisType}`, {
                    method: 'POST'
                });

                if (!analyzeResponse.ok) {
                    const errorData = await analyzeResponse.json();
                    throw new Error(errorData.detail || 'Document analysis failed');
                }

                const analyzeData = await analyzeResponse.json();

                const resultHtml = this.formatDocumentAnalysis(analyzeData.analysis, file.name);
                this.updateMessage(statusId, resultHtml);
                this.clearUploadedFile();

            } catch (error) {
                console.error('File processing error:', error);
                this.updateMessage(statusId, `<div style='color:red;'>Error during file processing: ${this.escapeHtml(error.message)}</div>`);
                this.clearUploadedFile();
            }
        },

        detectAnalysisType(filename, query) {
            const lowerFilename = filename.toLowerCase();
            const lowerQuery = (query || '').toLowerCase();

            if (lowerFilename.includes('contract') || lowerFilename.includes('agreement') || lowerFilename.includes('계약') || lowerQuery.includes('contract') || lowerQuery.includes('계약')) {
                return 'contract';
            }
            if (lowerQuery.includes('risk') || lowerQuery.includes('danger') || lowerQuery.includes('위험') || lowerQuery.includes('리스크')) {
                return 'risk_assessment';
            }
            return 'general';
        },

        formatDocumentAnalysis(analysis, filename) {
            const esc = (s) => this.escapeHtml(String(s || ''));
            let html = `<h3>📄 Document Analysis Results: ${esc(filename)}</h3>`;

            if (analysis.summary) {
                html += `<h3>Summary</h3><p>${esc(analysis.summary)}</p>`;
            }

            if (analysis.document_type || analysis.contract_type) {
                const docType = analysis.document_type || analysis.contract_type;
                html += `<p><strong>📋 Document Type:</strong> ${esc(docType)}</p>`;
            }

            if (analysis.risk_level) {
                const riskEmoji = { 'low': '🟢', 'medium': '🟡', 'high': '🟠', 'critical': '🔴' }[analysis.risk_level] || '⚪';
                const riskText = { 'low': 'Low', 'medium': 'Medium', 'high': 'High', 'critical': 'Critical' }[analysis.risk_level] || esc(analysis.risk_level);
                html += `<p><strong>Risk Level:</strong> ${riskEmoji} ${riskText}</p>`;
            }

            if (analysis.legal_category) {
                html += `<p><strong>Legal Area:</strong> ${esc(analysis.legal_category)}</p>`;
            }

            if (analysis.legal_issues && analysis.legal_issues.length > 0) {
                html += `<h3>Legal Issues</h3><ul>`;
                analysis.legal_issues.forEach(issue => { html += `<li>${esc(issue)}</li>`; });
                html += `</ul>`;
            }

            if (analysis.key_terms && analysis.key_terms.length > 0) {
                html += `<h3>📋 Key Terms</h3>`;
                analysis.key_terms.forEach((term, idx) => {
                    html += `<p><strong>${idx + 1}. ${esc(term.term)}</strong></p><p>${esc(term.content)}</p>`;
                    if (term.issue) html += `<p style="color: #f59e0b;">${esc(term.issue)}</p>`;
                });
            }

            if (analysis.key_points && analysis.key_points.length > 0) {
                html += `<h3>Key Points</h3><ul>`;
                analysis.key_points.forEach(point => { html += `<li>${esc(point)}</li>`; });
                html += `</ul>`;
            }

            if (analysis.recommendations && analysis.recommendations.length > 0) {
                html += `<h3>Recommendations</h3><ul>`;
                analysis.recommendations.forEach(rec => { html += `<li>${esc(rec)}</li>`; });
                html += `</ul>`;
            }

            html += `<p style="margin-top: 24px; padding-top: 16px; border-top: 2px solid var(--border); color: var(--text-muted); font-size: 0.9rem;">
                This analysis was automatically generated by Lawmadi OS. Please consult a legal professional for final decisions.
            </p>`;

            return html;
        },

        // ═══ 마크다운 렌더링 (코드블록 지원 추가) ═══
        formatReport(text) {
            if (!text) return "No response data received.";

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
                    const tagText = tagEnd > 0 ? trimmed.substring(1, tagEnd) : 'Madi Analysis';
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
            // Law citation highlight: Korean "민법 제750조" + English "Article 750" patterns
            result = result.replace(/((?:[가-힣]+\s)?제\d+조(?:의\d+)?(?:\s제\d+항)?(?:\s제\d+호)?)/g, '<span class="law-cite-chip">$1</span>');
            result = result.replace(/(Article\s+\d+(?:-\d+)?(?:\s+(?:Paragraph|Section|Item)\s+\d+)?)/gi, '<span class="law-cite-chip">$1</span>');
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
                    const romanName = leaderRomanNames[name] || name;
                    const safeRoman = this.escapeHtml(romanName);
                    const displayName = clevelTitles[name] ? `${safeRoman} (${clevelTitles[name]})` : safeRoman;
                    const specialty = serverSpecialties[idx] || leaderSpecialties[name] || '';
                    const specialtyHtml = specialty ? `<span class="leader-specialty">${this.escapeHtml(specialty)}</span>` : '';
                    const infoHtml = `<div class="leader-info"><span class="leader-name">${displayName}</span>${specialtyHtml}</div>`;
                    if (imgPath) {
                        return `<div class="leader-avatar-item"><img src="${imgPath}" alt="${safeRoman}">${infoHtml}</div>`;
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
                    const romanLeaderName = leaderName.split(',').map(n => leaderRomanNames[n.trim()] || n.trim()).join(', ');
                    let summaryHtml = `<span class="summary-badge"><span class="material-symbols-outlined">person</span>${this.escapeHtml(romanLeaderName)}</span>`;
                    if (leaderSpecialtyFromServer) summaryHtml += `<span class="summary-badge"><span class="material-symbols-outlined">category</span>${this.escapeHtml(leaderSpecialtyFromServer.split(',')[0].trim())}</span>`;
                    if (topicText) summaryHtml += `<span class="summary-badge"><span class="material-symbols-outlined">topic</span>${this.escapeHtml(topicText)}</span>`;
                    if (elapsedTime) summaryHtml += `<span class="summary-badge"><span class="material-symbols-outlined">timer</span>${elapsedTime}s</span>`;
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

                    const favBtn = this._createToolbarBtn('bookmark_add', 'Save', () => {
                        this.saveFavorite(originalQuery, rawResponse);
                        favBtn.querySelector('.material-symbols-outlined').textContent = 'bookmark_added';
                        favBtn.classList.add('active');
                    });
                    g1.appendChild(favBtn);

                    const shareBtn = this._createToolbarBtn('share', 'Share', async () => {
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

                    const exportBtn = this._createToolbarBtn('picture_as_pdf', 'PDF Save', async () => {
                        const icon = exportBtn.querySelector('.material-symbols-outlined');
                        icon.textContent = 'hourglass_top';
                        exportBtn.disabled = true;
                        try {
                            let pdfTitle = 'Legal Analysis';
                            if (leaderName) pdfTitle = `${leaderName} Analysis`;
                            let pdfContent = `[Question]\n${originalQuery}\n\n`;
                            if (leaderName) pdfContent += `[Assigned] ${leaderName}${leaderSpecialtyFromServer ? ' (' + leaderSpecialtyFromServer + ')' : ''}\n\n`;
                            pdfContent += `[Response]\n${rawResponse}`;
                            const pdfRes = await fetch(`${this.BASE_URL}/export-pdf`, {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({ title: pdfTitle, content: pdfContent })
                            });
                            if (!pdfRes.ok) throw new Error('PDF generation failed');
                            const blob = await pdfRes.blob();
                            const url = URL.createObjectURL(blob);
                            const now = new Date();
                            const pad = n => String(n).padStart(2, '0');
                            const fname = `lawmadi-analysis-${now.getFullYear()}${pad(now.getMonth()+1)}${pad(now.getDate())}-${pad(now.getHours())}${pad(now.getMinutes())}.pdf`;
                            const a = document.createElement('a'); a.href = url; a.download = fname; a.click();
                            URL.revokeObjectURL(url);
                            icon.textContent = 'check';
                            setTimeout(() => { icon.textContent = 'picture_as_pdf'; exportBtn.disabled = false; }, 2000);
                        } catch (e) {
                            icon.textContent = 'error';
                            exportBtn.disabled = false;
                            setTimeout(() => { icon.textContent = 'picture_as_pdf'; }, 2000);
                        }
                    });
                    g1.appendChild(exportBtn);
                    toolbar.appendChild(g1);

                    const g3 = document.createElement('div');
                    g3.className = 'toolbar-group';
                    const fbUp = this._createToolbarBtn('thumb_up', 'Helpful', () => _sendFb('up', fbUp));
                    const fbDown = this._createToolbarBtn('thumb_down', 'Not helpful', () => _sendFb('down', fbDown));
                    const _sendFb = async (rating, btn) => {
                        try {
                            await fetch(`${this.BASE_URL}/feedback`, {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({ rating, query: originalQuery, leader: leaderName || '' })
                            });
                        } catch(e) { /* 무시 */ }
                        fbUp.classList.add('voted');
                        fbDown.classList.add('voted');
                    };
                    g3.appendChild(fbUp);
                    g3.appendChild(fbDown);
                    toolbar.appendChild(g3);

                    msgDiv.appendChild(toolbar);

                    // ── Disclaimer ──
                    const disclaimerDiv = document.createElement('div');
                    disclaimerDiv.className = 'ai-disclaimer';
                    disclaimerDiv.textContent = 'This is an AI legal information service and does not substitute for professional legal advice from an attorney.';
                    msgDiv.appendChild(disclaimerDiv);

                    // ── 전문가 검증 + 변호사 상담 CTA (답변 맨 아래) ──
                    const ctaBar = document.createElement('div');
                    ctaBar.className = 'ai-bottom-cta';

                    const expertCta = document.createElement('button');
                    expertCta.className = 'bottom-cta-btn expert';
                    // Disable if insufficient credits
                    const _authUser = window.__lawmadiAuth && window.__lawmadiAuth.user;
                    const _userBal = _authUser ? (_authUser.credit_balance || 0) : -1;
                    const _isFreeNoCredit = _authUser && _userBal === 0 && _authUser.current_plan === 'free';
                    if (_isFreeNoCredit || (_authUser && _userBal >= 0 && _userBal < 2)) {
                        expertCta.innerHTML = '<span class="material-symbols-outlined">verified</span> Get Expert Verification <span style="font-size:0.75em;background:rgba(239,68,68,0.15);color:#ef4444;padding:2px 8px;border-radius:6px;margin-left:4px;">Insufficient Credits</span>';
                        expertCta.disabled = true;
                        expertCta.title = 'Purchase credits to use this feature (2 Credits required)';
                    } else {
                        expertCta.innerHTML = '<span class="material-symbols-outlined">verified</span> Get Expert Verification <span style="font-size:0.75em;background:rgba(139,92,246,0.15);padding:2px 8px;border-radius:6px;margin-left:4px;">2 Credit</span>';
                    }
                    expertCta.onclick = async () => {
                        // Login check
                        const _authU = window.__lawmadiAuth && window.__lawmadiAuth.user;
                        if (!_authU) {
                            const _goLogin = confirm('Login is required for expert verification.\n\nWould you like to log in?');
                            if (_goLogin && typeof UI !== 'undefined' && UI.openAuthModal) { UI.openAuthModal(); }
                            return;
                        }
                        // Credit confirmation
                        const _bal = _authU.credit_balance || 0;
                        if (_bal < 2) {
                            const _goPrice = confirm('Insufficient credits.\n\nWould you like to purchase credits?');
                            if (_goPrice) location.href = '/pricing-en';
                            return;
                        }
                        if (!confirm('Get expert verification?\n\n2 Credits will be deducted.\nCurrent balance: ' + _bal + ' Credits')) return;
                        expertCta.disabled = true;
                        expertCta.innerHTML = '<span class="material-symbols-outlined">hourglass_top</span> Verifying...';

                        // ── Waiting indicator ──
                        const waitingDiv = document.createElement('div');
                        waitingDiv.className = 'expert-waiting-indicator';
                        waitingDiv.innerHTML = `
                            <div class="expert-waiting-title">
                                <span class="material-symbols-outlined">sync</span>
                                Expert Verification in Progress
                            </div>
                            <div class="expert-waiting-steps">
                                <div class="expert-wait-step active" data-ew="1"><span class="ew-icon">🔍</span> Analyzing original response...</div>
                                <div class="expert-wait-step" data-ew="2"><span class="ew-icon">📖</span> Verifying statutes via DRF...</div>
                                <div class="expert-wait-step" data-ew="3"><span class="ew-icon">⚖️</span> Cross-checking decrees & rules...</div>
                                <div class="expert-wait-step" data-ew="4"><span class="ew-icon">📋</span> Generating verification report...</div>
                            </div>
                            <div class="expert-wait-elapsed">0s elapsed</div>
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
                            if (el) el.textContent = `${ewSec}s elapsed`;
                        }, 1000);

                        try {
                            const expertRes = await fetch(`${this.BASE_URL}/ask-expert`, {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                credentials: 'include',
                                body: JSON.stringify({ query: originalQuery, original_response: rawResponse })
                            });
                            if (!expertRes.ok) throw new Error('Expert verification failed');
                            const expertData = await expertRes.json();
                            ewTimers.forEach(t => clearTimeout(t));
                            clearInterval(ewElapsed);
                            waitingDiv.remove();
                            if (expertData.status === 'SUCCESS' && expertData.response) {
                                const panel = document.createElement('div');
                                panel.className = 'expert-response-panel';
                                panel.innerHTML = _sanitize(this.formatReport(expertData.response));
                                msgDiv.insertBefore(panel, ctaBar);
                                const vScore = expertData.verification?.ssot_compliance_score || 0;
                                if (vScore > 0) {
                                    const barDiv = document.createElement('div');
                                    barDiv.className = 'ssot-confidence-bar';
                                    const level = vScore >= 80 ? 'high' : vScore >= 50 ? 'medium' : 'low';
                                    barDiv.innerHTML = `<span class="bar-label">SSOT Confidence</span><div class="bar-track"><div class="bar-fill ${level}" style="width: ${vScore}%"></div></div><span class="bar-score ${level}">${vScore}%</span>`;
                                    msgDiv.insertBefore(barDiv, ctaBar);
                                }
                                expertCta.innerHTML = '<span class="material-symbols-outlined">check_circle</span> Verification Complete';
                                expertCta.classList.add('done');
                                // Scroll to expert panel
                                requestAnimationFrame(() => {
                                    panel.scrollIntoView({ behavior: 'smooth', block: 'start' });
                                });
                            } else { throw new Error('Verification failed'); }
                        } catch (e) {
                            ewTimers.forEach(t => clearTimeout(t));
                            clearInterval(ewElapsed);
                            if (waitingDiv.parentNode) waitingDiv.remove();
                            expertCta.disabled = false;
                            expertCta.innerHTML = '<span class="material-symbols-outlined">verified</span> Get Expert Verification <span style="font-size:0.75em;background:rgba(139,92,246,0.15);padding:2px 8px;border-radius:6px;margin-left:4px;">2 Credit</span>';
                            console.error('Expert verification failed:', e);
                        }
                    };
                    ctaBar.appendChild(expertCta);

                    if (leaderName) {
                        const clevelOnly = ['서연','지유','유나'];
                        const lNames = leaderName.split(',').map(n => n.trim()).filter(Boolean);
                        if (!lNames.every(n => clevelOnly.includes(n))) {
                            const lawyerCta = document.createElement('button');
                            lawyerCta.className = 'bottom-cta-btn lawyer';
                            lawyerCta.innerHTML = '<span class="material-symbols-outlined">gavel</span> Attorney Consultation Guide';
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

                // PDF download button (legal document code block detection)
                if (rawResponse) {
                    const docKeywords = ['고소장', '소장', '답변서', '내용증명', '고소취하서', 'complaint', 'petition', 'response', 'certification', 'legal notice', 'demand letter', 'affidavit', 'motion', 'brief'];
                    const hasCodeBlock = rawResponse.includes('```');
                    const hasDocKeyword = docKeywords.some(kw => rawResponse.includes(kw));

                    if (hasCodeBlock && hasDocKeyword) {
                        const codeMatch = rawResponse.match(/```[\s\S]*?\n([\s\S]*?)```/);
                        if (codeMatch) {
                            const docContent = codeMatch[1].trim();
                            const titleMatch = docContent.match(/^(고\s*소\s*장|소\s+장|답\s*변\s*서|내\s*용\s*증\s*명|고소취하서|Criminal\s+Complaint|Civil\s+Petition|Legal\s+Notice|Demand\s+Letter|Affidavit|Motion|Brief)/mi);
                            const docTitle = titleMatch ? titleMatch[1].replace(/\s+/g, ' ').trim() : 'Legal Document';

                            const pdfBtn = document.createElement('button');
                            pdfBtn.className = 'pdf-download-btn';
                            pdfBtn.innerHTML = '<span class="material-symbols-outlined" style="font-size: 18px;">picture_as_pdf</span> PDF Download';
                            pdfBtn.onclick = async () => {
                                pdfBtn.innerHTML = '<span class="material-symbols-outlined" style="font-size: 18px;">hourglass_top</span> Generating...';
                                pdfBtn.disabled = true;
                                try {
                                    const pdfRes = await fetch(`${this.BASE_URL}/export-pdf`, {
                                        method: 'POST',
                                        headers: { 'Content-Type': 'application/json' },
                                        body: JSON.stringify({ title: docTitle, content: docContent })
                                    });
                                    if (!pdfRes.ok) throw new Error('PDF generation failed');
                                    const blob = await pdfRes.blob();
                                    const url = window.URL.createObjectURL(blob);
                                    const a = document.createElement('a');
                                    a.href = url;
                                    a.download = `${docTitle}.pdf`;
                                    a.click();
                                    window.URL.revokeObjectURL(url);
                                    pdfBtn.innerHTML = '<span class="material-symbols-outlined" style="font-size: 18px;">check_circle</span> Complete';
                                    setTimeout(() => {
                                        pdfBtn.innerHTML = '<span class="material-symbols-outlined" style="font-size: 18px;">picture_as_pdf</span> PDF Download';
                                        pdfBtn.disabled = false;
                                    }, 2000);
                                } catch (e) {
                                    pdfBtn.innerHTML = '<span class="material-symbols-outlined" style="font-size: 18px;">error</span> Failed - Retry';
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
                tsText += ` · ⏱ ${elapsedTime}s`;
            }
            tsDiv.textContent = tsText;
            msgDiv.appendChild(tsDiv);

            // 협의/인수인계 컨테이너를 AI 메시지 안으로 이동
            if (sender === 'ai') {
                const delibEls = Array.from(this.convArea.querySelectorAll(':scope > .deliberation-container, :scope > .handoff-container'));
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

        addCopyButton(msgDiv) {
            const existingBtn = msgDiv.querySelector('.copy-btn');
            if (existingBtn) existingBtn.remove();

            const copyBtn = document.createElement('button');
            copyBtn.className = 'copy-btn';
            copyBtn.innerHTML = '<span class="material-symbols-outlined" style="font-size: 18px;">content_copy</span>';
            copyBtn.style.cssText = `
                position: absolute; top: 12px; right: 12px;
                background: rgba(255, 255, 255, 0.9); backdrop-filter: blur(8px);
                border: 1px solid #e5e7eb; border-radius: 8px; padding: 8px;
                cursor: pointer; display: flex; align-items: center; justify-content: center;
                opacity: 0.7; transition: all 0.2s ease;
                box-shadow: 0 2px 8px rgba(0,0,0,0.1); z-index: 10;
            `;

            copyBtn.onmouseenter = () => { copyBtn.style.opacity = '1'; copyBtn.style.background = 'rgba(37, 99, 235, 0.1)'; copyBtn.style.borderColor = '#2563eb'; };
            copyBtn.onmouseleave = () => { copyBtn.style.opacity = '0.7'; copyBtn.style.background = 'rgba(255, 255, 255, 0.9)'; copyBtn.style.borderColor = '#e5e7eb'; };

            copyBtn.onclick = async () => {
                try {
                    await navigator.clipboard.writeText(msgDiv.innerText);
                    copyBtn.innerHTML = '<span class="material-symbols-outlined" style="font-size: 18px; color: #10b981;">check</span>';
                    copyBtn.style.opacity = '1';
                    setTimeout(() => { copyBtn.innerHTML = '<span class="material-symbols-outlined" style="font-size: 18px;">content_copy</span>'; copyBtn.style.opacity = '0.7'; }, 2000);
                } catch (err) { console.error('Copy failed:', err); }
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
                        <span class="step-icon">🔍</span> Analyzing question...
                    </div>
                    <div class="typing-step" id="step-2">
                        <span class="step-icon">👥</span> Assigning expert leader...
                    </div>
                    <div class="typing-step" id="step-3">
                        <span class="step-icon">⚖️</span> Searching laws & precedents...
                    </div>
                    <div class="typing-step" id="step-4">
                        <span class="step-icon">✍️</span> Generating response...
                    </div>
                    <div class="typing-step" id="step-5">
                        <span class="step-icon">🔎</span> Cross-verifying...
                    </div>
                    <div class="typing-step" id="step-6">
                        <span class="step-icon">📋</span> Finalizing...
                    </div>
                    <div class="typing-elapsed" id="typing-elapsed" style="margin-top:6px;font-size:0.7rem;color:var(--text-muted);opacity:0.7;">0s elapsed</div>
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
                            if (prev) { prev.classList.remove('active'); prev.classList.add('done'); }
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
                if (el) el.textContent = `${elapsed}s elapsed`;
            }, 1000);

            return typingId;
        },

        // ═══ 새 대화 시작 ═══
        resetConversation() {
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
            if (this.scrollBottomBtn) this.scrollBottomBtn.classList.remove('visible');
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
            return now.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', hour12: true });
        },

        // ═══ 사용자 친화적 에러 메시지 ═══
        _friendlyError(error) {
            const msg = error.message || '';
            if (error.name === 'AbortError' || msg.includes('timeout') || msg.includes('abort')) {
                return 'Response timed out. Please try again later.';
            }
            if (msg.includes('NetworkError') || msg.includes('Failed to fetch') || msg.includes('network')) {
                return 'Please check your internet connection.';
            }
            if (msg.includes('5') && (msg.includes('Server') || msg.includes('server'))) {
                return 'Server is busy. Please try again later.';
            }
            return msg || 'An unknown error occurred.';
        },

        hideTypingIndicator() {
            if (this._typingStepTimers) {
                this._typingStepTimers.forEach(t => clearTimeout(t));
                this._typingStepTimers = [];
            }
            if (this._elapsedTimer) {
                clearInterval(this._elapsedTimer);
                this._elapsedTimer = null;
            }
            const typingDiv = document.getElementById('typing-indicator');
            if (typingDiv) typingDiv.remove();
        }
    };

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
                    window.location.href = '/en';
                } else if (action === 'leaders') {
                    window.location.href = '/leaders-en';
                } else if (action === 'clevel') {
                    window.location.href = '/clevel-en';
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
    var isInApp = /KAKAOTALK|FBAN|FBAV|Instagram|Line\/|NAVER|Snapchat|Twitter/i.test(ua);

    if (isInApp) {
        // 인앱 브라우저: 외부 브라우저로 열기 안내
        var titleEl = promptEl.querySelector('.install-prompt-title');
        if (titleEl) titleEl.textContent = 'Open in External Browser';
        if (isIOS) {
            guideText.innerHTML = 'Tap <b>···</b> at the bottom right or <b>Open in Safari</b>';
        } else {
            guideText.innerHTML = 'Tap <b>⋮</b> at the top right → <b>"Open in another browser"</b>';
        }
        // 인앱에서는 확인 버튼 옆에 "링크 복사" 버튼 추가
        var actionsEl = promptEl.querySelector('.install-prompt-actions');
        if (actionsEl && !document.getElementById('copyLinkBtn')) {
            var copyBtn = document.createElement('button');
            copyBtn.id = 'copyLinkBtn';
            copyBtn.className = 'install-btn install-btn-dismiss';
            copyBtn.textContent = 'Copy Link';
            copyBtn.setAttribute('aria-label', 'Copy Link');
            actionsEl.insertBefore(copyBtn, dismissBtn);
            copyBtn.addEventListener('click', function() {
                navigator.clipboard.writeText(window.location.href).then(function() {
                    copyBtn.textContent = 'Copied!';
                    setTimeout(function() { copyBtn.textContent = 'Copy Link'; }, 2000);
                }).catch(function() {
                    // clipboard API 미지원 시 fallback
                    var ta = document.createElement('textarea');
                    ta.value = window.location.href;
                    ta.style.cssText = 'position:fixed;opacity:0';
                    document.body.appendChild(ta);
                    ta.select();
                    document.execCommand('copy');
                    document.body.removeChild(ta);
                    copyBtn.textContent = 'Copied!';
                    setTimeout(function() { copyBtn.textContent = 'Copy Link'; }, 2000);
                });
            });
        }
    } else if (isIOS) {
        guideText.textContent = 'Tap the share button (□↑) at the bottom → "Add to Home Screen"';
    } else if (isSamsung) {
        guideText.textContent = 'Tap ≡ menu at the bottom right → "Add to Home Screen"';
    } else if (isAndroid) {
        guideText.textContent = 'Tap ⋮ menu at the top right → "Add to Home Screen"';
    }

    // 이전에 닫은 적이 있으면 7일 후에만 다시 표시 (인앱은 3일)
    var dismissed = localStorage.getItem('shortcut-dismissed');
    var cooldown = isInApp ? 259200000 : 604800000; // 인앱 3일, 일반 7일
    if (dismissed && Date.now() - parseInt(dismissed) < cooldown) return;

    setTimeout(function() { promptEl.classList.add('show'); }, isInApp ? 2000 : 4000);

    dismissBtn.addEventListener('click', function() {
        promptEl.classList.remove('show');
        localStorage.setItem('shortcut-dismissed', Date.now().toString());
    });
})();

document.addEventListener('contextmenu', function(e) { e.preventDefault(); });

/**
 * Lawmadi OS — Site Navigation Bar (서브 페이지 공통)
 * 인증 상태 표시 + 로그인/로그아웃 + 드롭다운 + 다크모드 + 홈 + 언어 전환
 * 모든 서브 페이지에서 로그인 상태를 유지합니다.
 */
(function() {
    'use strict';

    // 메인 페이지에서는 실행하지 않음 (자체 헤더 사용)
    var path = location.pathname;
    var isMain = /\/(index|index-en)?(\.html)?$/.test(path) || path === '/' || path === '/en';
    if (isMain) return;

    var isEn = path.indexOf('-en') !== -1 || path.indexOf('/en') !== -1;
    var homeUrl = isEn ? '/en' : '/';
    var langUrl = '';
    var langLabel = '';

    // 현재 페이지의 반대 언어 URL 계산 (쿼리 파라미터 유지)
    var qs = location.search || '';
    if (isEn) {
        langUrl = path.replace(/\.html$/, '').replace('-en', '').replace('/en', '/') + qs;
        langLabel = 'KO';
    } else {
        var cleanPath = path.replace(/\.html$/, '');
        langUrl = cleanPath + '-en';
        langUrl += qs;
        langLabel = 'EN';
    }

    // Auth state (synced with window.__lawmadiAuth)
    var authUser = null;

    // ─── 다크모드 복원 ───
    var savedDark = localStorage.getItem('lawmadi-dark-mode');
    if (savedDark === 'true') {
        document.body.classList.add('dark-mode');
    }

    // ─── 스타일 주입 ───
    var style = document.createElement('style');
    style.textContent = ''
        + '.site-nav{position:fixed;top:0;left:0;right:0;z-index:9999;display:flex;align-items:center;justify-content:space-between;padding:8px 16px;background:rgba(15,23,42,0.85);backdrop-filter:blur(12px);-webkit-backdrop-filter:blur(12px);border-bottom:1px solid rgba(255,255,255,0.08);}'
        + 'body:not(.dark-mode) .site-nav{background:rgba(255,255,255,0.9);border-bottom:1px solid rgba(0,0,0,0.08);}'
        + '.site-nav-left{display:flex;align-items:center;gap:8px;}'
        + '.site-nav-right{display:flex;align-items:center;gap:6px;}'
        + '.site-nav-btn{background:none;border:1px solid rgba(255,255,255,0.15);color:#e2e8f0;cursor:pointer;padding:6px 10px;border-radius:8px;display:flex;align-items:center;gap:6px;font-size:0.8rem;font-weight:600;transition:all 0.2s;text-decoration:none;}'
        + 'body:not(.dark-mode) .site-nav-btn{border-color:rgba(0,0,0,0.15);color:#334155;}'
        + '.site-nav-btn:hover{border-color:rgba(99,102,241,0.5);color:#818cf8;}'
        + 'body:not(.dark-mode) .site-nav-btn:hover{border-color:#3b82f6;color:#3b82f6;}'
        + '.site-nav-btn .material-symbols-outlined{font-size:1.1rem;}'
        + '.site-nav-auth{border-color:rgba(99,102,241,0.3);}'
        + '.site-nav-auth.logged-in{border-color:rgba(34,197,94,0.4);color:#4ade80;}'
        + 'body:not(.dark-mode) .site-nav-auth.logged-in{color:#16a34a;border-color:rgba(34,197,94,0.4);}'
        + '.site-nav-credit{font-weight:700;font-size:0.85rem;}'
        + '.site-nav-more-wrap{position:relative;}'
        + '.site-nav-dropdown{display:none;position:absolute;top:calc(100% + 6px);right:0;background:#1e293b;border:1px solid #334155;border-radius:10px;box-shadow:0 8px 24px rgba(0,0,0,0.4);min-width:180px;padding:4px 0;z-index:10000;}'
        + 'body:not(.dark-mode) .site-nav-dropdown{background:#fff;border-color:#e2e8f0;box-shadow:0 8px 24px rgba(0,0,0,0.12);}'
        + '.site-nav-dd-item{display:flex;align-items:center;gap:8px;width:100%;padding:9px 14px;background:none;border:none;color:#e2e8f0;font-size:0.85rem;cursor:pointer;transition:background 0.15s;text-align:left;text-decoration:none;}'
        + 'body:not(.dark-mode) .site-nav-dd-item{color:#334155;}'
        + '.site-nav-dd-item:hover{background:#334155;}'
        + 'body:not(.dark-mode) .site-nav-dd-item:hover{background:#f1f5f9;}'
        + '.site-nav-dd-item .material-symbols-outlined{font-size:1rem;color:#94a3b8;}'
        + 'body:not(.dark-mode) .site-nav-dd-item .material-symbols-outlined{color:#64748b;}'
        // Auth dropdown (logged-in user menu)
        + '.site-nav-auth-wrap{position:relative;}'
        + '.site-nav-auth-dd{display:none;position:absolute;top:calc(100% + 6px);right:0;background:#1e293b;border:1px solid #334155;border-radius:10px;box-shadow:0 8px 24px rgba(0,0,0,0.4);min-width:200px;padding:4px 0;z-index:10000;}'
        + 'body:not(.dark-mode) .site-nav-auth-dd{background:#fff;border-color:#e2e8f0;box-shadow:0 8px 24px rgba(0,0,0,0.12);}'
        + '.site-nav-auth-dd-email{padding:10px 14px;font-size:0.8rem;color:#94a3b8;border-bottom:1px solid #334155;word-break:break-all;}'
        + 'body:not(.dark-mode) .site-nav-auth-dd-email{border-color:#e2e8f0;color:#64748b;}'
        + '.site-nav-auth-dd-credits{padding:8px 14px;font-size:0.85rem;font-weight:700;border-bottom:1px solid #334155;}'
        + 'body:not(.dark-mode) .site-nav-auth-dd-credits{border-color:#e2e8f0;}'
        // OTP modal
        + '.sn-otp-overlay{display:none;position:fixed;inset:0;z-index:10001;background:rgba(0,0,0,0.7);backdrop-filter:blur(8px);align-items:center;justify-content:center;}'
        + '.sn-otp-box{background:#1e293b;border:1px solid rgba(255,255,255,0.15);border-radius:20px;padding:36px 28px;max-width:380px;width:90%;text-align:center;position:relative;}'
        + 'body:not(.dark-mode) .sn-otp-box{background:#fff;border-color:#e2e8f0;}'
        + '.sn-otp-box h3{font-weight:800;margin-bottom:8px;}'
        + '.sn-otp-box p{color:#94a3b8;font-size:0.9rem;margin-bottom:16px;}'
        + 'body:not(.dark-mode) .sn-otp-box p{color:#64748b;}'
        + '.sn-otp-input{width:100%;padding:14px 16px;background:#0f172a;border:1px solid rgba(255,255,255,0.2);border-radius:12px;color:#f1f5f9;font-size:1rem;margin-bottom:12px;outline:none;}'
        + 'body:not(.dark-mode) .sn-otp-input{background:#f8fafc;border-color:#cbd5e1;color:#0f172a;}'
        + '.sn-otp-btn{width:100%;padding:14px;background:linear-gradient(135deg,#2563eb,#8b5cf6);border:none;border-radius:12px;color:white;font-size:1rem;font-weight:700;cursor:pointer;}'
        + '.sn-otp-btn:disabled{opacity:0.5;cursor:not-allowed;}'
        + '.sn-otp-btn.verify{background:linear-gradient(135deg,#10b981,#059669);}'
        + '.sn-otp-msg{font-size:0.85rem;margin-top:8px;display:none;}'
        + '.sn-otp-close{position:absolute;top:12px;right:16px;background:none;border:none;color:#94a3b8;font-size:1.5rem;cursor:pointer;}'
        + 'body:not(.dark-mode) .sn-otp-close{color:#64748b;}'
        + '.sn-otp-resend{background:none;border:none;color:#93c5fd;font-size:0.85rem;cursor:pointer;margin-top:8px;text-decoration:underline;}'
        + 'body:not(.dark-mode) .sn-otp-resend{color:#2563eb;}'
        + 'body{padding-top:50px !important;}';
    document.head.appendChild(style);

    // ─── 기존 back-button, 언어토글 숨기기 ───
    setTimeout(function() {
        var backBtns = document.querySelectorAll('.back-button');
        backBtns.forEach(function(b) { b.style.display = 'none'; });
        document.querySelectorAll('a[style*="position:fixed"][style*="top:"]').forEach(function(a) {
            if (a.textContent.trim() === 'EN' || a.textContent.trim() === 'KO') {
                a.style.display = 'none';
            }
        });
    }, 0);

    // ─── OTP 모달 HTML 주입 ───
    var otpHtml = ''
        + '<div class="sn-otp-overlay" id="snOtpOverlay">'
        + '<div class="sn-otp-box">'
        +   '<button class="sn-otp-close" id="snOtpClose">&times;</button>'
        +   '<div id="snOtpStep1">'
        +     '<h3>' + (isEn ? 'Email Login' : '이메일 로그인') + '</h3>'
        +     '<p>' + (isEn ? 'No sign-up needed. Just verify your email.' : '회원가입 없이 이메일만으로 이용 가능합니다') + '</p>'
        +     '<input class="sn-otp-input" id="snOtpEmail" type="email" placeholder="' + (isEn ? 'Email address' : '이메일 주소') + '">'
        +     '<button class="sn-otp-btn" id="snOtpSendBtn">' + (isEn ? 'Send Code' : '인증번호 발송') + '</button>'
        +     '<div class="sn-otp-msg" id="snOtpSendMsg"></div>'
        +   '</div>'
        +   '<div id="snOtpStep2" style="display:none;">'
        +     '<h3>' + (isEn ? 'Enter Code' : '인증번호 입력') + '</h3>'
        +     '<p>' + (isEn ? 'Enter the 6-digit code sent to your email' : '이메일로 전송된 6자리 코드를 입력하세요') + '</p>'
        +     '<input class="sn-otp-input" id="snOtpCode" type="text" maxlength="6" placeholder="000000" style="font-size:1.5rem;font-weight:900;letter-spacing:8px;text-align:center;">'
        +     '<button class="sn-otp-btn verify" id="snOtpVerifyBtn">' + (isEn ? 'Verify' : '확인') + '</button>'
        +     '<div class="sn-otp-msg" id="snOtpVerifyMsg"></div>'
        +     '<button class="sn-otp-resend" id="snOtpResendBtn">' + (isEn ? 'Resend' : '재발송') + '</button>'
        +   '</div>'
        +   '<div id="snOtpStep3" style="display:none;">'
        +     '<div style="font-size:3rem;margin-bottom:12px;">&#10004;</div>'
        +     '<h3>' + (isEn ? 'Verified!' : '인증 완료!') + '</h3>'
        +     '<p>' + (isEn ? 'You are now logged in.' : '로그인되었습니다.') + '</p>'
        +   '</div>'
        + '</div>'
        + '</div>';
    var otpContainer = document.createElement('div');
    otpContainer.innerHTML = otpHtml;
    document.body.appendChild(otpContainer);

    // ─── 네비게이션 바 생성 ───
    var nav = document.createElement('nav');
    nav.className = 'site-nav';
    nav.innerHTML = ''
        + '<div class="site-nav-left">'
        +   '<a href="' + homeUrl + '" class="site-nav-btn" title="' + (isEn ? 'Home' : '메인') + '">'
        +     '<span class="material-symbols-outlined">arrow_back</span>'
        +     '<span>' + (isEn ? 'Home' : '메인') + '</span>'
        +   '</a>'
        + '</div>'
        + '<div class="site-nav-right">'
        +   '<div class="site-nav-auth-wrap">'
        +     '<button class="site-nav-btn site-nav-auth" id="siteNavAuth">'
        +       '<span class="material-symbols-outlined">login</span>'
        +       '<span>Login</span>'
        +     '</button>'
        +     '<div class="site-nav-auth-dd" id="siteNavAuthDD"></div>'
        +   '</div>'
        +   '<div class="site-nav-more-wrap">'
        +     '<button class="site-nav-btn" id="siteNavMore" aria-label="More">'
        +       '<span class="material-symbols-outlined">more_vert</span>'
        +     '</button>'
        +     '<div class="site-nav-dropdown" id="siteNavDropdown">'
        +       '<button class="site-nav-dd-item" id="siteNavDark">'
        +         '<span class="material-symbols-outlined">dark_mode</span>'
        +         '<span>' + (isEn ? 'Dark Mode' : '다크모드') + '</span>'
        +       '</button>'
        +       '<a href="' + langUrl + '" class="site-nav-dd-item">'
        +         '<span class="material-symbols-outlined">translate</span>'
        +         '<span>' + langLabel + '</span>'
        +       '</a>'
        +     '</div>'
        +   '</div>'
        + '</div>';

    document.body.insertBefore(nav, document.body.firstChild);

    // ─── Helpers ───
    function _esc(s) {
        var d = document.createElement('div');
        d.textContent = s;
        return d.innerHTML;
    }

    // ─── 인증 상태 확인 + UI 업데이트 ───
    var authBtn = document.getElementById('siteNavAuth');
    var authDD = document.getElementById('siteNavAuthDD');

    function updateAuthUI() {
        if (authUser) {
            var email = authUser.email || '';
            var bal = parseInt(authUser.credit_balance || 0, 10);
            var short = email.split('@')[0];
            if (short.length > 8) short = short.substring(0, 8) + '..';
            authBtn.classList.add('logged-in');
            authBtn.innerHTML = '<span class="material-symbols-outlined">toll</span>'
                + '<span class="site-nav-credit">' + bal + '</span>'
                + '<span>' + _esc(short) + '</span>';
            authBtn.title = email;
            // Sync global auth state
            window.__lawmadiAuth = { authenticated: true, email: email, user: authUser };
        } else {
            authBtn.classList.remove('logged-in');
            authBtn.innerHTML = '<span class="material-symbols-outlined">login</span>'
                + '<span>Login</span>';
            authBtn.title = isEn ? 'Email Login' : '이메일 로그인';
            window.__lawmadiAuth = { authenticated: false, email: '', user: null };
        }
    }

    function checkSession() {
        fetch('/api/paddle/me', { credentials: 'include' })
            .then(function(r) { if (r.ok) return r.json(); throw new Error('no'); })
            .then(function(d) {
                if (d.ok && d.user) {
                    authUser = d.user;
                } else {
                    authUser = null;
                }
                updateAuthUI();
            })
            .catch(function() {
                authUser = null;
                updateAuthUI();
            });
    }

    checkSession();

    // ─── Auth Button Click ───
    authBtn.onclick = function(e) {
        e.stopPropagation();
        if (authUser) {
            // Show auth dropdown
            var visible = authDD.style.display !== 'none';
            if (visible) { authDD.style.display = 'none'; return; }
            var email = authUser.email || '';
            var bal = parseInt(authUser.credit_balance || 0, 10);
            authDD.innerHTML = ''
                + '<div class="site-nav-auth-dd-email">' + _esc(email) + '</div>'
                + '<div class="site-nav-auth-dd-credits"><span class="material-symbols-outlined" style="font-size:1rem;vertical-align:middle;">toll</span> '
                +   (isEn ? 'Credits: ' : '크레딧: ') + '<strong>' + bal + '</strong></div>'
                + '<a href="/pricing' + (isEn ? '-en' : '') + '" class="site-nav-dd-item">'
                +   '<span class="material-symbols-outlined">add_circle</span>'
                +   '<span>' + (isEn ? 'Buy Credits' : '크레딧 충전') + '</span>'
                + '</a>'
                + '<button class="site-nav-dd-item" id="siteNavLogout">'
                +   '<span class="material-symbols-outlined">logout</span>'
                +   '<span>' + (isEn ? 'Logout' : '로그아웃') + '</span>'
                + '</button>';
            authDD.style.display = 'block';
            // Logout handler
            document.getElementById('siteNavLogout').onclick = function() {
                fetch('/api/paddle/logout', { method: 'POST', credentials: 'include' })
                    .finally(function() {
                        authUser = null;
                        localStorage.removeItem('lm_email');
                        localStorage.removeItem('lawmadi-chat-history');
                        localStorage.removeItem('lawmadi-favorites');
                        window.__lawmadiAuth = { authenticated: false, email: '', user: null };
                        authDD.style.display = 'none';
                        updateAuthUI();
                    });
            };
            // Close on outside click
            setTimeout(function() {
                document.addEventListener('click', function closeAuthDD(ev) {
                    if (!authDD.contains(ev.target) && ev.target !== authBtn) {
                        authDD.style.display = 'none';
                        document.removeEventListener('click', closeAuthDD);
                    }
                });
            }, 10);
        } else {
            // Show OTP modal
            showOtpModal();
        }
    };

    // ─── OTP Modal Logic ───
    var otpOverlay = document.getElementById('snOtpOverlay');
    var otpStep1 = document.getElementById('snOtpStep1');
    var otpStep2 = document.getElementById('snOtpStep2');
    var otpStep3 = document.getElementById('snOtpStep3');
    var otpEmail = '';

    function showOtpModal() {
        otpOverlay.style.display = 'flex';
        document.body.style.overflow = 'hidden';
        otpStep1.style.display = 'block';
        otpStep2.style.display = 'none';
        otpStep3.style.display = 'none';
        var emailInput = document.getElementById('snOtpEmail');
        var saved = localStorage.getItem('lm_email');
        if (saved) emailInput.value = saved;
        emailInput.focus();
    }

    function hideOtpModal() {
        otpOverlay.style.display = 'none';
        document.body.style.overflow = '';
    }

    document.getElementById('snOtpClose').onclick = hideOtpModal;
    otpOverlay.addEventListener('click', function(e) {
        if (e.target === otpOverlay) hideOtpModal();
    });
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape' && otpOverlay.style.display === 'flex') hideOtpModal();
    });

    // Send OTP
    document.getElementById('snOtpSendBtn').addEventListener('click', function() {
        var email = document.getElementById('snOtpEmail').value.trim().toLowerCase();
        if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
            showOtpMsg('snOtpSendMsg', isEn ? 'Please enter a valid email' : '유효한 이메일을 입력하세요', true);
            return;
        }
        otpEmail = email;
        var btn = this;
        btn.disabled = true;
        btn.textContent = isEn ? 'Sending...' : '발송 중...';
        fetch('/api/paddle/otp/send', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({ email: email })
        })
        .then(function(r) { return r.json().then(function(d) { return { ok: r.ok, data: d }; }); })
        .then(function(res) {
            btn.disabled = false;
            btn.textContent = isEn ? 'Send Code' : '인증번호 발송';
            if (res.ok) {
                otpStep1.style.display = 'none';
                otpStep2.style.display = 'block';
                document.getElementById('snOtpCode').focus();
                showOtpMsg('snOtpVerifyMsg', isEn ? 'Check your email (5 min)' : '이메일을 확인하세요 (5분)', false);
            } else {
                showOtpMsg('snOtpSendMsg', res.data.detail || res.data.error || 'Send failed', true);
            }
        })
        .catch(function() {
            btn.disabled = false;
            btn.textContent = isEn ? 'Send Code' : '인증번호 발송';
            showOtpMsg('snOtpSendMsg', 'Network error', true);
        });
    });

    // Verify OTP
    document.getElementById('snOtpVerifyBtn').addEventListener('click', verifyOtp);
    document.getElementById('snOtpCode').addEventListener('keydown', function(e) {
        if (e.key === 'Enter') verifyOtp();
    });

    function verifyOtp() {
        var code = document.getElementById('snOtpCode').value.trim();
        if (!code || code.length !== 6) {
            showOtpMsg('snOtpVerifyMsg', isEn ? 'Enter 6-digit code' : '6자리 코드를 입력하세요', true);
            return;
        }
        var btn = document.getElementById('snOtpVerifyBtn');
        btn.disabled = true;
        btn.textContent = isEn ? 'Verifying...' : '확인 중...';
        fetch('/api/paddle/otp/verify', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({ email: otpEmail, code: code })
        })
        .then(function(r) { return r.json().then(function(d) { return { ok: r.ok, data: d }; }); })
        .then(function(res) {
            btn.disabled = false;
            btn.textContent = isEn ? 'Verify' : '확인';
            if (res.ok) {
                authUser = res.data.user || null;
                localStorage.setItem('lm_email', otpEmail);
                otpStep2.style.display = 'none';
                otpStep3.style.display = 'block';
                setTimeout(function() {
                    hideOtpModal();
                    updateAuthUI();
                }, 1200);
            } else {
                showOtpMsg('snOtpVerifyMsg', res.data.error || 'Verification failed', true);
            }
        })
        .catch(function() {
            btn.disabled = false;
            btn.textContent = isEn ? 'Verify' : '확인';
            showOtpMsg('snOtpVerifyMsg', 'Network error', true);
        });
    }

    // Resend
    document.getElementById('snOtpResendBtn').addEventListener('click', function() {
        otpStep2.style.display = 'none';
        otpStep1.style.display = 'block';
        document.getElementById('snOtpSendBtn').click();
    });

    function showOtpMsg(id, text, isError) {
        var el = document.getElementById(id);
        if (!el) return;
        el.textContent = text;
        el.style.display = 'block';
        el.style.color = isError ? '#ef4444' : '#10b981';
    }

    // ─── 3-dot 더보기 메뉴 ───
    var moreBtn = document.getElementById('siteNavMore');
    var dropdown = document.getElementById('siteNavDropdown');
    moreBtn.onclick = function(e) {
        e.stopPropagation();
        var open = dropdown.style.display !== 'none';
        dropdown.style.display = open ? 'none' : 'block';
    };
    document.addEventListener('click', function(e) {
        if (!dropdown.contains(e.target) && e.target !== moreBtn) {
            dropdown.style.display = 'none';
        }
    });

    // ─── 다크모드 토글 ───
    var darkBtn = document.getElementById('siteNavDark');
    var darkIcon = darkBtn.querySelector('.material-symbols-outlined');
    var darkLabel = darkBtn.querySelector('span:last-child');
    function updateDarkUI() {
        var isDark = document.body.classList.contains('dark-mode');
        darkIcon.textContent = isDark ? 'light_mode' : 'dark_mode';
        darkLabel.textContent = isDark
            ? (isEn ? 'Light Mode' : '라이트모드')
            : (isEn ? 'Dark Mode' : '다크모드');
    }
    updateDarkUI();
    darkBtn.onclick = function() {
        document.body.classList.toggle('dark-mode');
        var isDark = document.body.classList.contains('dark-mode');
        localStorage.setItem('lawmadi-dark-mode', isDark);
        updateDarkUI();
    };
})();

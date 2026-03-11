/**
 * Lawmadi OS -- Paddle Checkout + Email OTP (no signup)
 * v2: DB sessions (HttpOnly cookie), /api/paddle/me for auth check
 */
(function() {
    'use strict';

    var API_BASE = '';  // same-origin via Firebase rewrite → Cloud Run proxy

    var state = {
        email: '',
        authenticated: false,
        selectedPack: '',
        paddleConfig: null,
        paddleReady: false,
        user: null
    };

    // Detect language from page
    var pageLang = (location.pathname.indexOf('-en') !== -1 || location.pathname.indexOf('/en') !== -1) ? 'en' : 'ko';

    // ─── Paddle Init ───
    function initPaddle() {
        fetch(API_BASE + '/api/paddle/config?lang=' + pageLang)
            .then(function(r) { return r.json(); })
            .then(function(cfg) {
                state.paddleConfig = cfg;
                // 결제 시스템 준비중 안내 (sandbox 모드)
                if (cfg.environment === 'sandbox') {
                    var banner = document.createElement('div');
                    banner.style.cssText = 'background:linear-gradient(135deg,#fef3c7,#fde68a);color:#92400e;padding:14px 20px;border-radius:12px;margin:0 auto 20px;max-width:800px;text-align:center;font-size:0.9rem;font-weight:600;border:1px solid #B8922D;';
                    banner.innerHTML = '<span class="material-symbols-outlined" style="font-size:1.1rem;vertical-align:middle;margin-right:6px;">construction</span>'
                        + (pageLang === 'en'
                            ? 'Payment system is being prepared. Credit purchases will be available soon.'
                            : '결제 시스템 준비 중입니다. 크레딧 구매 서비스가 곧 제공됩니다.');
                    var container = document.querySelector('.pricing-section') || document.querySelector('main') || document.body;
                    if (container.firstChild) container.insertBefore(banner, container.firstChild);
                    else container.appendChild(banner);
                    // 구매 버튼 비활성화
                    document.querySelectorAll('.buy-btn[data-pack]').forEach(function(b) {
                        b.disabled = true;
                        b.style.opacity = '0.5';
                        b.style.cursor = 'not-allowed';
                        b.title = pageLang === 'en' ? 'Coming soon' : '준비 중';
                    });
                }
                if (typeof Paddle !== 'undefined' && cfg.client_token) {
                    Paddle.Environment.set(cfg.environment || 'production');
                    Paddle.Initialize({ token: cfg.client_token });
                    state.paddleReady = true;
                    console.log('[Paddle] Initialized:', cfg.environment);
                } else {
                    console.warn('[Paddle] SDK not loaded or no client_token. Paddle:', typeof Paddle, 'token:', !!cfg.client_token);
                }
            })
            .catch(function(e) { console.warn('[Paddle] Config fetch failed:', e); });
    }

    // ─── Check existing session on load ───
    function checkSession() {
        fetch(API_BASE + '/api/paddle/me', { credentials: 'include' })
            .then(function(r) {
                if (r.ok) return r.json();
                throw new Error('not authenticated');
            })
            .then(function(d) {
                if (d.ok && d.user) {
                    state.authenticated = true;
                    state.email = d.user.email;
                    state.user = d.user;
                    updateCreditDisplay();
                }
            })
            .catch(function() {
                state.authenticated = false;
            });
    }

    function updateCreditDisplay() {
        var el = document.getElementById('otpCredits');
        if (el && state.user) {
            el.textContent = state.user.credit_balance;
        }
    }

    // ─── OTP Modal ───
    var modal = document.getElementById('otpModal');
    var step1 = document.getElementById('otpStep1');
    var step2 = document.getElementById('otpStep2');
    var step3 = document.getElementById('otpStep3');

    function showModal() {
        modal.style.display = 'flex';
        step1.style.display = 'block';
        step2.style.display = 'none';
        step3.style.display = 'none';
        var emailInput = document.getElementById('otpEmail');
        if (state.email) emailInput.value = state.email;
        emailInput.focus();
    }

    function hideModal() { modal.style.display = 'none'; }

    document.getElementById('otpClose').addEventListener('click', hideModal);
    modal.addEventListener('click', function(e) {
        if (e.target === modal) hideModal();
    });

    // Send OTP
    document.getElementById('otpSendBtn').addEventListener('click', function() {
        var email = document.getElementById('otpEmail').value.trim();
        if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
            showMsg('otpSendMsg', pageLang === 'en' ? 'Please enter a valid email' : '올바른 이메일을 입력하세요', true);
            return;
        }
        state.email = email;
        var btn = this;
        btn.disabled = true;
        btn.textContent = pageLang === 'en' ? 'Sending...' : '발송 중...';

        fetch(API_BASE + '/api/paddle/otp/send', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({ email: email })
        })
        .then(function(r) { return r.json().then(function(d) { return { ok: r.ok, data: d }; }); })
        .then(function(res) {
            btn.disabled = false;
            btn.textContent = pageLang === 'en' ? 'Send OTP' : '인증번호 발송';
            if (res.ok) {
                step1.style.display = 'none';
                step2.style.display = 'block';
                document.getElementById('otpCode').focus();
                showMsg('otpVerifyMsg', pageLang === 'en' ? 'Check your email (5 min)' : '이메일을 확인해주세요 (5분 이내)', false);
            } else {
                showMsg('otpSendMsg', res.data.detail || res.data.error || (pageLang === 'en' ? 'Send failed' : '발송 실패'), true);
            }
        })
        .catch(function() {
            btn.disabled = false;
            btn.textContent = pageLang === 'en' ? 'Send OTP' : '인증번호 발송';
            showMsg('otpSendMsg', pageLang === 'en' ? 'Network error' : '네트워크 오류', true);
        });
    });

    // Verify OTP
    document.getElementById('otpVerifyBtn').addEventListener('click', verifyOtp);
    document.getElementById('otpCode').addEventListener('keydown', function(e) {
        if (e.key === 'Enter') verifyOtp();
    });

    function verifyOtp() {
        var code = document.getElementById('otpCode').value.trim();
        if (!code || code.length !== 6) {
            showMsg('otpVerifyMsg', pageLang === 'en' ? 'Enter 6-digit code' : '6자리 코드를 입력하세요', true);
            return;
        }
        var btn = document.getElementById('otpVerifyBtn');
        btn.disabled = true;
        btn.textContent = pageLang === 'en' ? 'Verifying...' : '확인 중...';

        fetch(API_BASE + '/api/paddle/otp/verify', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({ email: state.email, code: code })
        })
        .then(function(r) { return r.json().then(function(d) { return { ok: r.ok, data: d }; }); })
        .then(function(res) {
            btn.disabled = false;
            btn.textContent = pageLang === 'en' ? 'Verify' : '확인';
            if (res.ok) {
                state.authenticated = true;
                state.user = res.data.user || null;
                localStorage.setItem('lm_email', state.email);
                step2.style.display = 'none';
                step3.style.display = 'block';
                updateCreditDisplay();
                // Open Paddle checkout after short delay
                setTimeout(function() {
                    hideModal();
                    openPaddleCheckout(state.selectedPack);
                }, 1500);
            } else {
                showMsg('otpVerifyMsg', res.data.error || (pageLang === 'en' ? 'Verification failed' : '인증 실패'), true);
            }
        })
        .catch(function() {
            btn.disabled = false;
            btn.textContent = pageLang === 'en' ? 'Verify' : '확인';
            showMsg('otpVerifyMsg', pageLang === 'en' ? 'Network error' : '네트워크 오류', true);
        });
    }

    // Resend
    document.getElementById('otpResendBtn').addEventListener('click', function() {
        step2.style.display = 'none';
        step1.style.display = 'block';
        document.getElementById('otpSendBtn').click();
    });

    // ─── Paddle Checkout ───
    function openPaddleCheckout(pack) {
        if (!state.paddleReady || !state.paddleConfig) {
            alert(pageLang === 'en' ? 'Payment system loading. Please try again.' : '결제 시스템을 불러오는 중입니다. 잠시 후 다시 시도해주세요.');
            return;
        }

        var priceId = state.paddleConfig.prices[pack];
        if (!priceId) {
            alert(pageLang === 'en' ? 'Product not found.' : '해당 상품을 찾을 수 없습니다.');
            return;
        }

        try {
            Paddle.Checkout.open({
                items: [{ priceId: priceId, quantity: 1 }],
                customer: { email: state.email },
                customData: { pack: pack },
                settings: {
                    displayMode: 'overlay',
                    theme: 'dark',
                    locale: pageLang === 'en' ? 'en' : 'ko',
                    successUrl: location.origin + (pageLang === 'en' ? '/pricing-en' : '/pricing') + '?success=1'
                }
            });
        } catch (err) {
            console.error('[Paddle] Checkout open failed:', err);
            alert(pageLang === 'en' ? 'Payment system error. Please refresh and try again.' : '결제 시스템 오류가 발생했습니다. 새로고침 후 다시 시도해주세요.');
        }
    }

    // ─── Buy Button Handlers ───
    document.querySelectorAll('.buy-btn[data-pack]').forEach(function(btn) {
        btn.addEventListener('click', function() {
            var pack = this.getAttribute('data-pack');
            state.selectedPack = pack;

            if (state.authenticated) {
                // Verify session is still valid
                fetch(API_BASE + '/api/paddle/me', { credentials: 'include' })
                .then(function(r) {
                    if (r.ok) {
                        openPaddleCheckout(pack);
                    } else {
                        state.authenticated = false;
                        showModal();
                    }
                })
                .catch(function() { showModal(); });
            } else {
                showModal();
            }
        });
    });

    // ─── Success redirect handling ───
    if (location.search.indexOf('success=1') !== -1) {
        history.replaceState(null, '', location.pathname);
        var toast = document.createElement('div');
        toast.style.cssText = 'position:fixed;top:20px;left:50%;transform:translateX(-50%);background:#3D8B5E;color:white;padding:16px 32px;border-radius:12px;font-weight:700;z-index:10000;animation:fadeInDown 0.5s ease;';
        toast.textContent = pageLang === 'en' ? 'Payment complete! Credits have been added.' : '결제가 완료되었습니다! 크레딧이 충전되었습니다.';
        document.body.appendChild(toast);
        setTimeout(function() { toast.remove(); }, 5000);
        // Refresh credit display
        setTimeout(checkSession, 2000);
    }

    // ─── Helper ───
    function showMsg(id, text, isError) {
        var el = document.getElementById(id);
        el.textContent = text;
        el.style.display = 'block';
        el.style.color = isError ? '#C45454' : '#3D8B5E';
    }

    // Init
    initPaddle();
    checkSession();

    // Restore email from storage
    var savedEmail = localStorage.getItem('lm_email');
    if (savedEmail) state.email = savedEmail;
})();

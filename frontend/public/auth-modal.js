/**
 * Lawmadi OS -- Auth Modal (Email OTP) + Header Credit Display
 * Self-contained: auto-creates floating auth button + OTP modal if DOM elements are missing.
 * Works on ALL pages — just include <script src="/auth-modal.js" defer></script>
 */
(function() {
    'use strict';

    var API_BASE = '';
    var pageLang = (location.pathname.indexOf('-en') !== -1 || location.pathname.indexOf('/en') !== -1) ? 'en' : 'ko';

    var authState = {
        email: '',
        authenticated: false,
        user: null
    };

    // Expose for app-inline-ko/en.js to read
    window.__lawmadiAuth = authState;

    // ─── Auto-inject floating auth button if not in page ───
    function ensureAuthButton() {
        if (document.getElementById('authHeaderBtn')) return;

        // Inject minimal CSS for floating button + dropdown
        var style = document.createElement('style');
        style.textContent = ''
            + '.auth-float-wrap{position:fixed;top:12px;right:16px;z-index:8000;}'
            + '.auth-header-btn{display:inline-flex;align-items:center;gap:6px;padding:8px 16px;'
            + 'border-radius:20px;font-size:0.85rem;font-weight:600;cursor:pointer;'
            + 'border:1px solid rgba(61,139,94,0.3);background:rgba(255,255,255,0.95);'
            + 'color:#3D8B5E;box-shadow:0 2px 12px rgba(0,0,0,0.08);transition:all 0.2s;'
            + 'backdrop-filter:blur(10px);-webkit-backdrop-filter:blur(10px);}'
            + '.auth-header-btn:hover{box-shadow:0 4px 16px rgba(61,139,94,0.15);border-color:#3D8B5E;}'
            + '.auth-header-btn.auth-logged-in{background:rgba(255,255,255,0.95);color:#1A2E22;border-color:#D4E4DA;}'
            + '.auth-credit-num{font-weight:800;color:#3D8B5E;}'
            + '.auth-email-short{color:#5D7D6D;font-size:0.78rem;}'
            + '#authDropdown{position:absolute;top:calc(100% + 8px);right:0;background:#fff;'
            + 'border:1px solid #D4E4DA;border-radius:14px;min-width:220px;box-shadow:0 8px 30px rgba(0,0,0,0.12);'
            + 'overflow:hidden;z-index:8001;}'
            + '.auth-dd-email{padding:12px 16px 4px;font-size:0.82rem;color:#5D7D6D;}'
            + '.auth-dd-credits{padding:4px 16px 12px;font-size:0.9rem;color:#1A2E22;border-bottom:1px solid #D4E4DA;}'
            + '.auth-dd-item{display:flex;align-items:center;gap:8px;width:100%;padding:10px 16px;'
            + 'border:none;background:none;font-size:0.88rem;color:#1A2E22;cursor:pointer;text-decoration:none;}'
            + '.auth-dd-item:hover{background:#E4EDE8;}'
            + '.auth-dd-logout{color:#C45454 !important;}'
            + '.auth-dd-logout:hover{background:#F5F0F0 !important;}';
        document.head.appendChild(style);

        var wrap = document.createElement('div');
        wrap.className = 'auth-float-wrap';
        wrap.innerHTML = '<button id="authHeaderBtn" class="auth-header-btn auth-logged-out" aria-label="Login">'
            + '<span class="material-symbols-outlined" style="font-size:1.1rem;">login</span>'
            + '<span class="auth-label">Login</span></button>';
        document.body.appendChild(wrap);
    }

    // ─── Auto-inject OTP modal if not in page ───
    function ensureOtpModal() {
        if (document.getElementById('authOtpModal')) return;

        var modal = document.createElement('div');
        modal.id = 'authOtpModal';
        modal.setAttribute('role', 'dialog');
        modal.setAttribute('aria-modal', 'true');
        modal.setAttribute('aria-label', 'Email Login');
        modal.style.cssText = 'display:none;position:fixed;inset:0;z-index:9999;background:rgba(0,0,0,0.7);backdrop-filter:blur(8px);align-items:center;justify-content:center;';
        modal.innerHTML = ''
            + '<div style="background:#fff;border:1px solid #D4E4DA;border-radius:20px;padding:36px 28px;max-width:380px;width:90%;text-align:center;position:relative;box-shadow:0 20px 60px rgba(0,0,0,0.15);">'
            + '<button id="authOtpClose" style="position:absolute;top:12px;right:16px;background:none;border:none;color:#5D7D6D;font-size:1.5rem;cursor:pointer;">&times;</button>'
            + '<div id="authOtpStep1">'
            + '<h3 style="color:#1A2E22;font-weight:800;margin-bottom:8px;">Email Login</h3>'
            + '<p style="color:#5D7D6D;font-size:0.9rem;margin-bottom:20px;">No signup needed. Just verify your email.</p>'
            + '<input id="authOtpEmail" type="email" placeholder="Email" style="width:100%;padding:14px 16px;background:#F4F8F5;border:1px solid #D4E4DA;border-radius:12px;color:#1A2E22;font-size:1rem;margin-bottom:12px;outline:none;">'
            + '<button id="authOtpSendBtn" style="width:100%;padding:14px;background:linear-gradient(135deg,#3D8B5E,#6DBB8F);border:none;border-radius:12px;color:white;font-size:1rem;font-weight:700;cursor:pointer;">Send Code</button>'
            + '<p id="authOtpSendMsg" style="color:#5D7D6D;font-size:0.85rem;margin-top:12px;display:none;"></p>'
            + '</div>'
            + '<div id="authOtpStep2" style="display:none;">'
            + '<h3 style="color:#1A2E22;font-weight:800;margin-bottom:8px;">Enter Code</h3>'
            + '<p style="color:#5D7D6D;font-size:0.9rem;margin-bottom:20px;">Enter the 6-digit code from your email</p>'
            + '<input id="authOtpCode" type="text" maxlength="6" placeholder="000000" inputmode="numeric" autocomplete="one-time-code" style="width:100%;padding:14px 16px;background:#F4F8F5;border:1px solid #D4E4DA;border-radius:12px;color:#1A2E22;font-size:1.5rem;font-weight:900;letter-spacing:8px;text-align:center;margin-bottom:12px;outline:none;">'
            + '<button id="authOtpVerifyBtn" style="width:100%;padding:14px;background:linear-gradient(135deg,#3D8B5E,#2D7A4E);border:none;border-radius:12px;color:white;font-size:1rem;font-weight:700;cursor:pointer;">Verify</button>'
            + '<p id="authOtpVerifyMsg" style="color:#5D7D6D;font-size:0.85rem;margin-top:12px;display:none;"></p>'
            + '<button id="authOtpResendBtn" style="background:none;border:none;color:#3D8B5E;font-size:0.85rem;cursor:pointer;margin-top:8px;text-decoration:underline;">Resend</button>'
            + '</div>'
            + '<div id="authOtpStep3" style="display:none;">'
            + '<div style="font-size:3rem;margin-bottom:12px;color:#3D8B5E;">&#10003;</div>'
            + '<h3 style="color:#1A2E22;font-weight:800;margin-bottom:8px;">Verified!</h3>'
            + '<p style="color:#5D7D6D;font-size:0.9rem;margin-bottom:4px;">Credits: <span id="authOtpCredits" style="color:#3D8B5E;font-weight:700;">0</span></p>'
            + '</div>'
            + '</div>';
        document.body.appendChild(modal);
    }

    // ─── Shared references (set by setupOtpModal) ───
    var showOtpModal = function() {};

    // ─── Session Check on Load ───
    function checkSession() {
        fetch(API_BASE + '/api/paddle/me', { credentials: 'include' })
            .then(function(r) {
                if (r.ok) return r.json();
                throw new Error('not authenticated');
            })
            .then(function(d) {
                if (d.ok && d.user) {
                    authState.authenticated = true;
                    authState.email = d.user.email;
                    authState.user = d.user;
                    updateHeaderAuth();
                }
            })
            .catch(function() {
                authState.authenticated = false;
                updateHeaderAuth();
            });
    }

    // ─── Header Auth UI ───
    function updateHeaderAuth() {
        var btn = document.getElementById('authHeaderBtn');
        if (!btn) return;

        if (authState.authenticated && authState.user) {
            var bal = authState.user.credit_balance || 0;
            var freeUsed = authState.user.daily_free_used || 0;
            var freeLimit = authState.user.daily_free_limit || 2;
            var emailShort = authState.email.split('@')[0];
            if (emailShort.length > 8) emailShort = emailShort.substring(0, 8) + '..';

            var safeEmail = authState.email.replace(/[<>"'&]/g, '');
            if (bal > 0) {
                btn.innerHTML = '<span class="material-symbols-outlined" style="font-size:1.1rem;">toll</span>'
                    + '<span class="auth-credit-num">' + parseInt(bal, 10) + '</span>'
                    + '<span class="auth-email-short">' + _escText(emailShort) + '</span>';
                btn.title = safeEmail + ' | ' + parseInt(bal, 10) + ' credits';
            } else {
                var freeRemain = Math.max(0, freeLimit - freeUsed);
                btn.innerHTML = '<span class="material-symbols-outlined" style="font-size:1.1rem;">toll</span>'
                    + '<span class="auth-credit-num">' + freeRemain + '/' + freeLimit + '</span>'
                    + '<span class="auth-email-short">' + _escText(emailShort) + '</span>';
                btn.title = safeEmail + ' | ' + freeRemain + '/' + freeLimit;
            }
            btn.classList.add('auth-logged-in');
            btn.classList.remove('auth-logged-out');
            btn.onclick = showAuthMenu;
        } else {
            btn.innerHTML = '<span class="material-symbols-outlined" style="font-size:1.1rem;">login</span>'
                + '<span class="auth-label">' + (pageLang === 'en' ? 'Login' : 'Login') + '</span>';
            btn.title = pageLang === 'en' ? 'Email Login' : 'Email Login';
            btn.classList.add('auth-logged-out');
            btn.classList.remove('auth-logged-in');
            btn.onclick = showOtpModal;
        }
    }

    function _escText(s) {
        var d = document.createElement('div');
        d.textContent = s;
        return d.innerHTML;
    }

    // ─── Auth Dropdown Menu ───
    function showAuthMenu(e) {
        e.stopPropagation();
        var existing = document.getElementById('authDropdown');
        if (existing) { existing.remove(); return; }

        var bal = parseInt((authState.user && authState.user.credit_balance) || 0, 10);
        var menu = document.createElement('div');
        menu.id = 'authDropdown';
        menu.innerHTML = '<div class="auth-dd-email">' + _escText(authState.email) + '</div>'
            + '<div class="auth-dd-credits"><span class="material-symbols-outlined" style="font-size:1rem;vertical-align:middle;">toll</span> '
            + 'Credits: <strong>' + bal + '</strong></div>'
            + '<div id="authDdHistory" class="auth-dd-history" style="display:none;max-height:180px;overflow-y:auto;font-size:0.78rem;border-top:1px solid var(--border,#D4E4DA);padding:8px 12px;"></div>'
            + '<button class="auth-dd-item" id="authHistoryBtn">'
            + '<span class="material-symbols-outlined" style="font-size:1rem;">receipt_long</span> '
            + (pageLang === 'en' ? 'Credit History' : '크레딧 내역') + '</button>'
            + '<a class="auth-dd-item" href="' + (pageLang === 'en' ? '/pricing-en' : '/pricing') + '">'
            + '<span class="material-symbols-outlined" style="font-size:1rem;">add_circle</span> '
            + (pageLang === 'en' ? 'Buy Credits' : '크레딧 충전') + '</a>'
            + '<button class="auth-dd-item auth-dd-logout" id="authLogoutBtn">'
            + '<span class="material-symbols-outlined" style="font-size:1rem;">logout</span> '
            + (pageLang === 'en' ? 'Logout' : '로그아웃') + '</button>';

        var btn = document.getElementById('authHeaderBtn');
        btn.parentNode.style.position = 'relative';
        btn.parentNode.appendChild(menu);

        document.getElementById('authHistoryBtn').addEventListener('click', function() {
            var histDiv = document.getElementById('authDdHistory');
            if (histDiv.style.display !== 'none') { histDiv.style.display = 'none'; return; }
            histDiv.innerHTML = '<div style="color:var(--text-muted,#5D7D6D);padding:4px 0;">Loading...</div>';
            histDiv.style.display = 'block';
            fetch(API_BASE + '/api/paddle/credits/history', { credentials: 'include' })
                .then(function(r) { return r.json(); })
                .then(function(d) {
                    if (!d.history || d.history.length === 0) {
                        histDiv.innerHTML = '<div style="color:var(--text-muted,#5D7D6D);padding:4px 0;">'
                            + (pageLang === 'en' ? 'No history yet' : '내역이 없습니다') + '</div>';
                        return;
                    }
                    var html = '';
                    d.history.forEach(function(h) {
                        var isDeduct = h.amount < 0;
                        var color = isDeduct ? '#C45454' : '#3D8B5E';
                        var sign = isDeduct ? '' : '+';
                        var typeLabel = h.type === 'expert_deduct' ? (pageLang === 'en' ? 'Expert' : '전문가') :
                            h.type === 'question_deduct' ? (pageLang === 'en' ? 'Query' : '질문') :
                            h.type === 'purchase' ? (pageLang === 'en' ? 'Purchase' : '충전') : _escText(String(h.type));
                        var date = h.created_at ? _escText(String(h.created_at).substring(0, 10)) : '';
                        var safeAmount = _escText(String(sign) + String(Math.abs(h.amount)));
                        html += '<div style="display:flex;justify-content:space-between;padding:3px 0;border-bottom:1px solid rgba(0,0,0,0.05);">'
                            + '<span>' + typeLabel + ' <span style="opacity:0.5;font-size:0.7rem;">' + date + '</span></span>'
                            + '<span style="color:' + color + ';font-weight:700;">' + safeAmount + '</span></div>';
                    });
                    histDiv.innerHTML = html;
                })
                .catch(function() {
                    histDiv.innerHTML = '<div style="color:#C45454;padding:4px 0;">Error</div>';
                });
        });

        document.getElementById('authLogoutBtn').addEventListener('click', function() {
            fetch(API_BASE + '/api/paddle/logout', { method: 'POST', credentials: 'include' })
                .finally(function() {
                    authState.authenticated = false;
                    authState.user = null;
                    authState.email = '';
                    window.__lawmadiAuth = { authenticated: false, email: '', user: null };
                    localStorage.removeItem('lm_email');
                    localStorage.removeItem('lawmadi-chat-history');
                    localStorage.removeItem('lawmadi-favorites');
                    menu.remove();
                    updateHeaderAuth();
                });
        });

        setTimeout(function() {
            document.addEventListener('click', function closeDD() {
                var dd = document.getElementById('authDropdown');
                if (dd) dd.remove();
                document.removeEventListener('click', closeDD);
            });
        }, 10);
    }

    // ─── OTP Modal Setup ───
    function setupOtpModal() {
        var modal = document.getElementById('authOtpModal');
        if (!modal) return;

        var step1 = document.getElementById('authOtpStep1');
        var step2 = document.getElementById('authOtpStep2');
        var step3 = document.getElementById('authOtpStep3');

        showOtpModal = function() {
            modal.style.display = 'flex';
            document.body.style.overflow = 'hidden';
            step1.style.display = 'block';
            step2.style.display = 'none';
            step3.style.display = 'none';
            var emailInput = document.getElementById('authOtpEmail');
            var saved = localStorage.getItem('lm_email');
            if (saved) emailInput.value = saved;
            if (authState.email) emailInput.value = authState.email;
            emailInput.focus();
        }

        function hideOtpModal() { modal.style.display = 'none'; document.body.style.overflow = ''; }

        document.getElementById('authOtpClose').addEventListener('click', hideOtpModal);
        modal.addEventListener('click', function(e) {
            if (e.target === modal) hideOtpModal();
        });
        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape' && modal.style.display === 'flex') hideOtpModal();
        });

        // Send OTP
        document.getElementById('authOtpSendBtn').addEventListener('click', function() {
            var email = document.getElementById('authOtpEmail').value.trim().toLowerCase();
            if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
                showMsg('authOtpSendMsg', 'Please enter a valid email', true);
                return;
            }
            authState.email = email;
            var btn = this;
            btn.disabled = true;
            btn.textContent = 'Sending...';

            fetch(API_BASE + '/api/paddle/otp/send', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify({ email: email })
            })
            .then(function(r) { return r.json().then(function(d) { return { ok: r.ok, data: d }; }); })
            .then(function(res) {
                btn.disabled = false;
                btn.textContent = 'Send Code';
                if (res.ok) {
                    step1.style.display = 'none';
                    step2.style.display = 'block';
                    document.getElementById('authOtpCode').focus();
                    showMsg('authOtpVerifyMsg', 'Check your email (5 min)', false);
                } else {
                    showMsg('authOtpSendMsg', res.data.detail || res.data.error || 'Send failed', true);
                }
            })
            .catch(function() {
                btn.disabled = false;
                btn.textContent = 'Send Code';
                showMsg('authOtpSendMsg', 'Network error', true);
            });
        });

        // Verify OTP
        document.getElementById('authOtpVerifyBtn').addEventListener('click', verifyOtp);
        document.getElementById('authOtpCode').addEventListener('keydown', function(e) {
            if (e.key === 'Enter') verifyOtp();
        });

        function verifyOtp() {
            var code = document.getElementById('authOtpCode').value.trim();
            if (!code || code.length !== 6) {
                showMsg('authOtpVerifyMsg', 'Enter 6-digit code', true);
                return;
            }
            var btn = document.getElementById('authOtpVerifyBtn');
            btn.disabled = true;
            btn.textContent = 'Verifying...';

            fetch(API_BASE + '/api/paddle/otp/verify', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify({ email: authState.email, code: code })
            })
            .then(function(r) { return r.json().then(function(d) { return { ok: r.ok, data: d }; }); })
            .then(function(res) {
                btn.disabled = false;
                btn.textContent = 'Verify';
                if (res.ok) {
                    authState.authenticated = true;
                    authState.user = res.data.user || null;
                    localStorage.setItem('lm_email', authState.email);

                    step2.style.display = 'none';
                    step3.style.display = 'block';

                    var credEl = document.getElementById('authOtpCredits');
                    if (credEl && authState.user) {
                        credEl.textContent = authState.user.credit_balance || 0;
                    }

                    setTimeout(function() {
                        hideOtpModal();
                        updateHeaderAuth();
                    }, 1200);
                } else {
                    showMsg('authOtpVerifyMsg', res.data.error || 'Verification failed', true);
                }
            })
            .catch(function() {
                btn.disabled = false;
                btn.textContent = 'Verify';
                showMsg('authOtpVerifyMsg', 'Network error', true);
            });
        }

        // Resend
        document.getElementById('authOtpResendBtn').addEventListener('click', function() {
            step2.style.display = 'none';
            step1.style.display = 'block';
            document.getElementById('authOtpSendBtn').click();
        });

        // Expose openAuthModal for external callers
        if (typeof window.UI !== 'undefined') {
            window.UI.openAuthModal = showOtpModal;
        } else {
            window.UI = { openAuthModal: showOtpModal };
        }
    }

    function showMsg(id, text, isError) {
        var el = document.getElementById(id);
        if (!el) return;
        el.textContent = text;
        el.style.display = 'block';
        el.style.color = isError ? '#C45454' : '#3D8B5E';
    }

    // ─── Init ───
    ensureAuthButton();
    ensureOtpModal();
    setupOtpModal();
    checkSession();
})();

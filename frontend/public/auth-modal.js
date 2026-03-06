/**
 * Lawmadi OS -- Auth Modal (Email OTP) + Header Credit Display
 * Shared by index.html / index-en.html
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
            + '<a class="auth-dd-item" href="/pricing' + (pageLang === 'en' ? '-en' : '') + '.html">'
            + '<span class="material-symbols-outlined" style="font-size:1rem;">add_circle</span> '
            + (pageLang === 'en' ? 'Buy Credits' : 'Buy Credits') + '</a>'
            + '<button class="auth-dd-item auth-dd-logout" id="authLogoutBtn">'
            + '<span class="material-symbols-outlined" style="font-size:1rem;">logout</span> '
            + (pageLang === 'en' ? 'Logout' : 'Logout') + '</button>';

        var btn = document.getElementById('authHeaderBtn');
        btn.parentNode.style.position = 'relative';
        btn.parentNode.appendChild(menu);

        document.getElementById('authLogoutBtn').addEventListener('click', function() {
            fetch(API_BASE + '/api/paddle/logout', { method: 'POST', credentials: 'include' })
                .finally(function() {
                    authState.authenticated = false;
                    authState.user = null;
                    authState.email = '';
                    localStorage.removeItem('lm_email');
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

    // ─── OTP Modal ───
    var modal = document.getElementById('authOtpModal');
    if (!modal) return;

    var step1 = document.getElementById('authOtpStep1');
    var step2 = document.getElementById('authOtpStep2');
    var step3 = document.getElementById('authOtpStep3');

    function showOtpModal() {
        modal.style.display = 'flex';
        step1.style.display = 'block';
        step2.style.display = 'none';
        step3.style.display = 'none';
        var emailInput = document.getElementById('authOtpEmail');
        var saved = localStorage.getItem('lm_email');
        if (saved) emailInput.value = saved;
        if (authState.email) emailInput.value = authState.email;
        emailInput.focus();
    }

    function hideOtpModal() { modal.style.display = 'none'; }

    document.getElementById('authOtpClose').addEventListener('click', hideOtpModal);
    modal.addEventListener('click', function(e) {
        if (e.target === modal) hideOtpModal();
    });

    // Send OTP
    document.getElementById('authOtpSendBtn').addEventListener('click', function() {
        var email = document.getElementById('authOtpEmail').value.trim().toLowerCase();
        if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
            showMsg('authOtpSendMsg', pageLang === 'en' ? 'Please enter a valid email' : 'Please enter a valid email', true);
            return;
        }
        authState.email = email;
        var btn = this;
        btn.disabled = true;
        btn.textContent = pageLang === 'en' ? 'Sending...' : 'Sending...';

        fetch(API_BASE + '/api/paddle/otp/send', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({ email: email })
        })
        .then(function(r) { return r.json().then(function(d) { return { ok: r.ok, data: d }; }); })
        .then(function(res) {
            btn.disabled = false;
            btn.textContent = pageLang === 'en' ? 'Send Code' : 'Send Code';
            if (res.ok) {
                step1.style.display = 'none';
                step2.style.display = 'block';
                document.getElementById('authOtpCode').focus();
                showMsg('authOtpVerifyMsg', pageLang === 'en' ? 'Check your email (5 min)' : 'Check your email (5 min)', false);
            } else {
                showMsg('authOtpSendMsg', res.data.detail || res.data.error || 'Send failed', true);
            }
        })
        .catch(function() {
            btn.disabled = false;
            btn.textContent = pageLang === 'en' ? 'Send Code' : 'Send Code';
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
            showMsg('authOtpVerifyMsg', pageLang === 'en' ? 'Enter 6-digit code' : 'Enter 6-digit code', true);
            return;
        }
        var btn = document.getElementById('authOtpVerifyBtn');
        btn.disabled = true;
        btn.textContent = pageLang === 'en' ? 'Verifying...' : 'Verifying...';

        fetch(API_BASE + '/api/paddle/otp/verify', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({ email: authState.email, code: code })
        })
        .then(function(r) { return r.json().then(function(d) { return { ok: r.ok, data: d }; }); })
        .then(function(res) {
            btn.disabled = false;
            btn.textContent = pageLang === 'en' ? 'Verify' : 'Verify';
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
            btn.textContent = pageLang === 'en' ? 'Verify' : 'Verify';
            showMsg('authOtpVerifyMsg', 'Network error', true);
        });
    }

    // Resend
    document.getElementById('authOtpResendBtn').addEventListener('click', function() {
        step2.style.display = 'none';
        step1.style.display = 'block';
        document.getElementById('authOtpSendBtn').click();
    });

    function showMsg(id, text, isError) {
        var el = document.getElementById(id);
        if (!el) return;
        el.textContent = text;
        el.style.display = 'block';
        el.style.color = isError ? '#ef4444' : '#10b981';
    }

    // Init
    checkSession();
})();

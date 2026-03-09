/**
 * Cookie Consent Banner
 * GA4 is blocked until user accepts analytics cookies.
 * Session cookie (__session) is strictly necessary — no consent needed.
 */
(function() {
    'use strict';
    var CONSENT_KEY = 'lm_cookie_consent';
    var GA_ID = 'G-C3VFDP0QPZ';

    var isKo = !location.pathname.includes('-en') && !location.pathname.includes('/en');

    var text = isKo
        ? { msg: '이 사이트는 서비스 개선을 위해 분석 쿠키를 사용합니다.', accept: '동의', reject: '거부', policy: '개인정보처리방침' }
        : { msg: 'This site uses analytics cookies to improve our service.', accept: 'Accept', reject: 'Decline', policy: 'Privacy Policy' };

    var policyUrl = isKo ? '/privacy' : '/privacy-en';

    function getConsent() { return localStorage.getItem(CONSENT_KEY); }

    function loadGA() {
        if (document.getElementById('ga-script')) return;
        var s = document.createElement('script');
        s.id = 'ga-script';
        s.async = true;
        s.src = 'https://www.googletagmanager.com/gtag/js?id=' + GA_ID;
        document.head.appendChild(s);
        window.dataLayer = window.dataLayer || [];
        function gtag(){dataLayer.push(arguments);}
        gtag('js', new Date());
        gtag('config', GA_ID);
        window.gtag = gtag;
    }

    function showBanner() {
        var banner = document.createElement('div');
        banner.id = 'cookieBanner';
        banner.style.cssText = 'position:fixed;bottom:0;left:0;right:0;background:#1e293b;color:#e2e8f0;padding:14px 20px;display:flex;align-items:center;justify-content:center;gap:12px;z-index:99999;font-size:14px;flex-wrap:wrap;box-shadow:0 -2px 10px rgba(0,0,0,0.3);';
        banner.innerHTML =
            '<span>' + text.msg + ' <a href="' + policyUrl + '" style="color:#60a5fa;text-decoration:underline;">' + text.policy + '</a></span>' +
            '<button id="cookieAccept" style="background:#2563eb;color:white;border:none;padding:8px 18px;border-radius:6px;cursor:pointer;font-weight:600;">' + text.accept + '</button>' +
            '<button id="cookieReject" style="background:transparent;color:#94a3b8;border:1px solid #475569;padding:8px 18px;border-radius:6px;cursor:pointer;">' + text.reject + '</button>';
        document.body.appendChild(banner);

        document.getElementById('cookieAccept').addEventListener('click', function() {
            localStorage.setItem(CONSENT_KEY, 'accepted');
            banner.remove();
            loadGA();
        });
        document.getElementById('cookieReject').addEventListener('click', function() {
            localStorage.setItem(CONSENT_KEY, 'rejected');
            banner.remove();
        });
    }

    // Init
    var consent = getConsent();
    if (consent === 'accepted') {
        loadGA();
    } else if (!consent) {
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', showBanner);
        } else {
            showBanner();
        }
    }
    // 'rejected' → do nothing (no GA, no banner)
})();

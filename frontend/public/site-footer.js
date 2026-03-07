/**
 * Lawmadi OS — Site Footer (서브 페이지 전용)
 * 메인 페이지: 사이드바 + 모바일 시트에 모든 정보 포함 → footer 없음
 * 서브 페이지: 면책 고지 + 정책 링크 + 저작권 표시
 * 환불 정책 페이지: 사업자 정보 직접 포함 → footer 없음
 */
(function() {
    'use strict';

    var isMainPage = /\/(index|index-en)?(\.html)?$/.test(location.pathname) || location.pathname === '/' || location.pathname === '/en';
    var isRefundPage = /\/refund(-en)?(\.html)?$/.test(location.pathname);

    // 메인 페이지, 환불 정책 페이지에서는 footer 생략
    if (isMainPage || isRefundPage) return;

    var isEn = location.pathname.indexOf('-en') !== -1 || location.pathname.indexOf('/en') !== -1;

    var footerHTML = isEn
        ? '<footer class="site-footer">'
            + '<div class="site-footer-inner">'
            + '<div class="footer-disclaimer">'
            + '<span class="material-symbols-outlined" style="font-size:1rem;vertical-align:middle;margin-right:4px;">info</span>'
            + 'Lawmadi OS is an AI-powered legal information service and does not provide legal advice by a licensed attorney.'
            + '</div>'
            + '<div class="footer-links">'
            + '<a href="/terms-en.html">Terms</a>'
            + '<a href="/privacy-en.html">Privacy</a>'
            + '<a href="/pricing-en.html">Pricing</a>'
            + '<a href="/refund-en.html">Refund</a>'
            + '</div>'
            + '<div class="footer-copy">&copy; 2026 Lawmadi. All rights reserved.</div>'
            + '</div>'
            + '</footer>'
        : '<footer class="site-footer">'
            + '<div class="site-footer-inner">'
            + '<div class="footer-disclaimer">'
            + '<span class="material-symbols-outlined" style="font-size:1rem;vertical-align:middle;margin-right:4px;">info</span>'
            + '본 서비스는 법률 정보를 제공하는 AI 시스템이며, 변호사에 의한 법률 자문을 대체하지 않습니다.'
            + '</div>'
            + '<div class="footer-links">'
            + '<a href="/terms.html">이용약관</a>'
            + '<a href="/privacy.html">개인정보처리방침</a>'
            + '<a href="/pricing.html">요금제</a>'
            + '<a href="/refund.html">환불정책</a>'
            + '</div>'
            + '<div class="footer-copy">&copy; 2026 법마디 Lawmadi. All rights reserved.</div>'
            + '</div>'
            + '</footer>';

    var style = document.createElement('style');
    style.textContent = ''
        + '.site-footer{background:var(--footer-bg,#0f172a);color:var(--footer-text,#94a3b8);padding:32px 20px;font-size:0.8rem;line-height:1.7;border-top:1px solid var(--footer-border,rgba(255,255,255,0.08));}'
        + '.site-footer-inner{max-width:800px;margin:0 auto;text-align:center;}'
        + '.footer-disclaimer{background:rgba(245,158,11,0.1);border:1px solid rgba(245,158,11,0.25);border-radius:8px;padding:10px 16px;margin-bottom:16px;color:var(--footer-warn,#fbbf24);font-size:0.78rem;font-weight:600;}'
        + '.footer-links{margin-bottom:10px;}'
        + '.footer-links a{color:var(--footer-text,#94a3b8);text-decoration:none;margin:0 10px;font-size:0.75rem;}'
        + '.footer-links a:hover{color:#e2e8f0;text-decoration:underline;}'
        + '.footer-copy{font-size:0.72rem;opacity:0.6;}';
    document.head.appendChild(style);

    var scripts = document.body.querySelectorAll('body > script');
    var temp = document.createElement('div');
    temp.innerHTML = footerHTML;
    var footerEl = temp.firstChild;
    if (scripts.length > 0) {
        document.body.insertBefore(footerEl, scripts[0]);
    } else {
        document.body.appendChild(footerEl);
    }
})();

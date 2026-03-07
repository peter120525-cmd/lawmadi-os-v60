/**
 * Lawmadi OS — Site Footer (사업자 정보 + AI 면책 고지)
 * 전자상거래법 제10조 준수
 */
(function() {
    'use strict';

    var isEn = location.pathname.indexOf('-en') !== -1 || location.pathname.indexOf('/en') !== -1;
    var isMainPage = /\/(index|index-en)?(\.html)?$/.test(location.pathname) || location.pathname === '/';

    var footerHTML = isEn
        ? '<footer class="site-footer">'
            + '<div class="site-footer-inner">'
            + '<div class="footer-disclaimer">'
            + '<span class="material-symbols-outlined" style="font-size:1rem;vertical-align:middle;margin-right:4px;">info</span>'
            + 'Lawmadi OS is an AI-powered legal information service and does not provide legal advice by a licensed attorney.'
            + '</div>'
            + '<div class="footer-biz">'
            + '<span class="footer-biz-name">Lawmadi (법마디)</span>'
            + '<span class="footer-sep">|</span>'
            + '<span>Representative: Jaenam Choe</span>'
            + '<span class="footer-sep">|</span>'
            + '<span>Business Reg. No: 751-29-01826</span>'
            + '<br class="footer-br">'
            + '<span>Mail-order Business No: 2026-울산울주-0086</span>'
            + '<span class="footer-sep">|</span>'
            + '<span>Address: 41 Jakgwaedel-gil, Samnam-eup, Ulju-gun, Ulsan, Republic of Korea</span>'
            + '</div>'
            + '<div class="footer-contact">'
            + '<span class="material-symbols-outlined" style="font-size:0.9rem;vertical-align:middle;margin-right:4px;">mail</span>'
            + '<a href="mailto:choepeter@outlook.kr">choepeter@outlook.kr</a>'
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
            + '<div class="footer-biz">'
            + '<span class="footer-biz-name">법마디 (Lawmadi)</span>'
            + '<span class="footer-sep">|</span>'
            + '<span>대표자: 최재남</span>'
            + '<span class="footer-sep">|</span>'
            + '<span>사업자등록번호: 751-29-01826</span>'
            + '<br class="footer-br">'
            + '<span>통신판매업신고: 제 2026-울산울주-0086호</span>'
            + '<span class="footer-sep">|</span>'
            + '<span>주소: 울산광역시 울주군 삼남읍 작괘들길 41</span>'
            + '</div>'
            + '<div class="footer-contact">'
            + '<span class="material-symbols-outlined" style="font-size:0.9rem;vertical-align:middle;margin-right:4px;">mail</span>'
            + '고객문의: <a href="mailto:choepeter@outlook.kr">choepeter@outlook.kr</a>'
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
        + '.site-footer{background:var(--footer-bg,#0f172a);color:var(--footer-text,#94a3b8);padding:32px 20px;font-size:0.8rem;line-height:1.7;border-top:1px solid var(--footer-border,rgba(255,255,255,0.08));'
        + (isMainPage ? 'margin-bottom:72px;' : '') + '}'
        + '.site-footer-inner{max-width:800px;margin:0 auto;text-align:center;}'
        + '.footer-disclaimer{background:rgba(245,158,11,0.1);border:1px solid rgba(245,158,11,0.25);border-radius:8px;padding:10px 16px;margin-bottom:16px;color:var(--footer-warn,#fbbf24);font-size:0.78rem;font-weight:600;}'
        + '.footer-biz{margin-bottom:8px;color:var(--footer-text,#94a3b8);}'
        + '.footer-biz-name{font-weight:700;color:var(--footer-name,#e2e8f0);}'
        + '.footer-sep{margin:0 8px;opacity:0.4;}'
        + '.footer-contact{margin-bottom:12px;}'
        + '.footer-contact a{color:#60a5fa;text-decoration:none;}'
        + '.footer-contact a:hover{text-decoration:underline;}'
        + '.footer-links{margin-bottom:10px;}'
        + '.footer-links a{color:var(--footer-text,#94a3b8);text-decoration:none;margin:0 10px;font-size:0.75rem;}'
        + '.footer-links a:hover{color:#e2e8f0;text-decoration:underline;}'
        + '.footer-copy{font-size:0.72rem;opacity:0.6;}'
        + '.footer-br{display:none;}'
        + '@media(max-width:640px){.footer-sep{display:none;}.footer-biz span{display:block;}.footer-br{display:block;}}';
    document.head.appendChild(style);

    // Insert footer before </body>
    var mobileTabBar = document.querySelector('.mobile-tab-bar');
    var target = document.body;
    var temp = document.createElement('div');
    temp.innerHTML = footerHTML;
    var footerEl = temp.firstChild;

    if (mobileTabBar) {
        target.insertBefore(footerEl, mobileTabBar);
    } else {
        // Sub-pages: insert before last script or at end of body
        var scripts = target.querySelectorAll('body > script');
        if (scripts.length > 0) {
            target.insertBefore(footerEl, scripts[0]);
        } else {
            target.appendChild(footerEl);
        }
    }
})();

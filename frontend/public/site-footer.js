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
    var isChatPage = /\/leader-chat(\.html)?$/.test(location.pathname);
    var isPricingPage = /\/pricing(-en)?(\.html)?$/.test(location.pathname);

    // 메인/환불/채팅/요금제 페이지에서는 footer 생략
    // 채팅: 전체화면 채팅 UI (footer가 채팅 영역 축소)
    // 요금제: 자체 <footer>에 사업자 정보 포함 (전자상거래법)
    if (isMainPage || isRefundPage || isChatPage || isPricingPage) return;

    var isEn = location.pathname.indexOf('-en') !== -1 || location.pathname.indexOf('/en') !== -1;

    var footerHTML = isEn
        ? '<footer class="site-footer">'
            + '<div class="site-footer-inner">'
            + '<div class="footer-disclaimer">'
            + '<span class="material-symbols-outlined" style="font-size:1rem;vertical-align:middle;margin-right:4px;">info</span>'
            + 'Lawmadi OS is an AI-powered legal information service and does not provide legal advice by a licensed attorney.'
            + '</div>'
            + '<div class="footer-biz">'
            + '<span style="font-weight:700;color:#D4E4DA;">Lawmadi</span>'
            + '<span class="sep">|</span>CEO: Jaenam Choi'
            + '<span class="sep">|</span>Business Reg: 751-29-01826'
            + '<br>'
            + '<span>E-Commerce Reg: 2026-울산울주-0086</span>'
            + '<span class="sep">|</span>Ulsan, South Korea'
            + '<br>'
            + '<span class="material-symbols-outlined" style="font-size:0.9rem;vertical-align:middle;margin-right:4px;">mail</span>'
            + 'Contact: <a href="mailto:choepeter@outlook.kr" style="color:#8DD4AA;text-decoration:none;">choepeter@outlook.kr</a>'
            + '</div>'
            + '<div class="footer-links">'
            + '<a href="/terms-en">Terms</a>'
            + '<a href="/privacy-en">Privacy</a>'
            + '<a href="/pricing-en">Pricing</a>'
            + '<a href="/refund-en">Refund</a>'
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
            + '<span style="font-weight:700;color:#D4E4DA;">법마디 (Lawmadi)</span>'
            + '<span class="sep">|</span>대표자: 최재남'
            + '<span class="sep">|</span>사업자등록번호: 751-29-01826'
            + '<br>'
            + '<span>통신판매업신고: 제 2026-울산울주-0086호</span>'
            + '<span class="sep">|</span>주소: 울산광역시 울주군 삼남읍 작괘들길 41'
            + '<br>'
            + '<span class="material-symbols-outlined" style="font-size:0.9rem;vertical-align:middle;margin-right:4px;">mail</span>'
            + '고객문의: <a href="mailto:choepeter@outlook.kr" style="color:#8DD4AA;text-decoration:none;">choepeter@outlook.kr</a>'
            + '</div>'
            + '<div class="footer-links">'
            + '<a href="/terms">이용약관</a>'
            + '<a href="/privacy">개인정보처리방침</a>'
            + '<a href="/pricing">요금제</a>'
            + '<a href="/refund">환불정책</a>'
            + '</div>'
            + '<div class="footer-copy">&copy; 2026 법마디 Lawmadi. All rights reserved.</div>'
            + '</div>'
            + '</footer>';

    var style = document.createElement('style');
    style.textContent = ''
        + '.site-footer{background:var(--footer-bg,#101A15);color:var(--footer-text,#7A9A88);padding:32px 20px;font-size:0.8rem;line-height:1.7;border-top:1px solid var(--footer-border,rgba(255,255,255,0.08));}'
        + '.site-footer-inner{max-width:800px;margin:0 auto;text-align:center;}'
        + '.footer-disclaimer{background:rgba(184,146,45,0.1);border:1px solid rgba(184,146,45,0.25);border-radius:8px;padding:10px 16px;margin-bottom:16px;color:var(--footer-warn,#fbbf24);font-size:0.78rem;font-weight:600;}'
        + '.footer-biz{margin-bottom:12px;font-size:0.78rem;line-height:1.8;}'
        + '.footer-biz .sep{margin:0 8px;opacity:0.4;}'
        + '.footer-links{margin-bottom:10px;}'
        + '.footer-links a{color:var(--footer-text,#7A9A88);text-decoration:none;margin:0 10px;font-size:0.75rem;}'
        + '.footer-links a:hover{color:#D4E4DA;text-decoration:underline;}'
        + '.footer-copy{font-size:0.72rem;opacity:0.6;}';
    document.head.appendChild(style);

    var temp = document.createElement('div');
    temp.innerHTML = footerHTML;
    var footerEl = temp.firstChild;
    document.body.appendChild(footerEl);
})();

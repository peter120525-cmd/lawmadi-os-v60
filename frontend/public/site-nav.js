/**
 * Lawmadi OS — Site Navigation Bar (서브 페이지 공통)
 * 인증 상태 표시 + 다크모드 + 홈 + 언어 전환
 * 모든 서브 페이지에서 로그인 상태를 유지합니다.
 */
(function() {
    'use strict';

    // 메인 페이지에서는 실행하지 않음 (자체 헤더 사용)
    var path = location.pathname;
    var isMain = /\/(index|index-en)?(\.html)?$/.test(path) || path === '/' || path === '/en';
    if (isMain) return;

    var isEn = path.indexOf('-en') !== -1 || path.indexOf('/en') !== -1;
    var homeUrl = isEn ? '/index-en.html' : '/index.html';
    var langUrl = '';
    var langLabel = '';

    // 현재 페이지의 반대 언어 URL 계산 (쿼리 파라미터 유지)
    var qs = location.search || '';
    if (isEn) {
        langUrl = path.replace('-en', '').replace('/en', '/') + qs;
        langLabel = 'KO';
    } else {
        // 파일명에 -en 추가
        langUrl = path.replace(/\.html$/, '-en.html');
        if (langUrl === path) langUrl = path + '-en';
        langUrl += qs;
        langLabel = 'EN';
    }

    // ─── 다크모드 복원 ───
    var savedDark = localStorage.getItem('lawmadi-dark-mode');
    if (savedDark === null || savedDark === 'true') {
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
        + '.site-nav-dropdown{display:none;position:absolute;top:calc(100% + 6px);right:0;background:#1e293b;border:1px solid #334155;border-radius:10px;box-shadow:0 8px 24px rgba(0,0,0,0.4);min-width:150px;padding:4px 0;z-index:10000;}'
        + 'body:not(.dark-mode) .site-nav-dropdown{background:#fff;border-color:#e2e8f0;box-shadow:0 8px 24px rgba(0,0,0,0.12);}'
        + '.site-nav-dd-item{display:flex;align-items:center;gap:8px;width:100%;padding:9px 14px;background:none;border:none;color:#e2e8f0;font-size:0.85rem;cursor:pointer;transition:background 0.15s;text-align:left;}'
        + 'body:not(.dark-mode) .site-nav-dd-item{color:#334155;}'
        + '.site-nav-dd-item:hover{background:#334155;}'
        + 'body:not(.dark-mode) .site-nav-dd-item:hover{background:#f1f5f9;}'
        + '.site-nav-dd-item .material-symbols-outlined{font-size:1rem;color:#94a3b8;}'
        + 'body{padding-top:50px !important;}';
    document.head.appendChild(style);

    // ─── 기존 back-button, 언어토글 숨기기 ───
    setTimeout(function() {
        // 기존 back-button 숨기기
        var backBtns = document.querySelectorAll('.back-button');
        backBtns.forEach(function(b) { b.style.display = 'none'; });
        // 기존 고정 위치 언어 토글 숨기기 (fixed top-right links)
        document.querySelectorAll('a[style*="position:fixed"][style*="top:"]').forEach(function(a) {
            if (a.textContent.trim() === 'EN' || a.textContent.trim() === 'KO') {
                a.style.display = 'none';
            }
        });
    }, 0);

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
        +   '<a href="' + homeUrl + '?auth=1" class="site-nav-btn site-nav-auth" id="siteNavAuth">'
        +     '<span class="material-symbols-outlined">login</span>'
        +     '<span>Login</span>'
        +   '</a>'
        +   '<div class="site-nav-more-wrap">'
        +     '<button class="site-nav-btn" id="siteNavMore" aria-label="More">'
        +       '<span class="material-symbols-outlined">more_vert</span>'
        +     '</button>'
        +     '<div class="site-nav-dropdown" id="siteNavDropdown">'
        +       '<button class="site-nav-dd-item" id="siteNavDark">'
        +         '<span class="material-symbols-outlined">dark_mode</span>'
        +         '<span>' + (isEn ? 'Dark Mode' : '다크모드') + '</span>'
        +       '</button>'
        +       '<a href="' + langUrl + '" class="site-nav-dd-item" style="text-decoration:none;">'
        +         '<span class="material-symbols-outlined">translate</span>'
        +         '<span>' + langLabel + '</span>'
        +       '</a>'
        +     '</div>'
        +   '</div>'
        + '</div>';

    document.body.insertBefore(nav, document.body.firstChild);

    // ─── 인증 상태 확인 ───
    var authBtn = document.getElementById('siteNavAuth');
    fetch('/api/paddle/me', { credentials: 'include' })
        .then(function(r) { if (r.ok) return r.json(); throw new Error('no'); })
        .then(function(d) {
            if (d.ok && d.user) {
                var email = d.user.email || '';
                var bal = d.user.credit_balance || 0;
                var short = email.split('@')[0];
                if (short.length > 8) short = short.substring(0, 8) + '..';
                authBtn.classList.add('logged-in');
                authBtn.href = homeUrl;
                authBtn.innerHTML = '<span class="material-symbols-outlined">toll</span>'
                    + '<span class="site-nav-credit">' + parseInt(bal, 10) + '</span>'
                    + '<span>' + _esc(short) + '</span>';
                authBtn.title = email;
            }
        })
        .catch(function() {});

    function _esc(s) {
        var d = document.createElement('div');
        d.textContent = s;
        return d.innerHTML;
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

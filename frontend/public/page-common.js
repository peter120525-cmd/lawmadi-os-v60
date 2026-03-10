// In-app browser detection & viewport fix
(function() {
    var ua = navigator.userAgent || '';
    var isInApp = /KAKAOTALK|FBAN|FBAV|Instagram|Line\/|NAVER|Snapchat|Twitter|SamsungBrowser|Whale|DaumApps|MicroMessenger|Telegram/i.test(ua);
    if (isInApp) {
        document.body.classList.add('is-inapp-browser');
        function setVH() {
            var vh = window.innerHeight;
            document.documentElement.style.setProperty('--app-height', vh + 'px');
            document.body.style.height = vh + 'px';
        }
        setVH();
        window.addEventListener('resize', setVH);
    }
})();

// Page load animation
window.addEventListener('load', function() {
    document.body.style.opacity = '0';
    setTimeout(function() {
        document.body.style.transition = 'opacity 0.5s';
        document.body.style.opacity = '1';
    }, 100);
});


// Disable right-click context menu
document.addEventListener('contextmenu', function(e) { e.preventDefault(); });

// Safe localStorage JSON parser (prevents crash on corrupt data)
window.safeParseJSON = function(key, fallback) {
    try {
        var raw = localStorage.getItem(key);
        if (!raw) return fallback;
        var parsed = JSON.parse(raw);
        if (fallback !== undefined && typeof parsed !== typeof fallback) return fallback;
        return parsed;
    } catch(e) {
        localStorage.removeItem(key);
        return fallback;
    }
};

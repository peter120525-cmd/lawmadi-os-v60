var allLeaders = [];
var currentFilter = 'all';

// Leader profile image mapping
var leaderImages = {
    'L01': { profile: 'images/leaders/L01-hwiyul.jpg', banner: 'images/leaders/L01-hwiyul-banner.jpg', video: 'videos/leaders/L01-hwiyul.webm' },
    'L02': { profile: 'images/leaders/L02-bonui.jpg', banner: 'images/leaders/L02-bonui-banner.jpg', video: 'videos/leaders/L02-bonui.webm' },
    'L03': { profile: 'images/leaders/L03-damseul.jpg', banner: 'images/leaders/L03-damseul-banner.jpg', video: 'videos/leaders/L03-damseul.webm' },
    'L04': { profile: 'images/leaders/L04-aki.jpg', banner: 'images/leaders/L04-aki-banner.jpg', video: 'videos/leaders/L04-aki.webm' },
    'L05': { profile: 'images/leaders/L05-yeonwoo.jpg', banner: 'images/leaders/L05-yeonwoo-banner.jpg', video: 'videos/leaders/L05-yeonwoo.webm' },
    'L06': { profile: 'images/leaders/L06-byeori.jpg', banner: 'images/leaders/L06-byeori-banner.jpg', video: 'videos/leaders/L06-byeori.webm' },
    'L07': { profile: 'images/leaders/L07-hanui.jpg', banner: 'images/leaders/L07-hanui-banner.jpg', video: 'videos/leaders/L07-hanui.webm' },
    'L08': { profile: 'images/leaders/L08-onyu.jpg', banner: 'images/leaders/L08-onyu-banner.jpg', video: 'videos/leaders/L08-onyu.webm' },
    'L09': { profile: 'images/leaders/L09-hanul.jpg', banner: 'images/leaders/L09-hanul-banner.jpg', video: 'videos/leaders/L09-hanul.webm' },
    'L10': { profile: 'images/leaders/L10-gyeolhwi.jpg', banner: 'images/leaders/L10-gyeolhwi-banner.jpg', video: 'videos/leaders/L10-gyeolhwi.webm' },
    'L11': { profile: 'images/leaders/L11-oreum.jpg', banner: 'images/leaders/L11-oreum-banner.jpg', video: 'videos/leaders/L11-oreum.webm' },
    'L12': { profile: 'images/leaders/L12-aseul.jpg', banner: 'images/leaders/L12-aseul-banner.jpg', video: 'videos/leaders/L12-aseul.webm' },
    'L13': { profile: 'images/leaders/L13-nuri.jpg', banner: 'images/leaders/L13-nuri-banner.jpg', video: 'videos/leaders/L13-nuri.webm' },
    'L14': { profile: 'images/leaders/L14-dasom.jpg', banner: 'images/leaders/L14-dasom-banner.jpg', video: 'videos/leaders/L14-dasom.webm' },
    'L15': { profile: 'images/leaders/L15-byeolha.jpg', banner: 'images/leaders/L15-byeolha-banner.jpg', video: 'videos/leaders/L15-byeolha.webm' },
    'L16': { profile: 'images/leaders/L16-seula.jpg', banner: 'images/leaders/L16-seula-banner.jpg', video: 'videos/leaders/L16-seula.webm' },
    'L17': { profile: 'images/leaders/L17-mir.jpg', banner: 'images/leaders/L17-mir-banner.jpg', video: 'videos/leaders/L17-mir.webm' },
    'L18': { profile: 'images/leaders/L18-daon.jpg', banner: 'images/leaders/L18-daon-banner.jpg', video: 'videos/leaders/L18-daon.webm' },
    'L19': { profile: 'images/leaders/L19-selong.jpg', banner: 'images/leaders/L19-selong-banner.jpg', video: 'videos/leaders/L19-selong.webm' },
    'L20': { profile: 'images/leaders/L20-chansol.jpg', banner: 'images/leaders/L20-chansol-banner.jpg', video: 'videos/leaders/L20-chansol.webm' },
    'L21': { profile: 'images/leaders/L21-sebin.jpg', banner: 'images/leaders/L21-sebin-banner.jpg', video: 'videos/leaders/L21-sebin.webm' },
    'L22': { profile: 'images/leaders/L22-gaon.jpg', banner: 'images/leaders/L22-gaon-banner.jpg', video: 'videos/leaders/L22-gaon.webm' },
    'L23': { profile: 'images/leaders/L23-seoun.jpg', banner: 'images/leaders/L23-seoun-banner.jpg', video: 'videos/leaders/L23-seoun.webm' },
    'L24': { profile: 'images/leaders/L24-doul.jpg', banner: 'images/leaders/L24-doul-banner.jpg', video: 'videos/leaders/L24-doul.webm' },
    'L25': { profile: 'images/leaders/L25-damwoo.jpg', banner: 'images/leaders/L25-damwoo-banner.jpg', video: 'videos/leaders/L25-damwoo.webm' },
    'L26': { profile: 'images/leaders/L26-jinu.jpg', banner: 'images/leaders/L26-jinu-banner.jpg', video: 'videos/leaders/L26-jinu.webm' },
    'L27': { profile: 'images/leaders/L27-ruda.jpg', banner: 'images/leaders/L27-ruda-banner.jpg', video: 'videos/leaders/L27-ruda.webm' },
    'L28': { profile: 'images/leaders/L28-haeseul.jpg', banner: 'images/leaders/L28-haeseul-banner.jpg', video: 'videos/leaders/L28-haeseul.webm' },
    'L29': { profile: 'images/leaders/L29-raon.jpg', banner: 'images/leaders/L29-raon-banner.jpg', video: 'videos/leaders/L29-raon.webm' },
    'L30': { profile: 'images/leaders/L30-damwoo.jpg', banner: 'images/leaders/L30-damwoo-banner.jpg', video: 'videos/leaders/L30-damwoo.webm' },
    'L31': { profile: 'images/leaders/L31-roun.jpg', banner: 'images/leaders/L31-roun-banner.jpg', video: 'videos/leaders/L31-roun.webm' },
    'L32': { profile: 'images/leaders/L32-bareum.jpg', banner: 'images/leaders/L32-bareum-banner.jpg', video: 'videos/leaders/L32-bareum.webm' },
    'L33': { profile: 'images/leaders/L33-byeoli.jpg', banner: 'images/leaders/L33-byeoli-banner.jpg', video: 'videos/leaders/L33-byeoli.webm' },
    'L34': { profile: 'images/leaders/L34-jinu.jpg', banner: 'images/leaders/L34-jinu-banner.jpg', video: 'videos/leaders/L34-jinu.webm' },
    'L35': { profile: 'images/leaders/L35-maru.jpg', banner: 'images/leaders/L35-maru-banner.jpg', video: 'videos/leaders/L35-maru.webm' },
    'L36': { profile: 'images/leaders/L36-dana.jpg', banner: 'images/leaders/L36-dana-banner.jpg', video: 'videos/leaders/L36-dana.webm' },
    'L37': { profile: 'images/leaders/L37-yesol.jpg', banner: 'images/leaders/L37-yesol-banner.jpg', video: 'videos/leaders/L37-yesol.webm' },
    'L38': { profile: 'images/leaders/L38-seulbi.jpg', banner: 'images/leaders/L38-seulbi-banner.jpg', video: 'videos/leaders/L38-seulbi.webm' },
    'L39': { profile: 'images/leaders/L39-gaon.jpg', banner: 'images/leaders/L39-gaon-banner.jpg', video: 'videos/leaders/L39-gaon.webm' },
    'L40': { profile: 'images/leaders/L40-hangyeol.jpg', banner: 'images/leaders/L40-hangyeol-banner.jpg', video: 'videos/leaders/L40-hangyeol.webm' },
    'L41': { profile: 'images/leaders/L41-sandeul.jpg', banner: 'images/leaders/L41-sandeul-banner.jpg', video: 'videos/leaders/L41-sandeul.webm' },
    'L42': { profile: 'images/leaders/L42-haram.jpg', banner: 'images/leaders/L42-haram-banner.jpg', video: 'videos/leaders/L42-haram.webm' },
    'L43': { profile: 'images/leaders/L43-haena.jpg', banner: 'images/leaders/L43-haena-banner.jpg', video: 'videos/leaders/L43-haena.webm' },
    'L44': { profile: 'images/leaders/L44-boram.jpg', banner: 'images/leaders/L44-boram-banner.jpg', video: 'videos/leaders/L44-boram.webm' },
    'L45': { profile: 'images/leaders/L45-ireum.jpg', banner: 'images/leaders/L45-ireum-banner.jpg', video: 'videos/leaders/L45-ireum.webm' },
    'L46': { profile: 'images/leaders/L46-daol.jpg', banner: 'images/leaders/L46-daol-banner.jpg', video: 'videos/leaders/L46-daol.webm' },
    'L47': { profile: 'images/leaders/L47-saeron.jpg', banner: 'images/leaders/L47-saeron-banner.jpg', video: 'videos/leaders/L47-saeron.webm' },
    'L48': { profile: 'images/leaders/L48-narae.jpg', banner: 'images/leaders/L48-narae-banner.jpg', video: 'videos/leaders/L48-narae.webm' },
    'L49': { profile: 'images/leaders/L49-garam.jpg', banner: 'images/leaders/L49-garam-banner.jpg', video: 'videos/leaders/L49-garam.webm' },
    'L50': { profile: 'images/leaders/L50-bitna.jpg', banner: 'images/leaders/L50-bitna-banner.jpg', video: 'videos/leaders/L50-bitna.webm' },
    'L51': { profile: 'images/leaders/L51-soul.jpg', banner: 'images/leaders/L51-soul-banner.jpg', video: 'videos/leaders/L51-soul.webm' },
    'L52': { profile: 'images/leaders/L52-miso.jpg', banner: 'images/leaders/L52-miso-banner.jpg', video: 'videos/leaders/L52-miso.webm' },
    'L53': { profile: 'images/leaders/L53-neulsol.jpg', banner: 'images/leaders/L53-neulsol-banner.jpg', video: 'videos/leaders/L53-neulsol.webm' },
    'L54': { profile: 'images/leaders/L54-iseo.jpg', banner: 'images/leaders/L54-iseo-banner.jpg', video: 'videos/leaders/L54-iseo.webm' },
    'L55': { profile: 'images/leaders/L55-yunbit.jpg', banner: 'images/leaders/L55-yunbit-banner.jpg', video: 'videos/leaders/L55-yunbit.webm' },
    'L56': { profile: 'images/leaders/L56-dain.jpg', banner: 'images/leaders/L56-dain-banner.jpg', video: 'videos/leaders/L56-dain.webm' },
    'L57': { profile: 'images/leaders/L57-seum.jpg', banner: 'images/leaders/L57-seum-banner.jpg', video: 'videos/leaders/L57-seum.webm' },
    'L58': { profile: 'images/leaders/L58-yeon.jpg', banner: 'images/leaders/L58-yeon-banner.jpg', video: 'videos/leaders/L58-yeon.webm' },
    'L59': { profile: 'images/leaders/L59-hanbit.jpg', banner: 'images/leaders/L59-hanbit-banner.jpg', video: 'videos/leaders/L59-hanbit.webm' },
    'L60': { profile: 'images/leaders/L60-madi.jpg', banner: 'images/leaders/L60-madi-banner.jpg', video: 'videos/leaders/L60-madi.webm' },
};

// Load leaders data
async function loadLeaders() {
    try {
        var response = await fetch('leaders.json');
        if (!response.ok) {
            throw new Error('HTTP error! status: ' + response.status);
        }
        var data = await response.json();

        // Extract leaders from leader_registry
        var leaderRegistry = data.swarm_engine_config?.leader_registry || {};

        // Convert object to array with code as property
        allLeaders = Object.entries(leaderRegistry).map(function([code, leader]) {
            return { code: code, ...leader };
        });

        if (allLeaders.length === 0) {
            throw new Error('\uB9AC\uB354 \uB370\uC774\uD130\uAC00 \uBE44\uC5B4\uC788\uC2B5\uB2C8\uB2E4.');
        }

        renderLeaders();
    } catch (error) {
        console.error('\uB9AC\uB354 \uB370\uC774\uD130 \uB85C\uB4DC \uC2E4\uD328:', error);
        document.getElementById('leadersGrid').innerHTML =
            '<p style="text-align: center; color: var(--text-secondary); padding: 40px;">' +
            '\uB370\uC774\uD130\uB97C \uBD88\uB7EC\uC624\uB294 \uC911 \uC624\uB958\uAC00 \uBC1C\uC0DD\uD588\uC2B5\uB2C8\uB2E4.<br>' +
            '<small>' + esc(error.message) + '</small></p>';
    }
}

function esc(text) {
    var d = document.createElement('div');
    d.textContent = text || '';
    return d.innerHTML;
}

// Render leaders
function renderLeaders(searchTerm) {
    searchTerm = searchTerm || '';
    var grid = document.getElementById('leadersGrid');
    var noResults = document.getElementById('noResults');

    var filteredLeaders = allLeaders;

    // Apply specialty filter
    if (currentFilter !== 'all') {
        filteredLeaders = filteredLeaders.filter(function(leader) {
            return leader.specialty.includes(currentFilter);
        });
    }

    // Apply search filter
    if (searchTerm) {
        filteredLeaders = filteredLeaders.filter(function(leader) {
            return leader.name.includes(searchTerm) ||
                leader.specialty.includes(searchTerm) ||
                leader.role.toLowerCase().includes(searchTerm.toLowerCase()) ||
                leader.profile.includes(searchTerm);
        });
    }

    if (filteredLeaders.length === 0) {
        grid.style.display = 'none';
        noResults.style.display = 'block';
        return;
    }

    grid.style.display = 'grid';
    noResults.style.display = 'none';

    grid.innerHTML = filteredLeaders.map(function(leader, index) {
        var img = leaderImages[leader.code];
        var safeName = esc(leader.name);
        var avatarContent = img
            ? '<img src="' + esc(img.profile) + '" alt="' + safeName + '" loading="lazy">'
            : safeName.charAt(0);
        var bannerHtml = '';
        if (img) {
            var videoTag = img.video
                ? '<video class="leader-video" src="' + esc(img.video) + '" muted loop playsinline preload="none"></video>'
                : '';
            bannerHtml = '<div class="leader-banner">' +
                '<img src="' + esc(img.banner) + '" alt="' + safeName + '" loading="lazy">' +
                videoTag + '</div>';
        }
        return '<div class="leader-card" data-name="' + safeName + '" data-code="' + esc(leader.code) + '" style="animation-delay: ' + (index * 0.02) + 's">' +
            '<div class="leader-header">' +
            '<div class="leader-avatar">' + avatarContent + '</div>' +
            '<div class="leader-name-group">' +
            '<div class="leader-name">' + safeName + '</div>' +
            '<div class="leader-code">' + esc(leader.code) + '</div>' +
            '</div></div>' +
            '<div class="leader-specialty">' + esc(leader.specialty) + '</div>' +
            '<div class="leader-role">' + esc(leader.role) + '</div>' +
            '<div class="leader-profile">' + esc(leader.profile) + '</div>' +
            '<a class="leader-chat-btn" href="/leader-chat?id=' + encodeURIComponent(leader.code) + '" onclick="event.stopPropagation();">' +
            '<span class="material-symbols-outlined" style="font-size:18px;">chat</span> 대화하기</a>' +
            bannerHtml +
            '</div>';
    }).join('');
}

// Search functionality
document.getElementById('searchBox').addEventListener('input', function(e) {
    renderLeaders(e.target.value);
});

// Filter functionality
document.querySelectorAll('.filter-tab').forEach(function(tab) {
    tab.addEventListener('click', function() {
        document.querySelectorAll('.filter-tab').forEach(function(t) { t.classList.remove('active'); });
        tab.classList.add('active');
        currentFilter = tab.dataset.filter;
        renderLeaders(document.getElementById('searchBox').value);
    });
});

// Load leaders on page load
loadLeaders();

// C-Level card click -> profile page
var clevelCodeMap = { '\uC11C\uC5F0': 'CSO', '\uC9C0\uC720': 'CTO', '\uC720\uB098': 'CCO' };
document.querySelectorAll('.clevel-card').forEach(function(card) {
    card.addEventListener('click', function() {
        var code = clevelCodeMap[card.dataset.name] || card.dataset.name;
        window.location.href = 'leader-profile.html?id=' + code;
    });
});

// Leader card click -> profile page (event delegation)
document.getElementById('leadersGrid').addEventListener('click', function(e) {
    var card = e.target.closest('.leader-card');
    if (card) {
        var code = card.dataset.code;
        if (code) {
            window.location.href = 'leader-profile.html?id=' + code;
        }
    }
});

// Page load animation
window.addEventListener('load', function() {
    document.body.style.opacity = '0';
    setTimeout(function() {
        document.body.style.transition = 'opacity 0.5s';
        document.body.style.opacity = '1';
    }, 100);
});

// Hover video playback on leader cards
document.getElementById('leadersGrid').addEventListener('mouseenter', function(e) {
    var card = e.target.closest('.leader-card');
    if (!card) return;
    var video = card.querySelector('.leader-video');
    if (video) {
        video.currentTime = 0;
        video.play().catch(function() {});
    }
}, true);

document.getElementById('leadersGrid').addEventListener('mouseleave', function(e) {
    var card = e.target.closest('.leader-card');
    if (!card) return;
    var video = card.querySelector('.leader-video');
    if (video) {
        video.pause();
        video.currentTime = 0;
    }
}, true);

// Disable right-click context menu
document.addEventListener('contextmenu', function(e) { e.preventDefault(); });

// Event delegation: stop-propagation for chat buttons inside clevel cards
document.addEventListener('click', function(e) {
    var el = e.target.closest('[data-action="stop-propagation"]');
    if (el) e.stopPropagation();
});

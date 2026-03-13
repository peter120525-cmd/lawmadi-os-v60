var allLeaders = [];
var currentFilter = 'all';

var MEDIA_BASE = 'https://storage.googleapis.com/lawmadi-media';
var leaderImages = {
    'L01': { profile: MEDIA_BASE + '/images/leaders/L01-hwiyul.jpg', banner: MEDIA_BASE + '/images/leaders/L01-hwiyul-banner.jpg', video: MEDIA_BASE + '/videos/leaders/L01-greeting.mp4' },
    'L02': { profile: MEDIA_BASE + '/images/leaders/L02-bonui.jpg', banner: MEDIA_BASE + '/images/leaders/L02-bonui-banner.jpg', video: MEDIA_BASE + '/videos/leaders/L02-greeting.mp4' },
    'L03': { profile: MEDIA_BASE + '/images/leaders/L03-damseul.jpg', banner: MEDIA_BASE + '/images/leaders/L03-damseul-banner.jpg', video: MEDIA_BASE + '/videos/leaders/L03-greeting.mp4' },
    'L04': { profile: MEDIA_BASE + '/images/leaders/L04-aki.jpg', banner: MEDIA_BASE + '/images/leaders/L04-aki-banner.jpg', video: MEDIA_BASE + '/videos/leaders/L04-aki.webm' },
    'L05': { profile: MEDIA_BASE + '/images/leaders/L05-yeonwoo.jpg', banner: MEDIA_BASE + '/images/leaders/L05-yeonwoo-banner.jpg', video: MEDIA_BASE + '/videos/leaders/L05-yeonwoo.webm' },
    'L06': { profile: MEDIA_BASE + '/images/leaders/L06-byeori.jpg', banner: MEDIA_BASE + '/images/leaders/L06-byeori-banner.jpg', video: MEDIA_BASE + '/videos/leaders/L06-byeori.webm' },
    'L07': { profile: MEDIA_BASE + '/images/leaders/L07-hanui.jpg', banner: MEDIA_BASE + '/images/leaders/L07-hanui-banner.jpg', video: MEDIA_BASE + '/videos/leaders/L07-hanui.webm' },
    'L08': { profile: MEDIA_BASE + '/images/leaders/L08-onyu.jpg', banner: MEDIA_BASE + '/images/leaders/L08-onyu-banner.jpg', video: MEDIA_BASE + '/videos/leaders/L08-onyu.webm' },
    'L09': { profile: MEDIA_BASE + '/images/leaders/L09-hanul.jpg', banner: MEDIA_BASE + '/images/leaders/L09-hanul-banner.jpg', video: MEDIA_BASE + '/videos/leaders/L09-hanul.webm' },
    'L10': { profile: MEDIA_BASE + '/images/leaders/L10-gyeolhwi.jpg', banner: MEDIA_BASE + '/images/leaders/L10-gyeolhwi-banner.jpg', video: MEDIA_BASE + '/videos/leaders/L10-gyeolhwi.webm' },
    'L11': { profile: MEDIA_BASE + '/images/leaders/L11-oreum.jpg', banner: MEDIA_BASE + '/images/leaders/L11-oreum-banner.jpg', video: MEDIA_BASE + '/videos/leaders/L11-oreum.webm' },
    'L12': { profile: MEDIA_BASE + '/images/leaders/L12-aseul.jpg', banner: MEDIA_BASE + '/images/leaders/L12-aseul-banner.jpg', video: MEDIA_BASE + '/videos/leaders/L12-aseul.webm' },
    'L13': { profile: MEDIA_BASE + '/images/leaders/L13-nuri.jpg', banner: MEDIA_BASE + '/images/leaders/L13-nuri-banner.jpg', video: MEDIA_BASE + '/videos/leaders/L13-greeting.mp4' },
    'L14': { profile: MEDIA_BASE + '/images/leaders/L14-dasom.jpg', banner: MEDIA_BASE + '/images/leaders/L14-dasom-banner.jpg', video: MEDIA_BASE + '/videos/leaders/L14-dasom.webm' },
    'L15': { profile: MEDIA_BASE + '/images/leaders/L15-byeolha.jpg', banner: MEDIA_BASE + '/images/leaders/L15-byeolha-banner.jpg', video: MEDIA_BASE + '/videos/leaders/L15-byeolha.webm' },
    'L16': { profile: MEDIA_BASE + '/images/leaders/L16-seula.jpg', banner: MEDIA_BASE + '/images/leaders/L16-seula-banner.jpg', video: MEDIA_BASE + '/videos/leaders/L16-seula.webm' },
    'L17': { profile: MEDIA_BASE + '/images/leaders/L17-mir.jpg', banner: MEDIA_BASE + '/images/leaders/L17-mir-banner.jpg', video: MEDIA_BASE + '/videos/leaders/L17-mir.webm' },
    'L18': { profile: MEDIA_BASE + '/images/leaders/L18-daon.jpg', banner: MEDIA_BASE + '/images/leaders/L18-daon-banner.jpg', video: MEDIA_BASE + '/videos/leaders/L18-greeting.mp4' },
    'L19': { profile: MEDIA_BASE + '/images/leaders/L19-selong.jpg', banner: MEDIA_BASE + '/images/leaders/L19-selong-banner.jpg', video: MEDIA_BASE + '/videos/leaders/L19-greeting.mp4' },
    'L20': { profile: MEDIA_BASE + '/images/leaders/L20-chansol.jpg', banner: MEDIA_BASE + '/images/leaders/L20-chansol-banner.jpg', video: MEDIA_BASE + '/videos/leaders/L20-chansol.webm' },
    'L21': { profile: MEDIA_BASE + '/images/leaders/L21-sebin.jpg', banner: MEDIA_BASE + '/images/leaders/L21-sebin-banner.jpg', video: MEDIA_BASE + '/videos/leaders/L21-sebin.webm' },
    'L22': { profile: MEDIA_BASE + '/images/leaders/L22-gaon.jpg', banner: MEDIA_BASE + '/images/leaders/L22-gaon-banner.jpg', video: MEDIA_BASE + '/videos/leaders/L22-gaon.webm' },
    'L23': { profile: MEDIA_BASE + '/images/leaders/L23-seoun.jpg', banner: MEDIA_BASE + '/images/leaders/L23-seoun-banner.jpg', video: MEDIA_BASE + '/videos/leaders/L23-greeting.mp4' },
    'L24': { profile: MEDIA_BASE + '/images/leaders/L24-doul.jpg', banner: MEDIA_BASE + '/images/leaders/L24-doul-banner.jpg', video: MEDIA_BASE + '/videos/leaders/L24-doul.webm' },
    'L25': { profile: MEDIA_BASE + '/images/leaders/L25-damwoo.jpg', banner: MEDIA_BASE + '/images/leaders/L25-damwoo-banner.jpg', video: MEDIA_BASE + '/videos/leaders/L25-damwoo.webm' },
    'L26': { profile: MEDIA_BASE + '/images/leaders/L26-jinu.jpg', banner: MEDIA_BASE + '/images/leaders/L26-jinu-banner.jpg', video: MEDIA_BASE + '/videos/leaders/L26-jinu.webm' },
    'L27': { profile: MEDIA_BASE + '/images/leaders/L27-ruda.jpg', banner: MEDIA_BASE + '/images/leaders/L27-ruda-banner.jpg', video: MEDIA_BASE + '/videos/leaders/L27-greeting.mp4' },
    'L28': { profile: MEDIA_BASE + '/images/leaders/L28-haeseul.jpg', banner: MEDIA_BASE + '/images/leaders/L28-haeseul-banner.jpg', video: MEDIA_BASE + '/videos/leaders/L28-haeseul.webm' },
    'L29': { profile: MEDIA_BASE + '/images/leaders/L29-raon.jpg', banner: MEDIA_BASE + '/images/leaders/L29-raon-banner.jpg', video: MEDIA_BASE + '/videos/leaders/L29-greeting.mp4' },
    'L30': { profile: MEDIA_BASE + '/images/leaders/L30-damwoo.jpg', banner: MEDIA_BASE + '/images/leaders/L30-damwoo-banner.jpg', video: MEDIA_BASE + '/videos/leaders/L30-damwoo.webm' },
    'L31': { profile: MEDIA_BASE + '/images/leaders/L31-roun.jpg', banner: MEDIA_BASE + '/images/leaders/L31-roun-banner.jpg', video: MEDIA_BASE + '/videos/leaders/L31-roun.webm' },
    'L32': { profile: MEDIA_BASE + '/images/leaders/L32-bareum.jpg', banner: MEDIA_BASE + '/images/leaders/L32-bareum-banner.jpg', video: MEDIA_BASE + '/videos/leaders/L32-bareum.webm' },
    'L33': { profile: MEDIA_BASE + '/images/leaders/L33-byeoli.jpg', banner: MEDIA_BASE + '/images/leaders/L33-byeoli-banner.jpg', video: MEDIA_BASE + '/videos/leaders/L33-greeting.mp4' },
    'L34': { profile: MEDIA_BASE + '/images/leaders/L34-jinu.jpg', banner: MEDIA_BASE + '/images/leaders/L34-jinu-banner.jpg', video: MEDIA_BASE + '/videos/leaders/L34-greeting.mp4' },
    'L35': { profile: MEDIA_BASE + '/images/leaders/L35-maru.jpg', banner: MEDIA_BASE + '/images/leaders/L35-maru-banner.jpg', video: MEDIA_BASE + '/videos/leaders/L35-greeting.mp4' },
    'L36': { profile: MEDIA_BASE + '/images/leaders/L36-dana.jpg', banner: MEDIA_BASE + '/images/leaders/L36-dana-banner.jpg', video: MEDIA_BASE + '/videos/leaders/L36-dana.webm' },
    'L37': { profile: MEDIA_BASE + '/images/leaders/L37-yesol.jpg', banner: MEDIA_BASE + '/images/leaders/L37-yesol-banner.jpg', video: MEDIA_BASE + '/videos/leaders/L37-yesol.webm' },
    'L38': { profile: MEDIA_BASE + '/images/leaders/L38-seulbi.jpg', banner: MEDIA_BASE + '/images/leaders/L38-seulbi-banner.jpg', video: MEDIA_BASE + '/videos/leaders/L38-seulbi.webm' },
    'L39': { profile: MEDIA_BASE + '/images/leaders/L39-gaon.jpg', banner: MEDIA_BASE + '/images/leaders/L39-gaon-banner.jpg', video: MEDIA_BASE + '/videos/leaders/L39-gaon.webm' },
    'L40': { profile: MEDIA_BASE + '/images/leaders/L40-hangyeol.jpg', banner: MEDIA_BASE + '/images/leaders/L40-hangyeol-banner.jpg', video: MEDIA_BASE + '/videos/leaders/L40-hangyeol.webm' },
    'L41': { profile: MEDIA_BASE + '/images/leaders/L41-sandeul.jpg', banner: MEDIA_BASE + '/images/leaders/L41-sandeul-banner.jpg', video: MEDIA_BASE + '/videos/leaders/L41-greeting.mp4' },
    'L42': { profile: MEDIA_BASE + '/images/leaders/L42-haram.jpg', banner: MEDIA_BASE + '/images/leaders/L42-haram-banner.jpg', video: MEDIA_BASE + '/videos/leaders/L42-haram.webm' },
    'L43': { profile: MEDIA_BASE + '/images/leaders/L43-haena.jpg', banner: MEDIA_BASE + '/images/leaders/L43-haena-banner.jpg', video: MEDIA_BASE + '/videos/leaders/L43-greeting.mp4' },
    'L44': { profile: MEDIA_BASE + '/images/leaders/L44-boram.jpg', banner: MEDIA_BASE + '/images/leaders/L44-boram-banner.jpg', video: MEDIA_BASE + '/videos/leaders/L44-boram.webm' },
    'L45': { profile: MEDIA_BASE + '/images/leaders/L45-ireum.jpg', banner: MEDIA_BASE + '/images/leaders/L45-ireum-banner.jpg', video: MEDIA_BASE + '/videos/leaders/L45-greeting.mp4' },
    'L46': { profile: MEDIA_BASE + '/images/leaders/L46-daol.jpg', banner: MEDIA_BASE + '/images/leaders/L46-daol-banner.jpg', video: MEDIA_BASE + '/videos/leaders/L46-daol.webm' },
    'L47': { profile: MEDIA_BASE + '/images/leaders/L47-saeron.jpg', banner: MEDIA_BASE + '/images/leaders/L47-saeron-banner.jpg', video: MEDIA_BASE + '/videos/leaders/L47-saeron.webm' },
    'L48': { profile: MEDIA_BASE + '/images/leaders/L48-narae.jpg', banner: MEDIA_BASE + '/images/leaders/L48-narae-banner.jpg', video: MEDIA_BASE + '/videos/leaders/L48-greeting.mp4' },
    'L49': { profile: MEDIA_BASE + '/images/leaders/L49-garam.jpg', banner: MEDIA_BASE + '/images/leaders/L49-garam-banner.jpg', video: MEDIA_BASE + '/videos/leaders/L49-garam.webm' },
    'L50': { profile: MEDIA_BASE + '/images/leaders/L50-bitna.jpg', banner: MEDIA_BASE + '/images/leaders/L50-bitna-banner.jpg', video: MEDIA_BASE + '/videos/leaders/L50-greeting.mp4' },
    'L51': { profile: MEDIA_BASE + '/images/leaders/L51-soul.jpg', banner: MEDIA_BASE + '/images/leaders/L51-soul-banner.jpg', video: MEDIA_BASE + '/videos/leaders/L51-soul.webm' },
    'L52': { profile: MEDIA_BASE + '/images/leaders/L52-miso.jpg', banner: MEDIA_BASE + '/images/leaders/L52-miso-banner.jpg', video: MEDIA_BASE + '/videos/leaders/L52-miso.webm' },
    'L53': { profile: MEDIA_BASE + '/images/leaders/L53-neulsol.jpg', banner: MEDIA_BASE + '/images/leaders/L53-neulsol-banner.jpg', video: MEDIA_BASE + '/videos/leaders/L53-greeting.mp4' },
    'L54': { profile: MEDIA_BASE + '/images/leaders/L54-iseo.jpg', banner: MEDIA_BASE + '/images/leaders/L54-iseo-banner.jpg', video: MEDIA_BASE + '/videos/leaders/L54-greeting.mp4' },
    'L55': { profile: MEDIA_BASE + '/images/leaders/L55-yunbit.jpg', banner: MEDIA_BASE + '/images/leaders/L55-yunbit-banner.jpg', video: MEDIA_BASE + '/videos/leaders/L55-greeting.mp4' },
    'L56': { profile: MEDIA_BASE + '/images/leaders/L56-dain.jpg', banner: MEDIA_BASE + '/images/leaders/L56-dain-banner.jpg', video: MEDIA_BASE + '/videos/leaders/L56-dain.webm' },
    'L57': { profile: MEDIA_BASE + '/images/leaders/L57-seum.jpg', banner: MEDIA_BASE + '/images/leaders/L57-seum-banner.jpg', video: MEDIA_BASE + '/videos/leaders/L57-seum.webm' },
    'L58': { profile: MEDIA_BASE + '/images/leaders/L58-yeon.jpg', banner: MEDIA_BASE + '/images/leaders/L58-yeon-banner.jpg', video: MEDIA_BASE + '/videos/leaders/L58-yeon.webm' },
    'L59': { profile: MEDIA_BASE + '/images/leaders/L59-hanbit.jpg', banner: MEDIA_BASE + '/images/leaders/L59-hanbit-banner.jpg', video: MEDIA_BASE + '/videos/leaders/L59-greeting.mp4' },
    'L60': { profile: MEDIA_BASE + '/images/leaders/L60-madi.jpg', banner: MEDIA_BASE + '/images/leaders/L60-madi-banner.jpg', video: MEDIA_BASE + '/videos/leaders/L60-madi.webm' },
};

async function loadLeaders() {
    try {
        var response = await fetch('leaders.json');
        if (!response.ok) {
            throw new Error('HTTP error! status: ' + response.status);
        }
        var data = await response.json();
        var leaderRegistry = data.swarm_engine_config?.leader_registry || {};
        allLeaders = Object.entries(leaderRegistry).map(function([code, leader]) {
            return { code: code, ...leader };
        });

        if (allLeaders.length === 0) {
            throw new Error('Leader data is empty.');
        }

        renderLeaders();
    } catch (error) {
        console.error('Failed to load leader data:', error);
        document.getElementById('leadersGrid').innerHTML =
            '<p style="text-align: center; color: var(--text-secondary); padding: 40px;">' +
            'An error occurred while loading data.<br>' +
            '<small>' + esc(error.message) + '</small></p>';
    }
}

function esc(text) {
    var d = document.createElement('div');
    d.textContent = text || '';
    return d.innerHTML;
}

function renderLeaders(searchTerm) {
    searchTerm = searchTerm || '';
    var grid = document.getElementById('leadersGrid');
    var noResults = document.getElementById('noResults');

    var filteredLeaders = allLeaders;

    if (currentFilter !== 'all') {
        filteredLeaders = filteredLeaders.filter(function(leader) {
            return leader.specialty.includes(currentFilter);
        });
    }

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
                ? '<video class="leader-video" src="' + esc(img.video) + '" muted loop playsinline preload="metadata"></video>'
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
            '<a class="leader-chat-btn" href="/leader-chat?id=' + encodeURIComponent(leader.code) + '&lang=en" onclick="event.stopPropagation();">' +
            '<span class="material-symbols-outlined" style="font-size:18px;">chat</span> Chat</a>' +
            bannerHtml +
            '</div>';
    }).join('');
}

document.getElementById('searchBox').addEventListener('input', function(e) {
    renderLeaders(e.target.value);
});

document.querySelectorAll('.filter-tab').forEach(function(tab) {
    tab.addEventListener('click', function() {
        document.querySelectorAll('.filter-tab').forEach(function(t) { t.classList.remove('active'); });
        tab.classList.add('active');
        currentFilter = tab.dataset.filter;
        renderLeaders(document.getElementById('searchBox').value);
    });
});

loadLeaders();

// C-Level card click -> profile page
var clevelCodeMap = { '\uC11C\uC5F0': 'CSO', '\uC9C0\uC720': 'CTO', '\uC720\uB098': 'CCO' };
document.querySelectorAll('.clevel-card').forEach(function(card) {
    card.addEventListener('click', function() {
        var code = clevelCodeMap[card.dataset.name] || card.dataset.name;
        window.location.href = 'leader-profile-en.html?id=' + code;
    });
});

// Leader card click -> profile page (event delegation)
document.getElementById('leadersGrid').addEventListener('click', function(e) {
    var card = e.target.closest('.leader-card');
    if (card) {
        var code = card.dataset.code;
        if (code) {
            window.location.href = 'leader-profile-en.html?id=' + code;
        }
    }
});

window.addEventListener('load', function() {
    document.body.style.opacity = '0';
    setTimeout(function() {
        document.body.style.transition = 'opacity 0.5s';
        document.body.style.opacity = '1';
    }, 100);
});

// Hover video playback on leader cards (mouseover/mouseout for reliable delegation)
document.getElementById('leadersGrid').addEventListener('mouseover', function(e) {
    var card = e.target.closest('.leader-card');
    if (!card || card._videoHover) return;
    card._videoHover = true;
    var video = card.querySelector('.leader-video');
    if (video) {
        video.currentTime = 0;
        video.play().catch(function() {});
    }
});

document.getElementById('leadersGrid').addEventListener('mouseout', function(e) {
    var card = e.target.closest('.leader-card');
    if (!card) return;
    var related = e.relatedTarget;
    if (related && card.contains(related)) return;
    card._videoHover = false;
    var video = card.querySelector('.leader-video');
    if (video) {
        video.pause();
        video.currentTime = 0;
    }
});

// Disable right-click context menu
document.addEventListener('contextmenu', function(e) { e.preventDefault(); });

// Event delegation: stop-propagation for chat buttons inside cards
document.addEventListener('click', function(e) {
    var el = e.target.closest('[data-action="stop-propagation"]');
    if (el) e.stopPropagation();
});

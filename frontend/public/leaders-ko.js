var allLeaders = [];
var currentFilter = 'all';

// Leader profile image mapping
var MEDIA_BASE = 'https://storage.googleapis.com/lawmadi-media';
var leaderImages = {
    'L01': { profile: MEDIA_BASE + '/images/leaders/L01-hwiyul.jpg', banner: MEDIA_BASE + '/images/leaders/L01-hwiyul-banner.jpg', video: MEDIA_BASE + '/videos/leaders/L01-greeting.mp4' },
    'L02': { profile: MEDIA_BASE + '/images/leaders/L02-bonui.jpg', banner: MEDIA_BASE + '/images/leaders/L02-bonui-banner.jpg', video: MEDIA_BASE + '/videos/leaders/L02-greeting.mp4' },
    'L03': { profile: MEDIA_BASE + '/images/leaders/L03-damseul.jpg', banner: MEDIA_BASE + '/images/leaders/L03-damseul-banner.jpg', video: MEDIA_BASE + '/videos/leaders/L03-greeting.mp4' },
    'L04': { profile: MEDIA_BASE + '/images/leaders/L04-aki.jpg', banner: MEDIA_BASE + '/images/leaders/L04-aki-banner.jpg', video: MEDIA_BASE + '/videos/leaders/L04-greeting.mp4' },
    'L05': { profile: MEDIA_BASE + '/images/leaders/L05-yeonwoo.jpg', banner: MEDIA_BASE + '/images/leaders/L05-yeonwoo-banner.jpg', video: MEDIA_BASE + '/videos/leaders/L05-greeting.mp4' },
    'L06': { profile: MEDIA_BASE + '/images/leaders/L06-byeori.jpg', banner: MEDIA_BASE + '/images/leaders/L06-byeori-banner.jpg', video: MEDIA_BASE + '/videos/leaders/L06-greeting.mp4' },
    'L07': { profile: MEDIA_BASE + '/images/leaders/L07-hanui.jpg', banner: MEDIA_BASE + '/images/leaders/L07-hanui-banner.jpg', video: MEDIA_BASE + '/videos/leaders/L07-greeting.mp4' },
    'L08': { profile: MEDIA_BASE + '/images/leaders/L08-onyu.jpg', banner: MEDIA_BASE + '/images/leaders/L08-onyu-banner.jpg', video: MEDIA_BASE + '/videos/leaders/L08-greeting.mp4' },
    'L09': { profile: MEDIA_BASE + '/images/leaders/L09-hanul.jpg', banner: MEDIA_BASE + '/images/leaders/L09-hanul-banner.jpg', video: MEDIA_BASE + '/videos/leaders/L09-greeting.mp4' },
    'L10': { profile: MEDIA_BASE + '/images/leaders/L10-gyeolhwi.jpg', banner: MEDIA_BASE + '/images/leaders/L10-gyeolhwi-banner.jpg', video: MEDIA_BASE + '/videos/leaders/L10-greeting.mp4' },
    'L11': { profile: MEDIA_BASE + '/images/leaders/L11-oreum.jpg', banner: MEDIA_BASE + '/images/leaders/L11-oreum-banner.jpg', video: MEDIA_BASE + '/videos/leaders/L11-greeting.mp4' },
    'L12': { profile: MEDIA_BASE + '/images/leaders/L12-aseul.jpg', banner: MEDIA_BASE + '/images/leaders/L12-aseul-banner.jpg', video: MEDIA_BASE + '/videos/leaders/L12-greeting.mp4' },
    'L13': { profile: MEDIA_BASE + '/images/leaders/L13-nuri.jpg', banner: MEDIA_BASE + '/images/leaders/L13-nuri-banner.jpg', video: MEDIA_BASE + '/videos/leaders/L13-greeting.mp4' },
    'L14': { profile: MEDIA_BASE + '/images/leaders/L14-dasom.jpg', banner: MEDIA_BASE + '/images/leaders/L14-dasom-banner.jpg', video: MEDIA_BASE + '/videos/leaders/L14-greeting.mp4' },
    'L15': { profile: MEDIA_BASE + '/images/leaders/L15-byeolha.jpg', banner: MEDIA_BASE + '/images/leaders/L15-byeolha-banner.jpg', video: MEDIA_BASE + '/videos/leaders/L15-greeting.mp4' },
    'L16': { profile: MEDIA_BASE + '/images/leaders/L16-seula.jpg', banner: MEDIA_BASE + '/images/leaders/L16-seula-banner.jpg', video: MEDIA_BASE + '/videos/leaders/L16-greeting.mp4' },
    'L17': { profile: MEDIA_BASE + '/images/leaders/L17-mir.jpg', banner: MEDIA_BASE + '/images/leaders/L17-mir-banner.jpg', video: MEDIA_BASE + '/videos/leaders/L17-greeting.mp4' },
    'L18': { profile: MEDIA_BASE + '/images/leaders/L18-daon.jpg', banner: MEDIA_BASE + '/images/leaders/L18-daon-banner.jpg', video: MEDIA_BASE + '/videos/leaders/L18-greeting.mp4' },
    'L19': { profile: MEDIA_BASE + '/images/leaders/L19-selong.jpg', banner: MEDIA_BASE + '/images/leaders/L19-selong-banner.jpg', video: MEDIA_BASE + '/videos/leaders/L19-greeting.mp4' },
    'L20': { profile: MEDIA_BASE + '/images/leaders/L20-chansol.jpg', banner: MEDIA_BASE + '/images/leaders/L20-chansol-banner.jpg', video: MEDIA_BASE + '/videos/leaders/L20-greeting.mp4' },
    'L21': { profile: MEDIA_BASE + '/images/leaders/L21-sebin.jpg', banner: MEDIA_BASE + '/images/leaders/L21-sebin-banner.jpg', video: MEDIA_BASE + '/videos/leaders/L21-greeting.mp4' },
    'L22': { profile: MEDIA_BASE + '/images/leaders/L22-gaon.jpg', banner: MEDIA_BASE + '/images/leaders/L22-gaon-banner.jpg', video: MEDIA_BASE + '/videos/leaders/L22-greeting.mp4' },
    'L23': { profile: MEDIA_BASE + '/images/leaders/L23-seoun.jpg', banner: MEDIA_BASE + '/images/leaders/L23-seoun-banner.jpg', video: MEDIA_BASE + '/videos/leaders/L23-greeting.mp4' },
    'L24': { profile: MEDIA_BASE + '/images/leaders/L24-doul.jpg', banner: MEDIA_BASE + '/images/leaders/L24-doul-banner.jpg', video: MEDIA_BASE + '/videos/leaders/L24-greeting.mp4' },
    'L25': { profile: MEDIA_BASE + '/images/leaders/L25-damwoo.jpg', banner: MEDIA_BASE + '/images/leaders/L25-damwoo-banner.jpg', video: MEDIA_BASE + '/videos/leaders/L25-greeting.mp4' },
    'L26': { profile: MEDIA_BASE + '/images/leaders/L26-jinu.jpg', banner: MEDIA_BASE + '/images/leaders/L26-jinu-banner.jpg', video: MEDIA_BASE + '/videos/leaders/L26-greeting.mp4' },
    'L27': { profile: MEDIA_BASE + '/images/leaders/L27-ruda.jpg', banner: MEDIA_BASE + '/images/leaders/L27-ruda-banner.jpg', video: MEDIA_BASE + '/videos/leaders/L27-greeting.mp4' },
    'L28': { profile: MEDIA_BASE + '/images/leaders/L28-haeseul.jpg', banner: MEDIA_BASE + '/images/leaders/L28-haeseul-banner.jpg', video: MEDIA_BASE + '/videos/leaders/L28-greeting.mp4' },
    'L29': { profile: MEDIA_BASE + '/images/leaders/L29-raon.jpg', banner: MEDIA_BASE + '/images/leaders/L29-raon-banner.jpg', video: MEDIA_BASE + '/videos/leaders/L29-greeting.mp4' },
    'L30': { profile: MEDIA_BASE + '/images/leaders/L30-damwoo.jpg', banner: MEDIA_BASE + '/images/leaders/L30-damwoo-banner.jpg', video: MEDIA_BASE + '/videos/leaders/L30-greeting.mp4' },
    'L31': { profile: MEDIA_BASE + '/images/leaders/L31-roun.jpg', banner: MEDIA_BASE + '/images/leaders/L31-roun-banner.jpg', video: MEDIA_BASE + '/videos/leaders/L31-greeting.mp4' },
    'L32': { profile: MEDIA_BASE + '/images/leaders/L32-bareum.jpg', banner: MEDIA_BASE + '/images/leaders/L32-bareum-banner.jpg', video: MEDIA_BASE + '/videos/leaders/L32-greeting.mp4' },
    'L33': { profile: MEDIA_BASE + '/images/leaders/L33-byeoli.jpg', banner: MEDIA_BASE + '/images/leaders/L33-byeoli-banner.jpg', video: MEDIA_BASE + '/videos/leaders/L33-greeting.mp4' },
    'L34': { profile: MEDIA_BASE + '/images/leaders/L34-jinu.jpg', banner: MEDIA_BASE + '/images/leaders/L34-jinu-banner.jpg', video: MEDIA_BASE + '/videos/leaders/L34-greeting.mp4' },
    'L35': { profile: MEDIA_BASE + '/images/leaders/L35-maru.jpg', banner: MEDIA_BASE + '/images/leaders/L35-maru-banner.jpg', video: MEDIA_BASE + '/videos/leaders/L35-greeting.mp4' },
    'L36': { profile: MEDIA_BASE + '/images/leaders/L36-dana.jpg', banner: MEDIA_BASE + '/images/leaders/L36-dana-banner.jpg', video: MEDIA_BASE + '/videos/leaders/L36-greeting.mp4' },
    'L37': { profile: MEDIA_BASE + '/images/leaders/L37-yesol.jpg', banner: MEDIA_BASE + '/images/leaders/L37-yesol-banner.jpg', video: MEDIA_BASE + '/videos/leaders/L37-greeting.mp4' },
    'L38': { profile: MEDIA_BASE + '/images/leaders/L38-seulbi.jpg', banner: MEDIA_BASE + '/images/leaders/L38-seulbi-banner.jpg', video: MEDIA_BASE + '/videos/leaders/L38-greeting.mp4' },
    'L39': { profile: MEDIA_BASE + '/images/leaders/L39-gaon.jpg', banner: MEDIA_BASE + '/images/leaders/L39-gaon-banner.jpg', video: MEDIA_BASE + '/videos/leaders/L39-greeting.mp4' },
    'L40': { profile: MEDIA_BASE + '/images/leaders/L40-hangyeol.jpg', banner: MEDIA_BASE + '/images/leaders/L40-hangyeol-banner.jpg', video: MEDIA_BASE + '/videos/leaders/L40-greeting.mp4' },
    'L41': { profile: MEDIA_BASE + '/images/leaders/L41-sandeul.jpg', banner: MEDIA_BASE + '/images/leaders/L41-sandeul-banner.jpg', video: MEDIA_BASE + '/videos/leaders/L41-greeting.mp4' },
    'L42': { profile: MEDIA_BASE + '/images/leaders/L42-haram.jpg', banner: MEDIA_BASE + '/images/leaders/L42-haram-banner.jpg', video: MEDIA_BASE + '/videos/leaders/L42-greeting.mp4' },
    'L43': { profile: MEDIA_BASE + '/images/leaders/L43-haena.jpg', banner: MEDIA_BASE + '/images/leaders/L43-haena-banner.jpg', video: MEDIA_BASE + '/videos/leaders/L43-greeting.mp4' },
    'L44': { profile: MEDIA_BASE + '/images/leaders/L44-boram.jpg', banner: MEDIA_BASE + '/images/leaders/L44-boram-banner.jpg', video: MEDIA_BASE + '/videos/leaders/L44-greeting.mp4' },
    'L45': { profile: MEDIA_BASE + '/images/leaders/L45-ireum.jpg', banner: MEDIA_BASE + '/images/leaders/L45-ireum-banner.jpg', video: MEDIA_BASE + '/videos/leaders/L45-greeting.mp4' },
    'L46': { profile: MEDIA_BASE + '/images/leaders/L46-daol.jpg', banner: MEDIA_BASE + '/images/leaders/L46-daol-banner.jpg', video: MEDIA_BASE + '/videos/leaders/L46-greeting.mp4' },
    'L47': { profile: MEDIA_BASE + '/images/leaders/L47-saeron.jpg', banner: MEDIA_BASE + '/images/leaders/L47-saeron-banner.jpg', video: MEDIA_BASE + '/videos/leaders/L47-greeting.mp4' },
    'L48': { profile: MEDIA_BASE + '/images/leaders/L48-narae.jpg', banner: MEDIA_BASE + '/images/leaders/L48-narae-banner.jpg', video: MEDIA_BASE + '/videos/leaders/L48-greeting.mp4' },
    'L49': { profile: MEDIA_BASE + '/images/leaders/L49-garam.jpg', banner: MEDIA_BASE + '/images/leaders/L49-garam-banner.jpg', video: MEDIA_BASE + '/videos/leaders/L49-greeting.mp4' },
    'L50': { profile: MEDIA_BASE + '/images/leaders/L50-bitna.jpg', banner: MEDIA_BASE + '/images/leaders/L50-bitna-banner.jpg', video: MEDIA_BASE + '/videos/leaders/L50-greeting.mp4' },
    'L51': { profile: MEDIA_BASE + '/images/leaders/L51-soul.jpg', banner: MEDIA_BASE + '/images/leaders/L51-soul-banner.jpg', video: MEDIA_BASE + '/videos/leaders/L51-greeting.mp4' },
    'L52': { profile: MEDIA_BASE + '/images/leaders/L52-miso.jpg', banner: MEDIA_BASE + '/images/leaders/L52-miso-banner.jpg', video: MEDIA_BASE + '/videos/leaders/L52-greeting.mp4' },
    'L53': { profile: MEDIA_BASE + '/images/leaders/L53-neulsol.jpg', banner: MEDIA_BASE + '/images/leaders/L53-neulsol-banner.jpg', video: MEDIA_BASE + '/videos/leaders/L53-greeting.mp4' },
    'L54': { profile: MEDIA_BASE + '/images/leaders/L54-iseo.jpg', banner: MEDIA_BASE + '/images/leaders/L54-iseo-banner.jpg', video: MEDIA_BASE + '/videos/leaders/L54-greeting.mp4' },
    'L55': { profile: MEDIA_BASE + '/images/leaders/L55-yunbit.jpg', banner: MEDIA_BASE + '/images/leaders/L55-yunbit-banner.jpg', video: MEDIA_BASE + '/videos/leaders/L55-greeting.mp4' },
    'L56': { profile: MEDIA_BASE + '/images/leaders/L56-dain.jpg', banner: MEDIA_BASE + '/images/leaders/L56-dain-banner.jpg', video: MEDIA_BASE + '/videos/leaders/L56-greeting.mp4' },
    'L57': { profile: MEDIA_BASE + '/images/leaders/L57-seum.jpg', banner: MEDIA_BASE + '/images/leaders/L57-seum-banner.jpg', video: MEDIA_BASE + '/videos/leaders/L57-greeting.mp4' },
    'L58': { profile: MEDIA_BASE + '/images/leaders/L58-yeon.jpg', banner: MEDIA_BASE + '/images/leaders/L58-yeon-banner.jpg', video: MEDIA_BASE + '/videos/leaders/L58-greeting.mp4' },
    'L59': { profile: MEDIA_BASE + '/images/leaders/L59-hanbit.jpg', banner: MEDIA_BASE + '/images/leaders/L59-hanbit-banner.jpg', video: MEDIA_BASE + '/videos/leaders/L59-greeting.mp4' },
    'L60': { profile: MEDIA_BASE + '/images/leaders/L60-madi.jpg', banner: MEDIA_BASE + '/images/leaders/L60-madi-banner.jpg', video: MEDIA_BASE + '/videos/leaders/L60-greeting.mp4' },
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

// Event delegation: stop-propagation for chat buttons inside clevel cards
document.addEventListener('click', function(e) {
    var el = e.target.closest('[data-action="stop-propagation"]');
    if (el) e.stopPropagation();
});

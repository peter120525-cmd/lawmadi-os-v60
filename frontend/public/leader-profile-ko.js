// Update lang toggle with validated query string (CSP compliant)
(function(){var p=new URLSearchParams(window.location.search);var id=p.get('id');if(id&&/^[A-Za-z0-9]+$/.test(id)){var el=document.getElementById('langToggle');if(el)el.href='/leader-en?id='+encodeURIComponent(id);}})();

(async function() {
    var params = new URLSearchParams(window.location.search);
    var id = params.get('id');

    if (!id || !/^[A-Za-z0-9]+$/.test(id)) { showError(); return; }

    try {
        var [leadersRes, profilesRes] = await Promise.all([
            fetch('leaders.json'),
            fetch('leader-profiles.json')
        ]);

        if (!leadersRes.ok || !profilesRes.ok) throw new Error('Data load failed');

        var leadersData = await leadersRes.json();
        var profilesData = await profilesRes.json();

        // Find leader basic info
        var basic = null;
        var code = id.toUpperCase();

        if (leadersData.core_registry && leadersData.core_registry[code]) {
            basic = leadersData.core_registry[code];
            basic.code = code;
        } else if (leadersData.swarm_engine_config?.leader_registry?.[code]) {
            basic = leadersData.swarm_engine_config.leader_registry[code];
            basic.code = code;
        }

        var profile = profilesData[code];

        if (!basic || !profile) { showError(); return; }

        renderProfile(basic, profile, code);
    } catch (err) {
        console.error('Profile load error:', err);
        showError();
    }
})();

function showError() {
    document.getElementById('loadingState').style.display = 'none';
    document.getElementById('errorState').style.display = 'flex';
}

function esc(text) {
    var d = document.createElement('div');
    d.textContent = text || '';
    return d.innerHTML;
}

function renderProfile(basic, profile, code) {
    // Update page title
    document.title = basic.name + ' - ' + (basic.specialty || basic.role) + ' | Lawmadi OS';

    // Hero
    var imgs = profile.images || {};
    document.getElementById('heroBanner').src = imgs.banner || '';
    document.getElementById('heroProfileImg').src = imgs.profile || '';
    document.getElementById('heroProfileImg').alt = basic.name;
    document.getElementById('heroBadge').textContent = basic.specialty
        ? code + ' \u00B7 ' + basic.specialty
        : code;
    document.getElementById('heroName').textContent = basic.name;
    document.getElementById('heroRole').textContent = basic.role;
    document.getElementById('heroStatement').textContent = profile.hero || '';

    // Identity
    var identityGrid = document.getElementById('identityGrid');
    if (profile.identity) {
        identityGrid.innerHTML =
            '<div class="identity-box"><h4>What We Do</h4><p>' + esc(profile.identity.what) + '</p></div>' +
            '<div class="identity-box"><h4>Why We Exist</h4><p>' + esc(profile.identity.why) + '</p></div>';
    }

    // What We Solve
    var solveGrid = document.getElementById('solveGrid');
    if (profile.whatWeSolve) {
        var ws = profile.whatWeSolve;
        solveGrid.innerHTML =
            '<div class="solve-item"><div class="solve-icon"><span class="material-symbols-outlined">report_problem</span></div>' +
            '<div><h4>\uAE30\uC874\uC758 \uBB38\uC81C</h4><p>' + esc(ws.problem) + '</p></div></div>' +
            '<div class="solve-item"><div class="solve-icon"><span class="material-symbols-outlined">block</span></div>' +
            '<div><h4>\uAE30\uC874\uC758 \uD55C\uACC4</h4><p>' + esc(ws.limit) + '</p></div></div>' +
            '<div class="solve-item"><div class="solve-icon"><span class="material-symbols-outlined">tips_and_updates</span></div>' +
            '<div><h4>\uC6B0\uB9AC\uC758 \uC811\uADFC</h4><p>' + esc(ws.approach) + '</p></div></div>';
    }

    // Expertise
    var expertiseGrid = document.getElementById('expertiseGrid');
    if (profile.expertise && profile.expertise.length) {
        expertiseGrid.innerHTML = profile.expertise.map(function(e) {
            return '<div class="expertise-item">' +
                '<div class="expertise-icon"><span class="material-symbols-outlined">' + esc(e.icon) + '</span></div>' +
                '<div><div class="expertise-label">' + esc(e.label) + '</div>' +
                '<div class="expertise-desc">' + esc(e.desc) + '</div></div></div>';
        }).join('');
    }

    // Philosophy
    if (profile.philosophy) {
        document.getElementById('philosophyCard').innerHTML = '<p>' + esc(profile.philosophy) + '</p>';
    }

    // Impact
    if (profile.impact) {
        document.getElementById('impactCard').innerHTML = '<p>' + esc(profile.impact) + '</p>';
    }

    // Vision
    if (profile.vision) {
        document.getElementById('visionCard').innerHTML = '<p>' + esc(profile.vision) + '</p>';
    }

    // YouTube Shorts
    if (profile.youtube) {
        var ytSection = document.getElementById('sectionYoutube');
        var ytEmbed = document.getElementById('youtubeEmbed');
        if (ytSection && ytEmbed) {
            ytEmbed.src = 'https://www.youtube.com/embed/' + encodeURIComponent(profile.youtube) + '?rel=0';
            ytSection.style.display = '';
        }
    }

    // Chat CTA link
    var chatCta = document.getElementById('chatCta');
    if (chatCta) chatCta.href = '/leader-chat?id=' + encodeURIComponent(code);

    // Show content
    document.getElementById('loadingState').style.display = 'none';
    document.getElementById('profileContent').style.display = 'block';

    // Scroll reveal
    requestAnimationFrame(function() {
        var observer = new IntersectionObserver(function(entries) {
            entries.forEach(function(entry) {
                if (entry.isIntersecting) {
                    entry.target.classList.add('visible');
                }
            });
        }, { threshold: 0.1, rootMargin: '0px 0px -40px 0px' });

        document.querySelectorAll('.profile-section').forEach(function(s) { observer.observe(s); });
    });
}

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

/**
 * Lawmadi OS — Leader 1:1 Chat Controller
 * SSE streaming via POST /api/chat-leader
 */
(function() {
    'use strict';

    var CHAT_API = '/api/chat-leader';
    var MAX_HISTORY = 20;
    var MAX_QUERY = 4000;
    var pageLang = (new URLSearchParams(window.location.search).get('lang') === 'en') ? 'en' : 'ko';

    // ── Category grouping for filters ──
    // (kept for future use if needed; currently leader-chat is single-leader)

    // ── DOM refs ──
    var pageLoading = document.getElementById('pageLoading');
    var errorBanner = document.getElementById('errorBanner');
    var profileHeader = document.getElementById('profileHeader');
    var chatViewport = document.getElementById('chatViewport');
    var inputArea = document.getElementById('inputArea');
    var userInput = document.getElementById('userInput');
    var sendBtn = document.getElementById('sendBtn');
    var charCounter = document.getElementById('charCounter');

    // ── State ──
    var leaderId = '';
    var leaderBasic = null;
    var leaderProfile = null;
    var leaderAvatarSrc = '';
    var isSending = false;
    var DAILY_FREE = 5;

    // ── Chat usage counter (session-based, approximate) ──
    function _getChatCount() {
        try {
            var d = new Date(); var key = 'lc_count_' + d.getFullYear() + (d.getMonth()+1) + d.getDate();
            return parseInt(sessionStorage.getItem(key) || '0', 10);
        } catch(e) { return 0; }
    }
    function _incChatCount() {
        try {
            var d = new Date(); var key = 'lc_count_' + d.getFullYear() + (d.getMonth()+1) + d.getDate();
            var c = parseInt(sessionStorage.getItem(key) || '0', 10) + 1;
            sessionStorage.setItem(key, String(c));
            _updateUsageBanner(c);
        } catch(e) {}
    }
    function _updateUsageBanner(count) {
        var banner = document.getElementById('usageBanner');
        if (!banner) return;
        var remain = DAILY_FREE - count;
        if (remain <= 0) {
            banner.style.display = 'block';
            banner.textContent = pageLang === 'en'
                ? 'Free daily limit reached. Additional uses require 2 credits per 5 chats.'
                : '오늘 무료 ' + DAILY_FREE + '회를 모두 사용했습니다. 추가 5회당 2크레딧이 필요합니다.';
            banner.style.background = '#fef2f2'; banner.style.color = '#dc2626';
        } else if (remain <= 2) {
            banner.style.display = 'block';
            banner.textContent = pageLang === 'en'
                ? remain + ' free chat(s) remaining today'
                : '오늘 무료 채팅 ' + remain + '회 남음';
            banner.style.background = '#fffbeb'; banner.style.color = '#d97706';
        } else {
            banner.style.display = 'none';
        }
    }

    // ── Dark mode sync ──
    (function() {
        var dm = localStorage.getItem('lawmadi-dark-mode');
        if (dm === 'true') document.body.classList.add('dark-mode');
    })();

    // ── Helpers ──
    function esc(text) {
        var d = document.createElement('div');
        d.textContent = text || '';
        return d.innerHTML;
    }

    function sanitize(html) {
        if (typeof DOMPurify !== 'undefined')
            return DOMPurify.sanitize(html, { ADD_ATTR: ['target'] });
        return esc(html);
    }

    function renderStreamingText(text) {
        text = text.replace(/<think>[\s\S]*?<\/think>/g, '');
        text = text.replace(/^#{1,4}\s+(.+)$/gm, '**$1**');
        return text
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
            .replace(/\n/g, '<br>');
    }

    // ── Storage: per-leader history ──
    function storageKey() { return 'leader-chat-' + leaderId; }

    function loadHistory() {
        try {
            var raw = sessionStorage.getItem(storageKey());
            return raw ? JSON.parse(raw) : [];
        } catch(e) { return []; }
    }

    function saveHistory(history) {
        // Keep last MAX_HISTORY turns
        if (history.length > MAX_HISTORY * 2) {
            history = history.slice(-MAX_HISTORY * 2);
        }
        try {
            sessionStorage.setItem(storageKey(), JSON.stringify(history));
        } catch(e) { /* quota exceeded — silent */ }
    }

    // ── UI: Messages ──
    function appendMessage(role, html) {
        var row = document.createElement('div');
        row.className = 'msg-row ' + (role === 'user' ? 'user' : 'ai');

        if (role === 'ai') {
            var av = document.createElement('img');
            av.className = 'bubble-avatar';
            av.src = leaderAvatarSrc;
            av.alt = (leaderBasic && leaderBasic.name) || '';
            av.loading = 'lazy';
            row.appendChild(av);
        }

        var bubble = document.createElement('div');
        bubble.className = 'msg-bubble';
        bubble.innerHTML = sanitize(html);
        row.appendChild(bubble);

        chatViewport.appendChild(row);
        scrollToBottom();
        return bubble;
    }

    function showTyping() {
        var row = document.createElement('div');
        row.className = 'typing-row';
        row.id = 'typingIndicator';

        var av = document.createElement('img');
        av.className = 'bubble-avatar';
        av.src = leaderAvatarSrc;
        av.alt = '';
        av.loading = 'lazy';
        row.appendChild(av);

        var dots = document.createElement('div');
        dots.className = 'typing-dots';
        dots.innerHTML = '<span></span><span></span><span></span>';
        row.appendChild(dots);

        chatViewport.appendChild(row);
        scrollToBottom();
    }

    function hideTyping() {
        var el = document.getElementById('typingIndicator');
        if (el) el.remove();
    }

    function scrollToBottom() {
        chatViewport.scrollTo({ top: chatViewport.scrollHeight, behavior: 'smooth' });
    }

    function showError(msg) {
        errorBanner.textContent = msg;
        errorBanner.style.display = 'block';
        setTimeout(function() { errorBanner.style.display = 'none'; }, 8000);
    }

    // ── SSE Parsing (extracted from app-inline-ko.js) ──
    function parseSSE(rawEvent) {
        var eventType = 'message';
        var dataLines = [];
        var lines = rawEvent.split('\n');
        for (var i = 0; i < lines.length; i++) {
            var line = lines[i];
            if (line.startsWith('event: ')) eventType = line.slice(7).trim();
            else if (line.startsWith('data: ')) dataLines.push(line.slice(6));
        }
        return { eventType: eventType, eventData: dataLines.join('\n') };
    }

    // ── Send Message ──
    async function sendMessage() {
        var query = userInput.value.trim();
        if (!query || isSending) return;
        if (query.length > MAX_QUERY) query = query.substring(0, MAX_QUERY);

        isSending = true;
        sendBtn.disabled = true;
        userInput.value = '';
        autoResize();
        updateCharCounter();

        // Append user message
        appendMessage('user', esc(query));

        // Get history
        var history = loadHistory();

        // Show typing
        showTyping();

        var accumulatedText = '';
        var streamBubble = null;

        try {
            var response = await fetch(CHAT_API, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify({
                    leader_id: leaderId,
                    query: query,
                    history: history
                })
            });

            if (response.status === 429) {
                hideTyping();
                try {
                    var errData = await response.json();
                    var errMsg = errData.error || '일일 무료 이용 한도에 도달했습니다.';
                    appendMessage('ai', '<p>' + esc(errMsg) + ' <a href="/pricing">크레딧 구매</a></p>');
                } catch(e) {
                    appendMessage('ai', '<p>' + (pageLang === 'en' ? 'Daily free limit reached.' : '일일 무료 이용 한도에 도달했습니다.') + ' <a href="' + (pageLang === 'en' ? '/pricing-en' : '/pricing') + '">' + (pageLang === 'en' ? 'Buy credits' : '크레딧 구매') + '</a></p>');
                }
                isSending = false;
                sendBtn.disabled = false;
                return;
            }

            if (!response.ok) {
                throw new Error((pageLang === 'en' ? 'Server error' : '서버 오류') + ' (' + response.status + ')');
            }

            var reader = response.body.getReader();
            var decoder = new TextDecoder();
            var buffer = '';

            while (true) {
                var result = await reader.read();
                if (result.done) break;

                buffer += decoder.decode(result.value, { stream: true });
                var parts = buffer.split('\n\n');
                buffer = parts.pop() || '';

                for (var i = 0; i < parts.length; i++) {
                    var rawEvent = parts[i].trim();
                    if (!rawEvent) continue;

                    var parsed = parseSSE(rawEvent);
                    var eventType = parsed.eventType;
                    var eventData;

                    try { eventData = JSON.parse(parsed.eventData); }
                    catch(e) { continue; }

                    if (eventType === 'answer_start') {
                        hideTyping();
                        // Create AI bubble
                        streamBubble = appendMessage('ai', '');
                    } else if (eventType === 'answer_chunk') {
                        if (!streamBubble) {
                            hideTyping();
                            streamBubble = appendMessage('ai', '');
                        }
                        var chunkText = eventData.text || '';
                        accumulatedText += chunkText;
                        streamBubble.innerHTML = sanitize(renderStreamingText(accumulatedText));
                        scrollToBottom();
                    } else if (eventType === 'answer_done') {
                        hideTyping();
                        if (streamBubble && accumulatedText) {
                            streamBubble.innerHTML = sanitize(renderStreamingText(accumulatedText));
                        }
                        // Save history
                        history.push({ role: 'user', content: query });
                        history.push({ role: 'assistant', content: accumulatedText });
                        saveHistory(history);
                        _incChatCount();
                    } else if (eventType === 'error') {
                        hideTyping();
                        var errMsg = eventData.message || '오류가 발생했습니다.';
                        if (!streamBubble) {
                            streamBubble = appendMessage('ai', '');
                        }
                        streamBubble.innerHTML = '<span style="color:#ef4444;">' + esc(errMsg) + '</span>';
                    }
                }
            }
        } catch (e) {
            hideTyping();
            showError(e.message || '네트워크 오류가 발생했습니다.');
            if (!streamBubble) {
                appendMessage('ai', '<span style="color:#ef4444;">연결 오류가 발생했습니다. 다시 시도해 주세요.</span>');
            }
        } finally {
            isSending = false;
            sendBtn.disabled = false;
            userInput.focus();
        }
    }

    // ── Auto-resize textarea ──
    function autoResize() {
        userInput.style.height = 'auto';
        userInput.style.height = Math.min(userInput.scrollHeight, 120) + 'px';
    }

    function updateCharCounter() {
        var len = userInput.value.length;
        charCounter.textContent = len + '/' + MAX_QUERY;
    }

    // ── Restore previous messages from sessionStorage ──
    function restoreHistory() {
        var history = loadHistory();
        for (var i = 0; i < history.length; i++) {
            var msg = history[i];
            if (msg.role === 'user') {
                appendMessage('user', esc(msg.content));
            } else if (msg.role === 'assistant') {
                appendMessage('ai', sanitize(renderStreamingText(msg.content)));
            }
        }
    }

    // ── Welcome message ──
    function showWelcome() {
        var name = (leaderBasic && leaderBasic.name) || '';
        var specialty = (leaderBasic && (leaderBasic.specialty || leaderBasic.role)) || '';
        var hero = (leaderProfile && leaderProfile.hero) || '';

        var welcomeDiv = document.createElement('div');
        welcomeDiv.className = 'welcome-msg';
        welcomeDiv.innerHTML =
            '<img class="welcome-avatar" src="' + esc(leaderAvatarSrc) + '" alt="' + esc(name) + '">' +
            '<h3>' + esc(name) + '</h3>' +
            '<p>' + esc(specialty) + (pageLang === 'en' ? ' AI Leader' : ' 전문 AI 리더') + '</p>' +
            (hero ? '<p style="margin-top:12px;font-style:italic;color:#64748b;">"' + esc(hero) + '"</p>' : '') +
            '<p style="margin-top:16px;font-size:0.85rem;color:#64748b;">' +
            (pageLang === 'en' ? 'Feel free to ask any legal questions.' : '궁금한 법률 문제를 자유롭게 질문해 주세요.') + '</p>';
        chatViewport.appendChild(welcomeDiv);
    }

    // ── Init ──
    async function init() {
        var params = new URLSearchParams(window.location.search);
        leaderId = (params.get('id') || '').toUpperCase();

        // Apply EN UI if needed
        if (pageLang === 'en') {
            document.documentElement.lang = 'en';
            document.title = 'Chat with Leader - Lawmadi OS';
            userInput.placeholder = 'Type your legal question...';
            var backBtn = document.querySelector('.back-btn');
            if (backBtn) { backBtn.href = '/leaders-en'; backBtn.setAttribute('aria-label', 'Back'); }
        }

        if (!leaderId) {
            pageLoading.innerHTML = pageLang === 'en'
                ? '<p style="color:#ef4444;">No leader ID specified. <a href="/leaders-en">View leaders</a></p>'
                : '<p style="color:#ef4444;">리더 ID가 지정되지 않았습니다. <a href="/leaders">리더 목록</a>으로 이동해 주세요.</p>';
            return;
        }

        try {
            var profileJson = pageLang === 'en' ? 'leader-profiles-en.json' : 'leader-profiles.json';
            var responses = await Promise.all([
                fetch('leaders.json'),
                fetch(profileJson)
            ]);

            if (!responses[0].ok || !responses[1].ok) throw new Error('Data load failed');

            var leadersData = await responses[0].json();
            var profilesData = await responses[1].json();

            // Find leader basic info (core_registry or leader_registry)
            if (leadersData.core_registry && leadersData.core_registry[leaderId]) {
                leaderBasic = leadersData.core_registry[leaderId];
            } else if (leadersData.swarm_engine_config && leadersData.swarm_engine_config.leader_registry && leadersData.swarm_engine_config.leader_registry[leaderId]) {
                leaderBasic = leadersData.swarm_engine_config.leader_registry[leaderId];
            }

            leaderProfile = profilesData[leaderId] || null;

            if (!leaderBasic) {
                pageLoading.innerHTML = pageLang === 'en'
                    ? '<p style="color:#ef4444;">Leader not found. <a href="/leaders-en">View leaders</a></p>'
                    : '<p style="color:#ef4444;">존재하지 않는 리더입니다. <a href="/leaders">리더 목록</a>으로 이동해 주세요.</p>';
                return;
            }

            // Avatar
            var profileImages = (leaderProfile && leaderProfile.images) || {};
            leaderAvatarSrc = profileImages.profile || ('images/leaders/' + leaderId + '.jpg');

            // Render header
            document.getElementById('headerAvatar').src = leaderAvatarSrc;
            document.getElementById('headerAvatar').alt = leaderBasic.name || '';
            document.getElementById('headerName').textContent = leaderBasic.name || leaderId;
            document.getElementById('headerSpecialty').textContent = leaderBasic.specialty || leaderBasic.role || '';
            document.getElementById('headerPersonality').textContent = (leaderProfile && leaderProfile.hero) || '';
            document.getElementById('profileLink').href = (pageLang === 'en' ? '/leader-en?id=' : '/leader-profile?id=') + encodeURIComponent(leaderId);

            // Update page title
            document.title = pageLang === 'en'
                ? 'Chat with ' + leaderBasic.name + ' - Lawmadi OS'
                : leaderBasic.name + '과 대화하기 - Lawmadi OS';

            // Show UI
            pageLoading.style.display = 'none';
            profileHeader.style.display = 'flex';
            chatViewport.style.display = 'flex';
            inputArea.style.display = 'block';

            // Show usage banner if near limit
            _updateUsageBanner(_getChatCount());

            // Restore history or show welcome
            var history = loadHistory();
            if (history.length > 0) {
                restoreHistory();
            } else {
                showWelcome();
            }

            // Focus input
            userInput.focus();

        } catch(e) {
            console.error('Leader chat init error:', e);
            pageLoading.innerHTML = pageLang === 'en'
                ? '<p style="color:#ef4444;">Failed to load data. <a href="/leaders-en">View leaders</a></p>'
                : '<p style="color:#ef4444;">데이터를 불러오지 못했습니다. <a href="/leaders">리더 목록</a>으로 이동해 주세요.</p>';
        }
    }

    // ── Event Listeners ──
    userInput.addEventListener('input', function() {
        autoResize();
        updateCharCounter();
        sendBtn.disabled = !userInput.value.trim() || isSending;
    });

    userInput.addEventListener('keydown', function(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            if (!sendBtn.disabled) sendMessage();
        }
    });

    sendBtn.addEventListener('click', function() {
        sendMessage();
    });

    // Virtual keyboard handling
    if (window.visualViewport) {
        var baseHeight = window.visualViewport.height;
        window.visualViewport.addEventListener('resize', function() {
            var kbOpen = window.visualViewport.height < baseHeight * 0.75;
            if (kbOpen) scrollToBottom();
        });
    }

    // ── Start ──
    init();
})();

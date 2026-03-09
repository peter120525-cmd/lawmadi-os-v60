/**
 * Lawmadi OS — Leader 1:1 Chat Controller
 * SSE streaming via POST /api/chat-leader
 */
(function() {
    'use strict';

    var CHAT_API = '/api/chat-leader';
    var MAX_HISTORY = 20;
    var MAX_QUERY = 4000;

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
                appendMessage('ai', '<p>일일 무료 이용 한도에 도달했습니다. <a href="/pricing">크레딧 구매</a>하시면 계속 이용 가능합니다.</p>');
                isSending = false;
                sendBtn.disabled = false;
                return;
            }

            if (!response.ok) {
                throw new Error('서버 오류 (' + response.status + ')');
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
            '<p>' + esc(specialty) + ' 전문 AI 리더</p>' +
            (hero ? '<p style="margin-top:12px;font-style:italic;color:#94a3b8;">"' + esc(hero) + '"</p>' : '') +
            '<p style="margin-top:16px;font-size:0.85rem;color:#94a3b8;">궁금한 법률 문제를 자유롭게 질문해 주세요.</p>';
        chatViewport.appendChild(welcomeDiv);
    }

    // ── Init ──
    async function init() {
        var params = new URLSearchParams(window.location.search);
        leaderId = (params.get('id') || '').toUpperCase();

        if (!leaderId) {
            pageLoading.innerHTML = '<p style="color:#ef4444;">리더 ID가 지정되지 않았습니다. <a href="/leaders">리더 목록</a>으로 이동해 주세요.</p>';
            return;
        }

        try {
            var responses = await Promise.all([
                fetch('leaders.json'),
                fetch('leader-profiles.json')
            ]);

            if (!responses[0].ok || !responses[1].ok) throw new Error('데이터 로드 실패');

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
                pageLoading.innerHTML = '<p style="color:#ef4444;">존재하지 않는 리더입니다. <a href="/leaders">리더 목록</a>으로 이동해 주세요.</p>';
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
            document.getElementById('profileLink').href = '/leader-profile?id=' + encodeURIComponent(leaderId);

            // Update page title
            document.title = leaderBasic.name + '과 대화하기 - Lawmadi OS';

            // Show UI
            pageLoading.style.display = 'none';
            profileHeader.style.display = 'flex';
            chatViewport.style.display = 'flex';
            inputArea.style.display = 'block';

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
            pageLoading.innerHTML = '<p style="color:#ef4444;">데이터를 불러오지 못했습니다. <a href="/leaders">리더 목록</a>으로 이동해 주세요.</p>';
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

document.addEventListener('DOMContentLoaded', () => {
    const tabs = document.querySelectorAll('nav li');
    const tabContents = document.querySelectorAll('.tab-content');
    const chatHistory = document.getElementById('chat-history');
    const userInput = document.getElementById('user-input');
    const sendBtn = document.getElementById('send-btn');
    const micBtn = document.getElementById('mic-btn');
    const typingIndicator = document.getElementById('typing-indicator');

    // ── Settings (localStorage) ───────────────────────────
    const SETTINGS_KEY = 'melloSettings';
    const DEFAULT_SETTINGS = {
        micModel:        'tiny',
        micLanguage:     'auto',
        micAutoStop:     true,
        micSilenceMs:    1500,
        micSilenceThresh:12,
        micAutoSend:     true,
        ttsEnabled:      false,
        ttsVoice:        '',
        ttsRate:         1.05,
        ttsPitch:        1.0,
        ttsVolume:       1.0,
    };

    function getSettings() {
        try {
            const s = localStorage.getItem(SETTINGS_KEY);
            return s ? { ...DEFAULT_SETTINGS, ...JSON.parse(s) } : { ...DEFAULT_SETTINGS };
        } catch { return { ...DEFAULT_SETTINGS }; }
    }

    function saveSettings(patch) {
        const s = { ...getSettings(), ...patch };
        localStorage.setItem(SETTINGS_KEY, JSON.stringify(s));
        // Persist mic model/language to server so Python backend picks it up
        if ('micModel' in patch || 'micLanguage' in patch) {
            fetch('/api/settings', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ settings: s }),
            }).catch(() => {});
        }
        return s;
    }

    // ── Bot Visual Engine ─────────────────────────────────
    const botVisual   = document.getElementById('bot-visual');
    const botStatusLbl = document.getElementById('bot-status-lbl');
    const botWave     = document.getElementById('bot-wave');

    // Generate wave bars with random height vars for organic look
    if (botWave) {
        const BAR_COUNT = 22;
        for (let i = 0; i < BAR_COUNT; i++) {
            const bar = document.createElement('div');
            bar.className = 'wave-bar';
            // Organic height envelope: tallest in middle, shorter at edges
            const center = (BAR_COUNT - 1) / 2;
            const dist   = Math.abs(i - center) / center;          // 0 = centre, 1 = edge
            const maxH   = Math.round(50 - dist * 30);              // 20-50 px
            const minH   = Math.max(3, Math.round(maxH * 0.1));
            bar.style.setProperty('--h-max', maxH + 'px');
            bar.style.setProperty('--h-min', minH + 'px');
            bar.style.animationDelay = (i * 0.07).toFixed(2) + 's';
            botWave.appendChild(bar);
        }
    }

    const STATE_LABELS = {
        idle:      'Ready',
        thinking:  'Thinking…',
        listening: 'Listening…',
        speaking:  'Speaking…',
    };

    function setBotState(state) {
        if (!botVisual) return;
        botVisual.className = 'bot-visual state-' + state;
        if (botStatusLbl) botStatusLbl.textContent = STATE_LABELS[state] || state;
    }

    // Auto-blink loop
    (function autoBlink() {
        const eyes = document.querySelectorAll('.bot-eye');
        eyes.forEach(e => e.classList.add('blink'));
        setTimeout(() => eyes.forEach(e => e.classList.remove('blink')), 130);
        // Occasionally double-blink
        if (Math.random() < 0.25) {
            setTimeout(() => {
                eyes.forEach(e => e.classList.add('blink'));
                setTimeout(() => eyes.forEach(e => e.classList.remove('blink')), 110);
            }, 280);
        }
        setTimeout(autoBlink, 2800 + Math.random() * 3200);
    })();

    // ── Model status elements ─────────────────────────────
    const liveDot = document.getElementById('model-live-dot');
    const activeModelDisplay = document.getElementById('active-model-display');

    let currentActiveModel = 'qwen3.5:4b';

    async function checkModelStatus() {
        try {
            const res = await fetch('/api/models/status');
            const data = await res.json();
            currentActiveModel = data.active_model || 'qwen3.5:4b';
            updateStatusDot(data.is_live);
            activeModelDisplay.textContent = currentActiveModel;
            return data;
        } catch {
            updateStatusDot(false);
            return { is_live: false, ollama_running: false, active_model: currentActiveModel };
        }
    }

    function updateStatusDot(isLive) {
        liveDot.className = `model-live-dot ${isLive ? 'online' : 'offline'}`;
        liveDot.title = isLive ? `${currentActiveModel} is live` : 'Model offline';
    }

    // ── Initial status check on page load ────────────────
    (async () => { await checkModelStatus(); })();

    // ── Tab Switching ─────────────────────────────────────
    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            tabs.forEach(t => t.classList.remove('active'));
            tabContents.forEach(c => c.classList.remove('active'));
            tab.classList.add('active');
            const target = document.getElementById(`${tab.dataset.tab}-tab`);
            if (target) target.classList.add('active');

            if (tab.dataset.tab === 'models')   loadModels();
            if (tab.dataset.tab === 'skills')   loadSkills();
            if (tab.dataset.tab === 'logs')     loadLogs();
            if (tab.dataset.tab === 'reports')  loadReports();
            if (tab.dataset.tab === 'security') loadSecurity();
            if (tab.dataset.tab === 'memory')   loadMemory();
            if (tab.dataset.tab === 'apps')     loadApps();
            if (tab.dataset.tab === 'settings') loadSettingsTab();
        });
    });

    // ── Settings shortcut button ──────────────────────────
    const settingsBtn = document.getElementById('settings-btn');
    if (settingsBtn) {
        settingsBtn.addEventListener('click', () => {
            // Activate the Settings nav item + tab
            tabs.forEach(t => t.classList.remove('active'));
            tabContents.forEach(c => c.classList.remove('active'));
            const settingsTab = document.querySelector('li[data-tab="settings"]');
            const settingsContent = document.getElementById('settings-tab');
            if (settingsTab)    settingsTab.classList.add('active');
            if (settingsContent) settingsContent.classList.add('active');
            loadSettingsTab();
        });
    }

    // ── Terminal Button ───────────────────────────────────
    const terminalBtn = document.getElementById('terminal-btn');
    if (terminalBtn) {
        terminalBtn.addEventListener('click', async () => {
            terminalBtn.textContent = '⌨ Opening…';
            terminalBtn.disabled = true;
            try {
                await fetch('/api/system/terminal', { method: 'POST' });
            } catch (_) {}
            setTimeout(() => {
                terminalBtn.textContent = '⌨ Wake Up';
                terminalBtn.disabled = false;
            }, 1500);
        });
    }

    // ── System Actions ────────────────────────────────────
    const shutdownBtn = document.getElementById('shutdown-btn');
    if (shutdownBtn) {
        shutdownBtn.addEventListener('click', async () => {
            if (confirm('Are you sure you want to completely shut down Mello?')) {
                const res = await fetch('/api/system/shutdown', { method: 'POST' });
                const data = await res.json();
                alert(data.message);
                window.close();
            }
        });
    }

    // ── Typing Indicator ──────────────────────────────────
    function showTyping() {
        chatHistory.appendChild(typingIndicator);
        typingIndicator.classList.add('visible');
        chatHistory.scrollTop = chatHistory.scrollHeight;
    }

    function hideTyping() {
        typingIndicator.classList.remove('visible');
    }

    // ── Chat ──────────────────────────────────────────────
    async function sendMessage() {
        const text = userInput.value.trim();
        if (!text) return;

        appendMessage('user', text);
        userInput.value = '';
        sendBtn.disabled = true;
        sendBtn.textContent = '…';
        showTyping();
        setBotState('thinking');

        let assistantBubble = null;

        try {
            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message: text })
            });

            const reader = response.body.getReader();
            const decoder = new TextDecoder();

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                const chunk = decoder.decode(value);
                for (const line of chunk.split('\n')) {
                    if (line.startsWith('data: ')) {
                        try {
                            const data = JSON.parse(line.slice(6));
                            if (data.text) {
                                if (!assistantBubble) {
                                    hideTyping();
                                    setBotState('speaking');
                                    assistantBubble = appendMessage('assistant', '');
                                }
                                assistantBubble.innerText += data.text;
                                chatHistory.scrollTop = chatHistory.scrollHeight;
                            }
                        } catch { /* skip malformed SSE */ }
                    }
                }
            }

            if (!assistantBubble) {
                hideTyping();
                appendMessage('assistant', 'No response received.');
                setBotState('idle');
            } else {
                speakText(assistantBubble.innerText, assistantBubble);
                // If TTS not enabled, go idle right away
                if (!speechEnabled) setBotState('idle');
            }
        } catch (error) {
            hideTyping();
            setBotState('idle');
            if (!assistantBubble) appendMessage('assistant', `Error: ${error.message}`);
        } finally {
            sendBtn.disabled = false;
            sendBtn.textContent = '→';
        }
    }

    function appendMessage(role, text) {
        const wrapper = document.createElement('div');
        wrapper.className = `message ${role}`;
        const label = document.createElement('span');
        label.className = 'message-label';
        label.textContent = role === 'user' ? 'You' : 'Mello';
        const bubble = document.createElement('div');
        bubble.className = 'message-bubble';
        bubble.innerText = text;
        wrapper.appendChild(label);
        wrapper.appendChild(bubble);
        chatHistory.appendChild(wrapper);
        chatHistory.scrollTop = chatHistory.scrollHeight;
        return bubble;
    }

    // ── Text-to-Speech ────────────────────────────────────
    const speakToggleBtn = document.getElementById('speak-toggle');
    const speakIndicator = document.getElementById('speak-indicator');

    // Initialise from saved settings
    let speechEnabled = getSettings().ttsEnabled;
    if (speakToggleBtn) {
        speakToggleBtn.textContent = speechEnabled ? '🔊' : '🔇';
        speakToggleBtn.classList.toggle('off', !speechEnabled);
        speakToggleBtn.classList.toggle('on',   speechEnabled);
    }

    function setSpeakIndicator(active) {
        speakIndicator.classList.toggle('active', active);
    }

    function cleanForSpeech(text) {
        return text
            .replace(/<think>[\s\S]*?<\/think>/gi, '')
            .replace(/\{[^{}]*\}/g, '')
            .replace(/\*\*\[Done\]\*\*[^\n]*/g, '')
            .replace(/\*\*(.*?)\*\*/g, '$1')
            .replace(/\*(.*?)\*/g, '$1')
            .replace(/`[^`]+`/g, '')
            .replace(/#{1,6}\s[^\n]*/g, '')
            .replace(/\n{3,}/g, '\n\n')
            .trim();
    }

    function speakText(text, bubbleEl = null) {
        if (!speechEnabled || !window.speechSynthesis) return;
        window.speechSynthesis.cancel();
        const clean = cleanForSpeech(text);
        if (!clean) return;

        const s   = getSettings();
        const utt = new SpeechSynthesisUtterance(clean);
        utt.rate   = s.ttsRate   || 1.05;
        utt.pitch  = s.ttsPitch  || 1.0;
        utt.volume = s.ttsVolume !== undefined ? s.ttsVolume : 1.0;

        // Apply chosen voice (or fall back to best English voice)
        const voices = window.speechSynthesis.getVoices();
        if (s.ttsVoice) {
            const found = voices.find(v => v.name === s.ttsVoice);
            if (found) utt.voice = found;
        } else {
            const preferred = voices.find(v =>
                v.lang.startsWith('en') &&
                (v.name.includes('Google') || v.name.includes('Natural') || v.name.includes('Neural'))
            ) || voices.find(v => v.lang.startsWith('en'));
            if (preferred) utt.voice = preferred;
        }

        const msgWrapper = bubbleEl ? bubbleEl.closest('.message') : null;
        utt.onstart = () => { setSpeakIndicator(true);  setBotState('speaking'); if (msgWrapper) msgWrapper.classList.add('speaking'); };
        utt.onend   = () => { setSpeakIndicator(false); setBotState('idle');     if (msgWrapper) msgWrapper.classList.remove('speaking'); };
        utt.onerror = () => { setSpeakIndicator(false); setBotState('idle');     if (msgWrapper) msgWrapper.classList.remove('speaking'); };
        window.speechSynthesis.speak(utt);
    }

    if (speakToggleBtn) {
        speakToggleBtn.addEventListener('click', () => {
            speechEnabled = !speechEnabled;
            saveSettings({ ttsEnabled: speechEnabled });
            speakToggleBtn.textContent = speechEnabled ? '🔊' : '🔇';
            speakToggleBtn.title       = speechEnabled ? 'Voice ON — click to mute' : 'Enable voice';
            speakToggleBtn.classList.toggle('off', !speechEnabled);
            speakToggleBtn.classList.toggle('on',   speechEnabled);
            // Sync the Settings tab toggle if it's visible
            const ttsChk = document.getElementById('tts-enabled');
            if (ttsChk) ttsChk.checked = speechEnabled;
            if (!speechEnabled) { window.speechSynthesis.cancel(); setSpeakIndicator(false); }
        });
    }

    sendBtn.addEventListener('click', sendMessage);
    userInput.addEventListener('keypress', e => { if (e.key === 'Enter') sendMessage(); });

    // ── Pull Model ────────────────────────────────────────
    const pullModelBtn = document.getElementById('pull-model-btn');
    const pullModelInput = document.getElementById('pull-model-input');
    if (pullModelBtn) {
        pullModelBtn.addEventListener('click', async () => {
            const name = pullModelInput.value.trim();
            if (!name) return;
            pullModelBtn.disabled = true;
            pullModelBtn.textContent = 'Pulling…';
            const res = await fetch('/api/models/pull', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name })
            });
            const data = await res.json();
            alert(data.message);
            pullModelBtn.disabled = false;
            pullModelBtn.textContent = 'Pull Model';
            loadModels();
        });
    }

    // ── Load Models Tab ───────────────────────────────────
    async function loadModels() {
        const container = document.getElementById('models-list');
        container.innerHTML = '<p style="color:var(--text-muted); grid-column:1/-1;">Loading models…</p>';

        // Fetch installed models + running state + active model in parallel
        const [modelsRes, statusRes] = await Promise.all([
            fetch('/api/models'),
            fetch('/api/models/status')
        ]);
        const modelsData = await modelsRes.json();
        const statusData = await statusRes.json();

        const activeModel = statusData.active_model || currentActiveModel;
        const runningSet = new Set((statusData.running || []).map(r => r.split(':')[0].toLowerCase()));

        // Refresh global state
        currentActiveModel = activeModel;
        updateStatusDot(statusData.is_live);
        activeModelDisplay.textContent = activeModel;

        container.innerHTML = '';
        const models = modelsData.models || [];

        if (!models.length) {
            container.innerHTML = '<p style="color:var(--text-muted); grid-column:1/-1;">No models installed. Pull one above.</p>';
            return;
        }

        models.forEach(m => {
            const modelName = m.name || m.model || 'Unknown';
            const baseName = modelName.split(':')[0].toLowerCase();
            const isActive = modelName === activeModel || baseName === activeModel.split(':')[0].toLowerCase();
            const isRunning = runningSet.has(baseName);

            const card = document.createElement('div');
            card.className = `card${isActive ? ' model-active' : ''}`;

            const badges = [];
            if (isActive) badges.push('<span class="model-badge active-badge">Active</span>');
            if (isRunning) badges.push('<span class="model-badge running-badge">Running</span>');

            card.innerHTML = `
                <div style="display:flex; justify-content:space-between; align-items:flex-start; gap:0.5rem;">
                    <div>
                        <h3 style="margin:0 0 0.4rem; font-size:0.82rem; word-break:break-all;">${modelName}</h3>
                        <p style="margin:0;">${(m.size / 1e9).toFixed(2)} GB</p>
                    </div>
                    <div style="display:flex; flex-direction:column; align-items:flex-end; gap:0.3rem; flex-shrink:0;">
                        ${badges.join('')}
                    </div>
                </div>
                <button class="model-use-btn${isActive ? ' is-active' : ''}" data-model="${modelName}">
                    ${isActive ? '✓ Currently Active' : 'Use This Model'}
                </button>
            `;

            // "Use This Model" button
            const useBtn = card.querySelector('.model-use-btn');
            if (!isActive) {
                useBtn.addEventListener('click', async () => {
                    useBtn.disabled = true;
                    useBtn.textContent = 'Switching…';
                    // Select + start loading
                    await Promise.all([
                        fetch('/api/models/select', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ name: modelName })
                        }),
                        fetch('/api/models/start', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ name: modelName })
                        })
                    ]);
                    currentActiveModel = modelName;
                    activeModelDisplay.textContent = modelName;
                    updateStatusDot(false); // will go online after warmup
                    loadModels(); // refresh cards
                });
            }

            container.appendChild(card);
        });
    }

    // ── Skills ────────────────────────────────────────────
    async function loadSkills() {
        const container = document.getElementById('skills-list');
        container.innerHTML = '<p style="color:var(--text-muted); grid-column:1/-1;">Loading skills…</p>';
        const res = await fetch('/api/skills');
        const data = await res.json();
        container.innerHTML = '';
        if (data.skills && data.skills.length) {
            data.skills.forEach(s => {
                const card = document.createElement('div');
                card.className = 'card';
                card.innerHTML = `
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.4rem;">
                        <h3 style="margin:0;">${s.name}</h3>
                        <label class="switch">
                            <input type="checkbox" id="toggle-${s.name}" ${s.enabled ? 'checked' : ''}>
                            <span class="slider"></span>
                        </label>
                    </div>
                    <p>${s.desc}</p>
                `;
                container.appendChild(card);
                card.querySelector(`#toggle-${s.name}`).addEventListener('change', async e => {
                    await fetch('/api/skills/toggle', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ name: s.name, enabled: e.target.checked })
                    });
                });
            });
        } else {
            container.innerHTML = '<p style="color:var(--text-muted); grid-column:1/-1;">No skills registered yet.</p>';
        }
    }

    // ── Skill Builder ─────────────────────────────────────
    window.nextStep = (step) => {
        document.querySelectorAll('.workflow-content').forEach(c => c.classList.remove('active'));
        document.querySelectorAll('.step').forEach(s => s.classList.remove('active'));
        document.getElementById(`step-${step}`).classList.add('active');
        document.querySelector(`.step[data-step="${step}"]`).classList.add('active');
        if (step === 3) {
            const name = document.getElementById('skill-name-input').value || '—';
            const type = document.getElementById('skill-type-input').value;
            const desc = document.getElementById('skill-desc-input').value || '—';
            document.getElementById('skill-review-summary').textContent =
                `Name: ${name}\nType: ${type}\nDescription: ${desc}\n\nSkill will be registered in the modular engine.`;
        }
    };

    const openBuilderBtn = document.getElementById('open-skill-builder');
    if (openBuilderBtn) {
        openBuilderBtn.addEventListener('click', () => {
            const builder = document.getElementById('skill-builder');
            builder.style.display = builder.style.display === 'none' ? 'block' : 'none';
        });
    }

    const finalCreateBtn = document.getElementById('final-create-skill-btn');
    if (finalCreateBtn) {
        finalCreateBtn.addEventListener('click', async () => {
            const name = document.getElementById('skill-name-input').value;
            const desc = document.getElementById('skill-desc-input').value;
            const res = await fetch('/api/skills/create', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name, description: desc })
            });
            const data = await res.json();
            alert(data.message);
            document.getElementById('skill-builder').style.display = 'none';
            loadSkills();
        });
    }

    // ── Logs ──────────────────────────────────────────────
    async function loadLogs() {
        const container = document.getElementById('logs-list');
        container.innerHTML = '<p style="color:var(--text-muted);">Loading logs…</p>';
        const res = await fetch('/api/logs');
        const data = await res.json();
        container.innerHTML = '';
        if (data.logs && data.logs.length) {
            data.logs.forEach(l => {
                const entry = document.createElement('div');
                entry.className = 'log-entry';
                entry.innerHTML = `<span class="log-time">[${l.time}]</span><span class="log-type">${l.type}</span><span>${l.desc}</span>`;
                container.appendChild(entry);
            });
        } else {
            container.innerHTML = '<p style="color:var(--text-muted);">No log entries yet.</p>';
        }
    }

    // ── Reports ───────────────────────────────────────────
    async function loadReports() {
        const container = document.getElementById('reports-list');
        container.innerHTML = '<p style="color:var(--text-muted);">Loading reports…</p>';
        const res = await fetch('/api/reports');
        const data = await res.json();
        container.innerHTML = '';
        if (data.reports && data.reports.length) {
            data.reports.forEach(r => {
                const item = document.createElement('div');
                item.className = 'card';
                item.innerHTML = `<h3>${r.name}</h3><p>${(r.size / 1024).toFixed(1)} KB</p>`;
                container.appendChild(item);
            });
        } else {
            container.innerHTML = '<p style="color:var(--text-muted);">No reports available.</p>';
        }
    }

    // ── Apps ──────────────────────────────────────────────
    async function loadApps() {
        const container = document.getElementById('apps-list');
        if (!container) return;
        container.innerHTML = '<p style="color:var(--text-muted);">Scanning applications…</p>';

        const [appsRes, secRes] = await Promise.all([
            fetch('/api/apps/installed'),
            fetch('/api/security')
        ]);
        const appsData = await appsRes.json();
        const secData = await secRes.json();
        const allowedSet = new Set((secData.policy?.allowed_apps || []).map(a => a.toLowerCase()));

        container.innerHTML = '';
        if (!appsData.apps || !appsData.apps.length) {
            container.innerHTML = '<p style="color:var(--text-muted);">No applications found.</p>';
            return;
        }

        const apps = [...appsData.apps].sort((a, b) => a.Name.localeCompare(b.Name));
        const allowed = apps.filter(a => allowedSet.has(a.Name.toLowerCase()));
        const blocked = apps.filter(a => !allowedSet.has(a.Name.toLowerCase()));

        function makeSection(title, color, appList) {
            if (!appList.length) return;
            const section = document.createElement('div');
            section.style.marginBottom = '1.5rem';
            section.innerHTML = `<h3 style="color:${color}; margin-bottom:0.75rem; font-size:0.75rem; text-transform:uppercase; letter-spacing:1px; font-weight:700;">${title} (${appList.length})</h3>`;
            const grid = document.createElement('div');
            grid.className = 'grid-container';
            appList.forEach(app => {
                const isAllowed = allowedSet.has(app.Name.toLowerCase());
                const card = document.createElement('div');
                card.className = 'app-permission-card';
                card.innerHTML = `
                    <div class="app-permission-info">
                        <span class="app-permission-name" title="${app.Name}">${app.Name}</span>
                        <span class="app-permission-badge ${isAllowed ? 'badge-allowed' : 'badge-blocked'}">${isAllowed ? 'Allowed' : 'Blocked'}</span>
                    </div>
                    <div class="app-permission-actions">
                        ${isAllowed ? `<button class="launch-btn" data-app="${app.Name}">Launch</button>` : ''}
                        <label class="switch">
                            <input type="checkbox" ${isAllowed ? 'checked' : ''}>
                            <span class="slider"></span>
                        </label>
                    </div>
                `;
                card.querySelector('input[type="checkbox"]').addEventListener('change', async e => {
                    await fetch('/api/security/apps/toggle', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ name: app.Name, allowed: e.target.checked })
                    });
                    loadApps();
                });
                const launchBtn = card.querySelector('.launch-btn');
                if (launchBtn) {
                    launchBtn.addEventListener('click', () => {
                        userInput.value = `Open ${app.Name}`;
                        sendMessage();
                        document.querySelector('li[data-tab="chat"]').click();
                    });
                }
                grid.appendChild(card);
            });
            section.appendChild(grid);
            container.appendChild(section);
        }

        makeSection('✅ Allowed', 'var(--success)', allowed);
        makeSection('🚫 Blocked', 'var(--danger)', blocked);
    }

    // ── Security ──────────────────────────────────────────
    async function loadSecurity() {
        const container = document.getElementById('security-display');
        if (!container) return;
        container.innerHTML = '<p style="color:var(--text-muted);">Loading policy…</p>';
        const res = await fetch('/api/security');
        const data = await res.json();
        container.innerHTML = '';
        if (!data.policy) return;
        const p = data.policy;

        async function secCall(endpoint, body) {
            await fetch(endpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body)
            });
            loadSecurity();
        }

        function makeCard(title) {
            const card = document.createElement('div');
            card.className = 'card security-card';
            const h = document.createElement('h3');
            h.textContent = title;
            card.appendChild(h);
            return card;
        }

        function makeAddRow(placeholder, onAdd) {
            const row = document.createElement('div');
            row.className = 'security-add-row';
            const input = document.createElement('input');
            input.type = 'text';
            input.placeholder = placeholder;
            const btn = document.createElement('button');
            btn.className = 'security-add-btn';
            btn.textContent = '+ Add';
            btn.addEventListener('click', () => {
                const val = input.value.trim();
                if (val) { onAdd(val); input.value = ''; }
            });
            input.addEventListener('keypress', e => { if (e.key === 'Enter') btn.click(); });
            row.appendChild(input);
            row.appendChild(btn);
            return row;
        }

        // ─── Allowed Folders ───────────────────────────
        const foldersCard = makeCard('📁 Allowed Folders');
        const foldersList = document.createElement('div');
        foldersList.className = 'security-list';

        (p.allowed_folders || []).forEach(f => {
            const item = document.createElement('div');
            item.className = 'security-item';
            const text = document.createElement('span');
            text.className = 'security-item-text';
            text.textContent = f;
            text.title = f;
            const rmBtn = document.createElement('button');
            rmBtn.className = 'security-remove-btn';
            rmBtn.textContent = '✕';
            rmBtn.title = 'Remove';
            rmBtn.addEventListener('click', () => secCall('/api/security/folders/remove', { path: f }));
            item.appendChild(text);
            item.appendChild(rmBtn);
            foldersList.appendChild(item);
        });

        if (!p.allowed_folders?.length) {
            foldersList.innerHTML = '<span style="font-size:0.8rem; color:var(--text-muted);">No folders added yet.</span>';
        }

        foldersCard.appendChild(foldersList);

        // Single folder-picker button — picks and adds in one click
        const folderPickBtn = document.createElement('button');
        folderPickBtn.className = 'security-folder-pick-btn';
        folderPickBtn.textContent = '📂 Add Folder';
        folderPickBtn.addEventListener('click', async () => {
            folderPickBtn.textContent = 'Opening…';
            folderPickBtn.disabled = true;
            try {
                const res = await fetch('/api/system/pick-folder');
                const data = await res.json();
                if (data.path) secCall('/api/security/folders/add', { path: data.path });
            } catch (_) {}
            folderPickBtn.textContent = '📂 Add Folder';
            folderPickBtn.disabled = false;
        });
        foldersCard.appendChild(folderPickBtn);
        container.appendChild(foldersCard);


        // ─── Restricted Keywords ───────────────────────
        const keywords = p.restricted_keywords || ['rm', 'del', 'format', 'shutdown'];
        const kwCard = makeCard('🚫 Restricted Keywords');
        const kwTags = document.createElement('div');
        kwTags.className = 'security-tags';

        keywords.forEach(k => {
            const tag = document.createElement('span');
            tag.className = 'security-tag danger-tag';
            const label = document.createTextNode(k);
            const rmBtn = document.createElement('button');
            rmBtn.className = 'security-tag-remove';
            rmBtn.textContent = '✕';
            rmBtn.title = 'Remove';
            rmBtn.addEventListener('click', () => secCall('/api/security/keywords/remove', { keyword: k }));
            tag.appendChild(label);
            tag.appendChild(rmBtn);
            kwTags.appendChild(tag);
        });

        if (!keywords.length) {
            kwTags.innerHTML = '<span style="font-size:0.8rem; color:var(--text-muted);">No restricted keywords.</span>';
        }

        kwCard.appendChild(kwTags);
        kwCard.appendChild(makeAddRow(
            'e.g. shutdown, format',
            val => secCall('/api/security/keywords/add', { keyword: val })
        ));
        container.appendChild(kwCard);
    }

    // ── Memory Tab ────────────────────────────────────────

    // Clean label from raw description
    function entryLabel(type, description) {
        const filePrefixes = ['File detected: ', 'File created: ', 'File moved: ', 'Moved to: ', 'Moved file: '];
        for (const pfx of filePrefixes) {
            if (description.startsWith(pfx)) {
                const rest = description.slice(pfx.length).trim();
                return rest.split(/[\\/]/).pop() || rest;
            }
        }
        return description.length > 60 ? description.slice(0, 60) + '…' : description;
    }

    function timeAgo(ts) {
        const diff = Math.floor((Date.now() - new Date(ts + 'Z')) / 1000);
        if (diff < 60)    return `${diff}s ago`;
        if (diff < 3600)  return `${Math.floor(diff / 60)}m ago`;
        if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
        return `${Math.floor(diff / 86400)}d ago`;
    }

    const CHIP_COLOR = { files: 'chip-file', skills: 'chip-skill', chat: 'chip-chat', other: 'chip-other' };
    const CAT_ORDER  = ['files', 'skills', 'chat', 'other'];

    async function loadMemory(search = '') {
        const res  = await fetch(`/api/memory?search=${encodeURIComponent(search)}`);
        const data = await res.json();

        // Master toggle UI
        const toggle = document.getElementById('memory-toggle');
        const lbl    = document.getElementById('memory-toggle-label');
        const badge  = document.getElementById('memory-total-count');
        if (toggle) toggle.checked      = data.enabled;
        if (lbl)    lbl.textContent     = data.enabled ? 'ON' : 'OFF';
        if (badge)  badge.textContent   = data.total;

        const flow = document.getElementById('memory-flow');
        if (!flow) return;
        flow.innerHTML = '';

        CAT_ORDER.forEach(catKey => {
            const group = data.groups[catKey];
            if (!group) return;
            if (!group.entries.length && !search) return; // skip empty sections

            const on    = group.enabled;
            const count = group.entries.length;

            const section = document.createElement('div');
            section.className = `mem-group${on ? '' : ' mem-group-off'}`;
            section.innerHTML = `
              <div class="mem-group-head">
                <span class="mem-group-icon">${group.icon}</span>
                <span class="mem-group-label">${group.label}</span>
                <span class="mem-group-count">${count}</span>
                <div class="mem-group-acts">
                  <button class="mem-onoff-btn ${on ? 'is-on' : 'is-off'}" data-cat="${catKey}">${on ? 'ON' : 'OFF'}</button>
                  <button class="mem-clr-btn"  data-cat="${catKey}" title="Clear all">🗑</button>
                </div>
              </div>
              <div class="mem-chips"></div>
            `;

            const chips = section.querySelector('.mem-chips');
            if (!count) {
                chips.innerHTML = '<span class="chip-empty">No memories yet</span>';
            } else {
                group.entries.forEach(e => {
                    const chip = document.createElement('div');
                    chip.className = `mem-chip ${CHIP_COLOR[catKey] || ''}`;
                    const label = entryLabel(e.type, e.description);
                    chip.innerHTML = `
                      <span class="chip-text" title="${e.description}">${label}</span>
                      <span class="chip-time">${timeAgo(e.timestamp)}</span>
                      <button class="chip-del" data-id="${e.id}">✕</button>
                    `;
                    chips.appendChild(chip);
                });
            }
            flow.appendChild(section);

            // ON / OFF toggle
            section.querySelector('.mem-onoff-btn').addEventListener('click', async ev => {
                const btn  = ev.currentTarget;
                const nowOn = btn.classList.contains('is-off'); // clicking OFF → turn ON
                await fetch('/api/memory/category/toggle', {
                    method: 'POST', headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ category: catKey, enabled: nowOn }),
                });
                loadMemory(document.getElementById('memory-search').value);
            });

            // Clear all in category
            section.querySelector('.mem-clr-btn').addEventListener('click', async ev => {
                if (!confirm(`Clear all ${group.label}?`)) return;
                await fetch('/api/memory/clear-category', {
                    method: 'POST', headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ category: catKey, enabled: true }),
                });
                loadMemory(document.getElementById('memory-search').value);
            });

            // Delete individual chip
            chips.querySelectorAll('.chip-del').forEach(btn => {
                btn.addEventListener('click', async () => {
                    await fetch(`/api/memory/${btn.dataset.id}`, { method: 'DELETE' });
                    loadMemory(document.getElementById('memory-search').value);
                });
            });
        });
    }

    // ── Master toggle ─────────────────────────────────────
    const masterToggle = document.getElementById('memory-toggle');
    if (masterToggle) {
        masterToggle.addEventListener('change', async () => {
            await fetch('/api/memory/toggle', {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ enabled: masterToggle.checked }),
            });
            const lbl = document.getElementById('memory-toggle-label');
            if (lbl) lbl.textContent = masterToggle.checked ? 'ON' : 'OFF';
            loadMemory(document.getElementById('memory-search').value);
        });
    }

    // ── Live search ───────────────────────────────────────
    const memSearch = document.getElementById('memory-search');
    let memSearchTimer;
    if (memSearch) {
        memSearch.addEventListener('input', () => {
            clearTimeout(memSearchTimer);
            memSearchTimer = setTimeout(() => loadMemory(memSearch.value), 300);
        });
    }

    // ── Add Memory panel ──────────────────────────────────
    const addBtn     = document.getElementById('add-memory-btn');
    const addPanel   = document.getElementById('add-memory-panel');
    const saveBtn    = document.getElementById('save-memory-btn');
    const cancelBtn  = document.getElementById('cancel-memory-btn');
    const newDesc    = document.getElementById('new-mem-desc');
    const newType    = document.getElementById('new-mem-type');

    if (addBtn && addPanel) {
        addBtn.addEventListener('click', () => {
            addPanel.classList.toggle('hidden');
            if (!addPanel.classList.contains('hidden')) newDesc.focus();
        });
        cancelBtn.addEventListener('click', () => {
            addPanel.classList.add('hidden');
            newDesc.value = '';
        });
        saveBtn.addEventListener('click', async () => {
            const desc = newDesc.value.trim();
            if (!desc) { newDesc.focus(); return; }
            saveBtn.disabled = true;
            saveBtn.textContent = 'Saving…';
            await fetch('/api/memory/add', {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ description: desc, type: newType.value }),
            });
            newDesc.value = '';
            addPanel.classList.add('hidden');
            saveBtn.disabled = false;
            saveBtn.textContent = 'Save';
            loadMemory(memSearch ? memSearch.value : '');
        });
        // Save on Ctrl+Enter
        newDesc.addEventListener('keydown', e => {
            if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) saveBtn.click();
        });
    }

    // ── Voice — offline MediaRecorder + VAD + server Whisper ─────────────────
    let mediaRecorder = null;
    let audioChunks   = [];
    let micListening  = false;
    let stopVAD       = null;   // call to cancel the VAD loop

    function resetMic() {
        micListening = false;
        if (stopVAD) { stopVAD(); stopVAD = null; }
        micBtn.textContent = '🎤';
        micBtn.title = 'Voice input (offline)';
        micBtn.classList.remove('mic-active');
        setBotState('idle');
    }

    /** VAD: call onSilence() after `silenceMs` ms of audio level < `thresh`.
     *  Returns a cancel function. */
    function startVAD(stream, silenceMs, thresh, onSilence) {
        let stopped = false, silenceStart = null;
        try {
            const ctx      = new (window.AudioContext || window.webkitAudioContext)();
            const analyser = ctx.createAnalyser();
            ctx.createMediaStreamSource(stream).connect(analyser);
            analyser.fftSize = 256;
            const buf = new Uint8Array(analyser.frequencyBinCount);

            function tick() {
                if (stopped) return;
                analyser.getByteFrequencyData(buf);
                const rms = Math.sqrt(buf.reduce((s, v) => s + v * v, 0) / buf.length);
                if (rms < thresh) {
                    if (!silenceStart) silenceStart = Date.now();
                    else if (Date.now() - silenceStart >= silenceMs) {
                        stopped = true;
                        ctx.close().catch(() => {});
                        onSilence();
                        return;
                    }
                } else { silenceStart = null; }
                requestAnimationFrame(tick);
            }
            requestAnimationFrame(tick);
            return () => { stopped = true; ctx.close().catch(() => {}); };
        } catch {
            return () => {};
        }
    }

    async function sendAudioBlob(blob) {
        micBtn.textContent = '⌛';
        micBtn.title = 'Transcribing…';
        if (blob.size < 800) { resetMic(); return; }

        const form = new FormData();
        form.append('audio', blob, 'recording.webm');
        try {
            const res  = await fetch('/api/transcribe', { method: 'POST', body: form });
            const data = await res.json();
            if (data.text && data.text.trim()) {
                userInput.value = data.text.trim();
                if (getSettings().micAutoSend) sendMessage();
                else userInput.focus();
            } else if (data.error === 'no_stt_backend') {
                appendMessage('assistant',
                    '📦 **Offline STT not installed.**\n\nRun:\n    pip install faster-whisper\nThen restart Mello.');
            } else if (data.error && data.error !== 'no_speech') {
                appendMessage('assistant', `🎤 Transcription error: ${data.error}`);
            }
        } catch (err) {
            appendMessage('assistant', `🎤 Could not reach transcription service: ${err.message}`);
        }
        resetMic();
    }

    if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
        micBtn.title = 'Voice input (offline)';

        micBtn.addEventListener('click', async () => {
            if (micListening) {
                if (mediaRecorder && mediaRecorder.state === 'recording') mediaRecorder.stop();
                return;
            }

            let stream;
            try {
                stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            } catch (err) {
                if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
                    appendMessage('assistant',
                        '🎤 Microphone access denied.\n' +
                        'Click the 🔒 in the address bar → allow microphone → try again.');
                } else {
                    appendMessage('assistant', `🎤 Cannot access microphone: ${err.message}`);
                }
                return;
            }

            const mime = ['audio/webm;codecs=opus','audio/ogg;codecs=opus','audio/webm','audio/ogg']
                .find(t => MediaRecorder.isTypeSupported(t)) || '';
            audioChunks  = [];
            mediaRecorder = mime ? new MediaRecorder(stream, { mimeType: mime }) : new MediaRecorder(stream);

            mediaRecorder.ondataavailable = e => { if (e.data?.size > 0) audioChunks.push(e.data); };
            mediaRecorder.onstop = () => {
                stream.getTracks().forEach(t => t.stop());
                const blob = new Blob(audioChunks, { type: mediaRecorder.mimeType || 'audio/webm' });
                sendAudioBlob(blob);
            };

            micListening = true;
            micBtn.textContent = '🔴';
            micBtn.title = 'Recording… click to stop';
            micBtn.classList.add('mic-active');
            setBotState('listening');
            mediaRecorder.start(200);   // collect data every 200 ms

            // Start VAD if auto-stop is on
            const s = getSettings();
            if (s.micAutoStop) {
                stopVAD = startVAD(stream, s.micSilenceMs, s.micSilenceThresh, () => {
                    if (mediaRecorder && mediaRecorder.state === 'recording') mediaRecorder.stop();
                });
            }
        });
    } else {
        micBtn.style.display = 'none';
    }

    // ── Settings Tab ──────────────────────────────────────
    function loadSettingsTab() {
        const s = getSettings();

        // ── Mic: Whisper model ────────────────────────────
        document.querySelectorAll('input[name="micModel"]').forEach(r => {
            r.checked = (r.value === s.micModel);
            r.closest('.model-chip').classList.toggle('selected', r.checked);
            r.addEventListener('change', () => {
                document.querySelectorAll('.model-chip').forEach(c => c.classList.remove('selected'));
                r.closest('.model-chip').classList.add('selected');
                saveSettings({ micModel: r.value });
            });
        });

        // ── Mic: language ─────────────────────────────────
        const langSel = document.getElementById('mic-language');
        if (langSel) {
            langSel.value = s.micLanguage;
            langSel.addEventListener('change', () => saveSettings({ micLanguage: langSel.value }));
        }

        // ── Mic: auto-stop ────────────────────────────────
        const autoStop = document.getElementById('mic-auto-stop');
        const silenceOpts = document.getElementById('silence-options');
        function updateSilenceVis() {
            if (silenceOpts) silenceOpts.style.display = autoStop.checked ? 'block' : 'none';
        }
        if (autoStop) {
            autoStop.checked = s.micAutoStop;
            updateSilenceVis();
            autoStop.addEventListener('change', () => {
                saveSettings({ micAutoStop: autoStop.checked });
                updateSilenceVis();
            });
        }

        // ── Mic: silence ms ───────────────────────────────
        const silMs    = document.getElementById('mic-silence-ms');
        const silMsBdg = document.getElementById('silence-ms-badge');
        function updateSilMsBadge(v) {
            if (silMsBdg) silMsBdg.textContent = (v / 1000).toFixed(1) + ' s';
        }
        if (silMs) {
            silMs.value = s.micSilenceMs;
            updateSilMsBadge(s.micSilenceMs);
            silMs.addEventListener('input', () => {
                updateSilMsBadge(silMs.value);
                saveSettings({ micSilenceMs: +silMs.value });
            });
        }

        // ── Mic: silence threshold ────────────────────────
        const silThr    = document.getElementById('mic-silence-thresh');
        const silThrBdg = document.getElementById('silence-thresh-badge');
        function updateThrBadge(v) {
            if (!silThrBdg) return;
            if (v <= 8)       silThrBdg.textContent = 'Very high';
            else if (v <= 15) silThrBdg.textContent = 'Normal';
            else if (v <= 28) silThrBdg.textContent = 'Low';
            else              silThrBdg.textContent = 'Very low';
        }
        if (silThr) {
            silThr.value = s.micSilenceThresh;
            updateThrBadge(s.micSilenceThresh);
            silThr.addEventListener('input', () => {
                updateThrBadge(silThr.value);
                saveSettings({ micSilenceThresh: +silThr.value });
            });
        }

        // ── Mic: auto-send ────────────────────────────────
        const autoSend = document.getElementById('mic-auto-send');
        if (autoSend) {
            autoSend.checked = s.micAutoSend;
            autoSend.addEventListener('change', () => saveSettings({ micAutoSend: autoSend.checked }));
        }

        // ── Mic: test button ──────────────────────────────
        const testMicBtn    = document.getElementById('test-mic-btn');
        const testMicResult = document.getElementById('test-mic-result');
        if (testMicBtn) {
            testMicBtn.addEventListener('click', async () => {
                testMicBtn.disabled = true;
                testMicBtn.textContent = '🔴 Recording 3 s…';
                if (testMicResult) testMicResult.textContent = '';
                try {
                    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                    const mime   = ['audio/webm;codecs=opus','audio/webm'].find(t => MediaRecorder.isTypeSupported(t)) || '';
                    const chunks = [];
                    const mr     = mime ? new MediaRecorder(stream, { mimeType: mime }) : new MediaRecorder(stream);
                    mr.ondataavailable = e => { if (e.data?.size > 0) chunks.push(e.data); };
                    mr.start();
                    await new Promise(res => setTimeout(res, 3000));
                    mr.stop();
                    stream.getTracks().forEach(t => t.stop());
                    await new Promise(res => { mr.onstop = res; });
                    const blob = new Blob(chunks, { type: mr.mimeType || 'audio/webm' });
                    testMicBtn.textContent = '⌛ Transcribing…';
                    const form = new FormData();
                    form.append('audio', blob, 'test.webm');
                    const res  = await fetch('/api/transcribe', { method: 'POST', body: form });
                    const data = await res.json();
                    if (testMicResult) testMicResult.textContent = data.text
                        ? `✅ Heard: "${data.text}"`
                        : (data.error === 'no_stt_backend' ? '⚠️ Install: pip install faster-whisper' : '— no speech detected —');
                } catch (err) {
                    if (testMicResult) testMicResult.textContent = `❌ ${err.message}`;
                }
                testMicBtn.disabled = false;
                testMicBtn.textContent = '🎤 Test Microphone';
            });
        }

        // ── TTS: enable toggle ────────────────────────────
        const ttsChk = document.getElementById('tts-enabled');
        if (ttsChk) {
            ttsChk.checked = s.ttsEnabled;
            ttsChk.addEventListener('change', () => {
                speechEnabled = ttsChk.checked;
                saveSettings({ ttsEnabled: ttsChk.checked });
                // Sync chat-header button
                if (speakToggleBtn) {
                    speakToggleBtn.textContent = speechEnabled ? '🔊' : '🔇';
                    speakToggleBtn.classList.toggle('off', !speechEnabled);
                    speakToggleBtn.classList.toggle('on',   speechEnabled);
                }
                if (!speechEnabled) { window.speechSynthesis.cancel(); setSpeakIndicator(false); }
            });
        }

        // ── TTS: voice selector ───────────────────────────
        const voiceSel = document.getElementById('tts-voice');
        function populateVoices() {
            if (!voiceSel) return;
            const voices = window.speechSynthesis.getVoices();
            const cur    = voiceSel.value || s.ttsVoice;
            voiceSel.innerHTML = '<option value="">— Default system voice —</option>';
            voices.forEach(v => {
                const opt = document.createElement('option');
                opt.value       = v.name;
                opt.textContent = `${v.name} (${v.lang})`;
                voiceSel.appendChild(opt);
            });
            voiceSel.value = cur;
        }
        if (window.speechSynthesis) {
            populateVoices();
            window.speechSynthesis.onvoiceschanged = populateVoices;
        }
        if (voiceSel) {
            voiceSel.addEventListener('change', () => saveSettings({ ttsVoice: voiceSel.value }));
        }

        // ── TTS: rate / pitch / volume sliders ────────────
        function makeSlider(id, badgeId, unit, decimals, key) {
            const el  = document.getElementById(id);
            const bdg = document.getElementById(badgeId);
            if (!el) return;
            el.value = s[key];
            if (bdg) bdg.textContent = (+s[key]).toFixed(decimals) + unit;
            el.addEventListener('input', () => {
                if (bdg) bdg.textContent = (+el.value).toFixed(decimals) + unit;
                saveSettings({ [key]: +el.value });
            });
        }
        makeSlider('tts-rate',   'tts-rate-badge',   '×', 2, 'ttsRate');
        makeSlider('tts-pitch',  'tts-pitch-badge',  '',  2, 'ttsPitch');
        makeSlider('tts-volume', 'tts-volume-badge', '%', 0, 'ttsVolume');
        // Volume needs % display
        const volEl  = document.getElementById('tts-volume');
        const volBdg = document.getElementById('tts-volume-badge');
        if (volEl && volBdg) {
            volEl.value = s.ttsVolume;
            volBdg.textContent = Math.round(s.ttsVolume * 100) + '%';
            volEl.addEventListener('input', () => {
                volBdg.textContent = Math.round(volEl.value * 100) + '%';
                saveSettings({ ttsVolume: +volEl.value });
            });
        }

        // ── TTS: test button ──────────────────────────────
        const testTtsBtn = document.getElementById('test-tts-btn');
        if (testTtsBtn) {
            testTtsBtn.addEventListener('click', () => {
                speakText("Hello! This is how I sound with your current voice settings.", null);
            });
        }
    }
});


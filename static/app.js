document.addEventListener('DOMContentLoaded', () => {
    const tabs = document.querySelectorAll('nav li');
    const tabContents = document.querySelectorAll('.tab-content');
    const chatHistory = document.getElementById('chat-history');
    const userInput = document.getElementById('user-input');
    const sendBtn = document.getElementById('send-btn');
    const micBtn = document.getElementById('mic-btn');
    const typingIndicator = document.getElementById('typing-indicator');

    // ── Model status elements ─────────────────────────────
    const liveDot = document.getElementById('model-live-dot');
    const activeModelDisplay = document.getElementById('active-model-display');
    const modal = document.getElementById('model-startup-modal');
    const modalModelSelect = document.getElementById('modal-model-select');
    const modalStartBtn = document.getElementById('modal-start-btn');
    const modalDismissBtn = document.getElementById('modal-dismiss-btn');
    const modalProgress = document.getElementById('modal-progress');
    const modalProgressText = document.getElementById('modal-progress-text');
    const modalSuccess = document.getElementById('modal-success');

    let statusPollTimer = null;
    let currentActiveModel = 'qwen3.5:4b';

    // ── Model Status & Modal ──────────────────────────────
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
            return { is_live: false, active_model: currentActiveModel };
        }
    }

    function updateStatusDot(isLive) {
        liveDot.className = `model-live-dot ${isLive ? 'online' : 'offline'}`;
        liveDot.title = isLive
            ? `${currentActiveModel} is live`
            : 'Model offline — click to start';
    }

    // Open modal when red dot is clicked
    liveDot.addEventListener('click', () => {
        if (liveDot.classList.contains('offline')) showModal();
    });
    activeModelDisplay.addEventListener('click', () => showModal());

    async function showModal() {
        // Populate model selector from installed models
        try {
            const res = await fetch('/api/models');
            const data = await res.json();
            const models = data.models || [];
            modalModelSelect.innerHTML = '';
            // Always have the default first
            const defaultOpt = document.createElement('option');
            defaultOpt.value = 'qwen3.5:4b';
            defaultOpt.textContent = 'qwen3.5:4b (recommended)';
            modalModelSelect.appendChild(defaultOpt);
            models.forEach(m => {
                const name = m.name || m.model;
                if (name && name !== 'qwen3.5:4b') {
                    const opt = document.createElement('option');
                    opt.value = name;
                    opt.textContent = name;
                    modalModelSelect.appendChild(opt);
                }
            });
            // Pre-select current active model if available
            if (currentActiveModel) modalModelSelect.value = currentActiveModel;
        } catch { /* use defaults */ }

        // Reset modal state
        modalProgress.classList.add('hidden');
        modalSuccess.classList.add('hidden');
        modalStartBtn.disabled = false;
        modalStartBtn.textContent = '⚡ Start Model';

        modal.classList.remove('hidden');
    }

    function hideModal() {
        modal.classList.add('hidden');
        if (statusPollTimer) { clearInterval(statusPollTimer); statusPollTimer = null; }
    }

    modalDismissBtn.addEventListener('click', hideModal);

    modalStartBtn.addEventListener('click', async () => {
        const selectedModel = modalModelSelect.value;
        modalStartBtn.disabled = true;
        modalStartBtn.textContent = 'Starting…';
        modalProgress.classList.remove('hidden');
        modalSuccess.classList.add('hidden');
        modalProgressText.textContent = `Loading ${selectedModel}…`;

        try {
            await fetch('/api/models/start', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name: selectedModel })
            });
        } catch (e) {
            modalProgressText.textContent = `Error: ${e.message}`;
            modalStartBtn.disabled = false;
            modalStartBtn.textContent = '⚡ Start Model';
            return;
        }

        // Poll until model goes live (max 90s)
        let elapsed = 0;
        statusPollTimer = setInterval(async () => {
            elapsed += 3;
            const data = await checkModelStatus();
            if (data.is_live) {
                clearInterval(statusPollTimer);
                statusPollTimer = null;
                modalProgress.classList.add('hidden');
                modalSuccess.classList.remove('hidden');
                // Auto-close after 1.5s
                setTimeout(hideModal, 1500);
            } else if (elapsed >= 90) {
                clearInterval(statusPollTimer);
                statusPollTimer = null;
                modalProgressText.textContent = 'Taking longer than expected — model may still be loading.';
                modalStartBtn.disabled = false;
                modalStartBtn.textContent = '⚡ Retry';
            }
        }, 3000);
    });

    // ── Initial status check on page load ────────────────
    (async () => {
        const data = await checkModelStatus();
        if (!data.is_live) showModal();
    })();

    // ── Tab Switching ─────────────────────────────────────
    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            tabs.forEach(t => t.classList.remove('active'));
            tabContents.forEach(c => c.classList.remove('active'));
            tab.classList.add('active');
            const target = document.getElementById(`${tab.dataset.tab}-tab`);
            if (target) target.classList.add('active');

            if (tab.dataset.tab === 'models') loadModels();
            if (tab.dataset.tab === 'skills') loadSkills();
            if (tab.dataset.tab === 'logs') loadLogs();
            if (tab.dataset.tab === 'reports') loadReports();
            if (tab.dataset.tab === 'security') loadSecurity();
            if (tab.dataset.tab === 'apps') loadApps();
        });
    });

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
            }
        } catch (error) {
            hideTyping();
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
        foldersCard.appendChild(makeAddRow(
            'e.g. C:\\Users\\user\\Documents',
            val => secCall('/api/security/folders/add', { path: val })
        ));
        container.appendChild(foldersCard);

        // ─── Allowed Applications ──────────────────────
        const appsCard = makeCard('🧩 Allowed Applications');
        const appsTags = document.createElement('div');
        appsTags.className = 'security-tags';

        (p.allowed_apps || []).forEach(a => {
            const tag = document.createElement('span');
            tag.className = 'security-tag';
            const label = document.createTextNode(a);
            const rmBtn = document.createElement('button');
            rmBtn.className = 'security-tag-remove';
            rmBtn.textContent = '✕';
            rmBtn.title = 'Remove';
            rmBtn.addEventListener('click', () => secCall('/api/security/apps/toggle', { name: a, allowed: false }));
            tag.appendChild(label);
            tag.appendChild(rmBtn);
            appsTags.appendChild(tag);
        });

        if (!p.allowed_apps?.length) {
            appsTags.innerHTML = '<span style="font-size:0.8rem; color:var(--text-muted);">No apps allowed yet.</span>';
        }

        appsCard.appendChild(appsTags);
        appsCard.appendChild(makeAddRow(
            'e.g. notepad, chrome, vlc',
            val => secCall('/api/security/apps/toggle', { name: val, allowed: true })
        ));
        container.appendChild(appsCard);

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

    // ── Voice ─────────────────────────────────────────────
    if ('webkitSpeechRecognition' in window) {
        const recognition = new webkitSpeechRecognition();
        recognition.continuous = false;
        recognition.interimResults = false;
        micBtn.addEventListener('click', () => {
            micBtn.textContent = '🔴';
            recognition.start();
        });
        recognition.onresult = e => {
            userInput.value = e.results[0][0].transcript;
            micBtn.textContent = '🎤';
            sendMessage();
        };
        recognition.onerror = () => { micBtn.textContent = '🎤'; };
    } else {
        micBtn.style.display = 'none';
    }
});

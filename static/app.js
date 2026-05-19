document.addEventListener('DOMContentLoaded', () => {
    const tabs = document.querySelectorAll('nav li');
    const tabContents = document.querySelectorAll('.tab-content');
    const chatHistory = document.getElementById('chat-history');
    const userInput = document.getElementById('user-input');
    const sendBtn = document.getElementById('send-btn');
    const micBtn = document.getElementById('mic-btn');

    // --- Tab Switching ---
    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            tabs.forEach(t => t.classList.remove('active'));
            tabContents.forEach(c => c.classList.remove('active'));

            tab.classList.add('active');
            const target = document.getElementById(`${tab.dataset.tab}-tab`);
            if (target) target.classList.add('active');

            // Refresh data when switching tabs
            if (tab.dataset.tab === 'models') loadModels();
            if (tab.dataset.tab === 'skills') loadSkills();
            if (tab.dataset.tab === 'logs') loadLogs();
            if (tab.dataset.tab === 'reports') loadReports();
            if (tab.dataset.tab === 'security') loadSecurity();
            if (tab.dataset.tab === 'apps') loadApps();
        });
    });

    // --- System Actions ---
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

    // --- Chat Logic ---
    async function sendMessage() {
        const text = userInput.value.trim();
        if (!text) return;

        appendMessage('user', text);
        userInput.value = '';

        const assistantMessageDiv = appendMessage('assistant', '');
        
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
                const lines = chunk.split('\n');
                
                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        try {
                            const data = JSON.parse(line.slice(6));
                            if (data.text) {
                                assistantMessageDiv.innerText += data.text;
                                chatHistory.scrollTop = chatHistory.scrollHeight;
                            }
                        } catch (e) {
                            console.error('Error parsing SSE:', e);
                        }
                    }
                }
            }
        } catch (error) {
            assistantMessageDiv.innerText = `Error: ${error.message}`;
        }
    }

    function appendMessage(role, text) {
        const div = document.createElement('div');
        div.className = `message ${role}`;
        div.innerText = text;
        chatHistory.appendChild(div);
        chatHistory.scrollTop = chatHistory.scrollHeight;
        return div;
    }

    sendBtn.addEventListener('click', sendMessage);
    userInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') sendMessage();
    });

    // --- Action Handlers ---
    const pullModelBtn = document.getElementById('pull-model-btn');
    const pullModelInput = document.getElementById('pull-model-input');
    if (pullModelBtn) {
        pullModelBtn.addEventListener('click', async () => {
            const name = pullModelInput.value.trim();
            if (!name) return;
            pullModelBtn.disabled = true;
            pullModelBtn.innerText = 'Pulling...';
            const res = await fetch('/api/models/pull', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name })
            });
            const data = await res.json();
            alert(data.message);
            pullModelBtn.disabled = false;
            pullModelBtn.innerText = 'Pull Model';
            loadModels();
        });
    }

    const createSkillBtn = document.getElementById('create-skill-btn');
    const newSkillNameInput = document.getElementById('new-skill-name');
    if (createSkillBtn) {
        createSkillBtn.addEventListener('click', async () => {
            const name = newSkillNameInput.value.trim();
            if (!name) return;
            const res = await fetch('/api/skills/create', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name, description: 'User defined skill' })
            });
            const data = await res.json();
            alert(data.message);
            loadSkills();
        });
    }

    // --- Skill Builder Logic ---
    window.nextStep = (step) => {
        document.querySelectorAll('.workflow-content').forEach(c => c.classList.remove('active'));
        document.querySelectorAll('.step').forEach(s => s.classList.remove('active'));
        
        document.getElementById(`step-${step}`).classList.add('active');
        document.querySelector(`.step[data-step="${step}"]`).classList.add('active');

        if (step === 3) {
            const name = document.getElementById('skill-name-input').value;
            const type = document.getElementById('skill-type-input').value;
            document.getElementById('skill-review-summary').innerHTML = `
                <p><strong>Name:</strong> ${name}</p>
                <p><strong>Type:</strong> ${type}</p>
                <p><strong>Manifest:</strong> Skill will be registered in modular engine.</p>
            `;
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

    // --- Data Fetching ---
    async function loadModels() {
        const container = document.getElementById('models-list');
        container.innerHTML = 'Loading models...';
        const res = await fetch('/api/models');
        const data = await res.json();
        container.innerHTML = '';
        if (data.models) {
            data.models.forEach(m => {
                const card = document.createElement('div');
                card.className = 'card';
                const modelName = m.name || m.model || 'Unknown';
                const isRunning = m.size > 0;
                const statusColor = isRunning ? '#34d399' : '#f87171';
                
                card.innerHTML = `
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <h3 style="margin:0;">${modelName}</h3>
                        <label class="switch">
                            <input type="checkbox" ${isRunning ? 'checked' : ''} disabled>
                            <span class="slider"></span>
                        </label>
                    </div>
                    <p style="margin-top:0.5rem;">Size: ${(m.size / 1e9).toFixed(2)} GB</p>
                    <p>Status: <span style="color:${statusColor}">${isRunning ? 'Loaded' : 'Dormant'}</span></p>
                `;
                container.appendChild(card);
            });
        }
    }

    async function loadSkills() {
        const container = document.getElementById('skills-list');
        container.innerHTML = 'Loading skills...';
        const res = await fetch('/api/skills');
        const data = await res.json();
        container.innerHTML = '';
        if (data.skills) {
            data.skills.forEach(s => {
                const card = document.createElement('div');
                card.className = 'card';
                card.innerHTML = `
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <h3 style="margin:0;">${s.name}</h3>
                        <label class="switch">
                            <input type="checkbox" id="toggle-${s.name}" ${s.enabled ? 'checked' : ''}>
                            <span class="slider"></span>
                        </label>
                    </div>
                    <p style="margin-top:0.5rem;">${s.desc}</p>
                `;
                container.appendChild(card);

                // Add Toggle Event
                const toggle = card.querySelector(`#toggle-${s.name}`);
                toggle.addEventListener('change', async () => {
                    await fetch('/api/skills/toggle', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ name: s.name, enabled: toggle.checked })
                    });
                });
            });
        }
    }

    async function loadLogs() {
        const container = document.getElementById('logs-list');
        container.innerHTML = 'Loading logs...';
        const res = await fetch('/api/logs');
        const data = await res.json();
        container.innerHTML = '';
        if (data.logs) {
            data.logs.forEach(l => {
                const entry = document.createElement('div');
                entry.className = 'log-entry';
                entry.innerHTML = `<span class="log-time">[${l.time}]</span><span class="log-type">${l.type}</span><span>${l.desc}</span>`;
                container.appendChild(entry);
            });
        }
    }

    async function loadReports() {
        const container = document.getElementById('reports-list');
        container.innerHTML = 'Loading reports...';
        const res = await fetch('/api/reports');
        const data = await res.json();
        container.innerHTML = '';
        if (data.reports) {
            data.reports.forEach(r => {
                const item = document.createElement('div');
                item.className = 'card';
                item.innerHTML = `<h3>${r.name}</h3><p>Size: ${(r.size / 1024).toFixed(1)} KB</p>`;
                container.appendChild(item);
            });
        }
    }

    async function loadApps() {
        const container = document.getElementById('apps-list');
        if (!container) return;
        container.innerHTML = '<p style="color:var(--text-muted)">Scanning for applications...</p>';

        const [appsRes, secRes] = await Promise.all([
            fetch('/api/apps/installed'),
            fetch('/api/security')
        ]);
        const appsData = await appsRes.json();
        const secData = await secRes.json();

        const allowedSet = new Set(
            (secData.policy?.allowed_apps || []).map(a => a.toLowerCase())
        );

        container.innerHTML = '';
        if (!appsData.apps || !appsData.apps.length) {
            container.innerHTML = '<p style="color:var(--text-muted)">No applications found.</p>';
            return;
        }

        const apps = [...appsData.apps].sort((a, b) => a.Name.localeCompare(b.Name));
        const allowed = apps.filter(a => allowedSet.has(a.Name.toLowerCase()));
        const blocked = apps.filter(a => !allowedSet.has(a.Name.toLowerCase()));

        function makeSection(title, color, appList) {
            if (!appList.length) return;
            const section = document.createElement('div');
            section.style.marginBottom = '1.5rem';
            section.innerHTML = `<h3 style="color:${color}; margin-bottom:0.75rem; font-size:0.85rem; text-transform:uppercase; letter-spacing:1px;">${title} (${appList.length})</h3>`;

            const grid = document.createElement('div');
            grid.className = 'grid-container';
            grid.style.marginTop = '0';

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

                card.querySelector('input[type="checkbox"]').addEventListener('change', async (e) => {
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

        makeSection('✅ Allowed', '#34d399', allowed);
        makeSection('🚫 Not Allowed', '#f87171', blocked);
    }

    async function loadSecurity() {
        const container = document.getElementById('security-display');
        if (!container) return;
        container.innerHTML = 'Loading policy...';
        const res = await fetch('/api/security');
        const data = await res.json();
        container.innerHTML = '';
        if (data.policy) {
            const p = data.policy;
            container.innerHTML = `
                <div class="card">
                    <h3>Allowed Folders</h3>
                    <ul style="list-style:none; margin-top:0.5rem;">
                        ${p.allowed_folders.map(f => `<li>📁 ${f}</li>`).join('')}
                    </ul>
                </div>
                <div class="card" style="margin-top:1rem;">
                    <h3>Allowed Applications</h3>
                    <div style="display:flex; gap:0.5rem; flex-wrap:wrap; margin-top:0.5rem;">
                        ${p.allowed_apps.map(a => `<span class="status-badge" style="background:#334155; color:white;">${a}</span>`).join('')}
                    </div>
                </div>
                <div class="card" style="margin-top:1rem;">
                    <h3>Restricted Keywords</h3>
                    <p style="color:var(--text-muted); margin-top:0.5rem;">Mello is blocked from using these commands:</p>
                    <div style="display:flex; gap:0.5rem; flex-wrap:wrap; margin-top:0.5rem;">
                        <span class="status-badge" style="background:#450a0a; color:#f87171;">rm</span>
                        <span class="status-badge" style="background:#450a0a; color:#f87171;">del</span>
                        <span class="status-badge" style="background:#450a0a; color:#f87171;">format</span>
                        <span class="status-badge" style="background:#450a0a; color:#f87171;">shutdown</span>
                    </div>
                </div>
            `;
        }
    }

    // --- Voice Logic (Basic) ---
    if ('webkitSpeechRecognition' in window) {
        const recognition = new webkitSpeechRecognition();
        recognition.continuous = false;
        recognition.interimResults = false;

        micBtn.addEventListener('click', () => {
            micBtn.innerText = '🔴';
            recognition.start();
        });

        recognition.onresult = (event) => {
            const transcript = event.results[0][0].transcript;
            userInput.value = transcript;
            micBtn.innerText = '🎤';
            sendMessage();
        };

        recognition.onerror = () => {
            micBtn.innerText = '🎤';
        };
    } else {
        micBtn.style.display = 'none';
    }
});

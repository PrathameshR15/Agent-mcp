document.addEventListener('DOMContentLoaded', () => {
    // --- Tabs Logic ---
    const navItems = document.querySelectorAll('.nav-item');
    const tabContents = document.querySelectorAll('.tab-content');

    navItems.forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            navItems.forEach(nav => nav.classList.remove('active'));
            tabContents.forEach(tab => tab.classList.remove('active'));
            
            item.classList.add('active');
            document.getElementById(item.dataset.tab + '-tab').classList.add('active');
            
            if (item.dataset.tab === 'agents') loadAgents();
        });
    });

    // --- Modal Logic ---
    const registerModal = document.getElementById('register-modal');
    const editModal = document.getElementById('edit-modal');
    document.getElementById('open-register-modal').addEventListener('click', () => registerModal.style.display = 'flex');
    registerModal.querySelector('.close').addEventListener('click', () => registerModal.style.display = 'none');
    document.getElementById('close-edit-modal').addEventListener('click', () => editModal.style.display = 'none');
    window.addEventListener('click', (e) => { 
        if (e.target === registerModal) registerModal.style.display = 'none'; 
        if (e.target === editModal) editModal.style.display = 'none'; 
    });

    // --- Agent Logic ---
    let agentsCache = {};
    async function loadAgents() {
        try {
            const res = await fetch('/api/agents');
            const agents = await res.json();
            agentsCache = {};
            const container = document.getElementById('agents-container');
            container.innerHTML = '';
            
            agents.forEach(agent => {
                agentsCache[agent.agent_id] = agent;
                const caps = agent.capabilities.map(c => `<span class="badge">${c}</span>`).join('');
                const authBadge = agent.metadata && agent.metadata.auth_header ? '<span class="badge" title="Auth Token Active">🔒 Auth Configured</span>' : '';
                container.innerHTML += `
                    <div class="card" id="agent-card-${agent.agent_id}">
                        <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                            <h3>${agent.name}</h3>
                            <div style="display: flex; gap: 0.4rem;">
                                <button class="btn secondary-btn" style="padding: 0.2rem 0.6rem; font-size: 0.75rem; color: #38bdf8; border-color: rgba(56, 189, 248, 0.4);" onclick="openEditModal('${agent.agent_id}')">Edit</button>
                                <button class="btn secondary-btn" style="padding: 0.2rem 0.6rem; font-size: 0.75rem; color: #ef4444; border-color: rgba(239, 68, 68, 0.3);" onclick="deleteAgent('${agent.agent_id}')">Delete</button>
                            </div>
                        </div>
                        <p>${agent.description}</p>
                        <div class="mb-2">
                            <span class="badge status-checking" id="health-${agent.agent_id}">Checking status...</span>
                            <span class="badge">v${agent.version}</span>
                            ${authBadge}
                        </div>
                        <div style="margin-bottom: 0.5rem; font-size: 0.8rem; word-break: break-all; color: #38bdf8;">
                            <strong>Endpoint:</strong> <span>${agent.endpoint}</span>
                        </div>
                        <div><strong>Capabilities:</strong><br>${caps}</div>
                        <div style="margin-top:0.5rem; font-size:0.75rem; color:#94a3b8">ID: ${agent.agent_id}</div>
                    </div>
                `;
            });

            // Trigger background health checks for all agents
            checkAgentsHealth();
        } catch (err) {
            console.error('Failed to load agents', err);
        }
    }

    async function checkAgentsHealth() {
        try {
            const res = await fetch('/api/agents/health');
            const healthMap = await res.json();
            for (const [agentId, info] of Object.entries(healthMap)) {
                const el = document.getElementById(`health-${agentId}`);
                if (el) {
                    if (info.healthy) {
                        el.className = 'badge status-active';
                        el.innerHTML = `🟢 Active (Online)`;
                        el.title = info.details || 'Online';
                    } else {
                        el.className = 'badge status-offline';
                        el.innerHTML = `🔴 Offline`;
                        el.title = info.details || 'Unreachable';
                    }
                }
            }
        } catch (err) {
            console.error('Failed to check agent health', err);
        }
    }

    window.openEditModal = function(agentId) {
        const agent = agentsCache[agentId];
        if (!agent) return;
        document.getElementById('edit-agent-id').value = agent.agent_id;
        document.getElementById('edit-agent-id-display').value = agent.agent_id;
        document.getElementById('edit-agent-name').value = agent.name || '';
        document.getElementById('edit-agent-desc').value = agent.description || '';
        document.getElementById('edit-agent-cap').value = (agent.capabilities || []).join(', ');
        document.getElementById('edit-agent-endpoint').value = agent.endpoint || '';
        document.getElementById('edit-agent-auth').value = (agent.metadata && agent.metadata.auth_header) || '';
        document.getElementById('edit-agent-inputs').value = (agent.input_types || []).join(', ');
        editModal.style.display = 'flex';
    };

    window.deleteAgent = async function(agentId) {
        if (!confirm(`Are you sure you want to remove agent '${agentId}'?`)) return;
        try {
            const res = await fetch(`/api/agents/${agentId}`, { method: 'DELETE' });
            if (res.ok) {
                loadAgents();
            } else {
                alert('Failed to delete agent');
            }
        } catch (err) {
            alert('Error deleting agent');
        }
    };

    document.getElementById('register-agent-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const endpointVal = document.getElementById('agent-endpoint').value.trim();
        const authVal = document.getElementById('agent-auth').value.trim();
        
        const payload = {
            agent_id: document.getElementById('agent-id').value.trim(),
            name: document.getElementById('agent-name').value.trim(),
            description: document.getElementById('agent-desc').value.trim(),
            capabilities: document.getElementById('agent-cap').value.split(',').map(s => s.trim()).filter(Boolean),
            input_types: document.getElementById('agent-inputs').value.split(',').map(s => s.trim()).filter(Boolean),
            output_types: ["application/json"],
            endpoint: endpointVal,
            version: "1.0",
            status: "active",
            priority: 0,
            metadata: authVal ? { auth_header: authVal } : {}
        };

        try {
            const res = await fetch('/api/agents', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            if (res.ok) {
                registerModal.style.display = 'none';
                e.target.reset();
                loadAgents();
            } else {
                const errData = await res.json();
                alert('Failed to register agent: ' + (errData.detail || 'Error'));
            }
        } catch (err) {
            console.error(err);
            alert('Failed to register agent');
        }
    });

    document.getElementById('edit-agent-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const agentId = document.getElementById('edit-agent-id').value;
        const currentAgent = agentsCache[agentId] || {};
        const endpointVal = document.getElementById('edit-agent-endpoint').value.trim();
        const authVal = document.getElementById('edit-agent-auth').value.trim();

        const metadata = { ...(currentAgent.metadata || {}) };
        if (authVal) {
            metadata.auth_header = authVal;
        } else {
            delete metadata.auth_header;
        }

        const payload = {
            name: document.getElementById('edit-agent-name').value.trim(),
            description: document.getElementById('edit-agent-desc').value.trim(),
            capabilities: document.getElementById('edit-agent-cap').value.split(',').map(s => s.trim()).filter(Boolean),
            endpoint: endpointVal,
            input_types: document.getElementById('edit-agent-inputs').value.split(',').map(s => s.trim()).filter(Boolean),
            metadata: metadata
        };

        try {
            const res = await fetch(`/api/agents/${agentId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            if (res.ok) {
                editModal.style.display = 'none';
                loadAgents();
            } else {
                const errData = await res.json();
                alert('Failed to update agent: ' + (errData.detail || 'Error'));
            }
        } catch (err) {
            console.error(err);
            alert('Failed to update agent');
        }
    });

    // --- Data Source Logic ---
    const dataSources = [
        { type: "image/jpeg", payload: { source: "camera_highway_01", event_time: new Date().toISOString(), url: "http://example.com/stream/frame_123.jpg", resolution: "1080p" } },
        { type: "application/json", payload: { source: "temp_sensor_04", event_time: new Date().toISOString(), temperature: 45.2, unit: "C" } },
        { type: "image/png", payload: { source: "radar_02", event_time: new Date().toISOString(), url: "http://example.com/radar/scan_456.png" } },
        { type: "text/csv", payload: { source: "log_batch", event_time: new Date().toISOString(), data: "timestamp,event\\n12345,boot" } }
    ];

    function formatAssignedAgents(result) {
        if (result.assigned_agent_details && result.assigned_agent_details.length > 0) {
            return result.assigned_agent_details.map(a => `<span class="badge status-active">${a.name} (ID: ${a.agent_id})</span>`).join(' ');
        }
        if (result.assigned_agents && result.assigned_agents.length > 0) {
            return result.assigned_agents.map(a => `<span class="badge status-active">${a}</span>`).join(' ');
        }
        return '<span style="color:red">No agents matched requirements!</span>';
    }

    document.getElementById('emit-data-btn').addEventListener('click', async () => {
        const resultBox = document.getElementById('routing-result-box');
        const emittedDisplay = document.getElementById('emitted-data-display');
        
        // Generate random data
        const randomData = dataSources[Math.floor(Math.random() * dataSources.length)];
        // Update timestamp for freshness
        if(randomData.payload.event_time) randomData.payload.event_time = new Date().toISOString();
        
        emittedDisplay.innerHTML = `<span style="color:var(--primary)">Event Emitted!</span>\n<strong>Data Type:</strong> ${randomData.type}\n<strong>Payload:</strong>\n${JSON.stringify(randomData.payload, null, 2)}`;
        resultBox.innerHTML = '<span class="placeholder">MCP is routing data...</span>';

        const payload = {
            data_type: randomData.type,
            requirements: [],
            payload: randomData.payload
        };

        try {
            const res = await fetch('/api/submit', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const result = await res.json();
            
            if (res.ok) {
                const agentsList = formatAssignedAgents(result);
                
                resultBox.innerHTML = `
                    <div style="color: var(--success); margin-bottom: 0.5rem; font-weight: bold;">
                        ✓ Data successfully routed by MCP!
                    </div>
                    <div><strong>Received by Agents:</strong></div>
                    <div style="margin-top: 0.5rem;">${agentsList}</div>
                    <div style="margin-top: 1rem; font-size: 0.8rem; color: var(--text-muted);">
                        Job ID: ${result.job_id}
                    </div>
                `;
                document.getElementById('check-job-id').value = result.job_id || '';
                
                // Automatically poll for real agent results
                pollJobResult(result.job_id);
            } else {
                resultBox.innerHTML = `<span style="color:red">${result.detail || 'Routing failed'}</span>`;
            }
        } catch (err) {
            resultBox.innerHTML = '<span style="color:red">Error communicating with MCP server.</span>';
        }
    });

    document.getElementById('fetch-api-btn').addEventListener('click', async () => {
        const apiUrl = document.getElementById('api-url-input').value;
        const dataType = document.getElementById('api-data-type-input').value || 'application/json';
        const loginId = document.getElementById('api-login-id') ? document.getElementById('api-login-id').value : '';
        const password = document.getElementById('api-password') ? document.getElementById('api-password').value : '';
        if (!apiUrl) {
            alert("Please enter an API URL.");
            return;
        }

        const resultBox = document.getElementById('routing-result-box');
        const emittedDisplay = document.getElementById('emitted-data-display');
        
        emittedDisplay.innerHTML = `<span style="color:var(--primary)">Fetching Data from API...</span>\n<strong>URL:</strong> ${apiUrl}\n<strong>Data Type:</strong> ${dataType}`;
        resultBox.innerHTML = '<span class="placeholder">MCP is fetching and routing data...</span>';

        const payload = {
            data_type: dataType,
            requirements: [],
            api_url: apiUrl,
            username: loginId,
            password: password
        };

        try {
            const res = await fetch('/api/submit_fetch', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const result = await res.json();
            
            if (res.ok) {
                const agentsList = formatAssignedAgents(result);
                
                resultBox.innerHTML = `
                    <div style="color: var(--success); margin-bottom: 0.5rem; font-weight: bold;">
                        ✓ Data successfully fetched and routed by MCP!
                    </div>
                    <div><strong>Received by Agents:</strong></div>
                    <div style="margin-top: 0.5rem;">${agentsList}</div>
                    <div style="margin-top: 1rem; font-size: 0.8rem; color: var(--text-muted);">
                        Job ID: ${result.job_id}
                    </div>
                `;
                document.getElementById('check-job-id').value = result.job_id || '';
                
                pollJobResult(result.job_id);
            } else {
                resultBox.innerHTML = `<span style="color:red">${result.detail || 'Routing failed'}</span>`;
            }
        } catch (err) {
            resultBox.innerHTML = '<span style="color:red">Error communicating with MCP server.</span>';
        }
    });

    document.getElementById('submit-custom-json-btn').addEventListener('click', async () => {
        const jsonText = document.getElementById('custom-json-input').value;
        const fileInput = document.getElementById('custom-image-input');
        
        let parsedPayload;
        try {
            parsedPayload = JSON.parse(jsonText || '{}');
        } catch (e) {
            alert("Invalid JSON format.");
            return;
        }

        const resultBox = document.getElementById('routing-result-box');
        const emittedDisplay = document.getElementById('emitted-data-display');

        const doSubmit = async (finalPayload) => {
            emittedDisplay.innerHTML = `<span style="color:var(--primary)">Submitting Custom Data...</span>\n<strong>Payload:</strong>\n${JSON.stringify(finalPayload, null, 2).substring(0, 500)}...`;
            resultBox.innerHTML = '<span class="placeholder">MCP is routing data...</span>';

            const payload = {
                data_type: "application/json",
                requirements: [],
                payload: finalPayload
            };

            try {
                const res = await fetch('/api/submit', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                const result = await res.json();
                
                if (res.ok) {
                    const agentsList = formatAssignedAgents(result);
                    
                    resultBox.innerHTML = `
                        <div style="color: var(--success); margin-bottom: 0.5rem; font-weight: bold;">
                            ✓ Data successfully routed by MCP!
                        </div>
                        <div><strong>Received by Agents:</strong></div>
                        <div style="margin-top: 0.5rem;">${agentsList}</div>
                        <div style="margin-top: 1rem; font-size: 0.8rem; color: var(--text-muted);">
                            Job ID: ${result.job_id}
                        </div>
                    `;
                    document.getElementById('check-job-id').value = result.job_id || '';
                    pollJobResult(result.job_id);
                } else {
                    resultBox.innerHTML = `<span style="color:red">${result.detail || 'Routing failed'}</span>`;
                }
            } catch (err) {
                resultBox.innerHTML = '<span style="color:red">Error communicating with MCP server.</span>';
            }
        };

        if (fileInput.files.length > 0) {
            const file = fileInput.files[0];
            const reader = new FileReader();
            reader.onload = async (e) => {
                parsedPayload.image_base64 = e.target.result.split(',')[1];
                parsedPayload.image_name = file.name;
                await doSubmit(parsedPayload);
            };
            reader.readAsDataURL(file);
        } else {
            await doSubmit(parsedPayload);
        }
    });

    async function pollJobResult(jobId) {
        const resultBox = document.getElementById('job-result-box');
        resultBox.innerHTML = '<span style="color:var(--primary)">Processing data through agents...</span>';
        
        let attempts = 0;
        const interval = setInterval(async () => {
            attempts++;
            try {
                const res = await fetch(`/api/jobs/${jobId}`);
                const job = await res.json();
                
                if (job.status === 'completed' || job.status === 'failed') {
                    clearInterval(interval);
                    resultBox.innerHTML = JSON.stringify(job.results, null, 2);
                } else if (attempts > 15) {
                    clearInterval(interval);
                    resultBox.innerHTML = '<span style="color:red">Timed out waiting for agents.</span>';
                }
            } catch (err) {
                clearInterval(interval);
                resultBox.innerHTML = '<span style="color:red">Error fetching job status.</span>';
            }
        }, 500);
    }

    document.getElementById('check-job-btn').addEventListener('click', async () => {
        const id = document.getElementById('check-job-id').value;
        if (!id) return;
        
        try {
            const res = await fetch(`/api/jobs/${id}`);
            const result = await res.json();
            document.getElementById('job-result-box').innerHTML = JSON.stringify(result.results || result, null, 2);
        } catch (err) {
            document.getElementById('job-result-box').innerHTML = '<span style="color:red">Job not found or error.</span>';
        }
    });

    let currentPollerId = null;

    document.getElementById('start-poll-btn').addEventListener('click', async () => {
        const apiUrl = document.getElementById('poll-url').value;
        const loginId = document.getElementById('poll-login-id').value;
        const password = document.getElementById('poll-password').value;
        const interval = document.getElementById('poll-interval').value;
        
        if (!apiUrl) {
            alert("Please provide an API URL.");
            return;
        }

        try {
            const res = await fetch('/api/polling/start', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    api_url: apiUrl,
                    login_id: loginId || "",
                    password: password || "",
                    interval_seconds: parseInt(interval) || 10,
                    requirements: []
                })
            });
            const result = await res.json();
            if (res.ok) {
                currentPollerId = result.poller_id;
                document.getElementById('start-poll-btn').style.display = 'none';
                document.getElementById('stop-poll-btn').style.display = 'block';
                document.getElementById('emitted-data-display').innerHTML = `<span style="color:var(--primary)">Polling started! MCP is checking ${apiUrl} every ${interval}s...</span>`;
            } else {
                alert("Failed to start polling: " + (result.detail || "Error"));
            }
        } catch (err) {
            alert("Error starting polling");
        }
    });

    document.getElementById('stop-poll-btn').addEventListener('click', async () => {
        if (!currentPollerId) return;
        try {
            const res = await fetch(`/api/polling/stop/${currentPollerId}`, { method: 'POST' });
            if (res.ok) {
                currentPollerId = null;
                document.getElementById('start-poll-btn').style.display = 'block';
                document.getElementById('stop-poll-btn').style.display = 'none';
                document.getElementById('emitted-data-display').innerHTML = `<span style="color:red">Polling stopped.</span>`;
            }
        } catch (err) {
            alert("Error stopping polling");
        }
    });

    // Init
    loadAgents();
});

// Global Variables
let currentData = null;
let lastQuestion = '';
let chatbotHistory = [];

// Configuration state
let config = {
    apiKey: '',
    runLocal: false,
    localUrl: '',
    localModel: ''
};

// DOM Elements
const chatHistory = document.getElementById('chatHistory');
const userInput = document.getElementById('userInput');
const sparqlCode = document.getElementById('sparqlCode');
const runSparqlBtn = document.getElementById('runSparqlBtn');
const loadingOverlay = document.getElementById('loadingOverlay');
const loadingText = document.getElementById('loadingText');

// Fill input from suggestions
function fillInput(text) {
    userInput.value = text;
    userInput.focus();
}

// Handle Enter key for main NLP query input
function handleKeyPress(event) {
    if (event.key === 'Enter') {
        processQuery();
    }
}

// Add message to main chat UI
function appendMessage(sender, text, extraClass = '') {
    const msgDiv = document.createElement('div');
    msgDiv.className = `message ${sender}-msg`;
    
    const avatar = document.createElement('div');
    avatar.className = 'msg-avatar';
    avatar.innerText = sender === 'user' ? '👤' : '🤖';
    
    const content = document.createElement('div');
    content.className = `msg-content ${extraClass}`;
    content.innerHTML = text;
    
    msgDiv.appendChild(avatar);
    msgDiv.appendChild(content);
    
    chatHistory.appendChild(msgDiv);
    chatHistory.scrollTop = chatHistory.scrollHeight;
    return content; // Return content element for streaming
}

// Streaming typewriter effect for summary
function streamText(element, text, speed = 15) {
    return new Promise((resolve) => {
        let i = 0;
        element.innerHTML = '';
        const interval = setInterval(() => {
            if (i < text.length) {
                if (text[i] === '<') {
                    const closeIdx = text.indexOf('>', i);
                    if (closeIdx !== -1) {
                        element.innerHTML += text.substring(i, closeIdx + 1);
                        i = closeIdx + 1;
                    } else {
                        element.innerHTML += text[i];
                        i++;
                    }
                } else {
                    element.innerHTML += text[i];
                    i++;
                }
                chatHistory.scrollTop = chatHistory.scrollHeight;
            } else {
                clearInterval(interval);
                resolve();
            }
        }, speed);
    });
}

// Show typing indicator
function showTypingIndicator() {
    const msgDiv = document.createElement('div');
    msgDiv.className = 'message system-msg';
    msgDiv.id = 'typingIndicator';
    
    const avatar = document.createElement('div');
    avatar.className = 'msg-avatar';
    avatar.innerText = '🤖';
    
    const content = document.createElement('div');
    content.className = 'msg-content';
    content.innerHTML = '<div class="typing-indicator"><span></span><span></span><span></span></div>';
    
    msgDiv.appendChild(avatar);
    msgDiv.appendChild(content);
    chatHistory.appendChild(msgDiv);
    chatHistory.scrollTop = chatHistory.scrollHeight;
}

function removeTypingIndicator() {
    const indicator = document.getElementById('typingIndicator');
    if (indicator) indicator.remove();
}

// Show/Hide Loading
function showLoading(text) {
    loadingText.innerText = text;
    loadingOverlay.classList.remove('hidden');
}

// Hide Loading
function hideLoading() {
    loadingOverlay.classList.add('hidden');
}

// Simple markdown-to-HTML formatter
function formatSummary(text) {
    let html = text
        // Bold
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        // List items
        .replace(/^[-*]\s+(.+)$/gm, '<li>$1</li>')
        .replace(/^(\d+)\.\s+(.+)$/gm, '<li>$2</li>')
        // Line breaks
        .replace(/\n/g, '<br>');
    
    // Wrap list items if present
    if (html.includes('<li>')) {
        // Simple heuristic to wrap consecutive lists
        html = html.replace(/((?:<li>.*?<\/li><br>?)+)/g, '<ul>$1</ul>');
        html = html.replace(/<ul><br>/g, '<ul>');
        html = html.replace(/<br><\/ul>/g, '</ul>');
    }
    
    return html;
}

// Step 1: Process NLP Query to SPARQL
async function processQuery() {
    const question = userInput.value.trim();
    if (!question) return;
    
    lastQuestion = question;
    appendMessage('user', question);
    userInput.value = '';
    sparqlCode.value = '';
    runSparqlBtn.disabled = true;
    showLoading('AI is generating SPARQL query...');
    
    try {
        const response = await fetch('/api/ask', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ question })
        });
        
        const data = await response.json();
        hideLoading();
        
        if (data.success) {
            appendMessage('system', '✅ SPARQL query generated. Review it below and click <strong>Run Query</strong> to fetch results.');
            sparqlCode.value = data.sparql;
            runSparqlBtn.disabled = false;
        } else {
            appendMessage('system', `<span class="status-badge error">Error</span> ${data.error}`);
        }
    } catch (error) {
        hideLoading();
        appendMessage('system', '<span class="status-badge error">Error</span> Connection error. Make sure the backend is running.');
        console.error(error);
    }
}

// Step 2: Execute SPARQL Query
async function executeSparql() {
    const query = sparqlCode.value.trim();
    if (!query) return;
    
    showLoading('Fetching data from NFDI4Culture...');
    
    try {
        const response = await fetch('/api/execute', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query, question: lastQuestion })
        });
        
        const data = await response.json();
        hideLoading();
        
        if (data.success) {
            currentData = data;
            renderTable(data.columns, data.results);
            
            const count = data.results.length;
            if (count === 0 && data.diagnostic) {
                const diag = data.diagnostic;
                let diagHtml = `
                    <div style="margin-top: 10px; padding: 12px; background-color: var(--bg-panel); border-left: 4px solid var(--accent); border-radius: 6px; font-size: 0.82rem; line-height: 1.6; border: 1px solid var(--border); border-left-width: 4px;">
                        <div style="font-weight: 600; margin-bottom: 8px; display: flex; align-items: center; gap: 6px; color: #a78bfa;">
                            🔍 CKG Diagnostic Engine Analysis
                        </div>
                        <div style="margin-bottom: 8px; color: var(--text-main);">
                            ${formatSummary(diag.message)}
                        </div>
                        <div style="margin-top: 8px; padding-top: 8px; border-top: 1px solid var(--border); color: #60a5fa;">
                            💡 <strong>Suggested Workaround / Action:</strong><br>
                            ${formatSummary(diag.recommendation)}
                        </div>
                    </div>
                `;
                appendMessage('system', `<span class="status-badge error" style="background:rgba(245,158,11,0.2);color:#f59e0b">0 results</span> Query returned no results. ${diagHtml}`);
                // Hide table assistant chatbot since there are no results
                document.getElementById('tableChatbot').classList.add('hidden');
            } else {
                appendMessage('system', `<span class="status-badge success">${count} results</span> Data retrieved successfully. Generating summary...`);
                
                // Show chatbot container
                document.getElementById('tableChatbot').classList.remove('hidden');
                chatbotHistory = [];
                document.getElementById('chatWindowBody').innerHTML = `<div class="chat-message system">
                    Welcome to the <strong>Table Assistant</strong>! I can answer questions about the active table or pull details from Wikidata. Ask me anything about the results.
                </div>`;
                
                // Show typing indicator while waiting for summary
                showTypingIndicator();
                
                try {
                    const sumRes = await fetch('/api/summarize', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            question: lastQuestion,
                            sparql: query,
                            results: data
                        })
                    });
                    const sumData = await sumRes.json();
                    removeTypingIndicator();
                    
                    if (sumData.success && sumData.summary) {
                        const formattedHtml = formatSummary(sumData.summary);
                        const contentEl = appendMessage('system', '', 'summary-text');
                        await streamText(contentEl, formattedHtml);
                    }
                } catch (error) {
                    removeTypingIndicator();
                    console.error('Summary error:', error);
                }
            }
            
        } else {
            appendMessage('system', `<span class="status-badge error">Error</span> ${data.error}`);
        }
    } catch (error) {
        hideLoading();
        appendMessage('system', '<span class="status-badge error">Error</span> Failed to execute query.');
        console.error(error);
    }
}

// Render Tabular Data
function renderTable(columns, results) {
    document.getElementById('tableEmptyState').style.display = 'none';
    const thead = document.getElementById('dataTableHead');
    const tbody = document.getElementById('dataTableBody');
    
    thead.innerHTML = '';
    tbody.innerHTML = '';
    
    if (results.length === 0) {
        document.getElementById('tableEmptyState').style.display = 'flex';
        document.getElementById('tableEmptyState').innerHTML = '<span class="empty-state-icon">📭</span><span>No results found.</span>';
        return;
    }
    
    // Headers
    const headerRow = document.createElement('tr');
    columns.forEach(col => {
        const th = document.createElement('th');
        th.innerText = col;
        headerRow.appendChild(th);
    });
    thead.appendChild(headerRow);
    
    // Rows
    results.forEach(row => {
        const tr = document.createElement('tr');
        columns.forEach(col => {
            const td = document.createElement('td');
            const val = row[col];
            if (val && val.startsWith('http')) {
                const shortName = decodeURIComponent(val.substring(val.lastIndexOf('/') + 1) || val);
                td.innerHTML = `<a href="${val}" target="_blank" style="color:var(--primary);text-decoration:none">${shortName}</a>`;
            } else {
                td.innerText = val || '-';
            }
            tr.appendChild(td);
        });
        tbody.appendChild(tr);
    });
}

// ====================== LLM CONFIGURATION MODAL ======================
function openSettingsModal() {
    document.getElementById('settingsModal').classList.remove('hidden');
    document.getElementById('apiKeyInput').value = config.apiKey || '';
    document.getElementById('runLocalToggle').checked = config.runLocal || false;
    document.getElementById('localUrlInput').value = config.localUrl || '';
    document.getElementById('localModelInput').value = config.localModel || '';
    toggleLocalInputs();
}

function closeSettingsModal() {
    document.getElementById('settingsModal').classList.add('hidden');
}

function toggleLocalInputs() {
    const isLocal = document.getElementById('runLocalToggle').checked;
    const apiGroup = document.getElementById('apiGroup');
    const localGroup = document.getElementById('localGroup');
    if (isLocal) {
        apiGroup.classList.add('hidden');
        localGroup.classList.remove('hidden');
    } else {
        apiGroup.classList.remove('hidden');
        localGroup.classList.add('hidden');
    }
}

async function saveSettings() {
    config.apiKey = document.getElementById('apiKeyInput').value.trim();
    config.runLocal = document.getElementById('runLocalToggle').checked;
    config.localUrl = document.getElementById('localUrlInput').value.trim();
    config.localModel = document.getElementById('localModelInput').value.trim();
    
    localStorage.setItem('ckg_explorer_config', JSON.stringify(config));
    
    try {
        const response = await fetch('/api/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                api_key: config.apiKey,
                run_local: config.runLocal,
                local_url: config.localUrl,
                local_model: config.localModel
            })
        });
        const res = await response.json();
        if (res.success) {
            console.log("LLM Config synchronized successfully:", res.config);
        }
    } catch (e) {
        console.error("Failed to sync settings with backend:", e);
    }
    closeSettingsModal();
}

async function loadSavedConfig() {
    const saved = localStorage.getItem('ckg_explorer_config');
    if (saved) {
        try {
            config = JSON.parse(saved);
            await fetch('/api/config', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    api_key: config.apiKey,
                    run_local: config.runLocal,
                    local_url: config.localUrl,
                    local_model: config.localModel
                })
            });
        } catch (e) {
            console.error("Error loading config:", e);
        }
    }
}

// ====================== FLOATING CHATBOT FOR TABLE RESULTS ======================
function toggleChatbot(show) {
    const badge = document.getElementById('chatbotBadge');
    const win = document.getElementById('chatWindow');
    if (show) {
        badge.classList.add('hidden');
        win.classList.remove('hidden');
        document.getElementById('chatWindowInput').focus();
    } else {
        badge.classList.remove('hidden');
        win.classList.add('hidden');
    }
}

function handleChatWindowKeyPress(event) {
    if (event.key === 'Enter') {
        sendChatMessage();
    }
}

function renderChatbotMessage(sender, text, wikidataCard = null) {
    const body = document.getElementById('chatWindowBody');
    const msgDiv = document.createElement('div');
    msgDiv.className = `chat-message ${sender}`;
    msgDiv.innerHTML = formatSummary(text);
    body.appendChild(msgDiv);
    
    if (wikidataCard) {
        const cardDiv = document.createElement('div');
        cardDiv.className = 'wikidata-card';
        
        let imgHtml = '';
        if (wikidataCard.image) {
            imgHtml = `<img src="${wikidataCard.image}" class="wikidata-card-img" alt="${wikidataCard.label}">`;
        } else {
            imgHtml = `<div class="wikidata-card-img" style="display:flex;align-items:center;justify-content:center;font-size:1.5rem;background:var(--bg-input)">👤</div>`;
        }
        
        const birth = wikidataCard.birthDate || 'Unknown';
        const death = wikidataCard.deathDate || 'Present';
        const wikiLink = wikidataCard.wikipedia_url ? `<a href="${wikidataCard.wikipedia_url}" target="_blank" class="wikidata-card-link">📖 Wikipedia Article</a>` : '';
        const gndLink = wikidataCard.gnd_id ? `<a href="https://d-nb.info/gnd/${wikidataCard.gnd_id}" target="_blank" class="wikidata-card-link" style="background:#2b6cb0;margin-top:5px">🎼 GND ID: ${wikidataCard.gnd_id}</a>` : '';
        const mimoLink = wikidataCard.mimo_id ? `<a href="https://vocabulary.mimo-international.com/de/instrument/${wikidataCard.mimo_id}" target="_blank" class="wikidata-card-link" style="background:#2c5282;margin-top:5px">🎹 MIMO ID: ${wikidataCard.mimo_id}</a>` : '';
        
        cardDiv.innerHTML = `
            ${imgHtml}
            <div class="wikidata-card-content">
                <div class="wikidata-card-title">${wikidataCard.label}</div>
                <div class="wikidata-card-dates">📅 ${birth} &ndash; ${death}</div>
                <div class="wikidata-card-desc">${wikidataCard.description || 'No description available.'}</div>
                ${wikiLink}
                ${gndLink}
                ${mimoLink}
            </div>
        `;
        body.appendChild(cardDiv);
    }
    
    body.scrollTop = body.scrollHeight;
}

async function sendChatMessage() {
    const input = document.getElementById('chatWindowInput');
    const question = input.value.trim();
    if (!question) return;
    
    input.value = '';
    renderChatbotMessage('user', question);
    
    const body = document.getElementById('chatWindowBody');
    const typingDiv = document.createElement('div');
    typingDiv.className = 'chat-message assistant';
    typingDiv.id = 'chatTypingIndicator';
    typingDiv.innerHTML = '<div class="typing-indicator"><span></span><span></span><span></span></div>';
    body.appendChild(typingDiv);
    body.scrollTop = body.scrollHeight;
    
    chatbotHistory.push({ sender: 'user', text: question });
    
    try {
        const response = await fetch('/api/chat_results', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                question: question,
                results: currentData ? currentData.results : [],
                history: chatbotHistory
            })
        });
        
        const data = await response.json();
        
        const indicator = document.getElementById('chatTypingIndicator');
        if (indicator) indicator.remove();
        
        if (data.success) {
            renderChatbotMessage('assistant', data.text, data.wikidata_card);
            chatbotHistory.push({ sender: 'assistant', text: data.text });
        } else {
            renderChatbotMessage('assistant', 'Sorry, I encountered an error: ' + data.error);
        }
    } catch (e) {
        const indicator = document.getElementById('chatTypingIndicator');
        if (indicator) indicator.remove();
        renderChatbotMessage('assistant', 'Connection error. Please try again.');
        console.error(e);
    }
}

// Initial initialization
document.addEventListener('DOMContentLoaded', () => {
    loadSavedConfig();
});

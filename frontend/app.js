/* ============================================
   JARVIS AI — Frontend Application Logic v2
   ============================================ */

// --------------- State ---------------
let state = 'idle';
let ws = null;
let mediaRecorder = null;
let audioChunks = [];
let isRecording = false;
let reconnectAttempts = 0;
let currentSessionId = 'session_' + Date.now();
const MAX_RECONNECT_DELAY = 30000;

// --------------- DOM Cache ---------------
const $ = (sel) => document.querySelector(sel);
const orb = $('#jarvis-orb');
const statusText = $('#status-text');
const chatMessages = $('#chat-messages');
const messageInput = $('#message-input');
const sendBtn = $('#send-btn');
const micBtn = $('#mic-btn');
const ttsAudio = $('#tts-audio');
const settingsBtn = $('#settings-btn');
const settingsPanel = $('#settings-panel');
const settingsClose = $('#settings-close');
const modelBadge = $('#model-badge');

// --------------- WebSocket URL (dynamic — works locally and remotely) ---------------
function getWsUrl() {
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const host = window.location.host || 'localhost:8000';
  return `${proto}//${host}/ws?session_id=${currentSessionId}`;
}

// --------------- WebSocket ---------------
function connectWebSocket() {
  try {
    ws = new WebSocket(getWsUrl());
  } catch (err) {
    handleConnectionError();
    return;
  }

  ws.onopen = () => {
    reconnectAttempts = 0;
    updateStatus('Connected');
    setState('idle');
    loadServerConfig();
  };

  ws.onmessage = (event) => {
    try {
      handleServerMessage(JSON.parse(event.data));
    } catch (err) {
      console.error('Failed to parse server message:', err);
    }
  };

  ws.onerror = () => console.error('WebSocket error');

  ws.onclose = () => {
    ws = null;
    handleConnectionError();
  };
}

function handleConnectionError() {
  reconnectAttempts++;
  const delay = Math.min(1000 * Math.pow(2, reconnectAttempts - 1), MAX_RECONNECT_DELAY);
  updateStatus(`Reconnecting in ${Math.round(delay / 1000)}s…`);
  setState('idle');
  setTimeout(connectWebSocket, delay);
}

// --------------- Load server config to show provider/model ---------------
async function loadServerConfig() {
  try {
    const res = await fetch('/api/config');
    if (!res.ok) return;
    const cfg = await res.json();
    if (modelBadge) {
      modelBadge.textContent = `${cfg.provider} · ${cfg.model}`;
      modelBadge.title = `Provider: ${cfg.provider}\nModel: ${cfg.model}\nSTT: ${cfg.stt_provider}`;
    }
  } catch (_) {}
}

// --------------- Markdown renderer (no external deps) ---------------
function renderMarkdown(text) {
  if (!text) return '';
  // Escape HTML first to prevent XSS
  let safe = text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');

  // Code blocks
  safe = safe.replace(/```[\w]*\n?([\s\S]*?)```/g, '<pre><code>$1</code></pre>');
  // Inline code
  safe = safe.replace(/`([^`\n]+)`/g, '<code>$1</code>');
  // Bold
  safe = safe.replace(/\*\*([^*\n]+)\*\*/g, '<strong>$1</strong>');
  // Italic
  safe = safe.replace(/\*([^*\n]+)\*/g, '<em>$1</em>');
  // H3
  safe = safe.replace(/^### (.+)$/gm, '<h3>$1</h3>');
  // H2
  safe = safe.replace(/^## (.+)$/gm, '<h2>$1</h2>');
  // H1
  safe = safe.replace(/^# (.+)$/gm, '<h1>$1</h1>');
  // Unordered list items
  safe = safe.replace(/^[-*] (.+)$/gm, '<li>$1</li>');
  safe = safe.replace(/(<li>[\s\S]*?<\/li>)(\s*<li>)/g, '$1$2');
  safe = safe.replace(/(<li>[\s\S]*?<\/li>)/g, '<ul>$1</ul>');
  // Numbered list
  safe = safe.replace(/^\d+\. (.+)$/gm, '<li>$1</li>');
  // Horizontal rule
  safe = safe.replace(/^---$/gm, '<hr>');
  // Line breaks
  safe = safe.replace(/\n\n/g, '<br><br>');
  safe = safe.replace(/\n/g, '<br>');
  return safe;
}

// --------------- Server Message Handler ---------------
function handleServerMessage(data) {
  switch (data.type) {
    case 'transcription':
      addMessage('user', `🎤 ${data.content}`, false);
      break;

    case 'response':
      removeTypingIndicator();
      addMessage('jarvis', data.content, true); // render markdown
      setState('speaking');
      break;

    case 'audio':
      playAudio(data.audio);
      break;

    case 'action':
      removeTypingIndicator();
      addMessage('jarvis', `🔧 ${data.description}`, false);
      break;

    case 'screenshot':
      removeTypingIndicator();
      addScreenshot(data.image);
      break;

    case 'status':
      updateStatus(data.message);
      break;

    case 'thinking':
      setState('thinking');
      showTypingIndicator();
      break;

    case 'done':
      removeTypingIndicator();
      setState('idle');
      break;

    case 'error':
      removeTypingIndicator();
      addMessage('jarvis', `❌ ${data.message}`, false);
      setState('idle');
      break;

    case 'ping':
      break; // keepalive, no action needed

    default:
      console.warn('Unknown message type:', data.type);
  }
}

// --------------- Send Message ---------------
function sendMessage(text) {
  const trimmed = text.trim();
  if (!trimmed) return;
  if (!ws || ws.readyState !== WebSocket.OPEN) {
    updateStatus('Not connected. Reconnecting…');
    connectWebSocket();
    return;
  }

  addMessage('user', trimmed, false);
  messageInput.value = '';
  autoResize(messageInput);

  try {
    ws.send(JSON.stringify({ type: 'text', content: trimmed }));
    setState('thinking');
    showTypingIndicator();
  } catch (err) {
    addMessage('jarvis', '❌ Failed to send message.', false);
    console.error('Send error:', err);
  }
}

// --------------- Voice Recording ---------------
async function toggleRecording() {
  if (isRecording) stopRecording();
  else await startRecording();
}

async function startRecording() {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    mediaRecorder = new MediaRecorder(stream, { mimeType: getSupportedMimeType() });
    audioChunks = [];

    mediaRecorder.ondataavailable = (e) => {
      if (e.data.size > 0) audioChunks.push(e.data);
    };

    mediaRecorder.onstop = () => {
      const audioBlob = new Blob(audioChunks, { type: mediaRecorder.mimeType || 'audio/webm' });
      sendAudio(audioBlob);
      stream.getTracks().forEach((t) => t.stop());
    };

    mediaRecorder.start();
    isRecording = true;
    micBtn.classList.add('recording');
    setState('listening');
  } catch (err) {
    addMessage('jarvis', '❌ Microphone access denied.', false);
    console.error('Mic error:', err);
  }
}

function getSupportedMimeType() {
  const types = ['audio/webm;codecs=opus', 'audio/webm', 'audio/ogg;codecs=opus', 'audio/mp4'];
  return types.find((t) => MediaRecorder.isTypeSupported(t)) || '';
}

function stopRecording() {
  if (mediaRecorder && mediaRecorder.state !== 'inactive') mediaRecorder.stop();
  isRecording = false;
  micBtn.classList.remove('recording');
  setState('thinking');
  showTypingIndicator();
}

async function sendAudio(blob) {
  if (!ws || ws.readyState !== WebSocket.OPEN) {
    addMessage('jarvis', '❌ Not connected.', false);
    return;
  }
  const reader = new FileReader();
  reader.onload = () => {
    try {
      ws.send(JSON.stringify({ type: 'audio', audio: reader.result.split(',')[1] }));
    } catch (err) {
      addMessage('jarvis', '❌ Failed to send audio.', false);
    }
  };
  reader.onerror = () => addMessage('jarvis', '❌ Failed to process audio.', false);
  reader.readAsDataURL(blob);
}

// --------------- Audio Playback ---------------
function playAudio(base64Audio) {
  try {
    ttsAudio.src = 'data:audio/mp3;base64,' + base64Audio;
    const p = ttsAudio.play();
    if (p) p.catch(() => setState('idle'));
    ttsAudio.onended = () => setState('idle');
  } catch (err) {
    setState('idle');
  }
}

// --------------- UI: Messages ---------------
function formatTimestamp() {
  return new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function addMessage(sender, text, useMarkdown = false) {
  removeTypingIndicator();

  const bubble = document.createElement('div');
  bubble.classList.add('message', sender);

  const content = document.createElement('div');
  content.classList.add('message-content');

  if (useMarkdown && sender === 'jarvis') {
    content.innerHTML = renderMarkdown(text);
  } else {
    content.textContent = text;
  }

  // Copy on click for Jarvis messages
  if (sender === 'jarvis') {
    bubble.title = 'Click to copy';
    bubble.style.cursor = 'pointer';
    bubble.addEventListener('click', () => {
      navigator.clipboard.writeText(text).then(() => {
        const orig = content.style.opacity;
        content.style.opacity = '0.5';
        setTimeout(() => (content.style.opacity = orig), 300);
      });
    });
  }

  const time = document.createElement('span');
  time.classList.add('message-time');
  time.textContent = formatTimestamp();

  bubble.appendChild(content);
  bubble.appendChild(time);
  chatMessages.appendChild(bubble);
  scrollToBottom();
}

function addScreenshot(base64Image) {
  removeTypingIndicator();

  const bubble = document.createElement('div');
  bubble.classList.add('message', 'jarvis');

  const label = document.createElement('div');
  label.classList.add('message-content');
  label.textContent = '📸 Screenshot:';

  const img = document.createElement('img');
  img.classList.add('screenshot-thumb');
  img.src = 'data:image/jpeg;base64,' + base64Image;
  img.alt = 'Screenshot';
  img.loading = 'lazy';
  img.addEventListener('click', () => openScreenshotOverlay(img.src));

  const time = document.createElement('span');
  time.classList.add('message-time');
  time.textContent = formatTimestamp();

  bubble.appendChild(label);
  bubble.appendChild(img);
  bubble.appendChild(time);
  chatMessages.appendChild(bubble);
  scrollToBottom();
}

function openScreenshotOverlay(src) {
  const overlay = document.createElement('div');
  overlay.classList.add('screenshot-overlay');

  const closeBtn = document.createElement('button');
  closeBtn.textContent = '✕';
  closeBtn.classList.add('overlay-close');
  closeBtn.addEventListener('click', (e) => { e.stopPropagation(); overlay.remove(); });

  const img = document.createElement('img');
  img.src = src;
  img.alt = 'Screenshot';

  overlay.appendChild(closeBtn);
  overlay.appendChild(img);
  overlay.addEventListener('click', () => overlay.remove());

  const escHandler = (e) => {
    if (e.key === 'Escape') { overlay.remove(); document.removeEventListener('keydown', escHandler); }
  };
  document.addEventListener('keydown', escHandler);
  document.body.appendChild(overlay);
}

// --------------- UI: Typing Indicator ---------------
function showTypingIndicator() {
  if (chatMessages.querySelector('.typing-indicator')) return;
  const indicator = document.createElement('div');
  indicator.classList.add('typing-indicator');
  indicator.innerHTML = '<span></span><span></span><span></span>';
  chatMessages.appendChild(indicator);
  scrollToBottom();
}

function removeTypingIndicator() {
  chatMessages.querySelector('.typing-indicator')?.remove();
}

// --------------- UI: State & Status ---------------
function setState(newState) {
  state = newState;
  orb.classList.remove('listening', 'thinking', 'speaking');
  if (newState !== 'idle') orb.classList.add(newState);

  const labels = { idle: 'Idle', listening: 'Listening…', thinking: 'Thinking…', speaking: 'Speaking…' };
  statusText.textContent = labels[newState] || newState;
  statusText.classList.remove('listening', 'thinking', 'speaking');
  if (newState !== 'idle') statusText.classList.add(newState);
}

function updateStatus(msg) {
  statusText.textContent = msg;
}

// --------------- UI: Auto-resize textarea ---------------
function autoResize(el) {
  el.style.height = 'auto';
  el.style.height = Math.min(el.scrollHeight, 120) + 'px';
}

// --------------- UI: Scroll ---------------
function scrollToBottom() {
  requestAnimationFrame(() => {
    chatMessages.scrollTop = chatMessages.scrollHeight;
  });
}

// --------------- Settings Panel ---------------
function openSettings() {
  if (settingsPanel) settingsPanel.classList.add('open');
}
function closeSettings() {
  if (settingsPanel) settingsPanel.classList.remove('open');
}

async function loadCostSummary() {
  try {
    const res = await fetch('/api/costs');
    if (!res.ok) return;
    const data = await res.json();
    const el = $('#cost-summary');
    if (!el) return;
    el.textContent = data.this_month_usd !== undefined
      ? `This month: $${data.this_month_usd.toFixed(4)}`
      : 'No cost data';
  } catch (_) {}
}

// --------------- Clear conversation ---------------
function clearConversation() {
  if (!ws || ws.readyState !== WebSocket.OPEN) return;
  ws.send(JSON.stringify({ type: 'clear' }));
  chatMessages.innerHTML = '';
  addMessage('jarvis', 'Conversation cleared.', false);
}

// --------------- Event Listeners ---------------
function initEventListeners() {
  sendBtn.addEventListener('click', () => sendMessage(messageInput.value));

  messageInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage(messageInput.value);
    }
  });

  messageInput.addEventListener('input', () => autoResize(messageInput));

  micBtn.addEventListener('click', toggleRecording);

  settingsBtn?.addEventListener('click', () => { openSettings(); loadCostSummary(); });
  settingsClose?.addEventListener('click', closeSettings);

  $('#clear-btn')?.addEventListener('click', clearConversation);

  // Single unified keydown handler
  document.addEventListener('keydown', (e) => {
    const activeEl = document.activeElement;
    const inInput = activeEl === messageInput;
    const overlayOpen = !!document.querySelector('.screenshot-overlay');
    const panelOpen = settingsPanel?.classList.contains('open');

    // Escape: close overlay or settings
    if (e.key === 'Escape') {
      if (overlayOpen) return; // overlay handles its own escape
      if (panelOpen) { closeSettings(); return; }
      if (isRecording) { stopRecording(); return; }
    }

    // Space: toggle voice when not in input
    if (e.code === 'Space' && !inInput && !overlayOpen && !panelOpen) {
      e.preventDefault();
      toggleRecording();
      return;
    }

    // Auto-focus input when typing printable chars
    if (!inInput && !e.ctrlKey && !e.metaKey && !e.altKey && e.key.length === 1 && !overlayOpen && !panelOpen) {
      messageInput.focus();
    }
  });
}

// --------------- Init ---------------
document.addEventListener('DOMContentLoaded', () => {
  initEventListeners();
  updateStatus('Connecting…');
  connectWebSocket();

  setTimeout(() => {
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      addMessage('jarvis', "I'm Jarvis. Start the backend server and I'll connect automatically.", false);
    }
  }, 2500);
});

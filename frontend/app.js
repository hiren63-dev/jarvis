/* ============================================
   JARVIS AI — Frontend Application Logic
   ============================================ */

// --------------- State ---------------
let state = 'idle'; // idle | listening | thinking | speaking
let ws = null;
let mediaRecorder = null;
let audioChunks = [];
let isRecording = false;
let reconnectAttempts = 0;
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

// --------------- WebSocket ---------------
function connectWebSocket() {
  try {
    ws = new WebSocket('ws://localhost:8000/ws');
  } catch (err) {
    handleConnectionError();
    return;
  }

  ws.onopen = () => {
    reconnectAttempts = 0;
    updateStatus('Connected to Jarvis');
    setState('idle');
  };

  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      handleServerMessage(data);
    } catch (err) {
      console.error('Failed to parse server message:', err);
    }
  };

  ws.onerror = () => {
    console.error('WebSocket error');
  };

  ws.onclose = () => {
    ws = null;
    handleConnectionError();
  };
}

function handleConnectionError() {
  reconnectAttempts++;
  const delay = Math.min(1000 * Math.pow(2, reconnectAttempts - 1), MAX_RECONNECT_DELAY);
  const delaySec = Math.round(delay / 1000);
  updateStatus(`Disconnected. Reconnecting in ${delaySec}s...`);
  setState('idle');
  setTimeout(connectWebSocket, delay);
}

// --------------- Server Message Handler ---------------
function handleServerMessage(data) {
  switch (data.type) {
    case 'response':
      removeTypingIndicator();
      addMessage('jarvis', data.content);
      setState('speaking');
      break;

    case 'audio':
      playAudio(data.audio);
      break;

    case 'action':
      removeTypingIndicator();
      addMessage('jarvis', `🔧 ${data.description}`);
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
      addMessage('jarvis', `❌ Error: ${data.message}`);
      setState('idle');
      break;

    default:
      console.warn('Unknown message type:', data.type);
  }
}

// --------------- Send Message ---------------
function sendMessage(text) {
  const trimmed = text.trim();
  if (!trimmed) return;
  if (!ws || ws.readyState !== WebSocket.OPEN) {
    updateStatus('Not connected. Trying to reconnect...');
    connectWebSocket();
    return;
  }

  addMessage('user', trimmed);
  messageInput.value = '';

  try {
    ws.send(JSON.stringify({ type: 'text', content: trimmed }));
    setState('thinking');
    showTypingIndicator();
  } catch (err) {
    addMessage('jarvis', '❌ Failed to send message.');
    console.error('Send error:', err);
  }
}

// --------------- Voice Recording ---------------
async function toggleRecording() {
  if (isRecording) {
    stopRecording();
  } else {
    await startRecording();
  }
}

async function startRecording() {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    mediaRecorder = new MediaRecorder(stream, { mimeType: getSupportedMimeType() });
    audioChunks = [];

    mediaRecorder.ondataavailable = (e) => {
      if (e.data.size > 0) {
        audioChunks.push(e.data);
      }
    };

    mediaRecorder.onstop = () => {
      const mimeType = mediaRecorder.mimeType || 'audio/webm';
      const audioBlob = new Blob(audioChunks, { type: mimeType });
      sendAudio(audioBlob);
      stream.getTracks().forEach((t) => t.stop());
    };

    mediaRecorder.start();
    isRecording = true;
    micBtn.classList.add('recording');
    setState('listening');
  } catch (err) {
    console.error('Microphone access denied:', err);
    addMessage('jarvis', '❌ Microphone access denied. Please allow microphone permissions.');
  }
}

function getSupportedMimeType() {
  const types = ['audio/webm;codecs=opus', 'audio/webm', 'audio/ogg;codecs=opus', 'audio/mp4'];
  for (const type of types) {
    if (MediaRecorder.isTypeSupported(type)) return type;
  }
  return '';
}

function stopRecording() {
  if (mediaRecorder && mediaRecorder.state !== 'inactive') {
    mediaRecorder.stop();
  }
  isRecording = false;
  micBtn.classList.remove('recording');
  setState('thinking');
  showTypingIndicator();
}

async function sendAudio(blob) {
  if (!ws || ws.readyState !== WebSocket.OPEN) {
    addMessage('jarvis', '❌ Not connected. Cannot send audio.');
    return;
  }

  const reader = new FileReader();
  reader.onload = () => {
    try {
      const base64 = reader.result.split(',')[1];
      ws.send(JSON.stringify({ type: 'audio', audio: base64 }));
    } catch (err) {
      addMessage('jarvis', '❌ Failed to send audio.');
      console.error('Audio send error:', err);
    }
  };
  reader.onerror = () => {
    addMessage('jarvis', '❌ Failed to process audio recording.');
  };
  reader.readAsDataURL(blob);
}

// --------------- Audio Playback ---------------
function playAudio(base64Audio) {
  try {
    ttsAudio.src = 'data:audio/mp3;base64,' + base64Audio;
    const playPromise = ttsAudio.play();
    if (playPromise !== undefined) {
      playPromise.catch((err) => {
        console.error('Audio playback error:', err);
        setState('idle');
      });
    }
    ttsAudio.onended = () => setState('idle');
  } catch (err) {
    console.error('Failed to play audio:', err);
    setState('idle');
  }
}

// --------------- UI: Messages ---------------
function formatTimestamp() {
  const now = new Date();
  return now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function addMessage(sender, text) {
  removeTypingIndicator();

  const bubble = document.createElement('div');
  bubble.classList.add('message', sender);

  const content = document.createElement('span');
  content.classList.add('message-content');
  content.textContent = text;
  bubble.appendChild(content);

  const time = document.createElement('span');
  time.classList.add('message-time');
  time.textContent = formatTimestamp();
  bubble.appendChild(time);

  chatMessages.appendChild(bubble);
  scrollToBottom();
}

function addScreenshot(base64Image) {
  removeTypingIndicator();

  const bubble = document.createElement('div');
  bubble.classList.add('message', 'jarvis');

  const label = document.createElement('span');
  label.classList.add('message-content');
  label.textContent = '📸 Screenshot captured:';
  bubble.appendChild(label);

  const img = document.createElement('img');
  img.classList.add('screenshot-thumb');
  img.src = 'data:image/png;base64,' + base64Image;
  img.alt = 'Screenshot';
  img.loading = 'lazy';
  img.addEventListener('click', () => openScreenshotOverlay(img.src));
  bubble.appendChild(img);

  const time = document.createElement('span');
  time.classList.add('message-time');
  time.textContent = formatTimestamp();
  bubble.appendChild(time);

  chatMessages.appendChild(bubble);
  scrollToBottom();
}

function openScreenshotOverlay(src) {
  const overlay = document.createElement('div');
  overlay.classList.add('screenshot-overlay');

  const img = document.createElement('img');
  img.src = src;
  img.alt = 'Screenshot full view';
  overlay.appendChild(img);

  overlay.addEventListener('click', () => overlay.remove());
  document.addEventListener('keydown', function handler(e) {
    if (e.key === 'Escape') {
      overlay.remove();
      document.removeEventListener('keydown', handler);
    }
  });

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
  const indicator = chatMessages.querySelector('.typing-indicator');
  if (indicator) indicator.remove();
}

// --------------- UI: State & Status ---------------
function setState(newState) {
  state = newState;

  // Update orb
  orb.classList.remove('listening', 'thinking', 'speaking');
  if (newState !== 'idle') {
    orb.classList.add(newState);
  }

  // Update status text
  const labels = {
    idle: 'Idle',
    listening: 'Listening...',
    thinking: 'Thinking...',
    speaking: 'Speaking...',
  };

  statusText.textContent = labels[newState] || newState;
  statusText.classList.remove('listening', 'thinking', 'speaking');
  if (newState !== 'idle') {
    statusText.classList.add(newState);
  }
}

function updateStatus(msg) {
  statusText.textContent = msg;
}

// --------------- UI: Scroll ---------------
function scrollToBottom() {
  requestAnimationFrame(() => {
    chatMessages.scrollTop = chatMessages.scrollHeight;
  });
}

// --------------- Event Listeners ---------------
function initEventListeners() {
  // Send button
  sendBtn.addEventListener('click', () => {
    sendMessage(messageInput.value);
  });

  // Enter to send
  messageInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage(messageInput.value);
    }
  });

  // Mic button
  micBtn.addEventListener('click', () => {
    toggleRecording();
  });

  // Space to toggle voice (when input not focused)
  document.addEventListener('keydown', (e) => {
    if (e.code === 'Space' && document.activeElement !== messageInput) {
      e.preventDefault();
      toggleRecording();
    }
    // Escape to stop recording
    if (e.key === 'Escape' && isRecording) {
      stopRecording();
    }
  });

  // Focus input when typing (if not recording)
  document.addEventListener('keydown', (e) => {
    if (
      !isRecording &&
      !e.ctrlKey &&
      !e.metaKey &&
      !e.altKey &&
      e.key.length === 1 &&
      document.activeElement !== messageInput
    ) {
      // Don't steal focus if overlay is open
      if (document.querySelector('.screenshot-overlay')) return;
      messageInput.focus();
    }
  });
}

// --------------- Init ---------------
document.addEventListener('DOMContentLoaded', () => {
  initEventListeners();
  updateStatus('Connecting to Jarvis...');
  connectWebSocket();

  // Welcome message after a brief delay
  setTimeout(() => {
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      addMessage(
        'jarvis',
        'Welcome. I\'m Jarvis — your AI assistant. The backend server isn\'t running yet. Start it and I\'ll connect automatically.'
      );
    }
  }, 2500);
});

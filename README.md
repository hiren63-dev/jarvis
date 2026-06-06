# 🤖 Jarvis AI Assistant

A voice-controlled AI desktop assistant with screen awareness, computer control, and a premium web dashboard. Inspired by Iron Man's JARVIS.

![Jarvis](https://img.shields.io/badge/AI-Jarvis-00d4ff?style=for-the-badge)
![Python](https://img.shields.io/badge/Python-3.11+-blue?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)

## ✨ Features

- 🎤 **Voice Control** — Talk to Jarvis using your microphone (Whisper STT)
- 🔊 **Voice Responses** — Jarvis speaks back with natural TTS (Edge TTS — free!)
- 🧠 **Multi-LLM Support** — OpenAI GPT-4, Google Gemini, Anthropic Claude, or local Ollama
- 👁️ **Screen Awareness** — Takes screenshots and describes what's on your screen
- 🖱️ **Computer Control** — Clicks, types, opens apps, keyboard shortcuts
- 📁 **File Management** — Read, write, search files
- 🌐 **Web Browsing** — Opens URLs, searches Google
- 💻 **Shell Commands** — Runs terminal commands
- 📊 **System Monitoring** — CPU, RAM, disk usage

## 🚀 Quick Start

### 1. Prerequisites

- **Python 3.11+** (download from [python.org](https://python.org))
- **At least one API key** (see below)

### 2. Clone & Setup

```bash
# Navigate to the project
cd jarvis-ai

# Create virtual environment
python -m venv venv
venv\Scripts\activate    # Windows
# source venv/bin/activate  # macOS/Linux

# Install dependencies
pip install -r backend/requirements.txt
```

### 3. Configure API Key

```bash
# Copy the example env file
copy .env.example .env    # Windows
# cp .env.example .env    # macOS/Linux

# Edit .env and add your API key
notepad .env
```

**Choose one provider:**

| Provider | Env Variable | Model | Cost |
|---|---|---|---|
| **OpenAI** ⭐ | `OPENAI_API_KEY` | GPT-4o + Whisper + Vision | Pay per use |
| **Gemini** | `GEMINI_API_KEY` | Gemini 2.0 Flash | Free tier available |
| **Claude** | `ANTHROPIC_API_KEY` | Claude Sonnet | Pay per use |
| **Ollama** | (none — local) | Any local model | Free (needs GPU) |

> **Recommended:** OpenAI gives the best all-in-one experience (chat + voice + vision in one API key).
>
> **Budget option:** Get a free Gemini API key from [Google AI Studio](https://aistudio.google.com).

### 4. Launch Jarvis

```bash
cd backend
python main.py
```

You should see:
```
     ██╗ █████╗ ██████╗ ██╗   ██╗██╗███████╗
     ██║██╔══██╗██╔══██╗██║   ██║██║██╔════╝
     ██║███████║██████╔╝██║   ██║██║███████╗
██   ██║██╔══██║██╔══██╗╚██╗ ██╔╝██║╚════██║
╚█████╔╝██║  ██║██║  ██║ ╚████╔╝ ██║███████║
 ╚════╝ ╚═╝  ╚═╝╚═╝  ╚═╝  ╚═══╝  ╚═╝╚══════╝

  Provider : openai
  Model    : gpt-4o
  Voice    : en-US-GuyNeural
  Server   : http://0.0.0.0:8000
```

### 5. Open the Dashboard

Open your browser to: **[http://localhost:8000](http://localhost:8000)**

## 🎮 Usage

### Text Commands
Type in the input bar and press Enter:
- "What time is it?"
- "Open Notepad"
- "Take a screenshot"
- "Search Google for weather in Tokyo"
- "List files in my Documents folder"
- "What's my CPU and RAM usage?"

### Voice Commands
- Click the **🎤 mic button** or press **Space** to start recording
- Speak your command
- Click again or press **Space** to stop — Jarvis will process and respond with voice

### Keyboard Shortcuts
| Key | Action |
|---|---|
| `Enter` | Send text message |
| `Space` | Toggle voice recording (when not typing) |
| `Escape` | Stop recording / close screenshot |

## 📁 Project Structure

```
jarvis-ai/
├── .env.example           # API key template
├── .env                   # Your API keys (create this)
├── README.md
├── backend/
│   ├── main.py            # FastAPI server + WebSocket
│   ├── jarvis_brain.py    # LLM brain + tool calling
│   ├── voice.py           # STT (Whisper) + TTS (Edge TTS)
│   ├── config.py          # Configuration management
│   ├── requirements.txt   # Python dependencies
│   └── tools/
│       ├── __init__.py    # Tool registry
│       ├── screen.py      # Screenshot + OCR
│       ├── computer.py    # Mouse/keyboard control
│       ├── filesystem.py  # File operations
│       ├── web.py         # Web browsing
│       └── system.py      # System info + shell
└── frontend/
    ├── index.html         # Dashboard UI
    ├── style.css          # Dark Jarvis theme
    └── app.js             # WebSocket + voice logic
```

## 🔧 Configuration

Edit `backend/config.py` or set environment variables:

| Setting | Env Var | Default | Description |
|---|---|---|---|
| LLM Provider | `LLM_PROVIDER` | `openai` | openai / gemini / anthropic / ollama |
| Model | `MODEL` | `gpt-4o` | Model name |
| TTS Voice | `TTS_VOICE` | `en-US-GuyNeural` | Edge TTS voice name |
| STT Provider | `STT_PROVIDER` | `openai` | openai / local |
| Server Port | `PORT` | `8000` | WebSocket server port |

### Available TTS Voices

Some popular Edge TTS voices:
- `en-US-GuyNeural` — Male, American (default)
- `en-US-AriaNeural` — Female, American
- `en-GB-RyanNeural` — Male, British (very Jarvis!)
- `en-US-JennyNeural` — Female, American
- `en-AU-WilliamNeural` — Male, Australian

## ⚠️ Safety Notes

- Jarvis can control your mouse, keyboard, and run shell commands
- PyAutoGUI **failsafe** is enabled — move your mouse to any screen corner to abort
- Shell commands have a 30-second timeout
- File operations are logged

## 📜 License

MIT License — build whatever you want with this! 🚀

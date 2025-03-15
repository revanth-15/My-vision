# J.A.R.V.I.S. — a self-hosted AI assistant

A voice-enabled personal assistant with persistent memory, natural-language
command handling, and live integrations. Python + Flask on the back, vanilla
JavaScript on the front, SQLite in the middle. Runs entirely on free tiers.

**Total cost: $0.** No paid API, no subscription, no credit card.

---

## What it does

| Capability | How it works |
|---|---|
| Conversational AI | Groq, Ollama or Together.AI — swappable in one line |
| Voice input | Web Speech API, built into the browser |
| Voice output | `speechSynthesis`, built into the browser |
| Tasks | Add, list, complete, delete — with priority and due dates |
| Calendar | Schedule events with natural dates ("Friday at 10am") |
| Notes | Save and search free-form notes |
| Reminders | Timed reminders stored alongside everything else |
| Weather | Open-Meteo — no API key needed at all |
| News | NewsAPI free tier (optional) |
| Jokes, quotes, facts, tips | Free public APIs with offline fallbacks |
| Memory | SQLite, survives restarts, injected into the model's context |

---

## The two-layer design

Every message hits the **command layer** first. If it matches a known
instruction ("add task buy milk"), it is handled locally: instant, deterministic,
and it costs nothing. Only what the command layer does not recognise gets sent
to the language model.

```
Browser  →  POST /api/chat  →  CommandService  ──match──→  SQLite  →  reply
                                     │
                                  no match
                                     ↓
                                 AIService  →  Groq / Ollama / Together  →  reply
```

This is why JARVIS feels fast even on a free tier: most of what you ask it never
touches the network.

---

## Step 1 — Get a free Groq API key (2 minutes)

1. Go to <https://console.groq.com>
2. Sign up. No card required.
3. Open **API Keys** → **Create API Key**
4. Copy it. It starts with `gsk_`.

> **Model names matter.** Groq retired `mixtral-8x7b-32768`,
> `llama-3.3-70b-versatile` and `llama-3.1-8b-instant`. The current production
> models are `openai/gpt-oss-20b` (fast, the default here) and
> `openai/gpt-oss-120b` (stronger reasoning). If you ever get a 404 from the
> model, check <https://console.groq.com/docs/models> and update `GROQ_MODEL`
> in `.env`. Nothing else in the code needs to change.

---

## Step 2 — Set up the backend

```bash
cd jarvis-assistant/backend

python -m venv venv

# Windows
venv\Scripts\activate
# macOS / Linux
source venv/bin/activate

pip install -r requirements.txt
```

Create your `.env` file from the template:

```bash
# Windows
copy .env.example .env
# macOS / Linux
cp .env.example .env
```

Open `backend/.env` and paste your key:

```
GROQ_API_KEY=gsk_your_actual_key_here
```

That is the only line you must change.

---

## Step 3 — Run it

Two terminals.

**Terminal 1 — backend:**
```bash
cd backend
python app.py
```

You should see:

```
==========================================================
  JARVIS — online
==========================================================
  Provider : groq  (openai/gpt-oss-20b)
  Server   : http://localhost:5000
  AI status: ready
==========================================================
```

**Terminal 2 — frontend:**
```bash
cd frontend
python -m http.server 8000
```

Open <http://localhost:8000>.

> Open `index.html` directly by double-clicking and the browser will block the
> API calls under its `file://` security rules. Always serve it over HTTP.

**Shortcut:** double-click `start-windows.bat` (or run `./start-mac-linux.sh`)
and both start together.

---

## Step 4 — Try it

Type or speak any of these:

```
hello jarvis
add task call the bank tomorrow at 3pm urgent
show my tasks
complete task call the bank
schedule dentist appointment on friday at 10am
what's on my calendar
note down: the wifi password is hunter2
remind me to submit the report on friday
my name is Revanth
what's the weather in Berlin
tell me a joke
status
what's the capital of France        ← this one goes to the model
```

Click the microphone to speak instead of typing. Chrome, Edge and Safari
support voice input; Firefox does not.

---

## Project layout

```
jarvis-assistant/
├── backend/
│   ├── app.py                     Flask app, all REST endpoints
│   ├── config.py                  Every setting, read from .env
│   ├── requirements.txt
│   ├── .env.example               Template — copy to .env
│   ├── Procfile                   For Render/Heroku
│   └── services/
│       ├── ai_service.py          Groq | Ollama | Together, one interface
│       ├── memory_service.py      SQLite: tasks, events, notes, reminders,
│       │                          preferences, conversation history
│       ├── command_service.py     Natural-language command routing
│       ├── weather_service.py     Open-Meteo
│       └── fun_service.py         Jokes, quotes, facts, tips, news
├── frontend/
│   ├── index.html                 HUD interface
│   ├── style.css                  Arc-reactor theme
│   ├── script.js                  API client, voice I/O, panels
│   └── config.js                  ← change API_BASE when you deploy
├── database/jarvis.db             Created on first run
├── render.yaml                    Backend deployment
├── netlify.toml                   Frontend deployment
├── start-windows.bat              One-click launcher
└── start-mac-linux.sh
```

---

## Switching the AI provider

The whole reason `ai_service.py` exists. Change one line in `.env`, restart,
and nothing else in the codebase moves.

**Ollama — fully local, fully private, no key, no quota:**

1. Install from <https://ollama.com>
2. `ollama pull mistral`
3. In `.env`: `AI_PROVIDER=ollama`

**Together.AI — free tier:**

1. Key from <https://api.together.xyz>
2. In `.env`: `AI_PROVIDER=together` and `TOGETHER_API_KEY=...`

**Adding a fourth provider:** subclass `BaseAIService`, implement `chat()`,
register it in the `PROVIDERS` dict. That is the entire change.

---

## API reference

Base URL: `http://localhost:5000`

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/health` | Status, model, memory counts |
| POST | `/api/chat` | `{"message": "..."}` — the main entry point |
| GET / DELETE | `/api/history` | Read or clear conversation history |
| GET / POST | `/api/tasks` | List or create |
| PUT / DELETE | `/api/tasks/<id>` | Edit or remove |
| POST | `/api/tasks/<id>/complete` | Mark done |
| GET / POST | `/api/events` | List or create |
| DELETE | `/api/events/<id>` | Remove |
| GET / POST | `/api/notes` | List (`?q=` to search) or create |
| PUT / DELETE | `/api/notes/<id>` | Edit or remove |
| GET / POST | `/api/reminders` | List or create |
| POST | `/api/reminders/<id>/complete` | Mark done |
| GET / POST | `/api/preferences` | Read or set key/value pairs |
| GET | `/api/weather?city=Berlin` | Current conditions and 3-day forecast |
| GET | `/api/fun/<kind>` | `joke`, `quote`, `fact`, `tip`, `news` |
| GET | `/api/stats` | Memory counts and database size |

Every response is `{"success": true, "data": ...}` or
`{"success": false, "error": "..."}`.

---

## Deploying (still free)

### Backend on Render

1. Push this repository to GitHub. `.gitignore` already keeps `.env` out.
2. On <https://render.com>: **New → Web Service**, connect the repo.
3. Root directory `backend`, build `pip install -r requirements.txt`,
   start `gunicorn app:app`.
4. Under **Environment**, add `GROQ_API_KEY`, and set `FLASK_DEBUG=False`
   and `DATABASE_PATH=/tmp/jarvis.db`.

The free tier sleeps after 15 minutes idle, so the first request after a nap
takes roughly 50 seconds. Render's free disk is also ephemeral — `/tmp/jarvis.db`
resets on redeploy. For persistent memory, attach a Render disk and point
`DATABASE_PATH` at it, or move to Postgres.

### Frontend on Netlify

1. Edit `frontend/config.js` and set `API_BASE` to your Render URL.
2. Drag the `frontend` folder onto <https://app.netlify.com/drop>. Done.
3. Tighten `CORS_ORIGINS` on Render to your Netlify domain instead of `*`.

---

## Troubleshooting

**"Core offline" in the interface.** The backend is not running, or the address
is wrong. Check <http://localhost:5000/api/health> in a browser tab, then confirm
the address under Settings.

**`groq rejected the API key`.** The key in `backend/.env` is wrong or has a
stray space. Regenerate it at console.groq.com.

**`Model 'x' was not found`.** Groq retired that model. Set a current one from
<https://console.groq.com/docs/models> in `GROQ_MODEL`.

**Rate limited.** Groq's free tier throttles per minute. Wait, or switch
`AI_PROVIDER=ollama` for unlimited local inference.

**Microphone does nothing.** Voice input needs Chrome, Edge or Safari, and a
secure context — `localhost` counts, but a deployed site must be HTTPS.

**No sound on replies.** Some browsers block speech until you interact with the
page. Click anywhere, then try again. Toggle it with the Voice output button.

**Commands answered by the model instead of executed.** Phrasing did not match
a pattern. Add your phrasing to the relevant regex in
`services/command_service.py`.

---

## Where to take it next

- **Reminder notifications** — a background thread that polls `remind_at` and
  pushes a browser notification.
- **Streaming replies** — Groq supports SSE; stream tokens into the message
  bubble instead of waiting.
- **Wake word** — keep recognition running continuously and trigger on "Jarvis".
- **Semantic memory** — embed conversations and retrieve by similarity rather
  than replaying the last N turns.
- **Home automation** — Home Assistant exposes a free local REST API.

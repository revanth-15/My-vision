# JARVIS — five minute start

## 1. Key (2 min)
<https://console.groq.com> → sign up → API Keys → Create → copy the `gsk_...` value.

## 2. Install (2 min)
```bash
cd backend
python -m venv venv
venv\Scripts\activate          # Windows
source venv/bin/activate       # macOS / Linux
pip install -r requirements.txt
cp .env.example .env           # copy .env.example .env  on Windows
```
Open `backend/.env`, paste your key into `GROQ_API_KEY=`.

## 3. Run (1 min)
```bash
# Terminal 1
cd backend && python app.py

# Terminal 2
cd frontend && python -m http.server 8000
```
Open <http://localhost:8000>.

Or just double-click `start-windows.bat`.

## 4. Say something
```
hello jarvis
add task buy milk tomorrow at 5pm
show my tasks
what's the weather
tell me a joke
```

Stuck? See the Troubleshooting section of `README.md`.

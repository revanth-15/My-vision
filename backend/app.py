"""
JARVIS — Flask application.

Run locally:      python app.py
Run in production: gunicorn app:app
"""

import traceback
from datetime import datetime

from flask import Flask, jsonify, request
from flask_cors import CORS

from config import Config
from services.ai_service import AIError, get_ai_service
from services.command_service import CommandService
from services.fun_service import FunService
from services.memory_service import MemoryService
from services.weather_service import WeatherService

app = Flask(__name__)
app.config.from_object(Config)

origins = (
    "*"
    if Config.CORS_ORIGINS.strip() == "*"
    else [o.strip() for o in Config.CORS_ORIGINS.split(",") if o.strip()]
)
CORS(app, resources={r"/api/*": {"origins": origins}})

# ---------------------------------------------------------------- services
memory = MemoryService(Config.DATABASE_PATH)
weather = WeatherService(Config)
fun = FunService(Config)
commands = CommandService(memory, weather, fun, Config)
ai = get_ai_service(Config)

# Restore a saved name across restarts.
if saved_name := memory.get_preference("user_name"):
    Config.USER_NAME = saved_name
    commands.user = saved_name


# ---------------------------------------------------------------- helpers
def ok(payload=None, **extra):
    body = {"success": True}
    if payload is not None:
        body["data"] = payload
    body.update(extra)
    return jsonify(body)


def fail(message, status=400):
    return jsonify({"success": False, "error": message}), status


def body():
    return request.get_json(silent=True) or {}


@app.errorhandler(404)
def not_found(_):
    return fail("No such endpoint.", 404)


@app.errorhandler(500)
def server_error(_):
    return fail("Internal server error.", 500)


# ------------------------------------------------------------------ health
@app.get("/")
@app.get("/api/health")
def health():
    return ok(
        {
            "status": "online",
            "assistant": Config.ASSISTANT_NAME,
            "time": datetime.now().isoformat(timespec="seconds"),
            "ai": ai.health(),
            "config": Config.summary(),
            "memory": memory.stats(),
        }
    )


# -------------------------------------------------------------------- chat
@app.post("/api/chat")
def chat():
    message = (body().get("message") or "").strip()
    if not message:
        return fail("Send a non-empty 'message'.")

    memory.save_message("user", message)

    # 1. Try to handle it locally — free and instant.
    try:
        command = commands.handle(message)
    except Exception:
        traceback.print_exc()
        command = None

    if command:
        memory.save_message("assistant", command["reply"])
        return ok(
            {
                "reply": command["reply"],
                "source": "command",
                "action": command["action"],
                "result": command.get("data"),
            }
        )

    # 2. Otherwise hand it to the language model.
    try:
        reply = ai.chat(
            message,
            history=memory.recent_messages(Config.HISTORY_TURNS * 2)[:-1],
            memory_context=memory.context_for_ai(),
        )
    except AIError as exc:
        memory.save_message("assistant", str(exc))
        return ok({"reply": str(exc), "source": "error", "action": "ai_error"})
    except Exception:
        traceback.print_exc()
        return fail("Something failed while contacting the model.", 500)

    memory.save_message("assistant", reply)
    return ok({"reply": reply, "source": ai.name, "action": "chat"})


@app.get("/api/history")
def get_history():
    limit = request.args.get("limit", default=50, type=int)
    return ok(memory.recent_messages(limit))


@app.delete("/api/history")
def clear_history():
    return ok({"removed": memory.clear_conversation()})


# ------------------------------------------------------------------- tasks
@app.get("/api/tasks")
def get_tasks():
    include = request.args.get("all", "false").lower() == "true"
    return ok(memory.list_tasks(include_completed=include))


@app.post("/api/tasks")
def create_task():
    data = body()
    if not (data.get("title") or "").strip():
        return fail("A task needs a 'title'.")
    return ok(
        memory.add_task(
            data["title"],
            priority=data.get("priority", "normal"),
            due_date=data.get("due_date"),
        )
    ), 201


@app.put("/api/tasks/<int:task_id>")
def edit_task(task_id):
    task = memory.update_task(task_id, **body())
    return ok(task) if task else fail("No such task.", 404)


@app.post("/api/tasks/<int:task_id>/complete")
def finish_task(task_id):
    task = memory.complete_task(task_id)
    return ok(task) if task else fail("No such task.", 404)


@app.delete("/api/tasks/<int:task_id>")
def remove_task(task_id):
    return ok({"deleted": task_id}) if memory.delete_task(task_id) else fail(
        "No such task.", 404
    )


# ------------------------------------------------------------------ events
@app.get("/api/events")
def get_events():
    return ok(memory.list_events())


@app.post("/api/events")
def create_event():
    data = body()
    if not (data.get("title") or "").strip():
        return fail("An event needs a 'title'.")
    return ok(
        memory.add_event(
            data["title"],
            event_time=data.get("event_time"),
            location=data.get("location"),
            notes=data.get("notes"),
        )
    ), 201


@app.delete("/api/events/<int:event_id>")
def remove_event(event_id):
    return ok({"deleted": event_id}) if memory.delete_event(event_id) else fail(
        "No such event.", 404
    )


# ------------------------------------------------------------------- notes
@app.get("/api/notes")
def get_notes():
    term = request.args.get("q")
    return ok(memory.search_notes(term) if term else memory.list_notes())


@app.post("/api/notes")
def create_note():
    data = body()
    if not (data.get("title") or "").strip():
        return fail("A note needs a 'title'.")
    return ok(
        memory.add_note(
            data["title"], content=data.get("content", ""), tags=data.get("tags", "")
        )
    ), 201


@app.put("/api/notes/<int:note_id>")
def edit_note(note_id):
    note = memory.update_note(note_id, **body())
    return ok(note) if note else fail("No such note.", 404)


@app.delete("/api/notes/<int:note_id>")
def remove_note(note_id):
    return ok({"deleted": note_id}) if memory.delete_note(note_id) else fail(
        "No such note.", 404
    )


# --------------------------------------------------------------- reminders
@app.get("/api/reminders")
def get_reminders():
    include = request.args.get("all", "false").lower() == "true"
    return ok(memory.list_reminders(include_done=include))


@app.post("/api/reminders")
def create_reminder():
    data = body()
    if not (data.get("message") or "").strip():
        return fail("A reminder needs a 'message'.")
    return ok(memory.add_reminder(data["message"], data.get("remind_at"))), 201


@app.post("/api/reminders/<int:reminder_id>/complete")
def finish_reminder(reminder_id):
    return ok({"completed": reminder_id}) if memory.complete_reminder(
        reminder_id
    ) else fail("No such reminder.", 404)


@app.delete("/api/reminders/<int:reminder_id>")
def remove_reminder(reminder_id):
    return ok({"deleted": reminder_id}) if memory.delete_reminder(
        reminder_id
    ) else fail("No such reminder.", 404)


# ------------------------------------------------------------- preferences
@app.get("/api/preferences")
def get_preferences():
    return ok(memory.all_preferences())


@app.post("/api/preferences")
def set_preferences():
    data = body()
    if not data:
        return fail("Send at least one key/value pair.")
    for key, value in data.items():
        memory.set_preference(key, value)
        if key == "user_name":
            Config.USER_NAME = str(value)
            commands.user = str(value)
    return ok(memory.all_preferences())


@app.delete("/api/preferences/<key>")
def remove_preference(key):
    return ok({"deleted": key}) if memory.delete_preference(key) else fail(
        "No such preference.", 404
    )


# -------------------------------------------------------------- integrations
@app.get("/api/weather")
def get_weather():
    city = request.args.get("city") or memory.get_preference(
        "city", Config.DEFAULT_CITY
    )
    try:
        data = weather.fetch(city)
    except Exception:
        return fail("Weather service unreachable.", 502)
    return fail(data["error"], 404) if "error" in data else ok(data)


@app.get("/api/fun/<kind>")
def get_fun(kind):
    handlers = {
        "joke": fun.joke,
        "quote": fun.quote,
        "fact": fun.fact,
        "tip": fun.tip,
        "news": fun.headlines,
    }
    handler = handlers.get(kind)
    if not handler:
        return fail(f"Unknown kind '{kind}'. Try: {', '.join(handlers)}.", 404)
    return ok({"kind": kind, "text": handler()})


@app.get("/api/stats")
def get_stats():
    return ok(memory.stats())


# ------------------------------------------------------------------- start
def banner():
    c = Config.summary()
    print("\n" + "=" * 58)
    print(f"  {Config.ASSISTANT_NAME} — online")
    print("=" * 58)
    print(f"  Provider : {c['provider']}  ({c['model']})")
    print(f"  Database : {c['database']}")
    print(f"  Server   : http://localhost:{Config.PORT}")
    print(f"  Health   : http://localhost:{Config.PORT}/api/health")
    health_info = ai.health()
    flag = "ready" if health_info["ok"] else f"WARNING — {health_info['detail']}"
    print(f"  AI status: {flag}")
    print("=" * 58 + "\n")


if __name__ == "__main__":
    banner()
    app.run(host=Config.HOST, port=Config.PORT, debug=Config.DEBUG)

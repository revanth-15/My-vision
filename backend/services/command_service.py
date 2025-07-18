"""
JARVIS — command service.

Runs before the model. If a message is clearly an instruction JARVIS can carry
out locally ("add task buy milk", "what's the weather"), it is handled here:
instant, deterministic, and it costs nothing. Anything else falls through to
the AI service.

Every handler returns a dict:
    {"handled": True, "reply": str, "action": str, "data": any}
or None, meaning "not my department, pass it to the model".
"""

import random
import re
from datetime import datetime, timedelta

# --------------------------------------------------------------- time words
WEEKDAYS = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6,
}

ACKS = [
    "Noted, {user}.",
    "Done, {user}.",
    "Logged.",
    "Consider it recorded, {user}.",
    "On the list.",
]


def parse_when(text: str):
    """Best-effort natural date/time extraction. Returns (iso_string|None,
    leftover_text)."""
    if not text:
        return None, text

    lowered = text.lower()
    base = datetime.now()
    target_date = None
    matched = ""

    if m := re.search(r"\b(today|tonight)\b", lowered):
        target_date, matched = base, m.group(0)
    elif m := re.search(r"\btomorrow\b", lowered):
        target_date, matched = base + timedelta(days=1), m.group(0)
    elif m := re.search(r"\bday after tomorrow\b", lowered):
        target_date, matched = base + timedelta(days=2), m.group(0)
    elif m := re.search(r"\bin (\d+) (day|days|week|weeks|hour|hours)\b", lowered):
        amount, unit = int(m.group(1)), m.group(2)
        delta = {
            "day": timedelta(days=amount), "days": timedelta(days=amount),
            "week": timedelta(weeks=amount), "weeks": timedelta(weeks=amount),
            "hour": timedelta(hours=amount), "hours": timedelta(hours=amount),
        }[unit]
        target_date, matched = base + delta, m.group(0)
    elif m := re.search(
        r"\b(?:next |on |this )?(" + "|".join(WEEKDAYS) + r")\b", lowered
    ):
        wanted = WEEKDAYS[m.group(1)]
        ahead = (wanted - base.weekday() + 7) % 7 or 7
        target_date, matched = base + timedelta(days=ahead), m.group(0)
    elif m := re.search(r"\b(\d{4}-\d{2}-\d{2})\b", lowered):
        try:
            target_date, matched = datetime.fromisoformat(m.group(1)), m.group(0)
        except ValueError:
            pass

    # Clock time, e.g. "at 5pm", "at 14:30", "5:30 pm"
    time_match = re.search(
        r"\bat\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b|\b(\d{1,2}):(\d{2})\s*(am|pm)?\b",
        lowered,
    )
    hour = minute = None
    if time_match:
        if time_match.group(1):
            hour = int(time_match.group(1))
            minute = int(time_match.group(2) or 0)
            meridiem = time_match.group(3)
        else:
            hour = int(time_match.group(4))
            minute = int(time_match.group(5))
            meridiem = time_match.group(6)
        if meridiem == "pm" and hour < 12:
            hour += 12
        elif meridiem == "am" and hour == 12:
            hour = 0
        matched = (matched + " " + time_match.group(0)).strip()

    if target_date is None and hour is None:
        return None, text

    target_date = target_date or base
    if hour is not None:
        target_date = target_date.replace(
            hour=min(hour, 23), minute=minute or 0, second=0, microsecond=0
        )
    else:
        target_date = target_date.replace(hour=9, minute=0, second=0, microsecond=0)

    leftover = text
    for token in matched.split():
        leftover = re.sub(rf"\b{re.escape(token)}\b", "", leftover, flags=re.I)
    leftover = re.sub(r"\s{2,}", " ", leftover).strip(" ,.-")

    return target_date.isoformat(timespec="minutes"), leftover


def parse_priority(text: str):
    lowered = text.lower()
    if re.search(r"\b(urgent|asap|high priority|important|critical)\b", lowered):
        cleaned = re.sub(
            r"\b(urgent|asap|high priority|important|critical)\b", "", text, flags=re.I
        )
        return "high", re.sub(r"\s{2,}", " ", cleaned).strip(" ,.-")
    if re.search(r"\b(low priority|whenever|someday|no rush)\b", lowered):
        cleaned = re.sub(
            r"\b(low priority|whenever|someday|no rush)\b", "", text, flags=re.I
        )
        return "low", re.sub(r"\s{2,}", " ", cleaned).strip(" ,.-")
    return "normal", text


class CommandService:
    def __init__(self, memory, weather, fun, config):
        self.memory = memory
        self.weather = weather
        self.fun = fun
        self.config = config
        self.user = config.USER_NAME

    # ------------------------------------------------------------ dispatcher
    def handle(self, message: str):
        text = (message or "").strip()
        if not text:
            return None

        for handler in (
            self._greeting,
            self._help,
            self._time,
            self._add_task,
            self._complete_task,
            self._delete_task,
            self._list_tasks,
            self._add_event,
            self._list_events,
            self._add_note,
            self._list_notes,
            self._add_reminder,
            self._list_reminders,
            self._set_preference,
            self._weather,
            self._news,
            self._fun,
            self._status,
            self._clear,
        ):
            result = handler(text)
            if result:
                return result
        return None

    def _ok(self, reply, action, data=None):
        return {"handled": True, "reply": reply, "action": action, "data": data}

    def _ack(self):
        return random.choice(ACKS).format(user=self.user)

    # --------------------------------------------------------------- basics
    def _greeting(self, text):
        if re.fullmatch(
            r"(hi|hey|hello|yo|good morning|good evening|good afternoon)"
            r"[\s,!.]*(jarvis)?[\s!.?]*",
            text,
            re.I,
        ):
            hour = datetime.now().hour
            part = "morning" if hour < 12 else "afternoon" if hour < 18 else "evening"
            open_tasks = len(self.memory.list_tasks())
            tail = (
                f" You have {open_tasks} open task{'s' if open_tasks != 1 else ''}."
                if open_tasks
                else " Nothing outstanding on your list."
            )
            return self._ok(
                f"Good {part}, {self.user}. All systems online.{tail}", "greeting"
            )
        return None

    def _help(self, text):
        if re.fullmatch(
            r"(help|what can you do|commands|show commands)[\s?!.]*", text, re.I
        ):
            return self._ok(
                "I can manage tasks, events, notes and reminders, fetch the "
                "weather and headlines, and answer anything else conversationally. "
                "Try: add task call the bank tomorrow at 3pm, show my tasks, "
                "schedule dentist on Friday at 10am, note down the wifi password, "
                "weather in Berlin, tell me a joke. Anything I do not recognise as "
                "a command goes to the language model.",
                "help",
            )
        return None

    def _time(self, text):
        if re.fullmatch(
            r"(?:what(?:'s|s| is)?\s+)?(?:the\s+)?(?:current\s+)?"
            r"(?:time|date|day)(?:\s+is\s+it)?(?:\s+today)?[\s?!.]*|"
            r"what\s+day\s+is\s+(?:it|today)[\s?!.]*|"
            r"what\s+time\s+is\s+it[\s?!.]*",
            text,
            re.I,
        ):
            now = datetime.now()
            return self._ok(
                f"It is {now.strftime('%H:%M')} on {now.strftime('%A, %d %B %Y')}.",
                "time",
            )
        return None

    # ---------------------------------------------------------------- tasks
    def _add_task(self, text):
        m = re.match(
            r"^(?:add|create|new|make)?\s*(?:a\s+)?task[:\s]+(.+)$|"
            r"^(?:remind me to|i need to|todo:?)\s+(.+)$",
            text,
            re.I,
        )
        if not m:
            return None
        body = (m.group(1) or m.group(2)).strip()
        priority, body = parse_priority(body)
        due, body = parse_when(body)
        if not body:
            return self._ok("I need a description for that task.", "error")

        task = self.memory.add_task(body, priority=priority, due_date=due)
        reply = f"{self._ack()} Task {task['id']}: {task['title']}"
        if due:
            reply += f", due {datetime.fromisoformat(due).strftime('%a %d %b at %H:%M')}"
        if priority == "high":
            reply += ", flagged high priority"
        return self._ok(reply + ".", "task_added", task)

    def _list_tasks(self, text):
        if not re.fullmatch(
            r"(show|list|what are|read)?\s*(me\s+)?(my\s+)?(open\s+|all\s+)?"
            r"(tasks|todos|to-dos|task list)[\s?!.]*",
            text,
            re.I,
        ):
            return None
        include_done = bool(re.search(r"\ball\b", text, re.I))
        tasks = self.memory.list_tasks(include_completed=include_done)
        if not tasks:
            return self._ok(
                f"Your task list is empty, {self.user}.", "tasks_listed", []
            )
        lines = []
        for t in tasks:
            mark = "done" if t["completed"] else "open"
            due = (
                f" (due {datetime.fromisoformat(t['due_date']).strftime('%a %d %b %H:%M')})"
                if t["due_date"]
                else ""
            )
            flag = " [high]" if t["priority"] == "high" else ""
            lines.append(f"{t['id']}. {t['title']}{due}{flag} — {mark}")
        return self._ok(
            f"You have {len(tasks)} task{'s' if len(tasks) != 1 else ''}:\n"
            + "\n".join(lines),
            "tasks_listed",
            tasks,
        )

    def _complete_task(self, text):
        m = re.match(
            r"^(?:complete|finish|done with|mark done|tick off|check off)\s+"
            r"(?:task\s+)?(.+)$",
            text,
            re.I,
        )
        if not m:
            return None
        target = m.group(1).strip(" .")
        task = (
            self.memory.complete_task(int(target))
            if target.isdigit()
            else self.memory.complete_task_by_title(target)
        )
        if not task:
            return self._ok(f"I could not find a task matching '{target}'.", "error")
        return self._ok(f"Task {task['id']} closed: {task['title']}.", "task_completed", task)

    def _delete_task(self, text):
        m = re.match(r"^(?:delete|remove|drop)\s+task\s+(\d+)[\s.]*$", text, re.I)
        if not m:
            return None
        task_id = int(m.group(1))
        ok = self.memory.delete_task(task_id)
        return self._ok(
            f"Task {task_id} deleted." if ok else f"No task {task_id} to delete.",
            "task_deleted" if ok else "error",
        )

    # --------------------------------------------------------------- events
    def _add_event(self, text):
        m = re.match(
            r"^(?:schedule|add event|new event|book|set up a meeting|meeting)"
            r"[:\s]+(.+)$",
            text,
            re.I,
        )
        if not m:
            return None
        body = m.group(1).strip()
        location = None
        if loc := re.search(r"\b(?:at|in)\s+(the\s+)?([A-Z][\w\s]{2,25})$", body):
            location = loc.group(2).strip()
        when, body = parse_when(body)
        body = re.sub(r"^(a|an|the)\s+", "", body, flags=re.I).strip(" ,.-")
        if not body:
            return self._ok("What should I call that event?", "error")

        event = self.memory.add_event(body, event_time=when, location=location)
        when_text = (
            datetime.fromisoformat(when).strftime("%A %d %B at %H:%M")
            if when
            else "no time set"
        )
        return self._ok(
            f"Scheduled: {event['title']} — {when_text}.", "event_added", event
        )

    def _list_events(self, text):
        if not re.fullmatch(
            r"(show|list|what(?:'s| is) on)?\s*(me\s+)?(my\s+)?"
            r"(events|schedule|calendar|agenda)[\s?!.]*",
            text,
            re.I,
        ):
            return None
        events = self.memory.list_events()
        if not events:
            return self._ok(f"Your calendar is clear, {self.user}.", "events_listed", [])
        lines = []
        for e in events:
            when = (
                datetime.fromisoformat(e["event_time"]).strftime("%a %d %b %H:%M")
                if e["event_time"]
                else "unscheduled"
            )
            where = f" at {e['location']}" if e["location"] else ""
            lines.append(f"{e['id']}. {e['title']} — {when}{where}")
        return self._ok(
            f"{len(events)} item{'s' if len(events) != 1 else ''} on your calendar:\n"
            + "\n".join(lines),
            "events_listed",
            events,
        )

    # ---------------------------------------------------------------- notes
    def _add_note(self, text):
        m = re.match(
            r"^(?:create |add |new |take a |make a )?note(?:\s+down)?[:\s]+(.+)$|"
            r"^(?:remember|note down)\s+(?:that\s+)?(.+)$",
            text,
            re.I,
        )
        if not m:
            return None
        body = (m.group(1) or m.group(2)).strip()
        if ":" in body:
            title, content = body.split(":", 1)
        else:
            words = body.split()
            title = " ".join(words[:6]) + ("..." if len(words) > 6 else "")
            content = body
        note = self.memory.add_note(title.strip(), content.strip())
        return self._ok(f"Note {note['id']} saved: {note['title']}", "note_added", note)

    def _list_notes(self, text):
        if not re.fullmatch(
            r"(show|list|read)?\s*(me\s+)?(my\s+)?notes[\s?!.]*", text, re.I
        ):
            return None
        notes = self.memory.list_notes()
        if not notes:
            return self._ok("You have no notes saved.", "notes_listed", [])
        lines = [f"{n['id']}. {n['title']}" for n in notes]
        return self._ok(
            f"{len(notes)} note{'s' if len(notes) != 1 else ''}:\n" + "\n".join(lines),
            "notes_listed",
            notes,
        )

    # ------------------------------------------------------------ reminders
    def _add_reminder(self, text):
        m = re.match(r"^(?:set a reminder|remind me)[:\s]+(?:about\s+)?(.+)$", text, re.I)
        if not m:
            return None
        body = m.group(1).strip()
        when, body = parse_when(body)
        reminder = self.memory.add_reminder(body or "reminder", remind_at=when)
        when_text = (
            f" for {datetime.fromisoformat(when).strftime('%a %d %b %H:%M')}"
            if when
            else ""
        )
        return self._ok(
            f"Reminder set{when_text}: {reminder['message']}.",
            "reminder_added",
            reminder,
        )

    def _list_reminders(self, text):
        if not re.fullmatch(
            r"(show|list)?\s*(me\s+)?(my\s+)?reminders[\s?!.]*", text, re.I
        ):
            return None
        items = self.memory.list_reminders()
        if not items:
            return self._ok("No active reminders.", "reminders_listed", [])
        lines = [
            f"{r['id']}. {r['message']}"
            + (
                f" — {datetime.fromisoformat(r['remind_at']).strftime('%a %d %b %H:%M')}"
                if r["remind_at"]
                else ""
            )
            for r in items
        ]
        return self._ok("\n".join(lines), "reminders_listed", items)

    # ---------------------------------------------------------- preferences
    def _set_preference(self, text):
        m = re.match(
            r"^(?:my name is|call me)\s+(.+)$|"
            r"^(?:i live in|my city is|set my city to)\s+(.+)$",
            text,
            re.I,
        )
        if not m:
            return None
        if m.group(1):
            name = m.group(1).strip(" .")
            self.memory.set_preference("user_name", name)
            self.config.USER_NAME = name
            self.user = name
            return self._ok(f"Understood. I will call you {name}.", "preference_set")
        city = m.group(2).strip(" .")
        self.memory.set_preference("city", city)
        return self._ok(f"City set to {city}.", "preference_set")

    # -------------------------------------------------------------- weather
    def _weather(self, text):
        if not re.search(r"\b(weather|forecast|temperature|how (hot|cold))\b", text, re.I):
            return None
        city = self.memory.get_preference("city", self.config.DEFAULT_CITY)
        if m := re.search(r"\b(?:in|for|at)\s+([A-Za-z\s'-]{2,40})$", text.strip(" ?.!")):
            city = m.group(1).strip()
        return self._ok(self.weather.describe(city), "weather", {"city": city})

    # ----------------------------------------------------------------- news
    def _news(self, text):
        if not re.search(r"\b(news|headlines|what(?:'s| is) happening)\b", text, re.I):
            return None
        return self._ok(self.fun.headlines(), "news")

    # ------------------------------------------------------------------ fun
    def _fun(self, text):
        if re.search(r"\b(joke|make me laugh|something funny)\b", text, re.I):
            return self._ok(self.fun.joke(), "joke")
        if re.search(r"\b(quote|inspire me|motivat)\w*\b", text, re.I):
            return self._ok(self.fun.quote(), "quote")
        if re.search(r"\b(fun fact|random fact|tell me a fact)\b", text, re.I):
            return self._ok(self.fun.fact(), "fact")
        if re.search(r"\b(productivity tip|give me a tip|focus tip)\b", text, re.I):
            return self._ok(self.fun.tip(), "tip")
        return None

    # --------------------------------------------------------------- system
    def _status(self, text):
        if not re.fullmatch(
            r"(status|system status|diagnostics|report|stats)[\s?!.]*", text, re.I
        ):
            return None
        s = self.memory.stats()
        return self._ok(
            f"All systems nominal. {s['tasks_open']} open tasks, "
            f"{s['tasks_done']} completed, {s['events']} calendar entries, "
            f"{s['notes']} notes, {s['messages']} messages in memory. "
            f"Database size {s['db_size_kb']} KB.",
            "status",
            s,
        )

    def _clear(self, text):
        if not re.fullmatch(
            r"(clear|reset|wipe)\s+(the\s+)?(chat|conversation|history|memory)[\s?!.]*",
            text,
            re.I,
        ):
            return None
        removed = self.memory.clear_conversation()
        return self._ok(
            f"Conversation history cleared. {removed} messages removed. "
            "Your tasks, events and notes are untouched.",
            "history_cleared",
        )

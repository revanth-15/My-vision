/* ═══════════════════════════════════════════════════════════════════
   JARVIS — frontend logic
   Talks to the Flask backend, handles speech in and speech out,
   and keeps the side panels in sync.
   ═══════════════════════════════════════════════════════════════════ */

(() => {
  "use strict";

  /* ─────────────────────────── element handles ─────────────────── */
  const $ = (id) => document.getElementById(id);

  const el = {
    stream: $("stream"),
    input: $("input"),
    composer: $("composer"),
    sendBtn: $("sendBtn"),
    micBtn: $("micBtn"),
    typing: $("typing"),
    reactor: $("reactor"),
    reactorLabel: $("reactorLabel"),
    linkState: $("linkState"),
    linkText: $("linkText"),
    clock: $("clock"),
    modelTag: $("modelTag"),
    mastheadSub: $("mastheadSub"),
    quickRow: $("quickRow"),
    rail: $("rail"),
    railToggle: $("railToggle"),
    voiceToggle: $("voiceToggle"),
    settingsBtn: $("settingsBtn"),
    sheetBackdrop: $("sheetBackdrop"),
    sheetCancel: $("sheetCancel"),
    sheetSave: $("sheetSave"),
    clearHistoryBtn: $("clearHistoryBtn"),
    apiInput: $("apiInput"),
    nameInput: $("nameInput"),
    cityInput: $("cityInput"),
    toast: $("toast"),
    weatherReadout: $("weatherReadout"),
    weatherTemp: $("weatherTemp"),
    weatherPlace: $("weatherPlace"),
    weatherCond: $("weatherCond"),
  };

  /* ──────────────────────── persistent settings ────────────────── */
  /* Wrapped so the page still works anywhere localStorage is blocked. */
  const store = {
    mem: {},
    get(key, fallback) {
      try {
        const v = localStorage.getItem(key);
        return v === null ? fallback : v;
      } catch {
        return key in this.mem ? this.mem[key] : fallback;
      }
    },
    set(key, value) {
      try {
        localStorage.setItem(key, value);
      } catch {
        this.mem[key] = value;
      }
    },
  };

  const state = {
    api: store.get("jarvis.api", JARVIS_CONFIG.API_BASE).replace(/\/+$/, ""),
    voice: store.get("jarvis.voice", String(JARVIS_CONFIG.VOICE_OUTPUT)) === "true",
    online: false,
    busy: false,
    listening: false,
    activePanel: "tasks",
  };

  /* ─────────────────────────── HUD helpers ─────────────────────── */

  function setReactor(mode, label) {
    el.reactor.dataset.state = mode;
    el.reactorLabel.textContent = label;
  }

  function setLink(online, text) {
    state.online = online;
    el.linkState.dataset.ok = String(online);
    el.linkText.textContent = text;
    if (!online) setReactor("offline", "Link lost");
    else if (!state.busy && !state.listening) setReactor("idle", "Standing by");
  }

  let toastTimer;
  function toast(text) {
    el.toast.textContent = text;
    el.toast.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => (el.toast.hidden = true), 3200);
  }

  function tickClock() {
    el.clock.textContent = new Date().toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  /* ───────────────────────────── API layer ─────────────────────── */

  async function api(path, options = {}) {
    const res = await fetch(state.api + path, {
      headers: { "Content-Type": "application/json" },
      ...options,
    });
    const payload = await res.json().catch(() => ({}));
    if (!res.ok || payload.success === false) {
      throw new Error(payload.error || `Request failed (${res.status})`);
    }
    return payload.data;
  }

  /* ───────────────────────────── messages ──────────────────────── */

  function addMessage(who, text, isError = false) {
    const wrap = document.createElement("div");
    wrap.className =
      "msg " + (who === "user" ? "from-user" : "from-jarvis") + (isError ? " is-error" : "");

    const label = document.createElement("div");
    label.className = "msg-who";
    label.textContent = who === "user" ? "You" : "JARVIS";

    const body = document.createElement("div");
    body.className = "msg-text";
    body.textContent = text;

    wrap.append(label, body);
    el.stream.appendChild(wrap);
    el.stream.scrollTop = el.stream.scrollHeight;
    return wrap;
  }

  /* ─────────────────────── speech synthesis (out) ──────────────── */

  let chosenVoice = null;

  function pickVoice() {
    const voices = speechSynthesis.getVoices();
    if (!voices.length) return;
    for (const wanted of JARVIS_CONFIG.VOICE_PREFERENCES) {
      const hit = voices.find((v) => v.name.includes(wanted));
      if (hit) {
        chosenVoice = hit;
        return;
      }
    }
    chosenVoice = voices.find((v) => v.lang.startsWith("en")) || voices[0];
  }

  if ("speechSynthesis" in window) {
    pickVoice();
    speechSynthesis.onvoiceschanged = pickVoice;
  }

  function speak(text) {
    if (!state.voice || !("speechSynthesis" in window)) return;
    speechSynthesis.cancel();
    // Strip list numbering and newlines so it reads naturally aloud.
    const spoken = text.replace(/^\d+\.\s*/gm, "").replace(/\n+/g, ". ").slice(0, 600);
    const utter = new SpeechSynthesisUtterance(spoken);
    utter.rate = JARVIS_CONFIG.SPEECH_RATE;
    utter.pitch = JARVIS_CONFIG.SPEECH_PITCH;
    if (chosenVoice) utter.voice = chosenVoice;
    speechSynthesis.speak(utter);
  }

  /* ────────────────────── speech recognition (in) ──────────────── */

  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  let recognizer = null;

  if (SR) {
    recognizer = new SR();
    recognizer.lang = JARVIS_CONFIG.RECOGNITION_LANG;
    recognizer.interimResults = true;
    recognizer.continuous = false;
    recognizer.maxAlternatives = 1;

    recognizer.onstart = () => {
      state.listening = true;
      el.micBtn.classList.add("is-live");
      setReactor("listening", "Listening");
    };

    recognizer.onresult = (event) => {
      let transcript = "";
      for (let i = event.resultIndex; i < event.results.length; i++) {
        transcript += event.results[i][0].transcript;
      }
      el.input.value = transcript;
      if (event.results[event.results.length - 1].isFinal) {
        stopListening();
        if (transcript.trim()) send(transcript.trim());
      }
    };

    recognizer.onerror = (event) => {
      stopListening();
      const messages = {
        "not-allowed": "Microphone access was denied. Allow it in your browser settings.",
        "no-speech": "I did not catch that.",
        "audio-capture": "No microphone found.",
        network: "Speech recognition needs a network connection.",
      };
      toast(messages[event.error] || `Microphone error: ${event.error}`);
    };

    recognizer.onend = stopListening;
  } else {
    el.micBtn.disabled = true;
    el.micBtn.title = "Voice input needs Chrome, Edge or Safari";
  }

  function stopListening() {
    state.listening = false;
    el.micBtn.classList.remove("is-live");
    if (!state.busy) setReactor(state.online ? "idle" : "offline",
      state.online ? "Standing by" : "Link lost");
  }

  el.micBtn.addEventListener("click", () => {
    if (!recognizer) return;
    if (state.listening) {
      recognizer.stop();
    } else {
      speechSynthesis.cancel();
      try {
        recognizer.start();
      } catch {
        /* already starting — ignore */
      }
    }
  });

  /* ────────────────────────── sending a message ────────────────── */

  async function send(text) {
    if (state.busy || !text.trim()) return;

    addMessage("user", text);
    el.input.value = "";
    state.busy = true;
    el.sendBtn.disabled = true;
    el.typing.hidden = false;
    setReactor("thinking", "Processing");

    try {
      const data = await api("/api/chat", {
        method: "POST",
        body: JSON.stringify({ message: text }),
      });

      const isError = data.source === "error";
      addMessage("jarvis", data.reply, isError);
      if (!isError) speak(data.reply);

      setLink(true, "Core link stable");

      // Refresh the panel the action touched.
      if (/task/.test(data.action)) loadPanel("tasks");
      else if (/event/.test(data.action)) loadPanel("events");
      else if (/note/.test(data.action)) loadPanel("notes");
      else if (data.action === "weather") loadWeather();
      else if (data.action === "history_cleared") el.stream.innerHTML = "";
    } catch (err) {
      addMessage(
        "jarvis",
        `I cannot reach the backend at ${state.api}. Check that it is running, ` +
          `then confirm the address under Settings. (${err.message})`,
        true
      );
      setLink(false, "Core offline");
    } finally {
      state.busy = false;
      el.sendBtn.disabled = false;
      el.typing.hidden = true;
      if (state.online && !state.listening) setReactor("idle", "Standing by");
      el.input.focus();
    }
  }

  el.composer.addEventListener("submit", (e) => {
    e.preventDefault();
    send(el.input.value.trim());
  });

  el.quickRow.addEventListener("click", (e) => {
    const button = e.target.closest("button[data-say]");
    if (button) send(button.dataset.say);
  });

  /* ─────────────────────────── side panels ─────────────────────── */

  function emptyPanel(message) {
    const p = document.createElement("p");
    p.className = "panel-empty";
    p.textContent = message;
    return p;
  }

  function buildEntry({ title, meta, priority, onCheck, onDelete }) {
    const row = document.createElement("div");
    row.className = "entry";
    if (priority) row.dataset.priority = priority;

    if (onCheck) {
      const check = document.createElement("button");
      check.className = "entry-check";
      check.setAttribute("aria-label", `Mark "${title}" done`);
      check.addEventListener("click", onCheck);
      row.appendChild(check);
    }

    const text = document.createElement("div");
    text.className = "entry-text";
    const heading = document.createElement("div");
    heading.className = "entry-title";
    heading.textContent = title;
    text.appendChild(heading);
    if (meta) {
      const sub = document.createElement("div");
      sub.className = "entry-meta";
      sub.textContent = meta;
      text.appendChild(sub);
    }
    row.appendChild(text);

    if (onDelete) {
      const kill = document.createElement("button");
      kill.className = "entry-kill";
      kill.textContent = "×";
      kill.setAttribute("aria-label", `Delete "${title}"`);
      kill.addEventListener("click", onDelete);
      row.appendChild(kill);
    }
    return row;
  }

  function formatWhen(iso) {
    if (!iso) return "";
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso;
    return d.toLocaleString([], {
      weekday: "short",
      day: "numeric",
      month: "short",
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  const panels = {
    async tasks(target) {
      const tasks = await api("/api/tasks");
      if (!tasks.length) return target.appendChild(emptyPanel("No open tasks."));
      tasks.forEach((t) =>
        target.appendChild(
          buildEntry({
            title: t.title,
            meta: t.due_date ? `Due ${formatWhen(t.due_date)}` : "",
            priority: t.priority,
            onCheck: async () => {
              await api(`/api/tasks/${t.id}/complete`, { method: "POST" });
              toast("Task closed");
              loadPanel("tasks");
            },
            onDelete: async () => {
              await api(`/api/tasks/${t.id}`, { method: "DELETE" });
              loadPanel("tasks");
            },
          })
        )
      );
    },

    async events(target) {
      const events = await api("/api/events");
      if (!events.length) return target.appendChild(emptyPanel("Calendar is clear."));
      events.forEach((ev) =>
        target.appendChild(
          buildEntry({
            title: ev.title,
            meta: [formatWhen(ev.event_time), ev.location].filter(Boolean).join(" · "),
            onDelete: async () => {
              await api(`/api/events/${ev.id}`, { method: "DELETE" });
              loadPanel("events");
            },
          })
        )
      );
    },

    async notes(target) {
      const notes = await api("/api/notes");
      if (!notes.length) return target.appendChild(emptyPanel("No notes saved."));
      notes.forEach((n) =>
        target.appendChild(
          buildEntry({
            title: n.title,
            meta: n.content && n.content !== n.title ? n.content.slice(0, 70) : "",
            onDelete: async () => {
              await api(`/api/notes/${n.id}`, { method: "DELETE" });
              loadPanel("notes");
            },
          })
        )
      );
    },
  };

  async function loadPanel(name) {
    const target = $(`panel-${name}`);
    if (!target) return;
    try {
      target.innerHTML = "";
      await panels[name](target);
    } catch {
      target.innerHTML = "";
      target.appendChild(emptyPanel("Cannot load — backend unreachable."));
    }
  }

  function loadAllPanels() {
    ["tasks", "events", "notes"].forEach(loadPanel);
  }

  document.querySelectorAll(".panel-tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      document.querySelectorAll(".panel-tab").forEach((t) => t.classList.remove("is-active"));
      document.querySelectorAll(".panel").forEach((p) => p.classList.remove("is-active"));
      tab.classList.add("is-active");
      $(`panel-${tab.dataset.panel}`).classList.add("is-active");
      state.activePanel = tab.dataset.panel;
      loadPanel(tab.dataset.panel);
    });
  });

  /* ───────────────────────────── weather ───────────────────────── */

  async function loadWeather() {
    try {
      const w = await api("/api/weather");
      el.weatherTemp.textContent = `${w.temperature}${w.unit}`;
      el.weatherPlace.textContent = w.city;
      el.weatherCond.textContent = w.condition;
      el.weatherReadout.hidden = false;
    } catch {
      el.weatherReadout.hidden = true;
    }
  }

  /* ──────────────────────────── settings ───────────────────────── */

  function openSheet() {
    el.apiInput.value = state.api;
    api("/api/preferences")
      .then((prefs) => {
        el.nameInput.value = prefs.user_name || "";
        el.cityInput.value = prefs.city || "";
      })
      .catch(() => {});
    el.sheetBackdrop.hidden = false;
  }

  function closeSheet() {
    el.sheetBackdrop.hidden = true;
  }

  el.settingsBtn.addEventListener("click", openSheet);
  el.sheetCancel.addEventListener("click", closeSheet);
  el.sheetBackdrop.addEventListener("click", (e) => {
    if (e.target === el.sheetBackdrop) closeSheet();
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !el.sheetBackdrop.hidden) closeSheet();
  });

  el.sheetSave.addEventListener("click", async () => {
    const nextApi = el.apiInput.value.trim().replace(/\/+$/, "");
    if (nextApi && nextApi !== state.api) {
      state.api = nextApi;
      store.set("jarvis.api", nextApi);
    }

    const prefs = {};
    if (el.nameInput.value.trim()) prefs.user_name = el.nameInput.value.trim();
    if (el.cityInput.value.trim()) prefs.city = el.cityInput.value.trim();

    if (Object.keys(prefs).length) {
      try {
        await api("/api/preferences", {
          method: "POST",
          body: JSON.stringify(prefs),
        });
      } catch {
        toast("Could not save preferences — backend unreachable");
      }
    }

    closeSheet();
    toast("Settings saved");
    boot();
  });

  el.clearHistoryBtn.addEventListener("click", async () => {
    try {
      await api("/api/history", { method: "DELETE" });
      el.stream.innerHTML = "";
      closeSheet();
      toast("Chat history cleared");
    } catch {
      toast("Could not clear history");
    }
  });

  el.voiceToggle.addEventListener("click", () => {
    state.voice = !state.voice;
    store.set("jarvis.voice", String(state.voice));
    el.voiceToggle.textContent = state.voice ? "Voice output on" : "Voice output off";
    el.voiceToggle.setAttribute("aria-pressed", String(state.voice));
    if (!state.voice) speechSynthesis.cancel();
  });

  el.railToggle.addEventListener("click", () => el.rail.classList.toggle("is-open"));
  el.stream.addEventListener("click", () => el.rail.classList.remove("is-open"));

  /* ──────────────────────────── start-up ───────────────────────── */

  async function restoreHistory() {
    try {
      const history = await api("/api/history?limit=30");
      history.forEach((m) => addMessage(m.role === "user" ? "user" : "jarvis", m.content));
      return history.length;
    } catch {
      return 0;
    }
  }

  async function boot() {
    el.voiceToggle.textContent = state.voice ? "Voice output on" : "Voice output off";
    el.voiceToggle.setAttribute("aria-pressed", String(state.voice));

    try {
      const health = await api("/api/health");
      setLink(true, "Core link stable");
      el.modelTag.textContent = `${health.ai.provider} · ${health.ai.model || "—"}`;

      if (!health.ai.ok) {
        addMessage("jarvis", `Model not ready: ${health.ai.detail}`, true);
      }

      el.mastheadSub.textContent =
        `Online · ${health.memory.tasks_open} open tasks · ${health.memory.notes} notes`;

      el.stream.innerHTML = "";
      const restored = await restoreHistory();
      if (!restored) {
        addMessage(
          "jarvis",
          "Systems online. Ask me anything, or try a command: add task, " +
            "schedule a meeting, note something down, or check the weather."
        );
      }

      loadAllPanels();
      loadWeather();
    } catch {
      setLink(false, "Core offline");
      el.modelTag.textContent = "offline";
      el.mastheadSub.textContent = "Backend unreachable";
      el.stream.innerHTML = "";
      addMessage(
        "jarvis",
        `No response from ${state.api}. Start the backend with "python app.py" ` +
          `in the backend folder, then reload. If you deployed it, set the address ` +
          `under Settings.`,
        true
      );
      loadAllPanels();
    }
  }

  tickClock();
  setInterval(tickClock, 20000);
  setInterval(() => {
    if (state.online) {
      loadPanel(state.activePanel);
    }
  }, JARVIS_CONFIG.REFRESH_INTERVAL);

  boot();
  el.input.focus();
})();

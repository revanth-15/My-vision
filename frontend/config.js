/* JARVIS — frontend configuration.
   The only file you edit when you deploy. */

const JARVIS_CONFIG = {
  // Local development. After deploying, change this to your Render URL,
  // e.g. "https://jarvis-backend-xxxx.onrender.com"
  API_BASE: "http://localhost:5000",

  // Speak replies aloud by default.
  VOICE_OUTPUT: true,

  // Speech synthesis tuning. Lower pitch reads as more JARVIS.
  SPEECH_RATE: 1.02,
  SPEECH_PITCH: 0.85,

  // Preferred voice names, tried in order. Falls back to the system default.
  VOICE_PREFERENCES: [
    "Google UK English Male",
    "Microsoft Ryan",
    "Microsoft George",
    "Daniel",
    "Arthur",
  ],

  // Speech recognition language.
  RECOGNITION_LANG: "en-US",

  // How often to refresh the side panels, in milliseconds.
  REFRESH_INTERVAL: 45000,
};

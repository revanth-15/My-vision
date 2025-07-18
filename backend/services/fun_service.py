"""
JARVIS — fun & information service.

Free public APIs with local fallbacks, so nothing here ever hard-fails just
because a third party is down.
"""

import random

import requests

TIMEOUT = 8

FALLBACK_JOKES = [
    "I would tell you a UDP joke, but you might not get it.",
    "There are two hard problems in computer science: cache invalidation, "
    "naming things, and off-by-one errors.",
    "A SQL query walks into a bar, approaches two tables and asks, "
    "may I join you?",
    "I told my computer I needed a break. It said: no problem, I will go to sleep.",
    "Debugging is being the detective in a crime film where you are also the murderer.",
]

FALLBACK_QUOTES = [
    ("Simplicity is the ultimate sophistication.", "Leonardo da Vinci"),
    ("The best way out is always through.", "Robert Frost"),
    ("Make it work, make it right, make it fast.", "Kent Beck"),
    ("It always seems impossible until it is done.", "Nelson Mandela"),
    ("Perfection is achieved when there is nothing left to take away.",
     "Antoine de Saint-Exupéry"),
]

FALLBACK_FACTS = [
    "Honey never spoils. Edible jars have been found in Egyptian tombs.",
    "Octopuses have three hearts, and two of them stop when the animal swims.",
    "The first computer bug was a literal moth, taped into a logbook in 1947.",
    "A day on Venus is longer than a year on Venus.",
    "Bananas are berries. Strawberries are not.",
]

TIPS = [
    "Work in 25 minute blocks with a 5 minute break. Four blocks, then a long break.",
    "Decide tomorrow's first task before you close the laptop today.",
    "If it takes under two minutes, do it now rather than writing it down.",
    "Batch your shallow work. Email twice a day beats email all day.",
    "Put your phone in another room. Distance beats willpower.",
    "Start with the task you are avoiding. Everything after it feels easy.",
    "Name your task as a verb: 'draft the intro', not 'report'.",
]


class FunService:
    def __init__(self, config):
        self.config = config

    # ----------------------------------------------------------------- joke
    def joke(self) -> str:
        try:
            resp = requests.get(
                "https://official-joke-api.appspot.com/random_joke", timeout=TIMEOUT
            )
            resp.raise_for_status()
            data = resp.json()
            return f"{data['setup']} ... {data['punchline']}"
        except Exception:
            return random.choice(FALLBACK_JOKES)

    # ---------------------------------------------------------------- quote
    def quote(self) -> str:
        try:
            resp = requests.get("https://zenquotes.io/api/random", timeout=TIMEOUT)
            resp.raise_for_status()
            item = resp.json()[0]
            return f"{item['q']} — {item['a']}"
        except Exception:
            text, author = random.choice(FALLBACK_QUOTES)
            return f"{text} — {author}"

    # ----------------------------------------------------------------- fact
    def fact(self) -> str:
        try:
            resp = requests.get(
                "https://uselessfacts.jsph.pl/api/v2/facts/random?language=en",
                timeout=TIMEOUT,
            )
            resp.raise_for_status()
            return resp.json()["text"]
        except Exception:
            return random.choice(FALLBACK_FACTS)

    # ------------------------------------------------------------------ tip
    def tip(self) -> str:
        return random.choice(TIPS)

    # ------------------------------------------------------------ headlines
    def headlines(self, limit=5) -> str:
        """Uses NewsAPI if a key is configured, otherwise says so plainly."""
        if not self.config.NEWS_API_KEY:
            return (
                "No news source is configured. Add a free NEWS_API_KEY from "
                "newsapi.org to backend/.env and I will read you the headlines."
            )
        try:
            resp = requests.get(
                "https://newsapi.org/v2/top-headlines",
                params={
                    "country": self.config.NEWS_COUNTRY,
                    "pageSize": limit,
                    "apiKey": self.config.NEWS_API_KEY,
                },
                timeout=TIMEOUT,
            )
            resp.raise_for_status()
            articles = resp.json().get("articles", [])
            if not articles:
                return "No headlines came back from the news service."
            lines = [
                f"{i}. {a['title']} ({a['source']['name']})"
                for i, a in enumerate(articles[:limit], start=1)
            ]
            return "Top headlines:\n" + "\n".join(lines)
        except Exception:
            return "I could not reach the news service just now."

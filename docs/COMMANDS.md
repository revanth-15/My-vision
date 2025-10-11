# Command reference

Anything not listed here is answered by the language model. Matching is
case-insensitive.

## Tasks
| Say | Result |
|---|---|
| `add task <text>` / `create task <text>` / `new task <text>` | Creates a task |
| `remind me to <text>` / `i need to <text>` / `todo: <text>` | Creates a task |
| `show my tasks` / `list tasks` / `what are my tasks` | Open tasks |
| `show all tasks` | Includes completed |
| `complete task <id or words>` / `finish <words>` / `done with <words>` | Closes it |
| `delete task <id>` | Removes it |

Add `urgent`, `asap`, `important` or `critical` anywhere for high priority.
Add `low priority`, `whenever` or `someday` for low.

## Calendar
| Say | Result |
|---|---|
| `schedule <text>` / `add event <text>` / `book <text>` / `meeting <text>` | Creates an event |
| `show my calendar` / `my schedule` / `what's on` / `agenda` | Lists events |

## Notes
| Say | Result |
|---|---|
| `note <text>` / `create note <text>` / `note down <text>` | Saves a note |
| `remember that <text>` | Saves a note |
| `show my notes` / `list notes` | Lists them |

Use a colon to split title from body: `note Groceries: milk, eggs, bread`.

## Reminders
| Say | Result |
|---|---|
| `set a reminder <text>` | Creates a timed reminder |
| `show my reminders` | Lists active ones |

## Dates and times understood
`today`, `tonight`, `tomorrow`, `day after tomorrow`,
`in 3 days`, `in 2 weeks`, `in 4 hours`,
`monday` … `sunday` (next occurrence), `2026-09-15`,
`at 5pm`, `at 14:30`, `5:30 pm`

No time given on a task or event defaults to 09:00.

## Information
| Say | Result |
|---|---|
| `what's the weather` / `weather in Berlin` / `forecast` | Current conditions |
| `news` / `headlines` | Top stories (needs NEWS_API_KEY) |
| `tell me a joke` | A joke |
| `give me a quote` / `inspire me` | A quote |
| `fun fact` / `random fact` | A fact |
| `productivity tip` / `focus tip` | A tip |

## System
| Say | Result |
|---|---|
| `hello` / `hi` / `good morning` | Greeting plus open task count |
| `what time is it` / `what's the date` | Current time and date |
| `status` / `diagnostics` / `stats` | Memory and database report |
| `help` / `what can you do` | Command summary |
| `clear the conversation` | Wipes chat history, keeps your data |

## Preferences
| Say | Result |
|---|---|
| `my name is <name>` / `call me <name>` | JARVIS uses that name from then on |
| `i live in <city>` / `set my city to <city>` | Default city for weather |

## Adding your own
Open `backend/services/command_service.py`. Write a method that returns
`self._ok(reply, action, data)` on a match and `None` otherwise, then add it
to the tuple inside `handle()`. Order matters — the first match wins.

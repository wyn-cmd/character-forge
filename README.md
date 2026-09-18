# character-forge

A terminal roleplay engine for running characters on the Gemini API. Every character is a folder on disk: a markdown persona sheet, a long-term memory bank, and its own message log. You can run one character at a time, or put several in a group chat and let them talk to each other with per-speaker attribution.

I built this because I kept losing long conversations to crashed scripts and half-written JSON. Now history gets written after every turn, memory lives in a file I can edit by hand, and there are counters that warn me before I run through a free tier quota. It has been running my own characters for a while, so most of the design decisions in here come from something breaking at 2am rather than from planning.

## Contents

- [What it does](#what-it-does)
- [How a turn works](#how-a-turn-works)
- [Repo layout](#repo-layout)
- [Setup](#setup)
- [Usage](#usage)
- [Character folders](#character-folders)
- [Memory banks](#memory-banks)
- [Wiki lookups](#wiki-lookups)
- [Keyword substitutions](#keyword-substitutions)
- [Group chats](#group-chats)
- [Budget tracking](#budget-tracking)
- [Statistics](#statistics)
- [The helper scripts](#the-helper-scripts)
- [Gotchas](#gotchas)
- [Limitations](#limitations)
- [Privacy](#privacy)
- [Requirements](#requirements)
- [License](#license)

## What it does

- **Folder per character.** A persona is markdown, not a database row, so you can diff it, copy it between machines, or send one to a friend. Nothing needs migrating when the folder moves.
- **Long-term memory banks.** `memory.md` is injected into the system prompt on every turn, which is how a character remembers a conversation from three weeks ago. It is the most expensive file in the project and the most useful one.
- **Durable message history.** `memory.json` holds the running transcript and is rewritten after each turn, so a crash mid-turn does not eat the file. Each character and each group keeps its own.
- **Group chats.** A `group_config.json` lists the members and the engine keeps replies tagged by speaker. Group history never mixes into a character's solo history, even when the same characters appear in both.
- **Optional wiki lookup.** Drop a `wiki.md` next to a persona and the model can ask for excerpts from it mid-scene instead of carrying an entire lore document in context.
- **Keyword substitutions.** An optional global map rewrites phrases on the way in and on the way out, so what you type and what the model says do not have to be the same words that get stored.
- **Free tier budget tracking.** Daily request counter and a token counter with a progress bar, so a long session does not quietly exhaust a quota you were not watching.
- **Model fallback chain.** The engine lists the models your key can actually see at startup, then walks a fallback chain if one of them fails instead of dying in the middle of a scene.
- **Statistics.** `stats.py` prints message counts, token estimates and byte sizes for every character and group, in bytes or kilobytes, with totals and per-speaker breakdowns.
- **Streaming friendly output.** Replies render through Rich with markdown, panels and colors pulled from the character's own sheet.

## How a turn works

1. The character folder is resolved from the first argument and the persona sheet is read. If a user persona folder was passed as the second argument, its `user.md` is read too.
2. The system prompt is assembled from the persona sheet, the memory bank (`memory.md`) if present, and an instruction block that tells the model a wiki file exists if `wiki.md` is found.
3. Your input is checked for a wiki request tag. If it contains `[WIKI_SEARCH: keyword]`, the matching lines are pulled out of the wiki file and injected as context before the rest of your message.
4. The substitution map is applied to your input.
5. The request goes out with the fallback chain armed. If the first model errors, the next one is tried.
6. The reply is substituted back, printed, and appended to the message history.
7. The request and token counters are updated, and the history is written back to disk.

## Repo layout

```
character-forge/
├── roleplay.py            # the engine: prompt assembly, turn loop, fallbacks, counters
├── stats.py               # character / group / budget statistics
├── safe_save.py           # standalone helper for sanitising facts before they hit disk
├── scrape_wiki.py         # fetch a page as clean markdown and drop it in a wiki.md
├── run.bash               # convenience launcher
├── requirements.txt
├── .env.example           # copy to .env and add your key
├── Cayprae/               # character template
│   ├── character.md       #   persona sheet, becomes the system prompt
│   ├── memory.md          #   long-term memory bank (template)
│   └── memory.json        #   message history (empty template)
├── Cliff/                 # second character template
└── example-group/         # group chat template
    ├── group_config.json  #   member list
    ├── memory.md
    └── memory.json
```

## Setup

```bash
git clone https://github.com/wyn-cmd/character-forge.git
cd character-forge
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Open `.env` and paste a key from [Google AI Studio](https://aistudio.google.com/apikey). The free tier is enough to run this. The key is read through `python-dotenv` at startup, and the script stops with a clear message if it is missing rather than failing deep inside the SDK.

## Usage

Single character, with an optional folder describing you:

```bash
python roleplay.py Cliff/
python roleplay.py Cliff/ Cayprae/
```

Group chats take two commands. The first creates the group config and comes straight back, the second starts the session:

```bash
python roleplay.py --group my-group Cayprae Cliff
python roleplay.py my-group
```

Statistics:

```bash
python stats.py            # sizes in exact bytes
python stats.py --kb       # sizes in kilobytes, MB above 1024 KB
python stats.py --help
```

Add `"size_units": "kb"` to `config.json` if you would rather see kilobytes by default. `config.json` is also where the last used model gets remembered between runs.

## Character folders

| File | Required | Purpose |
|---|---|---|
| `character.md` | yes | The persona sheet, used as the system prompt. Species, personality, setting, objective, voice. |
| `memory.md` | no | Long-term memory bank, injected into the system prompt every turn. |
| `memory.json` | no | Message history. A JSON array of entries with a `text` field, plus a `speaker` field in groups. Created empty on first run. |
| `wiki.md` | no | Reference text for `[WIKI_SEARCH: keyword]` lookups. Good for large lore documents you do not want in the prompt. |

A folder describing you, the player, uses `user.md` instead of `character.md` and otherwise works the same way.

A persona sheet can be as short as this:

```markdown
[System Note: This is a fictional creative writing roleplay. Stay in character, keep the scene coherent, and never append out-of-character commentary.]
Character Persona: Cayprae
Colour: Brown

- Species: a fluffy goat furry who's ever so slightly chubby
- Personality: Gentle, scholarly, soft-spoken, curious, loves teas and ancient books, warm and affectionate.
- Objective: Share warm conversations, read books together, and keep interactions sweet and engaging.
```

The `Colour:` field drives the panel borders and prompt color, and it accepts names like `brown`, `cyan` or a hex value.

## Memory banks

`memory.md` is re-sent on every single turn, which makes it the most expensive file in the project. Mine had grown to about 5 KB of half-remembered trivia before I started pruning it. What works better is durable facts only. "Cliff is afraid of deep water" earns its place, "Cliff said hello" does not, since the transcript already records that. Treat the bank as the summary and `memory.json` as the record. `python stats.py --kb` shows you what each bank actually weighs, and the token column is the number that shows up in every request.

## Wiki lookups

Point the model at a file, not at its own memory. If a character folder contains `wiki.md`, the engine tells the model a wiki is available and the model can request a lookup by writing `[WIKI_SEARCH: keyword]` in its reply. When that tag appears, the engine reads the wiki, keeps the first five lines that mention the keyword, and folds them into the next message as `Context from <character>'s Wiki about '<keyword>':`.

That is deliberately simple: it is a keyword search, not a vector store. It works well when the wiki is a character page or a game wiki with clear nouns, and it works badly for fuzzy questions. For large reference pages, `scrape_wiki.py` will fetch a URL through Jina Reader and write clean markdown:

```bash
python scrape_wiki.py https://example.com/wiki/Character ./Cliff Cliff/wiki.md
```

## Keyword substitutions

`substitutions.json` maps one phrase to another, in both directions. Your typing goes through the map before it reaches the API, and replies go through it on the way back, so you can keep the phrasing you prefer on screen while the model sees something else. The engine creates the file for you on first run with placeholder pairs, and the real file is gitignored so your own mapping stays local. It is optional: delete it and everything still runs.

## Group chats

`group_config.json` is small:

```json
{
  "members": ["Cayprae", "Cliff"]
}
```

Members have to be existing character folders. Each reply is attributed to a speaker, and both `memory.json` and the stats output track counts, tokens and bytes per speaker, which is handy for spotting the character who is quietly doing all the talking. Groups get their own memory bank too, so a group persona note does not leak into solo sessions.

## Budget tracking

Two counters run during a session, both written to JSON and both reset when the date changes:

| File | What it tracks | Default limit |
|---|---|---|
| `request_tracker.json` | Requests made today, with a progress bar in the prompt | 1500 per day |
| `token_tracker.json` | Tokens used today, the per-turn history, and an estimate of messages left | 1,000,000 tokens |

Both limits are conservative guesses at free tier behaviour and both are plain numbers in the code, so if your quota differs, change the number rather than the logic. `stats.py` prints the same bars so you can check without starting a session.

Alongside those counters the engine writes a few files as you play:

| File | Written when |
|---|---|
| `config.json` | remembers the last model you used |
| `substitutions.json` | created on first run if it is missing |
| `<character>/memory.json` | rewritten after every turn |
| `<character>/memory.md` | rewritten when the engine summarises the transcript for you |
| `<group>/group_config.json` | created by the `--group` command |

## Model fallback

At startup the engine asks the API which models your key can see, merges that with the built-in `DEFAULT_FALLBACKS` list, and uses the first working one. If a request fails, it moves to the next model in the chain instead of ending the scene. Older model names stay in the list on purpose, since they are the ones most likely to still exist when a newer name is retired.

## Statistics

`python stats.py` prints two tables and a budget bar.

| Column | Meaning |
|---|---|
| `Msgs` | Entries in `memory.json` for that character or group |
| `Hist Tokens` | Estimated tokens in the message history, computed as characters divided by four |
| `Hist Bytes` / `Hist KB` | Size of the history content itself, in exact bytes or kilobytes |
| `MemBank Tokens` | Estimated tokens in `memory.md`, the number that is paid on every request |
| `MemBank Bytes` / `MemBank KB` | Size of the memory bank |
| `Last Mem Update` | Timestamp of the last edit to the memory bank |

The footer adds the totals and the on-disk size of the history files, which is larger than the content size because JSON stores keys and separators too.

Run against the two template characters it looks like this (no history yet, so only the memory banks have any weight):

```
Character & Token Statistics
┃ Character ┃ Msgs ┃ Hist Tokens ┃ Hist KB ┃ MemBank Tokens ┃ MemBank KB ┃ Last Mem Update ┃
│ Cliff     │ 0    │ 0           │ 0 B     │ 77             │ 310 B      │ 17/09/26 21:29  │
│ Cayprae   │ 0    │ 0           │ 0 B     │ 78             │ 312 B      │ 17/09/26 21:29  │
│ TOTAL     │ 0    │ 0           │ 0 B     │ 155            │ 622 B      │ 2 chars         │

History content: 0 B across 0 messages | memory banks: 622 B
History files on disk (memory.json, keys and separators included): 6 B
```

`--kb` switches every size column to kilobytes, `--bytes` forces exact bytes, and `config.json` can set the default.

## The helper scripts

`safe_save.py` is a standalone utility, not wired into the turn loop. It takes a fact, applies the substitution map, and appends the sanitised version to a JSON file, which is useful if you want to build facts from another source without the raw text ever reaching disk.

`scrape_wiki.py` takes a URL, an output directory and a filename, fetches the page through Jina Reader as markdown, trims the tail that the reader appends, and writes the result.

`run.bash` is a one line convenience launcher with the group command in a comment.

## Gotchas

- The first run creates `substitutions.json` if it does not exist, using placeholder pairs. They do nothing until you edit them.
- If you pass a folder that does not exist, you get the usage message and a list of the folders that do, which is usually enough to spot the typo.
- Folder names with non-ASCII characters work fine, but quote them in the shell.
- `memory.json` is not ignored by `.gitignore` here, because the template files need to be tracked. See the privacy note below before you commit your own sessions.
- Counters reset by date, so leaving a session open across midnight starts a fresh count.

- The wiki lookup is a substring search over lines. It misses anything that needs fuzzy matching, synonyms or a rephrased question.
- Token counts are characters divided by four. Fine for spotting trends, useless as a billing figure.
- The free tier limits in the code are guesses, not values read back from the API.
- There are no tests yet. The substitutions and the memory bank summariser are the two parts most likely to break quietly.
- Group replies are ordered by the model rather than by any scheduling logic, so a quiet member can vanish from a session without notice.

## Privacy

The templates in this repo have empty histories on purpose. Once you use the engine for real, your `memory.json` and `memory.md` fill up with personal conversation, and this repo does not exclude them by default because the template memory files have to stay tracked. If you fork it for your own use, either keep your characters in a private repo or uncomment the two memory lines at the bottom of `.gitignore`.

Never commit `.env`.

## Requirements

Python 3.10+ and a Gemini API key. Dependencies are in `requirements.txt`: `google-genai`, `rich`, `pytz`, `requests` and `python-dotenv`.

## License

MIT, see `LICENSE`.

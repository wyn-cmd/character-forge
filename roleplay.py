import os
import sys
import json
import shutil
import re
import time
import datetime
import random
from google import genai
from google.genai import types
from dotenv import load_dotenv
from rich.console import Console
from rich.markdown import Markdown
from rich.rule import Rule
from rich.panel import Panel

console = Console()

load_dotenv()  # GEMINI_API_KEY lives in .env (gitignored)

CONFIG_FILE = "config.json"
DEFAULT_FALLBACKS = [
    "gemini-3.1-flash-lite",
    "gemini-2.5-flash-lite",
    "gemini-2.0-flash-exp",
    "gemini-1.5-pro",
    "gemini-1.5-flash",
    "gemini-1.5-flash-8b",
    "gemini-3.8-flash",
    "gemini-3.7-flash",
    "gemini-3.6-flash",
    "gemini-2.5-flash"
]

# Initialize client early to fetch models dynamically on startup
if not os.environ.get("GEMINI_API_KEY"):
    console.print("[red]GEMINI_API_KEY is not set. Copy .env.example to .env and add your key.[/red]")
    raise SystemExit(1)

client = genai.Client()

fetched_models = []
try:
    for m in client.models.list():
        name = m.name.replace("models/", "")
        if ("flash" in name or "pro" in name) and not any(x in name for x in ["tts", "image", "embed", "audio", "transcribe", "veo", "lyria", "robotics", "omni", "preview"]):
            fetched_models.append(name)
except Exception as e:
    console.print(f"[yellow]Could not fetch dynamic model list: {e}. Using defaults.[/yellow]")

FALLBACK_MODELS = []
last_working = DEFAULT_FALLBACKS[0]
if os.path.exists(CONFIG_FILE):
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            cfg = json.load(f)
            last_working = cfg.get("last_model", DEFAULT_FALLBACKS[0])
    except:
        pass

for m in [last_working] + fetched_models + DEFAULT_FALLBACKS:
    if m and m not in FALLBACK_MODELS:
        FALLBACK_MODELS.append(m)

MODEL_NAME = FALLBACK_MODELS[0]

if len(sys.argv) > 1 and sys.argv[1] == "--group":
    if len(sys.argv) < 4:
        print("Usage: python roleplay.py --group <GroupName> <Char1> <Char2> ...")
        sys.exit(1)
    g_name = sys.argv[2]
    g_members = sys.argv[3:]
    os.makedirs(g_name, exist_ok=True)
    cfg_path = os.path.join(g_name, "group_config.json")
    with open(cfg_path, "w", encoding="utf-8") as f:
        json.dump({"members": g_members}, f, indent=2)
    print(f"Group '{g_name}' created successfully with members: {g_members}")
    sys.exit(0)

if len(sys.argv) < 2:
    console.print("[bold red]Error: Please specify a character to chat with![/bold red]")
    console.print("Usage: [cyan]python roleplay.py <CharacterFolder> [UserPersonaFolder][/cyan]")
    
    subdirs = [d for d in os.listdir(".") if os.path.isdir(d) and d not in [".git", "__pycache__", ".venv"]]
    if subdirs:
        console.print(f"Available folders: [green]{', '.join(subdirs)}[/green]")
    sys.exit(1)


def get_safe_color(col, fallback="#00ffff"):
    if not col:
        return fallback
    col = col.strip().lower()
    mapping = {
        "silver": "#C0C0C0",
        "amber": "#FFB000",
        "gold": "#FFD700",
        "orange": "#FFA500",
        "red": "#FF4500",
        "green": "#00FF00",
        "blue": "#0000FF",
        "cyan": "#00FFFF",
        "magenta": "#FF00FF",
        "yellow": "#FFFF00",
        "brown": "#A52A2A",
        "purple": "#800080",
        "pink": "#FFC0CB"
    }
    if col.startswith("#"):
        return col
    return mapping.get(col, fallback)

ai_profile = sys.argv[1]
user_profile = sys.argv[2] if len(sys.argv) > 2 else None

AI_DIR = ai_profile
CHARACTER_FILE = os.path.join(AI_DIR, "character.md")
MEMORY_FILE = os.path.join(AI_DIR, "memory.json")
MEMORY_BANK_FILE = os.path.join(AI_DIR, "memory.md")
GLOBAL_SUBS_FILE = "substitutions.json"

if not os.path.exists(AI_DIR):
    os.makedirs(AI_DIR, exist_ok=True)
    console.print(f"[yellow]AI profile folder '{AI_DIR}' not found. Creating it...[/yellow]")
    if os.path.exists("character.md"):
        shutil.copy("character.md", CHARACTER_FILE)
    else:
        with open(CHARACTER_FILE, "w", encoding="utf-8") as f:
            f.write("# Character Persona: " + AI_DIR + "\nColour: Cyan\n- **Personality:** Immersive roleplay partner.")
    if os.path.exists(MEMORY_FILE):
        pass
    else:
        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump([], f)
    # Since it's a new or empty session, full_history is empty
    full_history = []
    console.print(f"[dim magenta]🧠 Generating character summary for {character_name} using {MODEL_NAME}... (owo)[/dim magenta]")
    try:
        summary_prompt = (
            f"You are an expert narrative architect. Read the character profile below and provide a concise, engaging summary of {character_name}, "
            "detailing their name, appearance, personality, and setting in a rich, immersive narrative overview.\n\n"
            f"Character Profile:\n{character_prompt}"
        )
        resp = client.models.generate_content(
            model=MODEL_NAME,
            contents=summary_prompt
        )
        summary_text = resp.text.strip() if resp and hasattr(resp, "text") and resp.text else f"**{character_name}**\n\n{character_prompt}"
    except Exception as e:
        summary_text = f"**{character_name}**\n\n{character_prompt}"
        
    console.print(Panel(Markdown(summary_text), title=f"[bold {character_color}]{character_name}[/bold {character_color}]", title_align="left", border_style=character_color, padding=(1, 2)))
    console.print("")

if not os.path.exists(GLOBAL_SUBS_FILE):
    # keyword rewrites applied to model output, swap these for your own pairs
    default_subs = {
        "example_phrase": "replacement_phrase",
        "another_phrase": "something_else"
    }
    with open(GLOBAL_SUBS_FILE, "w", encoding="utf-8") as f:
        json.dump(default_subs, f, indent=2)

spicy_to_safe = {}
if os.path.exists(GLOBAL_SUBS_FILE):
    try:
        with open(GLOBAL_SUBS_FILE, "r", encoding="utf-8") as f:
            spicy_to_safe = json.load(f)
        console.print(f"[dim]Loaded {len(spicy_to_safe)} global keyword substitutions from {GLOBAL_SUBS_FILE}[/dim]")
    except Exception as e:
        console.print(f"[yellow]Could not load substitutions.json: {e}[/yellow]")

safe_to_spicy = {v.lower(): k for k, v in spicy_to_safe.items()}

# 1. Load AI Character Description & Parse Name / Color
character_name = ai_profile
character_color = "cyan"
character_prompt = ""

is_group = False
group_members = []
group_config_path = os.path.join(AI_DIR, "group_config.json")
if os.path.exists(group_config_path):
    is_group = True
    try:
        with open(group_config_path, "r", encoding="utf-8") as f:
            g_data = json.load(f)
            group_members = g_data.get("members", [])
    except:
        pass

if is_group:
    character_name = ai_profile
    character_color = "magenta"
    character_prompt = f"You are managing a group chat group named {ai_profile} consisting of members: {', '.join(group_members)}."
    console.print(f"[bold green]Loaded Group Chat: {ai_profile} with members {group_members} (o_O)[/bold green]")
elif os.path.exists(CHARACTER_FILE):
    with open(CHARACTER_FILE, "r", encoding="utf-8") as f:
        character_prompt = f.read()
        
    for line in character_prompt.splitlines():
        if "colour:" in line.lower() or "color:" in line.lower():
            parts = line.split(":")
            if len(parts) > 1:
                col = parts[1].strip().lower()
                if col:
                    character_color = get_safe_color(col, "cyan")
        if "character persona:" in line.lower() or line.startswith("# "):
            if ":" in line:
                parts = line.split(":")
                if len(parts) > 1 and len(parts[1].strip()) > 0:
                    character_name = parts[1].strip()
            elif line.startswith("# "):
                character_name = line.replace("#", "").strip()

    console.print(f"[bold green]Loaded AI persona from {CHARACTER_FILE} ({character_name}) (^V^)[/bold green]")
else:
    character_prompt = "You are a helpful, immersive roleplay partner."

# 2. Load User Persona from user_profile folder if provided
user_prompt = ""
user_display_name = "You"
user_color = "blue"

if user_profile and os.path.exists(user_profile):
    user_char_file = os.path.join(user_profile, "character.md")
    user_md_file = os.path.join(user_profile, "user.md")
    
    target_user_file = user_char_file if os.path.exists(user_char_file) else (user_md_file if os.path.exists(user_md_file) else None)
    
    if target_user_file and os.path.exists(target_user_file):
        with open(target_user_file, "r", encoding="utf-8") as f:
            user_prompt = f.read()
            
        for line in user_prompt.splitlines():
            if "colour:" in line.lower() or "color:" in line.lower():
                parts = line.split(":")
                if len(parts) > 1:
                    col = parts[1].strip().lower()
                    if col:
                        user_color = get_safe_color(col, "blue")
            if "name:" in line.lower() or "persona:" in line.lower() or line.startswith("# "):
                if ":" in line:
                    parts = line.split(":")
                    if len(parts) > 1 and len(parts[1].strip()) > 0:
                        user_display_name = parts[1].strip()
                elif line.startswith("# "):
                    user_display_name = line.replace("#", "").strip()

        console.print(f"[bold {user_color}]Loaded user persona from folder '{user_profile}' ({user_display_name}) (O_O)[/bold {user_color}]")
else:
    root_user = "user.md"
    if os.path.exists(root_user):
        with open(root_user, "r", encoding="utf-8") as f:
            user_prompt = f.read()
        user_display_name = user_profile or "You"
        console.print(f"[bold blue]Loaded root user.md ({user_display_name})[/bold blue]")

# Combine system instructions + RAG-lite memory.md + wiki.md if available
system_prompt = character_prompt
system_prompt += "\n\nCRITICAL NARRATIVE INSTRUCTION: Adopt a high-literary, impressionistic style. Use abstract, poetic language and focus on sensory metaphors. Prioritize atmosphere and emotional resonance over explicit physical detail. Favor subtext and artistic expression. BE HIGHLY DESCRIPTIVE AND ELABORATE IN YOUR RESPONSES. PROVIDE EXTENSIVE DETAIL, LENGTHY NARRATIVE BLOCKS, AND DEEP SENSORY IMAGERY IN EVERY TURN. MAINTAIN THE EMPHASIS ON SUBTEXT AND ARTISTIC EXPRESSION THROUGHOUT YOUR NARRATIVE."

if user_prompt:
    system_prompt += f"\n\n--- User Persona ---\nThe user interacting with you is playing as the following character:\n{user_prompt}"

# Check for wiki.md and add knowledge access instructions
WIKI_FILE = os.path.join(AI_DIR, "wiki.md")
if os.path.exists(WIKI_FILE):
    system_prompt += (
        "\n\n--- Knowledge Access ---\n"
        "You have access to a local character wiki file (wiki.md). If you need specific information, "
        "output the tag '[WIKI_SEARCH: keyword]' and the system will provide the relevant details from the wiki. "
        "Use this sparingly for deep lore retrieval only."
    )
    console.print(f"[cyan]✨ Knowledge Access enabled: wiki.md found for {character_name}! ✨[/cyan]")

if os.path.exists(MEMORY_BANK_FILE):
    try:
        with open(MEMORY_BANK_FILE, "r", encoding="utf-8") as ff:
            mb_content = ff.read()
            if mb_content:
                system_prompt += f"\n\n--- Long-Term Memory Bank (memory.md) ---\n{mb_content}"
        console.print(f"[cyan]Loaded memory bank from {MEMORY_BANK_FILE} ✨[/cyan]")
    except Exception as e:
        console.print(f"[yellow]Could not load memory.md: {e}[/yellow]")

# 3. Load Full Persistent Memory / Chat History from disk
full_history = []
if os.path.exists(MEMORY_FILE):
    try:
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            full_history = json.load(f)
        if isinstance(full_history, list):
            sanitized = []
            for item in full_history:
                if isinstance(item, dict) and "role" in item and "text" in item:
                    sanitized.append(item)
                elif isinstance(item, str):
                    sanitized.append({"role": "user", "text": item})
            full_history = sanitized
        else:
            full_history = []
        console.print(f"[cyan]Loaded full chat history from {MEMORY_FILE} ({len(full_history)} total messages recorded) ✨[/cyan]")
        
        # Show last 2 messages
        if len(full_history) >= 2:
            console.print("\n[dim]--- Last 2 messages in memory ---[/dim]")
            for entry in full_history[-2:]:
                if not isinstance(entry, dict):
                    continue
                role = entry.get("role", "user")
                text = entry.get("text", str(entry))
                # Convert safe words back to spicy words for display
                for safe_word, spicy_word in safe_to_spicy.items():
                    pattern = re.compile(re.escape(safe_word), re.IGNORECASE)
                    text = pattern.sub(spicy_word, text)
                
                name = user_display_name if role == "user" else character_name
                color = user_color if role == "user" else character_color
                console.print(f"[bold {color}][{name}]:[/bold {color}] {text}")
            console.print("[dim]------------------------------------[/dim]\n")
            
    except Exception as e:
        console.print(f"[red]Could not load memory file: {e}. Starting fresh.[/red]")


REQUEST_TRACKER_FILE = "request_tracker.json"

import pytz
import datetime

def get_pacific_date():
    pacific_tz = pytz.timezone('US/Pacific')
    return datetime.datetime.now(pacific_tz).strftime("%d/%m/%y")

def check_and_update_requests():
    today_str = get_pacific_date()
    data = {"date": today_str, "requests_made": 0}
    
    if os.path.exists(REQUEST_TRACKER_FILE):
        try:
            with open(REQUEST_TRACKER_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except:
            pass
            
    if data.get("date") != today_str:
        data = {"date": today_str, "requests_made": 0}
        
    data["requests_made"] += 1
    with open(REQUEST_TRACKER_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    return data["requests_made"]

def get_request_bar():
    today_str = get_pacific_date()
    data = {"date": today_str, "requests_made": 0}
    if os.path.exists(REQUEST_TRACKER_FILE):
        try:
            with open(REQUEST_TRACKER_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except:
            pass
    
    # Refresh if day changed in Pacific time
    if data.get("date") != today_str:
        data = {"date": today_str, "requests_made": 0}
        
    count = data["requests_made"]
    limit = 1500
    pct = min(100.0, (count / limit) * 100.0)
    bar_width = 20
    filled = round(bar_width * (pct / 100.0))
    bar_str = "█" * filled + "░" * (bar_width - filled)
    return f"[{bar_str}] {pct:.1f}% ({count}/{limit})"

TOKEN_TRACKER_FILE = "token_tracker.json"

def check_and_update_tokens(turn_tokens):
    today_str = datetime.datetime.now().strftime("%d/%m/%y")
    data = {"date": today_str, "tokens_used": 0, "token_limit": 1000000, "recent_turns": []}
    
    if os.path.exists(TOKEN_TRACKER_FILE):
        try:
            with open(TOKEN_TRACKER_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except:
            pass
            
    saved_date_str = data.get("date", today_str)
    
    try:
        saved_date = datetime.datetime.strptime(saved_date_str, "%d/%m/%y").date()
        current_date = datetime.datetime.now().date()
        if current_date > saved_date:
            data["date"] = today_str
            data["tokens_used"] = 0
            data["recent_turns"] = []
    except Exception:
        data["date"] = today_str
        data["tokens_used"] = 0
        data["recent_turns"] = []
        
    if "recent_turns" not in data or not isinstance(data["recent_turns"], list):
        data["recent_turns"] = []

    if isinstance(turn_tokens, int) and turn_tokens > 0:
        data["tokens_used"] += turn_tokens
        data["recent_turns"].append(turn_tokens)
        if len(data["recent_turns"]) > 5:
            data["recent_turns"] = data["recent_turns"][-5:]
        
    with open(TOKEN_TRACKER_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        
    tokens_used = data["tokens_used"]
    token_limit = data["token_limit"]
    tokens_left = max(0, token_limit - tokens_used)
    recent = data["recent_turns"]
    
    est_msgs_left = "?"
    if len(recent) > 0:
        # Predictor: Handles linear or exponential-style growth trends
        avg_cost = sum(recent) / len(recent)
        
        if len(recent) >= 2:
            # Calculate deltas and proportional growth (ratios)
            deltas = [recent[i] - recent[i-1] for i in range(1, len(recent))]
            # Check for doubling (geometric) or constant growth (linear)
            ratios = [recent[i] / recent[i-1] for i in range(1, len(recent)) if recent[i-1] > 0]
            
            avg_delta = sum(deltas) / len(deltas)
            avg_ratio = sum(ratios) / len(ratios) if ratios else 1.0
            
            # Prediction: Use the stronger growth signal (Ratio vs Delta)
            # If ratio > 1.1, treat as exponential growth; otherwise linear
            if avg_ratio > 1.1:
                predicted_next_cost = recent[-1] * avg_ratio
            else:
                predicted_next_cost = recent[-1] + avg_delta
            
            # Future-looking projection: If we expect continued growth, 
            # the average cost over the remaining capacity is higher than the current average.
            # We estimate consumption by assuming the trend continues for the duration.
            avg_cost = (recent[-1] + predicted_next_cost) / 2
        
        avg_cost = max(100, avg_cost) # Safety Floor
        
        if avg_cost > 0:
            est_msgs_left = int(tokens_left / avg_cost)
            
    return tokens_used, token_limit, est_msgs_left, recent


def update_memory_bank(current_model):
    if not full_history:
        console.print("[yellow]No chat history to save yet! (OwO)[/yellow]")
        return

    dangerous_cat = types.HarmCategory.DANGEROUS_CONTENT if hasattr(types.HarmCategory, "DANGEROUS_CONTENT") else types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT
    safety_settings = [
        types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT, threshold=types.HarmBlockThreshold.BLOCK_NONE),
        types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_HARASSMENT, threshold=types.HarmBlockThreshold.BLOCK_NONE),
        types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH, threshold=types.HarmBlockThreshold.BLOCK_NONE),
        types.SafetySetting(category=dangerous_cat, threshold=types.HarmBlockThreshold.BLOCK_NONE),
    ]

    models_to_try = []
    for m in [current_model, "gemini-3.5-flash", "gemini-3.6-flash", "gemini-3.7-flash"]:
        if m and m not in models_to_try:
            models_to_try.append(m)

    for m in models_to_try:
        try:
            # Count the attempt as a request
            check_and_update_requests()
            time.sleep(2)
            console.print(f"[dim magenta]🧠 Updating memory.md using {m}... (owo)[/dim magenta]")
            
            # Build clean truncated history snippet using the last 30 messages
            turns_sample = []
            for entry in full_history[-30:]:
                role = entry["role"]
                txt = entry["text"][:300]
                turns_sample.append(f"{role}: {txt}")
            history_snippet = "\n".join(turns_sample)

            for spicy_word, safe_word in spicy_to_safe.items():
                pattern = re.compile(re.escape(spicy_word), re.IGNORECASE)
                history_snippet = pattern.sub(safe_word, history_snippet)

            # Read existing memory.md if available to evolve it
            existing_memory = ""
            if os.path.exists(MEMORY_BANK_FILE):
                try:
                    with open(MEMORY_BANK_FILE, "r", encoding="utf-8") as f:
                        existing_memory = f.read().strip()
                except:
                    pass

            prompt = (
                "You are an expert narrative architect. Update and evolve the existing memory bank in Markdown format (memory.md) using the provided new roleplay history snippet (the last 10 messages). "
                "Incorporate new developments while preserving key long-term facts, relationships, and lore from the existing memory bank.\n"
                "CRITICAL: Maintain a comprehensive list of ALL distinct locations visited or mentioned throughout the roleplay, not just the most recent one. Track the state and events associated with each location.\n"
                "Include sections like:\n"
                "- # Locations (Keep a detailed, persistent log of all locations)\n"
                "- # Relationships\n"
                "- # Major Plot Points\n"
                "- # Key Facts\n"
                "- # Secrets / Hidden Motivations\n"
                "Make it detailed, immersive, and structured so the AI can maintain continuity.\n"
                "Return ONLY the markdown content. Do not include introductory conversational filler."
            )
            if existing_memory:
                prompt += f"\n\nExisting Memory Bank (memory.md):\n{existing_memory}"
            prompt += f"\n\nNew History Snippet to Analyze:\n{history_snippet}"
            

            chat = client.chats.create(
                model=m,
                config=types.GenerateContentConfig(
                    temperature=0.7,
                    safety_settings=safety_settings
                )
            )
            resp = chat.send_message(prompt)
            
            # Track token usage for memory update
            usage = getattr(resp, "usage_metadata", None)
            total_tokens = usage.total_token_count if usage and hasattr(usage, "total_token_count") else 0
            if isinstance(total_tokens, int) and total_tokens > 0:
                check_and_update_tokens(total_tokens)

            text = resp.text.strip() if resp and hasattr(resp, "text") and resp.text else ""
            
            text = re.sub(r'^```markdown\s*', '', text)
            text = re.sub(r'^```\s*', '', text)
            text = re.sub(r'\s*```$', '', text)
            text = text.strip()
            
            if not text:
                console.print(f"[yellow]Model {m} returned empty response. Skipping update.[/yellow]")
                continue
            
            with open(MEMORY_BANK_FILE, "w", encoding="utf-8") as f:
                f.write(text)
            console.print("[dim green]✨ Successfully updated memory.md! ✨[/dim green]")
            return
        except Exception as e:
            console.print(f"[yellow]Error with model {m}: {e}[/yellow]")
            continue
            
    if not os.path.exists(MEMORY_BANK_FILE):
        with open(MEMORY_BANK_FILE, "w", encoding="utf-8") as f:
            f.write("# Memory Bank\n\n## Relationships\nActive roleplay partnership.\n\n## Key Facts\n- Session is active and saved.\n")
        console.print("[green]✨ Created baseline memory.md successfully! ✨[/green]")


def create_chat_session(model_name):
    # SLIDING WINDOW: Use only the last 40 messages for active model context
    MAX_WINDOW = 40
    recent_entries = full_history[-MAX_WINDOW:] if len(full_history) > MAX_WINDOW else full_history
    
    active_content = []
    for entry in recent_entries:
        if not isinstance(entry, dict):
            continue
        role = entry.get("role", "user")
        text = entry.get("text", str(entry))
        active_content.append(
            types.Content(
                role=role,
                parts=[types.Part.from_text(text=text)]
            )
        )
        
    return client.chats.create(
        model=model_name,
        history=active_content if active_content else None,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=0.85,
            safety_settings=[
                types.SafetySetting(
                    category=types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
                    threshold=types.HarmBlockThreshold.BLOCK_NONE,
                ),
                types.SafetySetting(
                    category=types.HarmCategory.HARM_CATEGORY_HARASSMENT,
                    threshold=types.HarmBlockThreshold.BLOCK_NONE,
                ),
                types.SafetySetting(
                    category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                    threshold=types.HarmBlockThreshold.BLOCK_NONE,
                ),
                types.SafetySetting(
                    category=types.HarmCategory.DANGEROUS_CONTENT if hasattr(types.HarmCategory, "DANGEROUS_CONTENT") else types.HarmCategory.HARM_CATEGORY_HATE_SPEECH, # fallback safely
                    threshold=types.HarmBlockThreshold.BLOCK_NONE,
                ),
            ],
        ),
    )

VERBOSE_MODE = False

console.print(f"\n[bold magenta]✨ Roleplay Active: [{user_display_name}] chatting with [{character_name}] (Discovered Models: {len(FALLBACK_MODELS)})! Type 'exit' to quit. ✨[/bold magenta]\n")

while True:
    try:
        console.print(Rule(style="dim magenta"))
        console.print(f"[bold {user_color}][{user_display_name}][/bold {user_color}] ", end="")
        user_input = input()

        if user_input.strip().lower() in ["exit", "quit", "/exit", "/quit", "/quit-clear"]:
            if user_input.strip().lower() == "/quit-clear":
                os.system('cls' if os.name == 'nt' else 'clear')
            
            console.print(Rule(style="dim magenta"))
            console.print("\n[bold green]Saving final history and updating long-term memory.md... Byeeeee! ( >w<)✨[/bold green]")
            if len(full_history) > 0:
                update_memory_bank(MODEL_NAME)
            break
            
        if user_input.strip().lower() == "/save":
            console.print(Rule(style="dim cyan"))
            console.print("[bold cyan]💾 Manually triggering memory.md memory bank update... (OwO)[/bold cyan]")
            if len(full_history) > 0:
                update_memory_bank(MODEL_NAME)
            else:
                console.print("[yellow]No history to save yet![/yellow]")
            continue
            
        if user_input.strip().lower() == "/history":
            console.print(Rule(style="dim cyan"))
            console.print(f"[bold cyan]📜 Full Chat History ({len(full_history)} messages):[/bold cyan]")
            for entry in full_history:
                role = entry["role"]
                text = entry["text"]
                # Convert safe words back to spicy words for display
                for safe_word, spicy_word in safe_to_spicy.items():
                    pattern = re.compile(re.escape(safe_word), re.IGNORECASE)
                    text = pattern.sub(spicy_word, text)
                
                if role == "user":
                    console.print(f"[bold {user_color}][{user_display_name}]:[/bold {user_color}] {text}")
                else:
                    console.print(f"[bold {character_color}][{character_name}]:[/bold {character_color}] {text}")
            console.print(Rule(style="dim cyan"))
            continue

        if user_input.strip().lower() == "/back":
            console.print(Rule(style="dim cyan"))
            if len(full_history) >= 2:
                removed_model = full_history.pop()
                removed_user = full_history.pop()
                with open(MEMORY_FILE, "w", encoding="utf-8") as f:
                    json.dump(full_history, f, indent=2, ensure_ascii=False)
                console.print(f"[bold yellow]Undid last exchange (removed last user & model message). Total history: {len(full_history)} messages. (owo)[/bold yellow]")
            else:
                console.print("[yellow]Not enough history to go back![/yellow]")
            console.print(Rule(style="dim cyan"))
            continue

        if user_input.strip().lower() == "/verbose":
            VERBOSE_MODE = not VERBOSE_MODE
            console.print(f"[bold cyan]VERBOSE MODE: {'ON' if VERBOSE_MODE else 'OFF'} (OwO)[/bold cyan]")
            continue

        # 1. Convert user's spicy words -> safe words before sending to API
        processed_input = user_input
        
        # Check for [WIKI_SEARCH:] tag
        if "[WIKI_SEARCH:" in processed_input:
            match = re.search(r"\[WIKI_SEARCH:\s*(.*?)\]", processed_input)
            if match and os.path.exists(WIKI_FILE):
                keyword = match.group(1).strip()
                console.print(f"[dim blue]🔍 Searching wiki for: {keyword}[/dim blue]")
                with open(WIKI_FILE, "r", encoding="utf-8") as wf:
                    wiki_text = wf.read()
                    # Find context around keyword
                    found_lines = [line for line in wiki_text.split('\n') if keyword.lower() in line.lower()]
                    context_snippet = "\n".join(found_lines[:5]) if found_lines else "No specific details found."
                    processed_input = f"Context from {character_name}'s Wiki about '{keyword}':\n{context_snippet}\n\nUser Question: {processed_input.replace(match.group(0), '')}"
        
        for spicy_word, safe_word in spicy_to_safe.items():
            pattern = re.compile(re.escape(spicy_word), re.IGNORECASE)
            processed_input = pattern.sub(safe_word, processed_input)

        if VERBOSE_MODE:
            console.print(Rule(style="dim yellow"))
            console.print("[yellow]--- Verbose Diagnostics: Prompts ---[/yellow]")
            console.print(f"[dim]Prompt BEFORE substitutions:[/dim]\n{user_input}")
            console.print(f"[dim]Prompt AFTER substitutions:[/dim]\n{processed_input}")
            console.print(Rule(style="dim yellow"))

        response = None
        success = False
        last_error = None
        active_chat = None

        start_time = time.time()
        turn_tokens = 0
        prompt_tokens = "?"
        response_tokens = "?"

        if is_group:
            # Randomly select between 1 and all members if group is large enough
            if len(group_members) >= 1:
                num_to_select = random.randint(1, len(group_members))
                selected_members = random.sample(group_members, num_to_select)
                console.print(f"[dim]Group chat active: {len(group_members)} total members. Randomly selected {num_to_select} members {selected_members} to respond this turn. (OwO)[/dim]")
            else:
                selected_members = group_members
            
            full_history.append({"role": "user", "speaker": "user", "text": processed_input})
            total_turn_tokens = 0
            
            for m_name in selected_members:
                # Track each group member attempt as a request
                check_and_update_requests()
                
                m_dir = m_name
                m_char_file = os.path.join(m_dir, "character.md")
                m_prompt = f"You are {m_name}, participating in a group chat. CRITICAL: Provide a unique response to the user's input. Do not repeat what other group members have already said in this turn. Focus on your specific character's perspective."
                m_color = "cyan"
                if os.path.exists(m_char_file):
                    with open(m_char_file, "r", encoding="utf-8") as mf:
                        m_content = mf.read()
                        m_prompt = m_content + "\n\nCRITICAL: You are part of a group chat. Provide a unique response to the user's input. Do not repeat what other group members have already said in this turn. Focus on your specific character's perspective."

                        for line in m_content.splitlines():
                            if "colour:" in line.lower() or "color:" in line.lower():
                                parts = line.split(":")
                                if len(parts) > 1:
                                    col = parts[1].strip().lower()
                                    if col:
                                        m_color = get_safe_color(col, "cyan")
                
                MAX_WINDOW = 40
                recent_entries = full_history[-MAX_WINDOW:] if len(full_history) > MAX_WINDOW else full_history
                active_content = []
                for entry in recent_entries:
                    role_val = entry["role"]
                    speaker_label = entry.get("speaker", role_val)
                    txt_val = entry["text"]
                    active_content.append(
                        types.Content(
                            role=role_val,
                            parts=[types.Part.from_text(text=f"[{speaker_label}]: {txt_val}")]
                        )
                    )
                
                m_response = None
                for model in FALLBACK_MODELS:
                    try:
                        chat_obj = client.chats.create(
                            model=model,
                            history=active_content if active_content else None,
                            config=types.GenerateContentConfig(
                                system_instruction=m_prompt,
                                temperature=0.7
                            )
                        )
            
                        m_response = chat_obj.send_message(f"[{m_name} respond to the group]: {processed_input}")
                        MODEL_NAME = model
                        break
                    except Exception as err:
                        last_error = err
                        continue
                
                if m_response and m_response.text:
                    raw_resp = m_response.text.strip()
                    display_r = raw_resp
                    for safe_w, spicy_w in safe_to_spicy.items():
                        pat = re.compile(re.escape(safe_w), re.IGNORECASE)
                        display_r = pat.sub(spicy_w, display_r)
                    
                    # Add group-chat specific update to stats bar logic
                    request_bar = get_request_bar()
                    console.print(f"[dim]Model: {MODEL_NAME} | Requests: {request_bar}[/dim]")
                    
                    console.print(Panel(Markdown(display_r), title=f"[bold {m_color}]{m_name}[/bold {m_color}]", title_align="left", border_style=m_color, padding=(0, 1)))
                    
                    full_history.append({"role": "model", "speaker": m_name, "text": raw_resp})
                    usage = getattr(m_response, "usage_metadata", None)
                    if usage and hasattr(usage, "total_token_count") and usage.total_token_count:
                        total_turn_tokens += usage.total_token_count
            
            success = True
            elapsed = time.time() - start_time
            turn_tokens = total_turn_tokens
            prompt_tokens = "N/A"
            response_tokens = "N/A"

        else:
            for model in FALLBACK_MODELS:
                try:
                    active_chat = create_chat_session(model)
        
                    response = active_chat.send_message(processed_input)
                    MODEL_NAME = model
                    with open(CONFIG_FILE, "w", encoding="utf-8") as cf:
                        json.dump({"last_model": MODEL_NAME}, cf, indent=2)
                    success = True
                    break
                except Exception as err:
                    last_error = err
                    continue
            elapsed = time.time() - start_time

            if not success:
                # Track request even on failure
                check_and_update_requests()
                console.print(f"[bold red]All available models failed! Last error: {last_error}[/bold red]")
                continue
            
            # Track request on success
            check_and_update_requests()
            
            raw_response_text = response.text if response and response.text else "[Model returned empty response]"
            display_text = raw_response_text
            for safe_word, spicy_word in safe_to_spicy.items():
                pattern = re.compile(re.escape(safe_word), re.IGNORECASE)
                display_text = pattern.sub(spicy_word, display_text)

            console.print(Panel(Markdown(display_text), title=f"[bold {character_color}]{character_name}[/bold {character_color}]", title_align="left", border_style=character_color, padding=(0, 1)))
            


            usage = getattr(response, "usage_metadata", None)
            prompt_tokens = usage.prompt_token_count if usage and hasattr(usage, "prompt_token_count") else "?"
            response_tokens = usage.candidates_token_count if usage and hasattr(usage, "candidates_token_count") else "?"
            total_tokens = usage.total_token_count if usage and hasattr(usage, "total_token_count") else "?"
            turn_tokens = total_tokens if isinstance(total_tokens, int) else 0
            
            full_history.append({"role": "user", "text": processed_input})
            full_history.append({"role": "model", "text": raw_response_text})

        # Update request count (removed from here as it's now in success/failure branches)
        # check_and_update_requests()

        global_used, global_limit, est_msgs_left, recent_turns = check_and_update_tokens(turn_tokens)
        tokens_left = (global_limit - global_used) if isinstance(global_used, int) else "?"

        now = datetime.datetime.now()
        day_str = str(now.day)
        month_str = str(now.month)
        year_str = now.strftime("%y")
        hour_str = str(int(now.strftime("%I")))
        minute_str = now.strftime("%M")
        ampm_str = "p.m." if now.strftime("%p").lower() == "pm" else "a.m."
        timestamp_str = f"{day_str}/{month_str}/{year_str} {hour_str}:{minute_str} {ampm_str}"

        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump(full_history, f, indent=2, ensure_ascii=False)

        if VERBOSE_MODE:
            console.print(Rule(style="dim yellow"))
            console.print("[yellow]--- Verbose Diagnostics: Response Statistics ---[/yellow]")
            console.print(f"[dim]Timestamp:[/dim] {timestamp_str}")
            console.print(f"[dim]Model Used:[/dim] {MODEL_NAME}")
            console.print(f"[dim]Generation Time:[/dim] {elapsed:.2f}s")
            console.print(Rule(style="dim yellow"))

        # Create ordered stats bar: timestamp, global daily percentage bar, generation time, history length, messages left estimate
        if isinstance(global_used, int) and isinstance(global_limit, int) and global_limit > 0:
            used_pct = min(100.0, (global_used / global_limit) * 100.0)
            bar_width = 30
            filled = round(bar_width * (used_pct / 100.0))
            if used_pct > 0 and filled == 0:
                filled = 1
            bar_str = "█" * filled + "░" * (bar_width - filled)
            bar_display = f"[{bar_str}] {used_pct:.1f}% ({global_used:,}/{global_limit:,})"
        else:
            bar_display = "[?] ?%"

        request_bar = get_request_bar()
        stats_display = f"[dim]{timestamp_str} | Requests: {request_bar} | Time: {elapsed:.2f}s[/dim]"
        console.print(Rule(style="dim cyan"))
        console.print(stats_display)

        # 4. RAG-lite: Every 18 messages, update memory.md automatically
        if len(full_history) > 0 and len(full_history) % 18 == 0:
            update_memory_bank(MODEL_NAME)

    except KeyboardInterrupt:
        console.print(Rule(style="dim yellow"))
        console.print("\n\n[yellow]Session interrupted. Saving final memory and updating memory.md... Take care! (^V^)[/yellow]")
        if len(full_history) > 0:
            try:
                update_memory_bank(MODEL_NAME)
            except:
                pass
        break

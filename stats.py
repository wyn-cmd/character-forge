import os
import json
import sys
from rich.console import Console
from rich.table import Table
import datetime

console = Console()

CHARACTER_DIR = "."
TOKEN_TRACKER_FILE = "token_tracker.json"
DEFAULT_UNITS = "bytes"  # change to "kb" to make kilobytes the default

def estimate_tokens(text):
    return int(len(text) / 4)

def text_bytes(text):
    return len(text.encode("utf-8"))

def file_bytes(path):
    return os.path.getsize(path) if os.path.exists(path) else 0

def unit_label(units):
    return "KB" if units == "kb" else "Bytes"

def format_size(n, units):
    if units == "kb":
        if n >= 1024 * 1024:
            return f"{n / (1024 * 1024):.2f} MB"
        if n >= 1024:
            return f"{n / 1024:.1f} KB"
        return f"{n:,} B"
    return f"{n:,}"

def format_bytes(n, units="bytes"):
    if n >= 1024 * 1024:
        compact = f"{n / (1024 * 1024):.2f} MB"
    elif n >= 1024:
        compact = f"{n / 1024:.1f} KB"
    else:
        compact = f"{n:,} B"
    exact = f"{n:,} B"
    if compact == exact:
        return exact
    return f"{compact} ({exact})" if units == "kb" else f"{exact} ({compact})"

def load_config():
    if os.path.exists("config.json"):
        try:
            with open("config.json", "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def parse_units(argv):
    units = DEFAULT_UNITS
    setting = str(load_config().get("size_units", "")).lower()
    if setting in ("kb", "kilobytes", "k"):
        units = "kb"
    elif setting in ("bytes", "b"):
        units = "bytes"

    for arg in argv:
        if arg in ("--kb", "-k", "--kilobytes"):
            units = "kb"
        elif arg in ("--bytes", "-b"):
            units = "bytes"
        elif arg in ("--mb",):
            units = "kb"
    return units

def get_stats(units=DEFAULT_UNITS):
    char_folders = sorted(
        d for d in os.listdir(CHARACTER_DIR)
        if os.path.isdir(d)
        and os.path.exists(os.path.join(d, "character.md"))
        and not os.path.exists(os.path.join(d, "group_config.json"))
    )
    
    table = Table(title="Character & Token Statistics")
    table.add_column("Character", style="cyan")
    table.add_column("Msgs", style="green")
    table.add_column("Hist Tokens", style="magenta")
    table.add_column(f"Hist {unit_label(units)}", style="magenta")
    table.add_column("MemBank Tokens", style="blue")
    table.add_column(f"MemBank {unit_label(units)}", style="blue")
    table.add_column("Last Mem Update", style="yellow")
    
    totals = {
        "msgs": 0, "hist_tokens": 0, "hist_bytes": 0,
        "mem_tokens": 0, "mem_bytes": 0, "hist_file_bytes": 0
    }
    
    for char in char_folders:
        mem_file = os.path.join(char, "memory.json")
        mem_bank_file = os.path.join(char, "memory.md")
        
        history_len = 0
        hist_tokens = 0
        hist_bytes = 0
        if os.path.exists(mem_file):
            try:
                with open(mem_file, "r", encoding="utf-8") as f:
                    history = json.load(f)
                    history_len = len(history)
                    full_text = "".join(entry.get("text", "") for entry in history)
                    hist_tokens = estimate_tokens(full_text)
                    hist_bytes = text_bytes(full_text)
            except Exception as exc:
                console.print(f"[yellow]Could not read {mem_file}: {exc}[/yellow]")
        
        mem_tokens = 0
        mem_bytes = 0
        if os.path.exists(mem_bank_file):
            try:
                with open(mem_bank_file, "r", encoding="utf-8") as f:
                    mem_text = f.read()
                mem_tokens = estimate_tokens(mem_text)
                mem_bytes = text_bytes(mem_text)
            except Exception as exc:
                console.print(f"[yellow]Could not read {mem_bank_file}: {exc}[/yellow]")
            
        last_mod = "N/A"
        if os.path.exists(mem_bank_file):
            last_mod = datetime.datetime.fromtimestamp(os.path.getmtime(mem_bank_file)).strftime('%d/%m/%y %H:%M')
            
        table.add_row(
            char, str(history_len), f"{hist_tokens:,}", format_size(hist_bytes, units),
            f"{mem_tokens:,}", format_size(mem_bytes, units), last_mod
        )
        
        totals["msgs"] += history_len
        totals["hist_tokens"] += hist_tokens
        totals["hist_bytes"] += hist_bytes
        totals["mem_tokens"] += mem_tokens
        totals["mem_bytes"] += mem_bytes
        totals["hist_file_bytes"] += file_bytes(mem_file)
    
    if char_folders:
        table.add_section()
        table.add_row(
            "TOTAL",
            f"{totals['msgs']:,}",
            f"{totals['hist_tokens']:,}",
            format_size(totals['hist_bytes'], units),
            f"{totals['mem_tokens']:,}",
            format_size(totals['mem_bytes'], units),
            f"{len(char_folders)} chars",
            style="bold",
        )
        
    console.print(table)
    if char_folders:
        console.print(
            f"[dim]History content: {format_bytes(totals['hist_bytes'], units)} across "
            f"{totals['msgs']:,} messages | memory banks: {format_bytes(totals['mem_bytes'], units)}[/dim]"
        )
        console.print(
            f"[dim]History files on disk (memory.json, keys and separators included): "
            f"{format_bytes(totals['hist_file_bytes'], units)}[/dim]"
        )
    
    group_folders = sorted(
        d for d in os.listdir(CHARACTER_DIR)
        if os.path.isdir(d) and os.path.exists(os.path.join(d, "group_config.json"))
    )
    
    if group_folders:
        group_msgs_total = 0
        console.print("\n")
        g_table = Table(title="Group Chat Statistics")
        g_table.add_column("Group Name", style="cyan")
        g_table.add_column("Members", style="green")
        g_table.add_column("Total Msgs", style="magenta")
        g_table.add_column("Hist Tokens", style="blue")
        g_table.add_column(f"Hist {unit_label(units)}", style="blue")
        g_table.add_column("MemBank (Est. Tokens)", style="magenta")
        g_table.add_column(f"MemBank ({unit_label(units)})", style="magenta")
        g_table.add_column("Last Mem Update", style="yellow")
        g_table.add_column("Per-Member Breakdown", style="cyan")
        
        for g in group_folders:
            cfg_file = os.path.join(g, "group_config.json")
            mem_file = os.path.join(g, "memory.json")
            mem_bank_file = os.path.join(g, "memory.md")
            
            members = []
            if os.path.exists(cfg_file):
                try:
                    with open(cfg_file, "r", encoding="utf-8") as f:
                        cfg = json.load(f)
                        members = cfg.get("members", [])
                except Exception:
                    pass
            
            history_len = 0
            group_tokens = 0
            group_bytes = 0
            
            speaker_counts = {m: 0 for m in members}
            speaker_tokens = {m: 0 for m in members}
            speaker_bytes = {m: 0 for m in members}
            
            if os.path.exists(mem_file):
                try:
                    with open(mem_file, "r", encoding="utf-8") as f:
                        history = json.load(f)
                        history_len = len(history)
                        for entry in history:
                            speaker = entry.get("speaker", entry.get("role", "unknown"))
                            text = entry.get("text", "")
                            toks = estimate_tokens(text)
                            byts = text_bytes(text)
                            group_tokens += toks
                            group_bytes += byts
                            
                            speaker_counts[speaker] = speaker_counts.get(speaker, 0) + 1
                            speaker_tokens[speaker] = speaker_tokens.get(speaker, 0) + toks
                            speaker_bytes[speaker] = speaker_bytes.get(speaker, 0) + byts
                except Exception:
                    pass

            group_mem_tokens = 0
            group_mem_bytes = 0
            if os.path.exists(mem_bank_file):
                try:
                    with open(mem_bank_file, "r", encoding="utf-8") as f:
                        mem_text = f.read()
                    group_mem_tokens = estimate_tokens(mem_text)
                    group_mem_bytes = text_bytes(mem_text)
                except Exception:
                    pass

            last_mod = "N/A"
            if os.path.exists(mem_bank_file):
                last_mod = datetime.datetime.fromtimestamp(os.path.getmtime(mem_bank_file)).strftime('%d/%m/%y %H:%M')
            
            breakdown_str = []
            for sp, cnt in sorted(speaker_counts.items()):
                toks = speaker_tokens.get(sp, 0)
                byts = speaker_bytes.get(sp, 0)
                breakdown_str.append(f"• {sp}: {cnt} msgs ({toks:,} tokens, {format_size(byts, units)})")
                
            breakdown_display = "\n".join(breakdown_str) if breakdown_str else "No messages recorded"
            
            g_table.add_row(
                g, 
                ", ".join(members), 
                str(history_len), 
                f"{group_tokens:,}", 
                format_size(group_bytes, units),
                f"{group_mem_tokens:,}",
                format_size(group_mem_bytes, units),
                last_mod,
                breakdown_display
            )
            group_msgs_total += history_len
            g_table.add_section()
            
        console.print(g_table)
        if group_folders:
            hist_file_total = sum(file_bytes(os.path.join(g, "memory.json")) for g in group_folders)
            console.print(f"[dim]{group_msgs_total:,} messages across {len(group_folders)} group(s) | history files on disk: {format_bytes(hist_file_total, units)}[/dim]")

    REQUEST_TRACKER_FILE = "request_tracker.json"
    if os.path.exists(REQUEST_TRACKER_FILE):
        try:
            with open(REQUEST_TRACKER_FILE, "r", encoding="utf-8") as f:
                t = json.load(f)
                console.print(f"\n[bold magenta]Daily API Requests ({t.get('date', 'N/A')}):[/bold magenta]")
                count = t.get('requests_made', 0)
                limit = 1500
                pct = min(100.0, (count / limit) * 100.0)
                bar_width = 30
                filled = round(bar_width * (pct / 100.0))
                bar_str = "█" * filled + "░" * (bar_width - filled)
                console.print(f"[{bar_str}] {pct:.1f}% ({count}/{limit})")
        except Exception:
            console.print("[yellow]Could not read request tracking data.[/yellow]")
    else:
        console.print("[yellow]No request tracking data found.[/yellow]")

if __name__ == "__main__":
    if any(a in ("-h", "--help") for a in sys.argv[1:]):
        print("usage: stats.py [--kb | --bytes]")
        print("  --kb      show sizes in KB (MB above 1024 KB)")
        print("  --bytes   show sizes in exact bytes (default)")
        print('  config.json {"size_units": "kb"} makes KB the default')
        raise SystemExit(0)

    get_stats(parse_units(sys.argv[1:]))
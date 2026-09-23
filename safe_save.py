import json
import os
import re


# Replaces text based on a substitutions dictionary, ignoring case
def apply_substitutions(text, subs):
    for original, replacement in subs.items():
        text = re.sub(re.escape(original), replacement, text, flags=re.IGNORECASE)
    return text


# Loads a JSON file or returns a default value if not found or unreadable
def load_json(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return default


# Processes a fact and appends it to the facts JSON file
def save_fact(fact_text, fact_file_path, subs_file_path):
    subs = load_json(subs_file_path, default={})
    safe_fact = apply_substitutions(fact_text, subs)

    facts = []
    if os.path.exists(fact_file_path):
        try:
            with open(fact_file_path, "r", encoding="utf-8") as f:
                facts = json.load(f)
        except json.JSONDecodeError:
            # Backup corrupt files to prevent data loss and allow manual recovery
            backup_path = f"{fact_file_path}.corrupt"
            os.replace(fact_file_path, backup_path)
            print(f"Could not parse {fact_file_path}, moved it to {backup_path}")

    facts.append(safe_fact)

    # Write to a temp file then rename to ensure the save is atomic
    tmp_path = f"{fact_file_path}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(facts, f, indent=2)
    os.replace(tmp_path, fact_file_path)

    return safe_fact


if __name__ == "__main__":
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        subs_path = os.path.join(tmp, "substitutions.json")
        facts_path = os.path.join(tmp, "memory.json")

        with open(subs_path, "w", encoding="utf-8") as f:
            json.dump({"example_phrase": "replacement_phrase"}, f)

        result = save_fact("A line that mentions example_phrase.", facts_path, subs_path)
        print(result)
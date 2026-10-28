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


# Picks a backup name so an earlier corrupt file is never overwritten
def next_backup_path(path):
    candidate = f"{path}.corrupt"
    index = 1
    while os.path.exists(candidate):
        candidate = f"{path}.corrupt.{index}"
        index += 1
    return candidate


# Loads the substitution map, skipping entries that are not plain strings
def load_substitutions(path):
    subs = load_json(path, default={})
    if not isinstance(subs, dict):
        print(f"Ignoring {path}: expected a JSON object of substitutions, got {type(subs).__name__}")
        return {}
    # Empty keys and non-string values make re.sub raise, so they are dropped here
    return {
        key: value for key, value in subs.items()
        if isinstance(key, str) and key and isinstance(value, str)
    }


# Reads the fact list, moving the file aside when it is not a JSON list
def load_facts(fact_file_path):
    try:
        with open(fact_file_path, "r", encoding="utf-8") as f:
            facts = json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        facts = None
        reason = exc
    else:
        reason = None
    if isinstance(facts, list):
        return facts
    # A valid JSON value that is not a list of facts cannot be appended to, so it
    # gets the same backup treatment as an unparseable file
    backup_path = next_backup_path(fact_file_path)
    try:
        os.replace(fact_file_path, backup_path)
    except OSError as exc:
        raise OSError(f"Could not move unreadable fact file {fact_file_path} aside: {exc}") from exc
    if reason is None:
        print(f"{fact_file_path} did not contain a list of facts, moved it to {backup_path}")
    else:
        print(f"Could not parse {fact_file_path} ({reason}), moved it to {backup_path}")
    return []


# Processes a fact and appends it to the facts JSON file with input validation
def save_fact(fact_text, fact_file_path, subs_file_path):
    # Reject non-string inputs or empty/whitespace-only strings that were previously accepted
    if not isinstance(fact_text, str):
        raise ValueError(f"Invalid input: fact_text must be a string, got {type(fact_text).__name__}")
    if not fact_text.strip():
        raise ValueError("Invalid input: fact_text cannot be empty or whitespace-only")

    subs = load_substitutions(subs_file_path)
    safe_fact = apply_substitutions(fact_text, subs)

    facts = []
    if os.path.exists(fact_file_path):
        facts = load_facts(fact_file_path)

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

        # Test input validation rejections
        try:
            save_fact("", facts_path, subs_path)
        except ValueError as e:
            print(f"Caught expected validation error: {e}")

        try:
            save_fact(123, facts_path, subs_path)
        except ValueError as e:
            print(f"Caught expected validation error: {e}")

        # A facts file holding something other than a list is set aside, not crashed on
        with open(facts_path, "w", encoding="utf-8") as f:
            json.dump({"not": "a list"}, f)
        print(save_fact("A fact saved after a wrong-shaped file.", facts_path, subs_path))
        print("wrong shape backed up:", os.path.exists(facts_path + ".corrupt"))

        # A substitutions file that is not an object is ignored instead of crashing
        with open(subs_path, "w", encoding="utf-8") as f:
            json.dump(["bad", "shape"], f)
        print(save_fact("A fact with a broken substitution map.", facts_path, subs_path))

        # A second corrupt facts file gets its own backup instead of replacing the first
        with open(facts_path, "w", encoding="utf-8") as f:
            f.write("{not json")
        print(save_fact("A fact saved after a second corrupt file.", facts_path, subs_path))
        print("second backup kept:", os.path.exists(facts_path + ".corrupt.1"))
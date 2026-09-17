import json
import os
import re


def apply_substitutions(text, subs):
    for original, replacement in subs.items():
        # case insensitive so the same word in any casing gets caught
        pattern = re.compile(re.escape(original), re.IGNORECASE)
        text = pattern.sub(replacement, text)
    return text


def save_fact(fact_text, fact_file_path, subs_file_path):
    # substitutions are applied on the way in, so nothing raw lands on disk
    if os.path.exists(subs_file_path):
        with open(subs_file_path, "r", encoding="utf-8") as f:
            subs = json.load(f)
    else:
        subs = {}

    safe_fact = apply_substitutions(fact_text, subs)

    if os.path.exists(fact_file_path):
        with open(fact_file_path, "r", encoding="utf-8") as f:
            try:
                facts = json.load(f)
            except json.JSONDecodeError:
                facts = []
    else:
        facts = []

    facts.append(safe_fact)

    with open(fact_file_path, "w", encoding="utf-8") as f:
        json.dump(facts, f, indent=2)

    return safe_fact


if __name__ == "__main__":
    import tempfile

    # self test against throwaway files, then print what got written
    with tempfile.TemporaryDirectory() as tmp:
        subs_path = os.path.join(tmp, "substitutions.json")
        facts_path = os.path.join(tmp, "memory.json")

        with open(subs_path, "w", encoding="utf-8") as f:
            json.dump({"example_phrase": "replacement_phrase"}, f)

        print(save_fact("A line that mentions example_phrase.", facts_path, subs_path))

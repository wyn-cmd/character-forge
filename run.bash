#!/bin/bash
# Pass a character folder as the first argument, or it defaults to Cliff/.
# A second argument names a folder describing you, the player.
CHARACTER="${1:-Cliff/}"
.venv/bin/python roleplay.py "$CHARACTER"

# Group chats: create one, then start it the same way
#   .venv/bin/python roleplay.py --group my-group Cayprae Cliff
#   .venv/bin/python roleplay.py my-group

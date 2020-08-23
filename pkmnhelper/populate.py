import hashlib
import json
import os
import subprocess
from typing import Dict, List

import imagehash
import PIL
import requests
import yaml

def hash2phash() -> None:
    import database

    db = database.Database(None)
    phashes: Dict[str, str] = {}
    with open('phashes.yaml', mode='r') as f:
        phashes.update(yaml.safe_load(f))
    for img in os.scandir('images'):
        if not img.name.endswith('.jpg'):
            continue
        with PIL.Image.open(img.path) as image:
            phash = str(imagehash.phash(image))
            pkmn = db.get_pokemon_image_by_phash(phash)
            if pkmn.pokemon is None:
                print(f'{phash} ({img.name}) is unknown')
                continue
            if pkmn.name:
                phashes[phash] = pkmn.name

    with open('phashes.yaml', mode='w') as f:
        yaml.dump(phashes, f)

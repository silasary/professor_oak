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
        md5 = img.name.split('.')[0]
        pkmn = db.get_pokemon_image_by_hash(md5)
        if pkmn.pokemon is None:
            continue
        with PIL.Image.open(img.path) as image:
            phash = str(imagehash.phash(image))
            if pkmn.name:
                phashes[phash] = pkmn.name

    with open('phashes.yaml', mode='w') as f:
        yaml.dump(phashes, f)

def evolutions() -> None:
    req = requests.get('https://docs.google.com/spreadsheets/d/1OGNmAax8ncek4VIb9TaeDTnyGKH808MoTHX9x_CwC_U/export?format=tsv&id=1OGNmAax8ncek4VIb9TaeDTnyGKH808MoTHX9x_CwC_U&gid=0')
    sheet = req.content.decode('utf-8').splitlines(False)
    data = []
    row: List[str] = []
    prevrow: List[str] = []
    def insert(i: int) -> None:
        if not row[i + 1]: # no third evolution
            return
        if row[i + 1] == 'None': # Doesn't evolve
            return
        if row[i] == '∟' and row[i + 2] == '→': # same as previous row, usually because second evolution diverges (eg Oddish)
            return
        if row[i] == '→': # As above
            row[i] = prevrow[i]
        if not row[i]: # First evolution diverges. See slowpoke/eevee
            row[i] = prevrow[i]
        d = {}
        d['base'] = row[i].strip()
        d['method'] = row[i + 1].strip()
        d['result'] = row[i + 2].strip()
        if row[5] == 'verified':
            d['verified'] = 'True'
        else:
            d['verified'] = 'False'
            d['note'] = row[5]
        data.append(d)

    for line in sheet[1:]:
        row = line.split('\t')
        insert(0)
        insert(2)
        prevrow = row
    with open('evos.yaml', mode='w') as f:
        yaml.dump(data, f)

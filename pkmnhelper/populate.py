import hashlib
import subprocess
import os
import json

import database

def discatcher(db: database.Database = None) -> None:
    if db is None:
        db = database.Database(None)

    owd = os.getcwd()
    wd = 'DisCatcher'
    if not os.path.exists(wd):
        subprocess.run(['git', 'clone', 'https://github.com/MikeTheShadow/DisCatcher.git'], check=True)
    os.chdir(wd)
    subprocess.run(['git', 'pull'], check=True)
    os.chdir(owd)
    hashes = {}
    with open('imagehashes.json', mode='r') as f:
        hashes.update({value["hash"]: value["name"] for value in json.load(f)})
    for img in os.scandir(os.path.join(wd, 'pokedex')):
        with open(img.path, mode='rb') as f:
            md5 = hashlib.md5(f.read()).hexdigest()
            name = img.name.split('.')[0]
            name = name[0].upper() + name[1:]
            hashes[md5] = name
    with open('imagehashes.json', mode='w') as f:
        json.dump([{'name': h[1], 'hash': h[0]} for h in hashes.items()], f, indent=2)


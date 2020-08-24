from discord.errors import NoMoreItems
import database
from database import PHash
import requests
import hashlib
import os
import PIL
import imagehash
import warnings

class EmbedImage():
    _filename = None
    def __init__(self, url_or_md5: str) -> None:
        if len(url_or_md5) == 32 and os.path.join('images', url_or_md5 + '.jpg'):
            self._filename = os.path.join('images', url_or_md5 + '.jpg')
        else:
            self.url = url_or_md5

    @property
    def filename(self) -> str:
        if not self._filename:
            resp = requests.get(self.url)
            self._md5 = hashlib.md5(resp.content).hexdigest()
            self._filename = os.path.join('images', self._md5 + '.jpg')
            if not os.path.exists(self._filename):
                print(f'saving {self._filename}')
                with open(self._filename, 'wb') as fd:
                    for chunk in resp.iter_content(chunk_size=128):
                        fd.write(chunk)
        return self._filename

    @property
    def md5(self) -> str:
        if self.filename:
            return self._md5
        raise Exception('No filename')

    @property
    def phash(self) -> str:
        with PIL.Image.open(self.filename) as image:
            phash = str(imagehash.phash(image))
        return phash

    def get_closest(self) -> PHash:
        _hash = imagehash.hex_to_hash(self.phash)
        def sortkey(h):
            return _hash - h.ihash()

        with database.Database(None):
            hashes = list(PHash.select().where(PHash.pokemon != None))

            hashes.sort(key=sortkey)
            if hashes:
                return hashes[0]
            raise NoMoreItems('DB Empty')



def get_phash(url: str) -> str:
    warnings.warn("deprecated", DeprecationWarning)
    resp = requests.get(url)
    md5 = hashlib.md5(resp.content).hexdigest()
    filename = os.path.join('images', md5 + '.jpg')
    if not os.path.exists(filename):
        print(f'saving {filename}')
        with open(filename, 'wb') as fd:
            for chunk in resp.iter_content(chunk_size=128):
                fd.write(chunk)
    with PIL.Image.open(filename) as image:
        phash = str(imagehash.phash(image))
    return phash

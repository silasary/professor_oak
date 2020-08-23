import requests
import hashlib
import os
import PIL
import imagehash

class EmbedImage():
    _filename = None
    def __init__(self, url: str) -> None:
        self.url = url

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


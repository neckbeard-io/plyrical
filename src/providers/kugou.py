import base64
import requests


class Kugou:
    def __init__(self, ctx):
        self.s = requests.Session()

    def get_lyric_by_metadata(self, artist, title, duration):

        search_url = "https://lyrics.kugou.com/search"
        params = {
            "ver": 1,
            "man": "yes",
            "client": "pc",
            "keyword": f"{artist}-{title}",
            "duration": duration,
        }
        r = self.s.get(url=search_url, params=params).json()
        if not r["candidates"]:
            return None

        id = r["candidates"][0]["id"]
        accesskey = r["candidates"][0]["accesskey"]

        download_url = "http://lyrics.kugou.com/download"
        params = {
            "ver": 1,
            "man": "yes",
            "client": "pc",
            "id": id,
            "accesskey": accesskey,
            "fmt": "lrc",
            "charset": "utf8",
        }
        r = self.s.get(url=download_url, params=params).json()
        content = r.get("content")
        if not content:
            return None

        lyrics = base64.b64decode(r["content"])
        return lyrics

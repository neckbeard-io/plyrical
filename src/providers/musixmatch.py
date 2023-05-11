import requests
import time


class Musixmatch:
    def __init__(self, ctx, api_url, token_sleep_seconds):
        self.api_url = api_url
        self.s = requests.Session()
        self.headers = {
            "Connection": "Keep-Alive",
            "User-Agent": "User-Agent: Mozilla/5.0 (X11; Linux x86_64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Musixmatch/0.19.4 Chrome/58.0.3029.110 "
            "Electron/1.7.6 Safari/537.36 ",
        }
        self.cookies = {
            "AWSELB": "0",
            "AWSELBCORS": "0",
        }
        self.params = {
            "user_language": "en",
            "app_id": "web-desktop-app-v1.0",
            "t": round(time.time()),
        }
        self.ctx = ctx
        self.token_pool = []
        self.token_iter = None
        self.active_token = None
        self.token_sleep_seconds = token_sleep_seconds

    def get_user_token(self):
        token_endpoint = "token.get"
        r = self.s.get(
            f"{self.api_url}{token_endpoint}",
            cookies=self.cookies,
            headers=self.headers,
            params=self.params,
        )
        r = r.json()
        status_code = r["message"]["header"]["status_code"]
        hint = r["message"]["header"].get("hint", None)

        while status_code == 401 and hint == "captcha":
            self.ctx.obj["logger"].info(
                f'msg="Rate limited trying to get user_token" '
                f'status="sleeping" seconds={self.token_sleep_seconds}'
            )
            time.sleep(self.token_sleep_seconds)
            r = self.s.get(
                f"{self.api_url}{token_endpoint}",
                cookies=self.cookies,
                headers=self.headers,
                params=self.params,
            )
            r = r.json()
            status_code = r["message"]["header"]["status_code"]
            hint = r["message"]["header"].get("hint", None)

        if r["message"]["header"]["status_code"] != 200:
            # need to decide what to do here. haven't seen this
            pass

        # haven't seen this yet
        if self.token_pool == "UpgradeOnlyUpgradeOnlyUpgradeOnlyUpgradeOnly":
            raise Exception("Getting user token failed")

        user_token = r["message"]["body"]["user_token"]
        # add token to the front of the pool
        self.token_pool.insert(0, user_token)
        self.ctx.obj["logger"].info(
            f'msg="Added new user_token to pool" token={user_token}'
        )
        # set the new token to the active_token
        self.active_token = user_token
        self.ctx.obj["logger"].info(f'msg="Setting active token" token={user_token}')
        # reset the iterator
        self.token_iter = iter(self.token_pool)

        # return it just in case someone wants it outside
        return self.active_token

    def _get(self, endpoint, extra_params):

        r = self.s.get(
            f"{self.api_url}{endpoint}",
            params={
                **self.params,
                **extra_params,
                **{"usertoken": self.active_token},
            },
            headers=self.headers,
            cookies=self.cookies,
        )
        if r.status_code not in [200, 201, 202]:
            return None
        r = r.json()
        status_code = r["message"]["header"]["status_code"]
        hint = r["message"]["header"].get("hint", None)

        while status_code == 401 and hint == "captcha":

            self.active_token = next(self.token_iter, "exhausted")
            self.ctx.obj["logger"].warning(
                f"status=throttled action=next_token active_token={self.active_token}"
            )
            # if we get to the end of the pool, get another token and put it
            # at the front of the list.
            if self.active_token == "exhausted":
                self.ctx.obj["logger"].warning(
                    'status="no valid tokens" action=get_new_token'
                )
                self.get_user_token()

            r = self.s.get(
                f"{self.api_url}{endpoint}",
                params={
                    **self.params,
                    **extra_params,
                    **{"usertoken": self.active_token},
                },
                headers=self.headers,
                cookies=self.cookies,
            )
            if r.status_code not in [200, 201, 202]:
                return None
            r = r.json()
            status_code = r["message"]["header"]["status_code"]
            hint = r["message"]["header"].get("hint", None)

        # haven't seen this yet
        if r["message"]["header"]["status_code"] != 200:
            return None

        return r["message"]["body"]

    def get_lyrics_by_metadata(
        self, track_name: str, artist_name: str, album_name: str
    ):
        lyrics_endpoint = "macro.subtitles.get"
        params = {
            "q_artist": artist_name,
            "q_track": track_name,
            "q_album": album_name,
            "format": "json",
            "namespace": "lyrics_richsynched",
            "optional_calls": "track.richsync",
        }
        data = self._get(
            endpoint=lyrics_endpoint,
            extra_params=params,
        )
        # any non 200 returns None except for Captcha
        if not data:
            return None

        data = data["macro_calls"]["track.subtitles.get"]["message"].get("body", None)
        # returned results but no sync'd lyrics available
        if not data:
            return None
        else:
            # results appear to have sync'd lyrics
            return data["subtitle_list"][0]["subtitle"]["subtitle_body"]

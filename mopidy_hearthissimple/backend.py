import logging
import json
import pykka
import requests
import base64
from datetime import datetime
from mopidy.models import Ref, Track, Album, Image, Artist
from mopidy.backend import *

logger = logging.getLogger(__name__)
ht_uri = "hearthissimple:"
ht_uri_root = ht_uri + "root"
ht_uri_user = ht_uri + "user:"
ht_uri_feed = ht_uri + "feed"
ht_api = "https://api-v2.hearthis.at"
myfeedLabel = "    Feed of "


class HearthisSimpleBackend(pykka.ThreadingActor, Backend):
    uri_schemes = ["hearthissimple"]

    # used uris:
    # hearthissimple:root (shows entry point for feed and users followed
    # hearthissimple:user:<userid> (shows tracks for a followed user)
    # hearthissimple:feed: (shows personal feed)
    # hearthissimple:feed: http   (the track feeding url in the personal feed)
    # hearthissimple:http....... (the track feeding url)

    def __init__(self, config, audio):
        super(HearthisSimpleBackend, self).__init__()
        self.library = HearthisSimpleLibrary(self, config)
        self.playback = HearthisSimplePlaybackProvider(audio=audio, backend=self)


class HearthisSimpleLibrary(LibraryProvider):
    root_directory = Ref.directory(uri=ht_uri_root, name="Hearthis")

    def __init__(self, backend, config):
        super(HearthisSimpleLibrary, self).__init__(backend)
        self.htemail = config["hearthissimple"]["username"]
        self.htpass = config["hearthissimple"]["password"]
        self.ht_username = ""
        self.imageCache = {}
        self.trackCache = {}
        self.refCache = {}
        self.lastRefresh = datetime.now()
        self.cacheTimeMin = 60 * 24
        self.secret = ""
        self.key = ""
        self.avatar_url = ""
        self.login()

    def login(self):
        r = requests.post(
            ht_api + "/login/",
            data={"email": self.htemail, "password": self.htpass},
            timeout=10,
        )
        if r.status_code == 200:
            jsonO = json.loads(r.text)
            self.secret = jsonO["secret"]
            self.key = jsonO["key"]
            self.avatar_url = jsonO["avatar_url"]
            self.ht_username = jsonO["username"]
        else:
            logger.error("login err")
        return {}

    def browse(self, uri):
        refs = []
        now = datetime.now()
        minutesSinceLastLoad = round((now - self.lastRefresh).total_seconds() / 60)
        logger.info(
            "Uri browse ("
            + uri
            + "). Data is "
            + str(minutesSinceLastLoad)
            + " min old. Last refresh was "
            + self.lastRefresh.strftime("%d/%m/%Y %H:%M:%S")
        )
        if minutesSinceLastLoad > self.cacheTimeMin:
            self.refresh("")
            self.lastRefresh = now
            logger.info("Clearing cache ... ")

        # root
        if uri == ht_uri_root:
            # try the cache first
            if uri in self.refCache and self.refCache[uri]:
                refs = self.refCache[uri]
            else:
                refs = self.loadRootDirectoryRefs()

        # feed
        elif uri.startswith(ht_uri_feed):
            # try the cache first
            if uri in self.refCache and self.refCache[uri]:
                refs = self.refCache[uri]
            else:
                t_idx = uri.rfind(":")
                page = uri[t_idx + 1 :]
                refs = self.loadTrackRefsFromHT("/feed", ht_uri_feed, page)

        # user
        else:
            # try the cache first
            if uri in self.refCache and self.refCache[uri]:
                refs = self.refCache[uri]
            else:
                t_idx = uri.rfind(":")
                page = uri[t_idx + 1 :]
                user = uri[:t_idx]
                user = user[user.rfind(":") + 1 :]
                refs = self.loadTrackRefsFromHT(
                    "/" + user + "?type=tracks", ht_uri_user + user, page
                )

        return refs

    def loadRootDirectoryRefs(self):
        refs = []
        try:
            # get feed node
            feedUri = ht_uri_feed + ":1"
            ref = Ref.directory(name=myfeedLabel + self.ht_username, uri=feedUri)
            self.imageCache[feedUri] = Image(uri=self.avatar_url)
            refs.append(ref)
            # get follows
            follows = self.htAPICall("/" + self.ht_username + "/following/")
            for f in follows:
                user_uri = ht_uri_user + f["permalink"] + ":1"
                ref = Ref.directory(name=f["username"], uri=user_uri)
                self.imageCache[user_uri] = Image(uri=f["avatar_url"])
                logger.debug("putting image cache for " + user_uri)
                refs.append(ref)

            self.refCache[ht_uri_root] = refs
        except requests.exceptions.HTTPError as err:
            logger.error("Error:" + str(err))
        except json.decoder.JSONDecodeError as err:
            logger.error("Error:" + str(err) + " for response " + r.text)
        return refs

    def loadTrackRefsFromHT(self, path, uri, page):
        refs = []
        logger.info("Loading tracks for: " + path + " from hearthis.")
        tracks = self.htAPICall(path, page)

        trackNo = (int(page) - 1) * 20
        for trackJSON in tracks:
            trackNo += 1
            trackRef = Ref.track(
                name=str(trackNo).zfill(2) + ". " + trackJSON["title"],
                uri=uri
                + ":"
                + base64.b64encode(trackJSON["stream_url"].encode()).decode(),
            )
            refs.append(trackRef)
            track = self.getTrackFromJSON(trackJSON, trackNo, trackRef.uri)
            self.trackCache[trackRef.uri] = track
        nextPage = int(page) + 1
        ref = Ref.directory(name="Page " + str(nextPage), uri=uri + ":" + str(nextPage))
        refs.append(ref)
        self.refCache[uri + ":" + page] = refs
        return refs

    def htAPICall(self, url, page=None):
        try:
            if page == None:
                page = "1"
            urlParams = {
                "secret": self.secret,
                "key": self.key,
                "count": 20,
                "page": page,
            }
            r = requests.get(ht_api + url, params=urlParams, timeout=10)
            jsonO = json.loads(r.text)
            return jsonO
        except:
            logger.error("Error while loading ht data")
            return {}

    def getTrackFromJSON(self, trackJSON, trackNo, trackuri):
        if trackJSON["artwork_url"]:
            artwork = trackJSON["artwork_url"]
            self.imageCache[trackuri] = Image(uri=artwork)
        album = Album(
            uri=ht_uri_user + trackJSON["user"]["permalink"],
            name=trackJSON["user"]["username"],
        )
        artist = Artist(
            uri=ht_uri_user + trackJSON["user"]["permalink"],
            name=trackJSON["user"]["username"],
        )
        dateString = trackJSON["created_at"]
        i_duration = int(trackJSON["duration"]) * 1000
        dateObj = datetime.strptime(dateString, "%Y-%m-%d %H:%M:%S")
        dateStringMop = dateObj.strftime("%Y-%m-%d")
        track = Track(
            uri=trackuri,
            name=str(trackNo).zfill(2) + ". " + trackJSON["title"],
            album=album,
            artists=[artist],
            date=dateStringMop,
            length=i_duration,
            track_no=trackNo,
        )
        return track

    def refresh(self, uri):
        logger.info("refreshing for uri: " + uri)
        if uri == "":
            # we need to flush everything
            self.refCache = {}
        else:
            self.refCache[uri] = None
        return

    def lookup(self, uris):
        logger.debug("lookup: " + str(uris))
        if uris in self.trackCache:
            track = self.trackCache[uris]
            return [track]
        else:
            return []

    def get_images(self, uris):
        logger.debug("get_images:" + str(uris))
        ret = {}
        for uri in uris:
            if uri in self.imageCache:
                img = self.imageCache[uri]
                if img is not None:
                    ret[uri] = [img]
        return ret

    def search(self, query=None, uris=None, exact=False):
        return {}


class HearthisSimplePlaybackProvider(PlaybackProvider):
    def translate_uri(self, uri):
        logger.debug("translate_uri: " + uri)
        play_uri = uri[uri.rfind(":") :]
        play_uri = base64.b64decode(play_uri.encode())
        logger.debug("play_uri: " + play_uri.decode())
        return play_uri.decode()

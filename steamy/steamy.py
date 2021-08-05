import logging
import time

import requests
import xmltodict
from pyquery import PyQuery

import SteamyMarket
from constants import *

log = logging.getLogger(__name__)


def retry_request(f, count=5, delay=3):
    for _ in range(count):
        try:
            r = f(requests)
            r.raise_for_status()
            return r
        except requests.exceptions.RequestException:
            log.exception("Failed to make a request in retry-mode: ")
            time.sleep(delay)
    return None


class WorkshopEntity(object):
    """
    Represents an entity on the Steam workshop. This is a base
    class that has some base attributes for workshop items, which
    is inherited by sub-types/objects
    """

    def __init__(self, id, title, desc, game, user):
        self.id = id
        self.title = title
        self.desc = desc
        self.game = game
        self.user = user
        self.tags = []


class WorkshopFile(WorkshopEntity):
    """
    Represents an actual file on the workshop. Normally a map,
    sometimes other types of files (skins, etc)
    """

    def __init__(self, *args):
        super(WorkshopFile, self).__init__(*args)

        self.size = None
        self.posted = None
        self.updated = None
        self.thumb = None
        self.images = []


class WorkshopCollection(WorkshopEntity):
    """
    Represents a collection of workshop files
    """

    def __init__(self, *args):
        super(WorkshopCollection, self).__init__(*args)

        self.files = []


class SteamAPIError(Exception):
    """
    This Exception is raised when the Steam API
    either times out, or returns invalid data to us
    """


def get_group_members(id_, page=1):
    """
    Returns a list of steam 64bit ID's for every member in group `group`,
    a group public shortname or ID.
    """
    r = retry_request(lambda f: f.get(STEAM_GROUP_LIST_URL.format(id=id_), timeout=10, params={
        "p": page
    }))

    if not r:
        raise SteamAPIError("Failed to getGroupMembers for group id `%s`" % id_)

    try:
        data = xmltodict.parse(r.content)
    except Exception:
        raise SteamAPIError("Failed to parse result from getGroupMembers for group id `%s`" % id_)

    # result = list(map(int, data['memberList']['members'].values()))

    result = list(dict(data['memberList']['members']).values())[0]
    # result = data['memberList']['members'].values()
    return result
    # return map(int, data['memberList']['members'].values()[0])


class SteamAPI(object):
    """
    A wrapper around the normal steam API
    """

    def __init__(self, key, retry=True):
        self.key = key
        self.retry = retry

    def market(self, appid):
        """
        Obtain a SteamMarketAPI object with a proper Steam API key set
        """
        return SteamyMarket.SteamMarketAPI(appid, key=self.key)

    def request(self, url, data, verb="GET", **kwargs):
        """
        A meta function used to call the steam API
        """
        url = "http://api.steampowered.com/%s" % url
        data['key'] = self.key

        if self.retry:
            resp = retry_request(lambda f: getattr(f, verb.lower())(url, params=data, **kwargs))
        else:
            resp = getattr(requests, verb.lower())(url, params=data, **kwargs)

        if not resp:
            raise SteamAPIError("Failed to request url `%s`" % url)
        return resp.json()

    def get_trade_offer(self, id):
        """
        Gets a TradeOffer object for the given id
        """
        data = self.request("IEconService/GetTradeOffer/v1/", {
            "tradeofferid": id
        }, timeout=10)

        return data["response"]["offer"]

    def cancel_trade_offer(self, id):
        data = self.request("IEconService/CancelTradeOffer/v1/", {
            "tradeofferid": id
        }, timeout=10, verb="POST")

        return True

    def get_friend_list(self, id, relationship="all"):
        data = self.request("ISteamUser/GetFriendList/v0001/", {
            "steamid": id,
            "relationship": relationship
        }, timeout=10)

        return map(lambda i: i.get("steamid"), data["friendslist"]["friends"])

    def get_from_vanity(self, vanity):
        """
        Returns a steamid from a vanity name
        """

        data = self.rqeuest("ISteamUser/ResolveVanityURL/v0001/", {
            "vanityurl": vanity
        }, timeout=10)

        return int(data["response"].get("steamid", 0))

    def get_user_info(self, id):
        """
        Returns a dictionary of user info for a steam id
        """

        data = self.request("ISteamUser/GetPlayerSummaries/v0001", {
            "steamids": id
        }, timeout=10)

        if not data['response']['players']['player'][0]:
            raise SteamAPIError("Failed to get user info for user id `%s`" % id)

        return data['response']['players']['player'][0]

    def get_recent_games(self, id):
        return self.request("IPlayerService/GetRecentlyPlayedGames/v0001", {"steamid": id}, timeout=10)["response"][
            "games"]

    def get_player_bans(self, id):
        data = self.request("ISteamUser/GetPlayerBans/v1", {
            "steamids": str(id)
        }, timeout=10)

        return data["players"][0]

    def get_workshop_file(self, id):
        r = retry_request(
            lambda f: f.get("http://steamcommunity.com/sharedfiles/filedetails/", params={"id": id}, timeout=10))
        q = PyQuery(r.content)

        if not len(q(".breadcrumbs")):
            raise SteamAPIError("Failed to get workshop file id `%s`" % id)

        breadcrumbs = [(i.text, i.get("href")) for i in q(".breadcrumbs")[0]]
        if not len(breadcrumbs):
            raise Exception("Invalid Workshop ID!")

        gameid = int(breadcrumbs[0][1].rsplit("/", 1)[-1])
        userid = re.findall("steamcommunity.com/(profiles|id)/(.*?)$",
                            breadcrumbs[-1][1])[0][-1].split("/", 1)[0]
        title = q(".workshopItemTitle")[0].text

        desc = (q(".workshopItemDescription") if len(q(".workshopItemDescription"))
                else q(".workshopItemDescriptionForCollection"))[0].text

        if len(breadcrumbs) == 3:
            size, posted, updated = [[x.text for x in i]
                                     for i in q(".detailsStatsContainerRight")][0]

            wf = WorkshopFile(id, title, desc, gameid, userid)
            wf.size = size
            wf.posted = posted
            wf.updated = updated
            wf.tags = [i[1].text.lower() for i in q(".workshopTags")]
            thumbs = q(".highlight_strip_screenshot")
            base = q(".workshopItemPreviewImageEnlargeable")
            if len(thumbs):
                wf.images = [i[0].get("src").rsplit("/", 1)[0] + "/" for i in thumbs]
            elif len(base):
                wf.images.append(base[0].get("src").rsplit("/", 1)[0] + "/")
            if len(q(".workshopItemPreviewImageMain")):
                wf.thumb = q(".workshopItemPreviewImageMain")[0].get("src")
            else:
                wf.thumb = wf.images[0]

            return wf
        elif len(breadcrumbs) == 4 and breadcrumbs[2][0] == "Collections":
            wc = WorkshopCollection(id, title, desc, gameid, userid)
            for item in q(".workshopItem"):
                id = item[0].get("href").rsplit("?id=", 1)[-1]
                wc.files.append(self.getWorkshopFile(id))
            return wc

    def get_asset_class_info(self, assetid, appid, instanceid=None):
        args = {
            "appid": appid,
            "class_count": 1,
            "classid0": assetid
        }

        ikey = str(assetid)
        if instanceid:
            args['instanceid0'] = instanceid
            ikey = "{}_{}".format(assetid, instanceid)

        data = self.request("ISteamEconomy/GetAssetClassInfo/v001/", args, timeout=10)
        return data["result"][ikey]

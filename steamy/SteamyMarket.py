import logging
import time
import json
import datetime

import requests
from pyquery import PyQuery

from constants import *

log = logging.getLogger(__name__)


def format_query_string(**kwargs):
    return "?" + '&'.join(['%s=%s' % i for i in kwargs.items()])


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


class SteamAPIError(Exception):
    """
    This Exception is raised when the Steam API
    either times out, or returns invalid data to us
    """


class InvalidInventoryException(SteamAPIError):
    """
    This exception is raised when an inventory is empty or invalid. Generally
    this will be raised if the user does not own the game, or has never owned
    an item from the game. May also occur from invalid appid/contextid
    """


# TODO Unclear what the purpose of this function is as it is never called anywhere nor documented.
def parse_item_name(name) -> object:
    """
    Strip out unicode
    :param name:
    :rtype: object
    """
    name = filter(lambda i: ord(i) <= 256, name)

    r_skin = ""
    r_wear = ""
    r_stat = False
    r_holo = False
    r_mkit = False
    parsed = False

    if name.strip().startswith("Sticker"):
        r_item = "sticker"
        r_skin = name.split("|", 1)[-1]
        if "(holo)" in r_skin:
            r_skin = r_skin.replace("(holo)")
            r_holo = True
        if "|" in r_skin:
            r_skin, r_wear = r_skin.split("|", 1)
        parsed = True
    elif name.strip().startswith("Music Kit"):
        r_item = "musickit"
        r_skin = name.split("|", 1)[-1]
        r_mkit = True
    else:
        if '|' in name:
            start, end = name.split(" | ")
        else:
            start = name
            end = None

        if start.strip().startswith("StatTrak"):
            r_stat = True
            r_item = start.split(" ", 2)[-1]
        else:
            r_stat = False
            r_item = start.strip()

        if end:
            r_skin, ext = end.split("(")
            r_wear = ext.replace(")", "")
        parsed = True

    if not parsed:
        log.warning("Failed to parse item name `%s`" % name)

    return (
        r_item.lower().strip() or None,
        r_skin.lower().strip() or None,
        r_wear.lower().strip() or None,
        r_stat,
        r_holo,
        r_mkit
    )


def get_bulkitem_price(nameid):
    url = BULK_ITEM_PRICE_QUERY.format(nameid=nameid)
    r = retry_request(lambda f: f.get(url))

    if not r:
        raise SteamAPIError("Failed to get bulkitem price for nameid `%s`" % nameid)
    r = r.json()

    data = PyQuery(r["sell_order_summary"])("span")
    b_volume = int(data.text().split(" ", 1)[0])
    b_price = int(r["lowest_sell_order"]) * .01

    return b_volume, b_price


class SteamMarketAPI(object):
    def __init__(self, appid, key=None, retries=5):
        self.appid = appid
        self.key = key
        self.retries = retries

    def get_inventory(self, steamid, context=2):
        url = INVENTORY_QUERY.format(id=steamid, app=self.appid, ctx=context)

        r = retry_request(lambda f: f.get(url, timeout=10))
        if not r:
            raise SteamAPIError("Failed to get inventory for steamid %s" % id)

        data = r.json()
        if not data.get("success"):
            raise InvalidInventoryException("Invalid Inventory")

        return data

    def get_item_count(self, query=""):
        r = retry_request(lambda f: f.get(MARKET_SEARCH_URL.format(args=format_query_string(
            query=query, appid=self.appid
        ))))

        if not r:
            raise SteamAPIError("Failed to get item count for query `%s`" % query)

        return r.json()["total_count"]

    def list_items(self, query="", start=0, count=10, sort="quantity", order="desc"):
        url = LIST_ITEMS_QUERY.format(
            query=query,
            start=start,
            count=count,
            sort=sort,
            order=order,
            appid=self.appid)

        r = retry_request(lambda f: f.get(url))
        if not r:
            log.error("Failed to list items: %s", url)
            return None

        pq = PyQuery(r.json()["results_html"])
        rows = pq(".market_listing_row .market_listing_item_name")
        return map(lambda i: i.text, rows)

    def get_item_meta(self, item_name):
        r = retry_request(
            lambda f: f.get(ITEM_PAGE_QUERY.format(name=item_name, appid=self.appid), timeout=10))

        if not r:
            raise SteamAPIError("Failed to get item meta data for item `%s`" % item_name)

        data = {}

        class_id = class_id_re.findall(r.content)
        if not len(class_id):
            raise SteamAPIError("Failed to find class_id for item_meta `%s`" % item_name)
        data["classid"] = int(class_id[0])

        name_id = name_id_re.findall(r.content)
        data["nameid"] = name_id[0] if len(name_id) else None

        pq = PyQuery(r.content)
        try:
            data["image"] = pq(".market_listing_largeimage")[0][0].get("src")
        except Exception:
            data["image"] = None

        return data

    def get_historical_price_data(self, item_name):
        url = ITEM_PAGE_QUERY.format(name=item_name, appid=self.appid)
        r = retry_request(lambda f: f.get(url))
        if not r:
            raise Exception("Failed to get historical price data for `%s`" % item_name)

        if not "var line1=[[" in r.content:
            raise Exception("Invalid response from steam for historical price data")
        data = json.loads(r.content.split("var line1=", 1)[-1].split(";", 1)[0])
        return data

    def get_item_price_history(self, item_name):
        url = ITEM_PAGE_QUERY.format(
            name=item_name,
            appid=self.appid)

        r = retry_request(lambda f: f.get(url))
        if not r:
            raise SteamAPIError("Failed to get_item_price_history for item `%s`" % item_name)

        if 'var line1' not in r.content:
            raise SteamAPIError("Invalid response for get_item_price_history of `%s`" % item_name)

        raw = json.loads(re.findall("var line1=(.+);", r.content)[0])

        keys = map(lambda i: datetime.strptime(i[0].split(":")[0], "%b %d %Y %M"), raw)
        values = map(lambda i: i[1], raw)
        return dict(zip(keys, values))

    def get_item_price(self, item_name):
        url = ITEM_PRICE_QUERY.format(
            name=item_name,
            appid=self.appid)

        r = retry_request(lambda f: f.get(url))
        if not r:
            return (0, 0.0, 0.0)

        r = r.json()
        return (
            int(r["volume"].replace(",", "")) if 'volume' in r else -1,
            float(r["lowest_price"].split(";")[-1]) if 'lowest_price' in r else 0.0,
            float(r["median_price"].split(";")[-1]) if 'median_price' in r else 0.0,
        )

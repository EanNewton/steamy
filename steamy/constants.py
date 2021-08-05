import re

MARKET_URL = u"http://steamcommunity.com/market/"
MARKET_SEARCH_URL = MARKET_URL + "search/render/{args}"
STEAM_GROUP_LIST_URL = u"http://steamcommunity.com/groups/{id}/memberslistxml/?xml=1"

LIST_ITEMS_QUERY = u"http://steamcommunity.com/market/search/render/?query={query}&start={start}&count={" \
                   u"count}&search_descriptions=0&sort_column={sort}&sort_dir={order}&appid={appid} "
ITEM_PRICE_QUERY = u"http://steamcommunity.com/market/priceoverview/?country=US&currency=1&appid={" \
                   u"appid}&market_hash_name={name} "
ITEM_PAGE_QUERY = u"http://steamcommunity.com/market/listings/{appid}/{name}"
INVENTORY_QUERY = u"http://steamcommunity.com/profiles/{id}/inventory/json/{app}/{ctx}"
BULK_ITEM_PRICE_QUERY = u"http://steamcommunity.com/market/itemordershistogram?country=US&language=english&currency=1" \
                        u"&item_nameid={nameid} "

steam_id_re = re.compile('steamcommunity.com/openid/id/(.*?)$')
class_id_re = re.compile('"classid":"(\\d+)"')
name_id_re = re.compile('Market_LoadOrderSpread\( (\\d+) \)\;')

id_RimWorld = 294100

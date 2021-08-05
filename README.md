# Steamy

This is a fork of b1naryth1ef/steamy which was last updated in 2015; the original code was solid but I did some refactoring and other changes with the intent of breathing some life into it and use for Discord bots. 

Important API changes that will break legacy code:
* In SteamMarketAPI parse_item_name() and get_bulkitem_price() have been moved from methods to functions.
* In SteamAPI get_group_members() has been moved from a method to a function.

The following is the origin codebase's README.md (sic):

Steamy is a lightweight, limited-abstraction interface to both the [public Steam Web API](https://developer.valvesoftware.com/wiki/Steam_Web_API) and a custom Steam Market API.

## Public Steam Web API
To interface with the public Steam Web API, you must have a [Steam API Key](https://steamcommunity.com/dev/apikey). To get started, create an instance of the SteamAPI interface:

```
steam = SteamAPI(my_api_key)
```

### Examples

Get a trade offer
```
offer = steam.get_trade_offer(offer_id)
assert offer['tradeofferid'] == offer_id
```

Get members for a group
```
members = steam.get_group_members("testgroupplzignore", page=1)
assert len(members)
```

### Workshop Interface
The SteamAPI interface also provides the ability to query workshop items:

```
wfile = steam.get_workshop_file("447269341")
assert isinstance(wfile, WorkshopFile)
assert wfile.id == "447269341"
```


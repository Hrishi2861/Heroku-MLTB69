#!/usr/bin/env python3
from time import sleep, time
from uuid import uuid4
from base64 import b64encode
from random import (
    choice,
    random,
    randrange
)
from ..ext_utils.status_utils import get_readable_time
from ..telegram_helper.button_build import ButtonMaker

from cloudscraper import create_scraper
from urllib.parse import quote
from urllib3 import disable_warnings

from bot import (
    LOGGER,
    shorteneres_list,
    config_dict,
    user_data,
    DATABASE_URL,
    bot_name
)
from .db_handler import DbManager

def short_url(longurl, attempt=0):
    if not shorteneres_list:
        return longurl
    if attempt >= 4:
        return longurl
    i = (
        0
        if len(shorteneres_list) == 1
        else randrange(len(shorteneres_list))
    )
    _shorten_dict = shorteneres_list[i]
    _shortener = _shorten_dict["domain"]
    _shortener_api =  _shorten_dict["api_key"]
    cget = create_scraper().request
    disable_warnings()
    try:
        if "shorte.st" in _shortener:
            headers = {"public-api-token": _shortener_api}
            data = {"urlToShorten": quote(longurl)}
            return cget(
                "PUT",
                "https://api.shorte.st/v1/data/url",
                headers=headers,
                data=data
            ).json()["shortenedUrl"]
        elif "linkvertise" in _shortener:
            url = quote(b64encode(longurl.encode("utf-8")))
            linkvertise = [
                f"https://link-to.net/{_shortener_api}/{random() * 1000}/dynamic?r={url}",
                f"https://up-to-down.net/{_shortener_api}/{random() * 1000}/dynamic?r={url}",
                f"https://direct-link.net/{_shortener_api}/{random() * 1000}/dynamic?r={url}",
                f"https://file-link.net/{_shortener_api}/{random() * 1000}/dynamic?r={url}"]
            return choice(linkvertise)
        elif "bitly.com" in _shortener:
            headers = {"Authorization": f"Bearer {_shortener_api}"}
            return cget(
                "POST",
                "https://api-ssl.bit.ly/v4/shorten",
                json={"long_url": longurl},
                headers=headers
            ).json()["link"]
        elif "ouo.io" in _shortener:
            return cget(
                "GET",
                f"http://ouo.io/api/{_shortener_api}?s={longurl}",
                verify=False
            ).text
        elif "cutt.ly" in _shortener:
            return cget(
                "GET",
                f"http://cutt.ly/api/api.php?key={_shortener_api}&short={longurl}",
                verify=False
            ).json()["url"]["shortLink"]
        else:
            res = cget(
                "GET",
                f"https://{_shortener}/api?api={_shortener_api}&url={quote(longurl)}"
            ).json()
            shorted = res["shortenedUrl"]
            if not shorted:
                shrtco_res = cget(
                    "GET",
                    f"https://api.shrtco.de/v2/shorten?url={quote(longurl)}"
                ).json()
                shrtco_link = shrtco_res["result"]["full_short_link"]
                res = cget(
                    "GET",
                    f"https://{_shortener}/api?api={_shortener_api}&url={shrtco_link}"
                ).json()
                shorted = res["shortenedUrl"]
            if not shorted:
                shorted = longurl
            return shorted
    except Exception as e:
        LOGGER.error(e)
        sleep(1)
        attempt +=1
        return short_url(
            longurl,
            attempt
        )

async def checking_access(user_id, button=None):
    if not config_dict["TOKEN_TIMEOUT"]:
        return None, button
    user_data.setdefault(user_id, {})
    data = user_data[user_id]
    if DATABASE_URL:
        data["time"] = await DbManager().get_token_expire_time(user_id)
    expire = data.get("time")
    isExpired = (
        expire is None
        or expire is not None
        and (time() - expire) > config_dict["TOKEN_TIMEOUT"]
    )
    if isExpired:
        token = (
            data["token"]
            if expire is None
            and "token" in data
            else str(uuid4())
        )
        inittime = time()
        if expire is not None:
            del data["time"]
        data["token"] = token
        data["inittime"] = inittime
        if DATABASE_URL:
            await DbManager().update_user_token(
                user_id,
                token,
                inittime
            )
        user_data[user_id].update(data)
        if button is None:
            button = ButtonMaker()
        button.url_button(
            "Get New Token",
            short_url(f"https://redirect.jet-mirror.in/{bot_name}/{token}")
        )
        tmsg = (
            "Your <b>Token</b> is expired. Get a new one."
            f"\n<b>Token Validity</b>: {get_readable_time(config_dict["TOKEN_TIMEOUT"])}\n\n"
            "<b>Your Limites:</b>\n"
            f"{config_dict["USER_MAX_TASKS"]} parallal tasks.\n"
        )
        return (
            tmsg,
            button
        )
    return (
        None,
        button
    )
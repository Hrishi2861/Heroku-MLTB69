from aiofiles import open as aiopen
from aiofiles.os import path as aiopath, remove
from asyncio import gather, create_subprocess_exec
from os import execl as osexecl
from psutil import (
    disk_usage,
    cpu_percent,
    swap_memory,
    cpu_count,
    virtual_memory,
    net_io_counters,
    boot_time,
)
import asyncio
from pyrogram.filters import command
from pyrogram.handlers import MessageHandler
from signal import signal, SIGINT
from sys import executable
from time import time
from uuid import uuid4

from bot import (
    bot,
    botStartTime,
    LOGGER,
    intervals,
    config_dict,
    scheduler,
    sabnzbd_client,
    user_data,
    bot_name,
    DATABASE_URL
)
from .helper.ext_utils.db_handler import DbManager
from .helper.ext_utils.shorteners import short_url
from .helper.ext_utils.telegraph_helper import telegraph
from .helper.ext_utils.bot_utils import (
    cmd_exec,
    sync_to_async,
    create_help_buttons,
    new_task,
)
from .helper.ext_utils.db_handler import database
from .helper.ext_utils.files_utils import clean_all, exit_clean_up
from .helper.ext_utils.jdownloader_booter import jdownloader
from .helper.ext_utils.status_utils import get_readable_file_size, get_readable_time
from .helper.listeners.aria2_listener import start_aria2_listener
from .helper.mirror_leech_utils.rclone_utils.serve import rclone_serve_booter
from .helper.telegram_helper.bot_commands import BotCommands
from .helper.telegram_helper.button_build import ButtonMaker
from .helper.telegram_helper.filters import CustomFilters
from .helper.telegram_helper.message_utils import send_message, edit_message, send_file
from .modules import (
    authorize,
    cancel_task,
    clone,
    exec,
    file_selector,
    gd_count,
    gd_delete,
    gd_search,
    mirror_leech,
    status,
    ytdlp,
    shell,
    users_settings,
    bot_settings,
    help,
    force_start,
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


async def start(client, message):
    sticker_message = await message.reply_sticker("CAACAgIAAxkBAAEarGtmq8a_Hy6_Pk8IzUHRO8i1dvwDyAACFh4AAuzxOUkNYHq7o3u0ODUE")
    await asyncio.sleep(2)
    await sticker_message.delete()
    if (
        len(message.command) > 1
        and len(message.command[1]) == 36
    ):
        userid = message.from_user.id
        input_token = message.command[1]
        if DATABASE_URL:
            stored_token = await DbManager().get_user_token(userid)
            if stored_token is None:
                return await send_message(
                    message,
                    "This token is not associated with your account.\n\nPlease generate your own token."
                )
            if input_token != stored_token:
                return await send_message(
                    message,
                    "Invalid token.\n\nPlease generate a new one."
                )
        if userid not in user_data:
            return await send_message(
                message,
                "This token is not yours!\n\nKindly generate your own."
            )
        data = user_data[userid]
        if (
            "token" not in data
            or data["token"] != input_token
        ):
            return await send_message(
                message,
                "Token already used!\n\nKindly generate a new one."
            )
        token = str(uuid4())
        ttime = time()
        data["token"] = token
        data["time"] = ttime
        user_data[userid].update(data)
        if DATABASE_URL:
            await DbManager().update_user_tdata(
                userid,
                token,
                ttime
            )
        msg = (
            "<b>Your token refreshed successfully!</b>\n"
            f"➜ Validity: {get_readable_time(int(config_dict["TOKEN_TIMEOUT"]))}\n\n"
            "<b><i>Your Limites:</i></b>\n"
            f"➜ {config_dict["USER_MAX_TASKS"]} parallal tasks.\n"
        )

        return await send_message(
            message,
            msg
        )
    elif (
        config_dict["DM_MODE"]
        and message.chat.type != message.chat.type.SUPERGROUP
    ):
        start_string = 'Bot Started.\n' \
                       'Now I will send all of your stuffs here.\n' \
                       'Use me at: @JetMirror \n'
    elif (
        not config_dict["DM_MODE"]
        and message.chat.type != message.chat.type.SUPERGROUP
        and not await CustomFilters.authorized(client, message)
    ):
        start_string = 'Sorry, you cannot use me here!\n' \
                       'Join: @JetMirror to use me.\n' \
                       'Thank You.\n'
    elif (
        not config_dict["DM_MODE"]
        and message.chat.type != message.chat.type.SUPERGROUP
        and await CustomFilters.authorized(client, message)
    ):
        start_string = 'Sorry, you cannot use me here!\n' \
                       'Join: @JetMirror to use me.\n' \
                       'Thank You.\n'
    else:
        tag = message.from_user.mention
        start_string = "Start me in DM, not in the group.\n" \
                       f"cc: {tag}"
#     await send_message(
#         message,
#         start_string
# )
    buttons = ButtonMaker()
    buttons.url_button("Join Channel 🚀", "https://t.me/JetMirror")
    buttons.url_button("Owner ☀️", "https://t.me/hrishikesh2861")
    reply_markup = buttons.build_menu(2)
    await client.send_photo(
        chat_id=message.chat.id,
        photo="/usr/src/app/Jet.jpg",
        caption=start_string,
        reply_markup=reply_markup
    )


@new_task
async def restart(_, message):
    intervals["stopAll"] = True
    restart_message = await send_message(message, "Restarting...")
    if scheduler.running:
        scheduler.shutdown(wait=False)
    if qb := intervals["qb"]:
        qb.cancel()
    if jd := intervals["jd"]:
        jd.cancel()
    if nzb := intervals["nzb"]:
        nzb.cancel()
    if st := intervals["status"]:
        for intvl in list(st.values()):
            intvl.cancel()
    await sync_to_async(clean_all)
    if sabnzbd_client.LOGGED_IN:
        await gather(
            sabnzbd_client.pause_all(),
            sabnzbd_client.purge_all(True),
            sabnzbd_client.delete_history("all", delete_files=True),
        )
    proc1 = await create_subprocess_exec(
        "pkill",
        "-9",
        "-f",
        "gunicorn|xria|xnox|xtra|xone|java|sabnzbdplus",
    )
    proc2 = await create_subprocess_exec("python3", "update.py")
    await gather(proc1.wait(), proc2.wait())
    async with aiopen(".restartmsg", "w") as f:
        await f.write(f"{restart_message.chat.id}\n{restart_message.id}\n")
    osexecl(executable, executable, "-m", "bot")


@new_task
async def ping(_, message):
    start_time = int(round(time() * 1000))
    reply = await send_message(message, "Starting Ping")
    end_time = int(round(time() * 1000))
    await edit_message(reply, f"{end_time - start_time} ms")


@new_task
async def log(_, message):
    await send_file(message, "log.txt")


help_string = f"""
NOTE: Try each command without any argument to see more detalis.
/{BotCommands.MirrorCommand[0]} or /{BotCommands.MirrorCommand[1]}: Start mirroring to cloud.
/{BotCommands.QbMirrorCommand[0]} or /{BotCommands.QbMirrorCommand[1]}: Start Mirroring to cloud using qBittorrent.
/{BotCommands.JdMirrorCommand[0]} or /{BotCommands.JdMirrorCommand[1]}: Start Mirroring to cloud using JDownloader.
/{BotCommands.NzbMirrorCommand[0]} or /{BotCommands.NzbMirrorCommand[1]}: Start Mirroring to cloud using Sabnzbd.
/{BotCommands.YtdlCommand[0]} or /{BotCommands.YtdlCommand[1]}: Mirror yt-dlp supported link.
/{BotCommands.LeechCommand[0]} or /{BotCommands.LeechCommand[1]}: Start leeching to Telegram.
/{BotCommands.QbLeechCommand[0]} or /{BotCommands.QbLeechCommand[1]}: Start leeching using qBittorrent.
/{BotCommands.JdLeechCommand[0]} or /{BotCommands.JdLeechCommand[1]}: Start leeching using JDownloader.
/{BotCommands.NzbLeechCommand[0]} or /{BotCommands.NzbLeechCommand[1]}: Start leeching using Sabnzbd.
/{BotCommands.YtdlLeechCommand[0]} or /{BotCommands.YtdlLeechCommand[1]}: Leech yt-dlp supported link.
/{BotCommands.CloneCommand} [drive_url]: Copy file/folder to Google Drive.
/{BotCommands.CountCommand} [drive_url]: Count file/folder of Google Drive.
/{BotCommands.DeleteCommand} [drive_url]: Delete file/folder from Google Drive (Only Owner & Sudo).
/{BotCommands.UserSetCommand[0]} or /{BotCommands.UserSetCommand[1]} [query]: Users settings.
/{BotCommands.BotSetCommand[0]} or /{BotCommands.BotSetCommand[1]} [query]: Bot settings.
/{BotCommands.SelectCommand}: Select files from torrents or nzb by gid or reply.
/{BotCommands.CancelTaskCommand[0]} or /{BotCommands.CancelTaskCommand[1]} [gid]: Cancel task by gid or reply.
/{BotCommands.ForceStartCommand[0]} or /{BotCommands.ForceStartCommand[1]} [gid]: Force start task by gid or reply.
/{BotCommands.CancelAllCommand} [query]: Cancel all [status] tasks.
/{BotCommands.ListCommand} [query]: Search in Google Drive(s).
/{BotCommands.SearchCommand} [query]: Search for torrents with API.
/{BotCommands.StatusCommand}: Shows a status of all the downloads.
/{BotCommands.StatsCommand}: Show stats of the machine where the bot is hosted in.
/{BotCommands.PingCommand}: Check how long it takes to Ping the Bot (Only Owner & Sudo).
/{BotCommands.AuthorizeCommand}: Authorize a chat or a user to use the bot (Only Owner & Sudo).
/{BotCommands.UnAuthorizeCommand}: Unauthorize a chat or a user to use the bot (Only Owner & Sudo).
/{BotCommands.UsersCommand}: show users settings (Only Owner & Sudo).
/{BotCommands.AddSudoCommand}: Add sudo user (Only Owner).
/{BotCommands.RmSudoCommand}: Remove sudo users (Only Owner).
/{BotCommands.RestartCommand}: Restart and update the bot (Only Owner & Sudo).
/{BotCommands.LogCommand}: Get a log file of the bot. Handy for getting crash reports (Only Owner & Sudo).
/{BotCommands.ShellCommand}: Run shell commands (Only Owner).
/{BotCommands.AExecCommand}: Exec async functions (Only Owner).
/{BotCommands.ExecCommand}: Exec sync functions (Only Owner).
/{BotCommands.ClearLocalsCommand}: Clear {BotCommands.AExecCommand} or {BotCommands.ExecCommand} locals (Only Owner).
/{BotCommands.RssCommand}: RSS Menu.
"""


@new_task
async def bot_help(_, message):
    await send_message(message, help_string)


async def restart_notification():
    if await aiopath.isfile(".restartmsg"):
        with open(".restartmsg") as f:
            chat_id, msg_id = map(int, f)
    else:
        chat_id, msg_id = 0, 0

    async def send_incomplete_task_message(cid, msg):
        try:
            if msg.startswith("Restarted Successfully!"):
                await bot.edit_message_text(
                    chat_id=chat_id, message_id=msg_id, text=msg
                )
                await remove(".restartmsg")
            else:
                await bot.send_message(
                    chat_id=cid,
                    text=msg,
                    disable_web_page_preview=True,
                    disable_notification=True,
                )
        except Exception as e:
            LOGGER.error(e)

    if config_dict["INCOMPLETE_TASK_NOTIFIER"] and config_dict["DATABASE_URL"]:
        if notifier_dict := await database.get_incomplete_tasks():
            for cid, data in notifier_dict.items():
                msg = "Restarted Successfully!" if cid == chat_id else "Bot Restarted!"
                for tag, links in data.items():
                    msg += f"\n\n{tag}: "
                    for index, link in enumerate(links, start=1):
                        msg += f" <a href='{link}'>{index}</a> |"
                        if len(msg.encode()) > 4000:
                            await send_incomplete_task_message(cid, msg)
                            msg = ""
                if msg:
                    await send_incomplete_task_message(cid, msg)

    if await aiopath.isfile(".restartmsg"):
        try:
            await bot.edit_message_text(
                chat_id=chat_id, message_id=msg_id, text="Restarted Successfully!"
            )
        except:
            pass
        await remove(".restartmsg")


async def main():
    if config_dict["DATABASE_URL"]:
        await database.db_load()
    await gather(
        jdownloader.boot(),
        sync_to_async(clean_all),
        bot_settings.initiate_search_tools(),
        restart_notification(),
        telegraph.create_account(),
        rclone_serve_booter(),
        sync_to_async(start_aria2_listener, wait=False),
    )
    create_help_buttons()

    bot.add_handler(
        MessageHandler(
            start, filters=command(BotCommands.StartCommand, case_sensitive=True)
        )
    )
    bot.add_handler(
        MessageHandler(
            log,
            filters=command(BotCommands.LogCommand, case_sensitive=True)
            & CustomFilters.sudo,
        )
    )
    bot.add_handler(
        MessageHandler(
            restart,
            filters=command(BotCommands.RestartCommand, case_sensitive=True)
            & CustomFilters.sudo,
        )
    )
    bot.add_handler(
        MessageHandler(
            ping,
            filters=command(BotCommands.PingCommand, case_sensitive=True)
            & CustomFilters.authorized,
        )
    )
    bot.add_handler(
        MessageHandler(
            bot_help,
            filters=command(BotCommands.HelpCommand, case_sensitive=True)
            & CustomFilters.authorized,
        )
    )
    LOGGER.info("🚀 Jet Bot Started!")
    signal(SIGINT, exit_clean_up)


bot.loop.run_until_complete(main())
bot.loop.run_forever()

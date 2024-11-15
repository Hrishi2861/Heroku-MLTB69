from psutil import (
    boot_time,
    cpu_count,
    cpu_freq,
    cpu_percent,
    disk_usage,
    net_io_counters,
    swap_memory,
    virtual_memory
)
from pyrogram.filters import command, regex
from pyrogram.handlers import MessageHandler, CallbackQueryHandler
from time import time

from bot import (
    task_dict_lock,
    status_dict,
    task_dict,
    botStartTime,
    DOWNLOAD_DIR,
    intervals,
    bot,
    config_dict,
    LOGGER
)
from ..helper.ext_utils.bot_utils import sync_to_async, new_task
from ..helper.ext_utils.status_utils import (
    MirrorStatus,
    get_progress_bar_string,
    get_readable_file_size,
    get_readable_time,
    get_specific_tasks,
    speed_string_to_bytes,
)
from ..helper.telegram_helper.bot_commands import BotCommands
from ..helper.telegram_helper.filters import CustomFilters
from ..helper.telegram_helper.message_utils import (
    send_message,
    delete_message,
    auto_delete_message,
    send_status_message,
    update_status_message,
    edit_message,
)
from ..helper.telegram_helper.button_build import ButtonMaker


@new_task
async def mirror_status(_, message):
    async with task_dict_lock:
        count = len(task_dict)
    if count == 0:
        currentTime = get_readable_time(time() - botStartTime)
        free = get_readable_file_size(disk_usage(DOWNLOAD_DIR).free)
        msg = '<b>Uninstall Telegram and enjoy your life!</b>'
        msg += '\n\nNo Active Tasks!\n___________________________'
        msg += (
            f"\n<b>CPU:</b> {cpu_percent()}% | <b>FREE:</b> {free}"
            f"\n<b>RAM:</b> {virtual_memory().percent}% | <b>UPTIME:</b> {currentTime}" \
            f"\n\n<a href='https://t.me/JetMirror'>𝑩𝒐𝒕 𝒃𝒚 🚀 𝑱𝒆𝒕-𝑴𝒊𝒓𝒓𝒐𝒓</a>")
        reply_message = await send_message(message, msg)
        await auto_delete_message(message, reply_message)
    else:
        text = message.text.split()
        if len(text) > 1:
            user_id = message.from_user.id if text[1] == "me" else int(text[1])
        else:
            user_id = 0
            sid = message.chat.id
            if obj := intervals["status"].get(sid):
                obj.cancel()
                del intervals["status"][sid]
        await send_status_message(message, user_id)
        await delete_message(message)


@new_task
async def status_pages(_, query):
    data = query.data.split()
    key = int(data[1])
    if data[2] == "ref":
        await query.answer()
        await update_status_message(key, force=True)
    elif data[2] in ["nex", "pre"]:
        await query.answer()
        async with task_dict_lock:
            if data[2] == "nex":
                status_dict[key]["page_no"] += status_dict[key]["page_step"]
            else:
                status_dict[key]["page_no"] -= status_dict[key]["page_step"]
    elif data[2] == "ps":
        await query.answer()
        async with task_dict_lock:
            status_dict[key]["page_step"] = int(data[3])
    elif data[2] == "st":
        await query.answer()
        async with task_dict_lock:
            status_dict[key]["status"] = data[3]
        await update_status_message(key, force=True)
    elif data[2] == "ov":
        message = query.message
        tasks = {
            "Download": 0,
            "Upload": 0,
            "Seed": 0,
            "Archive": 0,
            "Extract": 0,
            "Split": 0,
            "QueueDl": 0,
            "QueueUp": 0,
            "Clone": 0,
            "CheckUp": 0,
            "Pause": 0,
            "SamVid": 0,
            "ConvertMedia": 0,
        }
        dl_speed = 0
        up_speed = 0
        seed_speed = 0
        async with task_dict_lock:
            for download in task_dict.values():
                match await sync_to_async(download.status):
                    case MirrorStatus.STATUS_DOWNLOADING:
                        tasks["Download"] += 1
                        dl_speed += speed_string_to_bytes(download.speed())
                    case MirrorStatus.STATUS_UPLOADING:
                        tasks["Upload"] += 1
                        up_speed += speed_string_to_bytes(download.speed())
                    case MirrorStatus.STATUS_SEEDING:
                        tasks["Seed"] += 1
                        seed_speed += speed_string_to_bytes(download.seed_speed())
                    case MirrorStatus.STATUS_ARCHIVING:
                        tasks["Archive"] += 1
                    case MirrorStatus.STATUS_EXTRACTING:
                        tasks["Extract"] += 1
                    case MirrorStatus.STATUS_SPLITTING:
                        tasks["Split"] += 1
                    case MirrorStatus.STATUS_QUEUEDL:
                        tasks["QueueDl"] += 1
                    case MirrorStatus.STATUS_QUEUEUP:
                        tasks["QueueUp"] += 1
                    case MirrorStatus.STATUS_CLONING:
                        tasks["Clone"] += 1
                    case MirrorStatus.STATUS_CHECKING:
                        tasks["CheckUp"] += 1
                    case MirrorStatus.STATUS_PAUSED:
                        tasks["Pause"] += 1
                    case MirrorStatus.STATUS_SAMVID:
                        tasks["SamVid"] += 1
                    case MirrorStatus.STATUS_CONVERTING:
                        tasks["ConvertMedia"] += 1
                    case _:
                        tasks["Download"] += 1
                        dl_speed += speed_string_to_bytes(download.speed())

        msg = f"""<b>DL:</b> {tasks['Download']} | <b>UP:</b> {tasks['Upload']} | <b>SD:</b> {tasks['Seed']} | <b>AR:</b> {tasks['Archive']}
<b>EX:</b> {tasks['Extract']} | <b>SP:</b> {tasks['Split']} | <b>QD:</b> {tasks['QueueDl']} | <b>QU:</b> {tasks['QueueUp']}
<b>CL:</b> {tasks['Clone']} | <b>CK:</b> {tasks['CheckUp']} | <b>PA:</b> {tasks['Pause']} | <b>SV:</b> {tasks['SamVid']}
<b>CM:</b> {tasks['ConvertMedia']}

<b>ODLS:</b> {get_readable_file_size(dl_speed)}/s
<b>OULS:</b> {get_readable_file_size(up_speed)}/s
<b>OSDS:</b> {get_readable_file_size(seed_speed)}/s
"""
        button = ButtonMaker()
        button.data_button("Back", f"status {data[1]} ref")
        await edit_message(message, msg, button.build_menu())

async def stats(_, message, edit_mode=False):
    buttons = ButtonMaker()
    sysTime = get_readable_time(time() - boot_time()) # type: ignore
    botTime = get_readable_time(time() - botStartTime) # type: ignore
    remaining_time = 86400 - (time() - botStartTime)
    res_time = (
        "⚠️ Soon ⚠️"
        if remaining_time <= 0
        else get_readable_time(remaining_time)
    )
    (
        total,
        used,
        free,
        disk
    ) = disk_usage("/")
    total = get_readable_file_size(total)
    used = get_readable_file_size(used)
    free = get_readable_file_size(free)
    sent = get_readable_file_size(net_io_counters().bytes_sent)
    recv = get_readable_file_size(net_io_counters().bytes_recv)
    tb = get_readable_file_size(net_io_counters().bytes_sent + net_io_counters().bytes_recv)
    cpuUsage = cpu_percent(interval=0.1)
    v_core = cpu_count(logical=True) - cpu_count(logical=False)
    freq_info = cpu_freq(percpu=False)
    if freq_info is not None:
        frequency = freq_info.current / 1000
    else:
        frequency = "-_-"
    memory = virtual_memory()
    mem_p = memory.percent
    swap = swap_memory()

    bot_stats = f"<b><i><u>Jet 🚀 Bot Statistics</u></i></b>\n\n"\
                f"<code>CPU  : </code>{get_progress_bar_string(cpuUsage)} {cpuUsage}%\n" \
                f"<code>RAM  : </code>{get_progress_bar_string(mem_p)} {mem_p}%\n" \
                f"<code>SWAP : </code>{get_progress_bar_string(swap.percent)} {swap.percent}%\n" \
                f"<code>DISK : </code>{get_progress_bar_string(disk)} {disk}%\n\n" \
                f"<code>Bot Uptime      : </code> {botTime}\n" \
                f"<code>BOT Restart     : </code> {res_time}\n\n" \
                f"<code>Uploaded        : </code> {sent}\n" \
                f"<code>Downloaded      : </code> {recv}\n" \
                f"<code>Total Bandwidth : </code> {tb}" \
                f'\n\n<a href="https://t.me/JetMirror">𝑩𝒐𝒕 𝒃𝒚 🚀 𝑱𝒆𝒕-𝑴𝒊𝒓𝒓𝒐𝒓</a>'

    sys_stats = f"<b><i><u>Jet 🚀 System Statistics</u></i></b>\n\n"\
                f"<b>System Uptime:</b> <code>{sysTime}</code>\n" \
                f"<b>CPU:</b> {get_progress_bar_string(cpuUsage)}<code> {cpuUsage}%</code>\n" \
                f"<b>CPU Total Core(s):</b> <code>{cpu_count(logical=True)}</code>\n" \
                f"<b>P-Core(s):</b> <code>{cpu_count(logical=False)}</code> | " \
                f"<b>V-Core(s):</b> <code>{v_core}</code>\n" \
                f"<b>Frequency:</b> <code>{frequency} GHz</code>\n\n" \
                f"<b>RAM:</b> {get_progress_bar_string(mem_p)}<code> {mem_p}%</code>\n" \
                f"<b>Total:</b> <code>{get_readable_file_size(memory.total)}</code> | " \
                f"<b>Free:</b> <code>{get_readable_file_size(memory.available)}</code>\n\n" \
                f"<b>SWAP:</b> {get_progress_bar_string(swap.percent)}<code> {swap.percent}%</code>\n" \
                f"<b>Total</b> <code>{get_readable_file_size(swap.total)}</code> | " \
                f"<b>Free:</b> <code>{get_readable_file_size(swap.free)}</code>\n\n" \
                f"<b>DISK:</b> {get_progress_bar_string(disk)}<code> {disk}%</code>\n" \
                f"<b>Total:</b> <code>{total}</code> | <b>Free:</b> <code>{free}</code>" \
                f'\n\n<a href="https://t.me/JetMirror">𝑩𝒐𝒕 𝒃𝒚 🚀 𝑱𝒆𝒕-𝑴𝒊𝒓𝒓𝒐𝒓</a>'

    buttons.data_button(
        "Sys Stats",
        "show_sys_stats"
    )
    buttons.data_button(
        "Repo Stats",
        "show_repo_stats"
    )
    buttons.data_button(
        "Bot Limits",
        "show_bot_limits"
    )
    buttons.data_button(
        "Close",
        "close_signal"
    )
    sbtns = buttons.build_menu(2)
    if not edit_mode:
        await message.reply(
            bot_stats,
            reply_markup=sbtns
        )
    return bot_stats, sys_stats


async def send_bot_stats(_, query):
    buttons = ButtonMaker()
    (
        bot_stats,
        _
    ) = await stats(
        _,
        query.message,
        edit_mode=True
    )
    buttons.data_button(
        "Sys Stats",
        "show_sys_stats"
    )
    buttons.data_button(
        "Repo Stats",
        "show_repo_stats"
    )
    buttons.data_button(
        "Bot Limits",
        "show_bot_limits"
    )
    buttons.data_button(
        "Close",
        "close_signal"
    )
    sbtns = buttons.build_menu(2)
    await query.answer()
    await query.message.edit_text(
        bot_stats,
        reply_markup=sbtns
    )


async def send_sys_stats(_, query):
    buttons = ButtonMaker()
    (
        _,
        sys_stats
    ) = await stats(
        _,
        query.message,
        edit_mode=True
    )
    buttons.data_button(
        "Bot Stats",
        "show_bot_stats"
    )
    buttons.data_button(
        "Repo Stats",
        "show_repo_stats"
    )
    buttons.data_button(
        "Bot Limits",
        "show_bot_limits"
    )
    buttons.data_button(
        "Close",
        "close_signal"
    )
    sbtns = buttons.build_menu(2)
    await query.answer()
    await query.message.edit_text(
        sys_stats,
        reply_markup=sbtns
    )


async def send_repo_stats(_, query):
    buttons = ButtonMaker()
    last_commit = "No UPSTREAM_REPO"
    version = "N/A"
    change_log = "N/A"
    update_info = ""
    repo_stats = f"<b><i>Jet 🚀 Bot Repository</i></b>             \n"   \
                 f"<code>- Updated   : </code> {last_commit}\n"   \
                 f"<code>- Version   : </code> {version}    \n"   \
                 f"<code>- Changelog : </code> {change_log} \n" \
                 f"<b>{update_info}</b>\n" \
                 f'<a href="https://t.me/JetMirror">𝑩𝒐𝒕 𝒃𝒚 🚀 𝑱𝒆𝒕-𝑴𝒊𝒓𝒓𝒐𝒓</a>'

    buttons.data_button(
        "Bot Stats", 
        "show_bot_stats"
    )
    buttons.data_button(
        "Sys Stats",
        "show_sys_stats"
    )
    buttons.data_button(
        "Bot Limits",
        "show_bot_limits"
    )
    buttons.data_button(
        "Close",
        "close_signal"
    )
    sbtns = buttons.build_menu(2)
    await query.answer()
    await query.message.edit_text(
        repo_stats,
        reply_markup=sbtns
    )


async def send_bot_limits(_, query):
    buttons = ButtonMaker()
    DIR = "Unlimited" if config_dict["DIRECT_LIMIT"] == "" else config_dict["DIRECT_LIMIT"]
    JDL = "Unlimited" if config_dict["JD_LIMIT"] == "" else config_dict["JD_LIMIT"]
    NZB = "Unlimited" if config_dict["NZB_LIMIT"] == "" else config_dict["NZB_LIMIT"]
    YTD = "Unlimited" if config_dict["YTDLP_LIMIT"] == "" else config_dict["YTDLP_LIMIT"]
    YTP = "Unlimited" if config_dict["PLAYLIST_LIMIT"] == "" else config_dict["PLAYLIST_LIMIT"]
    GDL = "Unlimited" if config_dict["GDRIVE_LIMIT"] == "" else config_dict["GDRIVE_LIMIT"]
    TOR = "Unlimited" if config_dict["TORRENT_LIMIT"] == "" else config_dict["TORRENT_LIMIT"]
    CLL = "Unlimited" if config_dict["CLONE_LIMIT"] == "" else config_dict["CLONE_LIMIT"]
    RCL = "Unlimited" if config_dict["RCLONE_LIMIT"] == "" else config_dict["RCLONE_LIMIT"]
    MGA = "Unlimited" if config_dict["MEGA_LIMIT"] == "" else config_dict["MEGA_LIMIT"]
    TGL = "Unlimited" if config_dict["LEECH_LIMIT"] == "" else config_dict["LEECH_LIMIT"]
    UMT = "Unlimited" if config_dict["USER_MAX_TASKS"] == "" else config_dict["USER_MAX_TASKS"]
    BMT = "Unlimited" if config_dict["QUEUE_ALL"] == "" else config_dict["QUEUE_ALL"]

    bot_limit = f"<b><i><u>Jet 🚀 Bot Limitations</u></i></b>\n" \
                f"<code>Torrent   : {TOR}</code> <b>GB</b>\n" \
                f"<code>G-Drive   : {GDL}</code> <b>GB</b>\n" \
                f"<code>Yt-Dlp    : {YTD}</code> <b>GB</b>\n" \
                f"<code>Playlist  : {YTP}</code> <b>NO</b>\n" \
                f"<code>Direct    : {DIR}</code> <b>GB</b>\n" \
                f"<code>JDownL    : {JDL}</code> <b>GB</b>\n" \
                f"<code>NZB       : {NZB}</code> <b>GB</b>\n" \
                f"<code>Clone     : {CLL}</code> <b>GB</b>\n" \
                f"<code>Rclone    : {RCL}</code> <b>GB</b>\n" \
                f"<code>Leech     : {TGL}</code> <b>GB</b>\n" \
                f"<code>MEGA      : {MGA}</code> <b>GB</b>\n\n" \
                f"<code>User Tasks: {UMT}</code>\n" \
                f"<code>Bot Tasks : {BMT}</code>" \
                f'\n\n<a href="https://t.me/JetMirror">𝑩𝒐𝒕 𝒃𝒚 🚀 𝑱𝒆𝒕-𝑴𝒊𝒓𝒓𝒐𝒓</a>'

    buttons.data_button(
        "Bot Stats",
        "show_bot_stats"
    )
    buttons.data_button(
        "Sys Stats",
        "show_sys_stats"
    )
    buttons.data_button(
        "Repo Stats",
        "show_repo_stats"
    )
    buttons.data_button(
        "Close",
        "close_signal"
    )
    sbtns = buttons.build_menu(2)
    await query.answer()
    await query.message.edit_text(
        bot_limit,
        reply_markup=sbtns
    )


async def send_close_signal(_, query):
    await query.answer()
    try:
        await delete_message(query.message.reply_to_message)
    except Exception as e:
        LOGGER.error(e)
    await delete_message(query.message)


bot.add_handler( # type: ignore
    MessageHandler(
        stats,
        filters=command(
            BotCommands.StatsCommand,
            case_sensitive=True
        ) & CustomFilters.authorized
    )
)

bot.add_handler( # type: ignore
    MessageHandler(
        mirror_status,
        filters=command(
            BotCommands.StatusCommand,
            case_sensitive=True
        ) & CustomFilters.authorized,
    )
)

bot.add_handler( # type: ignore
    CallbackQueryHandler(
        send_close_signal,
        filters=regex(
            "^close_signal"
        )
    )
)

bot.add_handler( # type: ignore
    CallbackQueryHandler(
        send_bot_stats,
        filters=regex(
            "^show_bot_stats"
        )
    )
)

bot.add_handler( # type: ignore
    CallbackQueryHandler(
        send_sys_stats,
        filters=regex(
            "^show_sys_stats"
        )
    )
)

bot.add_handler( # type: ignore
    CallbackQueryHandler(
        send_repo_stats,
        filters=regex(
            "^show_repo_stats"
        )
    )
)

bot.add_handler( # type: ignore
    CallbackQueryHandler(
        send_bot_limits,
        filters=regex(
            "^show_bot_limits"
        )
    )
)

bot.add_handler( # type: ignore
    CallbackQueryHandler(
        status_pages,
        filters=regex(
            "^status"
        )
    )
)

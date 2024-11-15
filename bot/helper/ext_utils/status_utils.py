from html import escape
from math import e
from psutil import (
    virtual_memory,
    cpu_percent,
    disk_usage
)
from time import time
from asyncio import iscoroutinefunction

from bot import (
    DOWNLOAD_DIR,
    task_dict,
    task_dict_lock,
    botStartTime,
    config_dict,
    status_dict,
)
from .bot_utils import sync_to_async
from ..telegram_helper.button_build import ButtonMaker
from ..telegram_helper.bot_commands import BotCommands

SIZE_UNITS = [
    "B",
    "KB",
    "MB",
    "GB",
    "TB",
    "PB"
]


class MirrorStatus:
    STATUS_UPLOADING = "Upload 📤"
    STATUS_DOWNLOADING = "Download 📥"
    STATUS_CLONING = "Clone 🔃"
    STATUS_QUEUEDL = "QueueDL ⏳"
    STATUS_QUEUEUP = "QueueUL ⏳"
    STATUS_PAUSED = "Paused ⛔️"
    STATUS_ARCHIVING = "Archive 🛠"
    STATUS_EXTRACTING = "Extract 📂"
    STATUS_SPLITTING = "Split ✂️"
    STATUS_CHECKING = "CheckUp ⏱"
    STATUS_SEEDING = "Seed 🌧"
    STATUS_SAMVID = "SampleVid 🎬"
    STATUS_CONVERTING = "Convert ♻️"
    STATUS_METADATA = "Metadata 📝"


STATUSES = {
    "ALL": "All",
    "DL": MirrorStatus.STATUS_DOWNLOADING,
    "UP": MirrorStatus.STATUS_UPLOADING,
    "QD": MirrorStatus.STATUS_QUEUEDL,
    "QU": MirrorStatus.STATUS_QUEUEUP,
    "AR": MirrorStatus.STATUS_ARCHIVING,
    "EX": MirrorStatus.STATUS_EXTRACTING,
    "SD": MirrorStatus.STATUS_SEEDING,
    "CM": MirrorStatus.STATUS_CONVERTING,
    "CL": MirrorStatus.STATUS_CLONING,
    "SP": MirrorStatus.STATUS_SPLITTING,
    "CK": MirrorStatus.STATUS_CHECKING,
    "SV": MirrorStatus.STATUS_SAMVID,
    "PA": MirrorStatus.STATUS_PAUSED,
    "MD": MirrorStatus.STATUS_METADATA
}


async def get_task_by_gid(gid: str):
    async with task_dict_lock:
        for tk in task_dict.values():
            if hasattr(
                tk,
                "seeding"
            ):
                await sync_to_async(tk.update)
            if tk.gid() == gid:
                return tk
        return None


def get_specific_tasks(status, user_id):
    if status == "All":
        if user_id:
            return [
                tk
                for tk
                in task_dict.values()
                if tk.listener.user_id == user_id
            ]
        else:
            return list(task_dict.values())
    elif user_id:
        return [
            tk
            for tk in task_dict.values()
            if tk.listener.user_id == user_id
            and (
                (st := tk.status())
                and st == status
                or status == MirrorStatus.STATUS_DOWNLOADING
                and st not in STATUSES.values()
            )
        ]
    else:
        return [
            tk
            for tk in task_dict.values()
            if (st := tk.status())
            and st == status
            or status == MirrorStatus.STATUS_DOWNLOADING
            and st not in STATUSES.values()
        ]


async def get_all_tasks(req_status: str, user_id):
    async with task_dict_lock:
        return await sync_to_async(
            get_specific_tasks,
            req_status,
            user_id
        )


def get_readable_file_size(size_in_bytes):
    if not size_in_bytes:
        return "0B"

    index = 0
    while size_in_bytes >= 1024 and index < len(SIZE_UNITS) - 1:
        size_in_bytes /= 1024
        index += 1

    return f"{size_in_bytes:.2f}{SIZE_UNITS[index]}"


def get_readable_time(seconds):
    periods = [
        ("d", 86400),
        ("h", 3600),
        ("m", 60),
        ("s", 1)
    ]
    result = ""
    for (
        period_name,
        period_seconds
    ) in periods:
        if seconds >= period_seconds:
            (
                period_value,
                seconds
            ) = divmod(
                seconds,
                period_seconds
            )
            result += f"{int(period_value)}{period_name}"
    return result


def time_to_seconds(time_duration):
    (
        hours,
        minutes,
        seconds
    ) = map(int, time_duration.split(":"))
    return hours * 3600 + minutes * 60 + seconds


def speed_string_to_bytes(size_text: str):
    size = 0
    size_text = size_text.lower()
    if "k" in size_text:
        size += float(size_text.split("k")[0]) * 1024
    elif "m" in size_text:
        size += float(size_text.split("m")[0]) * 1048576
    elif "g" in size_text:
        size += float(size_text.split("g")[0]) * 1073741824
    elif "t" in size_text:
        size += float(size_text.split("t")[0]) * 1099511627776
    elif "b" in size_text:
        size += float(size_text.split("b")[0])
    return size


def get_progress_bar_string(pct):
    if isinstance(pct, str):
        pct = float(pct.strip("%"))
    p = min(
        max(pct, 0),
        100
    )
    cFull = int(p // 10)
    p_str = "★" * cFull
    p_str += "✩" * (10 - cFull)
    return f"{p_str}"


async def get_readable_message(
        sid,
        is_user,
        page_no=1,
        status="All",
        page_step=1
    ):
    msg = "<a href='https://t.me/JetMirror'>𝑩𝒐𝒕 𝒃𝒚 🚀 𝑱𝒆𝒕-𝑴𝒊𝒓𝒓𝒐𝒓</a>\n"
    button = None

    tasks = await sync_to_async(
        get_specific_tasks,
        status,
        sid
        if is_user
        else None
    )

    STATUS_LIMIT = config_dict["STATUS_LIMIT"]
    tasks_no = len(tasks)
    pages = (max(tasks_no, 1) + STATUS_LIMIT - 1) // STATUS_LIMIT
    if page_no > pages:
        page_no = (page_no - 1) % pages + 1
        status_dict[sid]["page_no"] = page_no
    elif page_no < 1:
        page_no = pages - (abs(page_no) % pages)
        status_dict[sid]["page_no"] = page_no
    start_position = (page_no - 1) * STATUS_LIMIT

    for index, task in enumerate(
        tasks[start_position : STATUS_LIMIT + start_position],
        start=1
    ):
        tstatus = (
            await sync_to_async(task.status)
            if status == "All"
            else status
        )
        # elapse = time() - task.listener.time
        # elapsed = (
        #     "-"
        #     if elapse < 1
        #     else get_readable_time(elapse)
        # )
        user_tag = task.listener.tag.replace("@", "@").replace("_", "_")
        cancel_task = (
            f"/{BotCommands.CancelTaskCommand[1]}_{task.gid()}"
        )

        # if (
        #     config_dict["DELETE_LINKS"]
        #     and int(config_dict["AUTO_DELETE_MESSAGE_DURATION"]) > 0
        # ):
        #     msg += (
        #         f"```\n#Zee{index + start_position}: "
        #         f"{escape(f"{task.name()}")}\n```"
        #         if elapse <= config_dict["AUTO_DELETE_MESSAGE_DURATION"]
        #         else f"\n<blockquote>#Zee{index + start_position}...(Processing)</blockquote>"
        #     )
        # else:
        #     msg += (
        #         f"```\n#Zee{index + start_position}: "
        #         f"{escape(f"{task.name()}")}\n```"
        #     )
        msg += (
            f"\n<blockquote>#JetMirror{index + start_position}...(Processing)</blockquote>\n"
            f"Filename: {escape(f"{task.name()}")}\n"
        )
        if tstatus not in [
            MirrorStatus.STATUS_SEEDING,
            MirrorStatus.STATUS_QUEUEUP,
        ]:
            progress = (
                await task.progress()
                if iscoroutinefunction(task.progress)
                else task.progress()
            )
            msg += (
                f"\n⌑ <b>{tstatus}</b> » {task.speed()}"
                f"\n⌑ {get_progress_bar_string(progress)} » <b><i>{progress}</i></b>"
                f"\n⌑ <code>Done   :</code> {task.processed_bytes()} of {task.size()}"
                f"\n⌑ <code>ETA    :</code> {task.eta()}"
                # f"\n⌑ <code>Past   :</code> {elapsed}"
                f"\n⌑ <code>Engine :</code> <b><i>{task.engine}</i></b>"
                f"\n⌑ <code>User   :</code> <b>{user_tag}</b>"
                f"\n⌑ <code>UserID :</code> ||{task.listener.userId}||"
                f"\n⌑ <code>Upload :</code> {task.listener.mode}"
            )
            if hasattr(
                task,
                "playList"
            ):
                try:
                    if playlist := task.playList():
                        msg += f"\n⌑ <code>YtList :</code> {playlist}"
                except:
                    pass
            if hasattr(
                task,
                "seeders_num"
            ):
                try:
                    msg += f"\n⌑ <code>S/L    :</code> {task.seeders_num()}/{task.leechers_num()}"
                except:
                    pass
        elif tstatus == MirrorStatus.STATUS_SEEDING:
            msg += (
                f"\n⌑ <code>Size   : </code>{task.size()}"
                f"\n⌑ <code>Speed  : </code>{task.seed_speed()}"
                f"\n⌑ <code>Upload : </code>{task.uploaded_bytes()}"
                f"\n⌑ <code>Ratio  : </code>{task.ratio()}"
                f"\n⌑ <code>Time   : </code>{task.seeding_time()}"
            )
        else:
            msg += (
                f"\n⌑ <code>Size   :</code> {task.size()}"
                f"\n⌑ <code>Upload :</code> {task.listener.mode}"
                # f"\n⌑ <code>Past   :</code> {elapsed}"
                f"\n⌑ <code>User   :</code> {user_tag}"
                f"\n⌑ <code>Engine :</code> {task.engine}"
            )
        msg += f"\n<blockquote>⚠️ {cancel_task}</blockquote>\n\n"

    if len(msg) == 0:
        if status == "All":
            return None, None
        else:
            msg = f"No Active {status} Tasks!\n\n"
    buttons = ButtonMaker()
    # if is_user:
    #     buttons.ibutton(
    #         "Refresh",
    #         f"status {sid} ref",
    #         position="header"
    #     )
    if not is_user:
        buttons.ibutton(
            "Task Info",
            f"status {sid} ov",
            position="footer"
        )
        buttons.ibutton(
            "System Info",
            f"status {sid} stats",
            position="footer"
        )
    if len(tasks) > STATUS_LIMIT:
        msg += f"<b>Tasks:</b> {tasks_no} | <b>Step:</b> {page_step}\n"
        buttons.ibutton(
            "⫷",
            f"status {sid} pre",
            position="header"
        )
        buttons.ibutton(
            f"Pages {page_no}/{pages}",
            f"status {sid} ref",
            position="header"
        )
        buttons.ibutton(
            "⫸",
            f"status {sid} nex",
            position="header"
        )

        if tasks_no > 30:
            for i in [
                1,
                2,
                4,
                6,
                8,
                10,
                15
            ]:
                buttons.ibutton(
                    i,
                    f"status {sid} ps {i}"
                )
    if (
        status != "All" or
        tasks_no > 20
    ):
        for (
            label,
            status_value
        ) in list(STATUSES.items())[:9]:
            if status_value != status:
                buttons.ibutton(
                    label,
                    f"status {sid} st {status_value}"
                )
    buttons.ibutton(
        "Refresh",
        f"status {sid} ref",
        position="header"
    )
    button = buttons.build_menu(8)
    msg += (
        f"<b>CPU</b>: {cpu_percent()}% | "
        f"<b>FREE</b>: {get_readable_file_size(disk_usage(DOWNLOAD_DIR).free)}\n"
        f"<b>RAM</b>: {virtual_memory().percent}% | "
        f"<b>UPTM</b>: {get_readable_time(time() - botStartTime)}"
    )
    remaining_time = 86400 - (time() - botStartTime)
    if remaining_time < 3600:
        if remaining_time > 0:
            msg += f"\n\n<b><i>Bot Restarts In: {get_readable_time(remaining_time)}</i></b>"
        else:
            msg += f"\n\n<b><i>⚠️ BOT WILL RESTART ANYTIME ⚠️</i></b>"
    return (
        msg,
        button
    )
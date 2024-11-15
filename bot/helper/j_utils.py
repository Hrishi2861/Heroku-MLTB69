from cryptography.hazmat.backends import default_backend

from bot import (
    LOGGER,
    config_dict
)
from .ext_utils.task_manager import check_user_tasks
from .ext_utils.shorteners import checking_access
from .ext_utils.db_handler import database
from .telegram_helper.message_utils import (
    auto_delete_message,
    delete_links,
    force_subscribe,
    send_message
)

async def stop_duplicate_tasks(message, link, file_=None):
    if (
        config_dict["DATABASE_URL"]
        and config_dict["STOP_DUPLICATE_TASKS"]
    ):
        raw_url = (
            file_.file_unique_id
        )
        exist = await database.check_download(raw_url) # type: ignore
        if exist:
            _msg = f'<b>Download is already added by {exist["tag"]}</b>\n'
            _msg += f'Check the download status in @{exist["botname"]}\n\n'
            _msg += f'<b>Link</b>: <code>{exist["_id"]}</code>'
            reply_message = await send_message(
                message,
                _msg
            )
            await auto_delete_message(
                message,
                reply_message
            )
            await delete_links(message)
            return "duplicate_tasks"
        return raw_url


async def none_admin_utils(message, is_leech=False):
    msg = []
    if (
        (
            maxtask := config_dict["USER_MAX_TASKS"]
        ) 
        and await check_user_tasks(
            message.from_user.id,
            maxtask
        )
    ):
        msg.append(f"Your tasks limit exceeded!\n💡Use other bots.\n\nTasks limit: {maxtask}")
    button = None
    if (
        message.chat.type
        !=
        message.chat.type.PRIVATE
    ):
        (
            token_msg,
            button
        ) = await checking_access(
            message.from_user.id,
            button
        )
        if token_msg is not None:
            msg.append(token_msg)
        if ids := config_dict["FSUB_IDS"]:
            (
                _msg,
                button
            ) = await force_subscribe(
                message,
                ids,
                button
            )
            if _msg:
                msg.append(_msg)
    await delete_links(message)
    return (
        msg,
        button
    )


backend = default_backend()
iterations = 100_000
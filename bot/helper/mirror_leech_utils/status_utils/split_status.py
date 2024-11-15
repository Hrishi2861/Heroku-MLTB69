from bot import LOGGER, subprocess_lock
from ...ext_utils.status_utils import get_readable_file_size, MirrorStatus
from subprocess import run as frun

class SplitStatus:
    def __init__(self, listener, gid):
        self.listener = listener
        self._gid = gid
        self._size = self.listener.size
        self.engine = self._eng_ver()

    def _eng_ver(self):
        if self.listener.as_doc:
            pkg = "Split v"
            _engine = frun(
                [
                    "split",
                    "--version"
                ],
                capture_output=True,
                text=True
            )
            _engine = _engine.stdout.split("\n")[0].split(" ")[3]
            result = f"{pkg}{_engine}"
            return result
        else:
            pkg = "FFmpeg v"
            _engine = frun(
                [
                    "ffmpeg",
                    "-version"
                ],
                capture_output=True,
                text=True
            )
            _engine = _engine.stdout.split("\n")[0].split(" ")[2].split("-")[0]
            result = f"{pkg}{_engine}"
            return result

    def gid(self):
        return self._gid

    def name(self):
        return self.listener.name

    def size(self):
        return get_readable_file_size(self._size)

    def status(self):
        return MirrorStatus.STATUS_SPLITTING

    def task(self):
        return self

    async def cancel_task(self):
        LOGGER.info(f"Cancelling Split: {self.listener.name}")
        self.listener.is_cancelled = True
        async with subprocess_lock:
            if (
                self.listener.suproc is not None
                and self.listener.suproc.returncode is None
            ):
                self.listener.suproc.kill()
        await self.listener.on_upload_error("splitting stopped by user!")

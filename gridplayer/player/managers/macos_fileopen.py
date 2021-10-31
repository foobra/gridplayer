import subprocess

from PyQt5.QtCore import QEvent, pyqtSignal

from gridplayer.player.managers.base import ManagerBase
from gridplayer.settings import Settings
from gridplayer.utils.single_instance import is_the_only_instance
from gridplayer.version import __app_name__


class MacOSFileOpenManager(ManagerBase):
    file_opened = pyqtSignal(list)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self._event_map = {QEvent.FileOpen: self.handle_macos_fileopen}

    def handle_macos_fileopen(self, event):
        file = event.file()

        if not file:
            return

        Settings().sync()

        is_empty = bool(self._context["video_blocks"])
        is_only_empty = is_the_only_instance() and is_empty

        if Settings().get("player/one_instance") or is_only_empty:
            self.file_opened.emit([file])
        else:
            subprocess.run(  # noqa: S603, S607
                [
                    "open",
                    "-n",
                    f"/Applications/{__app_name__}.app",
                    "--args",
                    file,
                ]
            )
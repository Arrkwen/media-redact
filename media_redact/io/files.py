"""文件类型判断。"""

from __future__ import annotations

import mimetypes
import os


def get_file_type(path: str) -> str | None:
    if not os.path.isfile(path):
        return "notfound"
    mime = mimetypes.guess_type(path)[0]
    if mime is None:
        return None
    if mime.startswith("video"):
        return "video"
    if mime.startswith("image"):
        return "image"
    return mime

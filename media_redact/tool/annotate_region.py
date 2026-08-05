#!/usr/bin/env python3
"""启动 OSD 标注 Web 服务，在浏览器/VSCode 中标注区域。"""

from __future__ import annotations

import argparse
import cgi
import json
import mimetypes
import os
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
import webbrowser
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import BinaryIO
from urllib import error as urllib_error
from urllib import parse as urllib_parse
from urllib import request as urllib_request

import cv2

from media_redact.log import PrintfLogger, setup_logging

DEFAULT_PORT = 8765
_TEMPLATE_PATH = Path(__file__).resolve().parent / "templates" / "annotate.html"
LOGGER = PrintfLogger()

_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff"}
_VIDEO_EXTS = {".mp4", ".avi", ".mkv", ".mov", ".webm", ".m4v", ".ts"}
_STREAM_SCHEMES = {"rtsp", "rtmp", "http", "https"}
_RTSP_FFMPEG_OPTIONS = "rtsp_transport;tcp|stimeout;5000000"
_STREAM_CAPTURE_TIMEOUT_SEC = 30


def _safe_url(url: str) -> str:
    parsed = urllib_parse.urlparse(url)
    if not parsed.password:
        return url
    netloc = parsed.hostname or ""
    if parsed.port:
        netloc = f"{netloc}:{parsed.port}"
    if parsed.username:
        netloc = f"{parsed.username}:***@{netloc}"
    return urllib_parse.urlunparse(parsed._replace(netloc=netloc))


@dataclass(frozen=True)
class UploadedMedia:
    path: Path
    name: str
    media_type: str


def detect_media_type(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in _IMAGE_EXTS:
        return "image"
    if ext in _VIDEO_EXTS:
        return "video"
    if cv2.imread(str(path)) is not None:
        return "image"
    return "video"


def image_dimensions(path: Path) -> tuple[int, int] | None:
    image = cv2.imread(str(path))
    if image is None:
        return None
    height, width = image.shape[:2]
    return width, height


def _parse_source(source: str) -> urllib_parse.ParseResult:
    return urllib_parse.urlparse(source)


def _is_network_stream(source: str) -> bool:
    return _parse_source(source).scheme in _STREAM_SCHEMES


def _is_rtsp_like(source: str) -> bool:
    return _parse_source(source).scheme in {"rtsp", "rtmp"}


def _open_video_capture(source: str) -> cv2.VideoCapture:
    safe = _safe_url(source)
    if _is_rtsp_like(source):
        LOGGER.debug("OpenCV open RTSP/RTMP via FFMPEG: %s options=%s", safe, _RTSP_FFMPEG_OPTIONS)
        previous = os.environ.get("OPENCV_FFMPEG_CAPTURE_OPTIONS")
        os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = _RTSP_FFMPEG_OPTIONS
        try:
            capture = cv2.VideoCapture(source, cv2.CAP_FFMPEG)
        finally:
            if previous is None:
                os.environ.pop("OPENCV_FFMPEG_CAPTURE_OPTIONS", None)
            else:
                os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = previous
        LOGGER.debug("OpenCV opened=%s source=%s", capture.isOpened(), safe)
        return capture
    if _is_network_stream(source):
        LOGGER.debug("OpenCV open network stream via FFMPEG: %s", safe)
        capture = cv2.VideoCapture(source, cv2.CAP_FFMPEG)
        LOGGER.debug("OpenCV opened=%s source=%s", capture.isOpened(), safe)
        return capture
    LOGGER.debug("OpenCV open local file: %s", source)
    capture = cv2.VideoCapture(source)
    LOGGER.debug("OpenCV opened=%s source=%s", capture.isOpened(), source)
    return capture


def _encode_frame_jpeg(frame) -> tuple[bytes, int, int]:
    height, width = frame.shape[:2]
    ok, encoded = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 95])
    if not ok:
        raise ValueError("Cannot encode frame as JPEG")
    return encoded.tobytes(), width, height


def _classify_ffmpeg_error(stderr: str) -> str:
    text = stderr.lower()
    if any(token in text for token in ("connection refused", "connection timed out", "timed out", "unable to open", "404 not found", "401 unauthorized", "403 forbidden", "no route to host", "network is unreachable")):
        return "connect"
    return "decode"


def extract_stream_frame_ffmpeg(
    url: str,
    *,
    time_sec: float | None = None,
) -> tuple[bytes, int, int]:
    with tempfile.TemporaryDirectory() as tmpdir:
        out_path = Path(tmpdir) / "frame.jpg"
        cmd = ["ffmpeg", "-y", "-loglevel", "error"]
        if _is_rtsp_like(url):
            cmd.extend(["-rtsp_transport", "tcp"])
        if time_sec is not None and time_sec > 0:
            cmd.extend(["-ss", str(time_sec)])
        cmd.extend(["-i", url, "-frames:v", "1", "-q:v", "2", str(out_path)])
        LOGGER.debug("ffmpeg extract frame: %s", " ".join(_safe_url(part) if part == url else part for part in cmd))
        started = time.monotonic()
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=_STREAM_CAPTURE_TIMEOUT_SEC,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            LOGGER.warning(
                "ffmpeg timeout after %.1fs url=%s",
                time.monotonic() - started,
                _safe_url(url),
            )
            raise ValueError(
                f"Stream connect timeout: no data received within {_STREAM_CAPTURE_TIMEOUT_SEC}s ({url})"
            ) from exc

        elapsed = time.monotonic() - started
        if result.returncode != 0 or not out_path.exists():
            stderr = (result.stderr or "").strip() or "ffmpeg failed"
            stage = _classify_ffmpeg_error(stderr)
            LOGGER.warning(
                "ffmpeg failed rc=%s stage=%s elapsed=%.1fs url=%s stderr=%s",
                result.returncode,
                stage,
                elapsed,
                _safe_url(url),
                stderr,
            )
            if stage == "connect":
                raise ValueError(f"Stream connect failed: {stderr}")
            raise ValueError(f"Stream decode failed: {stderr}")

        frame = cv2.imread(str(out_path))
        if frame is None:
            LOGGER.warning("ffmpeg produced invalid image url=%s elapsed=%.1fs", _safe_url(url), elapsed)
            raise ValueError("Stream decode failed: ffmpeg output is not a valid image")
        LOGGER.info("ffmpeg frame ok url=%s elapsed=%.1fs size=%sx%s", _safe_url(url), elapsed, frame.shape[1], frame.shape[0])
        return _encode_frame_jpeg(frame)


def extract_video_frame(
    path: Path | str,
    *,
    time_sec: float | None = None,
    frame_index: int | None = None,
) -> tuple[bytes, int, int]:
    source = str(path)
    safe = _safe_url(source)
    stream_like = _is_network_stream(source)
    rtsp_like = _is_rtsp_like(source)
    LOGGER.debug(
        "extract_video_frame source=%s stream=%s rtsp_like=%s time=%s index=%s",
        safe if stream_like else source,
        stream_like,
        rtsp_like,
        time_sec,
        frame_index,
    )
    started = time.monotonic()

    capture = _open_video_capture(source)
    if not capture.isOpened():
        LOGGER.debug("OpenCV cannot open source=%s elapsed=%.1fs", safe if stream_like else source, time.monotonic() - started)
        if rtsp_like:
            LOGGER.info("fallback to ffmpeg for RTSP/RTMP url=%s", safe)
            return extract_stream_frame_ffmpeg(source, time_sec=time_sec)
        if stream_like:
            raise ValueError(f"Stream connect failed: cannot open {source}")
        raise ValueError(f"Cannot open video: {source}")

    try:
        if time_sec is not None:
            capture.set(cv2.CAP_PROP_POS_MSEC, max(0.0, time_sec) * 1000.0)
        elif frame_index is not None:
            capture.set(cv2.CAP_PROP_POS_FRAMES, max(0, frame_index))

        ok, frame = capture.read()
        elapsed = time.monotonic() - started
        if not ok or frame is None:
            LOGGER.debug("OpenCV read failed ok=%s source=%s elapsed=%.1fs", ok, safe if stream_like else source, elapsed)
            if rtsp_like:
                LOGGER.info("fallback to ffmpeg after OpenCV read failure url=%s", safe)
                return extract_stream_frame_ffmpeg(source, time_sec=time_sec)
            if stream_like:
                raise ValueError(f"Stream decode failed: connected but cannot read frame from {source}")
            raise ValueError("Cannot read frame from video")
        LOGGER.info(
            "OpenCV frame ok source=%s elapsed=%.1fs size=%sx%s",
            safe if stream_like else source,
            elapsed,
            frame.shape[1],
            frame.shape[0],
        )
        return _encode_frame_jpeg(frame)
    finally:
        capture.release()


def _error_stage(message: str) -> str:
    lower = message.lower()
    if "connect" in lower or "timeout" in lower or "cannot open" in lower:
        return "connect"
    if "decode" in lower or "read frame" in lower:
        return "decode"
    return "unknown"


def build_init_payload(media_path: Path | None) -> dict:
    if media_path is None:
        return {"media": None}

    media_type = detect_media_type(media_path)
    payload: dict = {
        "media": {
            "type": media_type,
            "name": media_path.name,
            "url": "/api/file",
            "source": "file",
        }
    }
    if media_type == "image":
        dims = image_dimensions(media_path)
        if dims:
            payload["media"]["width"], payload["media"]["height"] = dims
    return payload


def _parse_frame_query(query: str) -> tuple[float | None, int | None]:
    params = urllib_parse.parse_qs(query)
    time_raw = params.get("time", [None])[0]
    index_raw = params.get("index", [None])[0]
    time_sec = float(time_raw) if time_raw not in (None, "") else None
    frame_index = int(index_raw) if index_raw not in (None, "") else None
    if time_sec is None and frame_index is None:
        frame_index = 0
    return time_sec, frame_index


def create_handler(
    template_path: Path,
    media_path: Path | None,
    init_payload: dict,
    upload_dir: Path,
):
    template_bytes = template_path.read_bytes()
    media_bytes = media_path.read_bytes() if media_path else None
    media_mime = (
        mimetypes.guess_type(str(media_path))[0] or "application/octet-stream"
        if media_path
        else None
    )
    uploads: dict[str, UploadedMedia] = {}

    class AnnotateHandler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args) -> None:  # noqa: A003
            LOGGER.info("%s - %s", self.address_string(), format % args)

        def _log_request(self, method: str, path: str) -> None:
            LOGGER.debug("HTTP %s %s", method, path)

        def _send_bytes(
            self,
            status: HTTPStatus,
            body: bytes,
            content_type: str,
            extra_headers: dict[str, str] | None = None,
        ) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            if extra_headers:
                for key, value in extra_headers.items():
                    self.send_header(key, value)
            self.end_headers()
            self.wfile.write(body)

        def _send_json(self, status: HTTPStatus, payload: dict) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self._send_bytes(status, body, "application/json; charset=utf-8")

        def _read_json_body(self) -> dict:
            length = int(self.headers.get("Content-Length", 0))
            if length <= 0:
                return {}
            raw = self.rfile.read(length)
            if not raw:
                return {}
            return json.loads(raw.decode("utf-8"))

        def _send_jpeg_frame(self, body: bytes, width: int, height: int) -> None:
            self._send_bytes(
                HTTPStatus.OK,
                body,
                "image/jpeg",
                {
                    "X-Frame-Width": str(width),
                    "X-Frame-Height": str(height),
                },
            )

        def do_GET(self) -> None:  # noqa: N802
            parsed = urllib_parse.urlparse(self.path)
            path = parsed.path
            self._log_request("GET", path)

            if path in {"/", "/index.html"}:
                self._send_bytes(HTTPStatus.OK, template_bytes, "text/html; charset=utf-8")
                return

            if path == "/api/init":
                self._send_json(HTTPStatus.OK, init_payload)
                return

            if path == "/api/file":
                if media_bytes is None or media_mime is None:
                    self._send_json(
                        HTTPStatus.NOT_FOUND,
                        {"error": "No media file was provided at startup."},
                    )
                    return
                self._send_bytes(HTTPStatus.OK, media_bytes, media_mime)
                return

            if path == "/api/file/frame":
                self._handle_file_frame(parsed.query)
                return

            if path.startswith("/api/media/"):
                suffix = path.removeprefix("/api/media/")
                if suffix.endswith("/frame"):
                    media_id = suffix[: -len("/frame")]
                    self._handle_uploaded_frame(media_id, parsed.query)
                    return
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "Not found"})
                return

            if path == "/api/proxy":
                self._handle_proxy(parsed.query)
                return

            self._send_json(HTTPStatus.NOT_FOUND, {"error": "Not found"})

        def do_POST(self) -> None:  # noqa: N802
            parsed = urllib_parse.urlparse(self.path)
            self._log_request("POST", parsed.path)
            if parsed.path == "/api/extract-frame":
                self._handle_extract_frame()
                return
            if parsed.path == "/api/stream/frame":
                self._handle_stream_frame()
                return
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "Not found"})

        def _handle_file_frame(self, query: str) -> None:
            if media_path is None or detect_media_type(media_path) != "video":
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": "No preloaded video available"})
                return
            self._extract_and_send_frame(media_path, query)

        def _handle_uploaded_frame(self, media_id: str, query: str) -> None:
            uploaded = uploads.get(media_id)
            if uploaded is None or uploaded.media_type != "video":
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "Uploaded video not found"})
                return
            self._extract_and_send_frame(uploaded.path, query)

        def _extract_and_send_frame(self, video_path: Path, query: str) -> None:
            time_sec, frame_index = _parse_frame_query(query)
            LOGGER.debug(
                "extract file frame path=%s time=%s index=%s",
                video_path,
                time_sec,
                frame_index,
            )
            try:
                body, width, height = extract_video_frame(
                    video_path,
                    time_sec=time_sec,
                    frame_index=frame_index,
                )
            except ValueError as exc:
                LOGGER.warning("file frame failed path=%s error=%s", video_path, exc)
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
                return
            self._send_jpeg_frame(body, width, height)

        def _handle_stream_frame(self) -> None:
            payload = self._read_json_body()
            url = payload.get("url")
            if not url:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": "Missing url"})
                return

            parsed_url = urllib_parse.urlparse(url)
            if parsed_url.scheme not in {"http", "https", "rtsp", "rtmp"}:
                self._send_json(
                    HTTPStatus.BAD_REQUEST,
                    {"error": "Unsupported stream scheme"},
                )
                return

            time_sec = payload.get("time")
            frame_index = payload.get("index")
            if time_sec is None and frame_index is None:
                frame_index = 0

            LOGGER.info(
                "stream frame request scheme=%s url=%s time=%s index=%s",
                parsed_url.scheme,
                _safe_url(url),
                time_sec,
                frame_index,
            )
            try:
                body, width, height = extract_video_frame(
                    url,
                    time_sec=float(time_sec) if time_sec is not None else None,
                    frame_index=int(frame_index) if frame_index is not None else None,
                )
            except ValueError as exc:
                stage = _error_stage(str(exc))
                LOGGER.warning(
                    "stream frame failed stage=%s url=%s error=%s",
                    stage,
                    _safe_url(url),
                    exc,
                )
                self._send_json(
                    HTTPStatus.BAD_GATEWAY,
                    {"error": str(exc), "stage": stage},
                )
                return
            LOGGER.info("stream frame ok url=%s size=%sx%s", _safe_url(url), width, height)
            self._send_jpeg_frame(body, width, height)

        def _handle_extract_frame(self) -> None:
            content_type = self.headers.get("Content-Type", "")
            if "multipart/form-data" not in content_type:
                self._send_json(
                    HTTPStatus.BAD_REQUEST,
                    {"error": "Expected multipart/form-data upload"},
                )
                return

            form = cgi.FieldStorage(
                fp=self.rfile,
                headers=self.headers,
                environ={
                    "REQUEST_METHOD": "POST",
                    "CONTENT_TYPE": content_type,
                    "CONTENT_LENGTH": self.headers.get("Content-Length", ""),
                },
            )
            if "file" not in form:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": "Missing file field"})
                return

            item = form["file"]
            if not getattr(item, "filename", None):
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": "Empty upload"})
                return

            filename = Path(item.filename).name
            complete = form.getvalue("complete", "false").lower() in {"1", "true", "yes"}
            time_raw = form.getvalue("time")
            index_raw = form.getvalue("index")
            time_sec = float(time_raw) if time_raw not in (None, "") else None
            frame_index = int(index_raw) if index_raw not in (None, "") else None
            if time_sec is None and frame_index is None:
                frame_index = 0

            media_id = uuid.uuid4().hex
            dest_dir = upload_dir / media_id
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest_path = dest_dir / filename

            file_obj: BinaryIO | None = getattr(item, "file", None)
            if file_obj is None:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": "Invalid upload payload"})
                return

            with dest_path.open("wb") as handle:
                shutil.copyfileobj(file_obj, handle)

            size_bytes = dest_path.stat().st_size
            LOGGER.info(
                "extract-frame upload filename=%s bytes=%s complete=%s time=%s index=%s",
                filename,
                size_bytes,
                complete,
                time_sec,
                frame_index,
            )
            try:
                body, width, height = extract_video_frame(
                    dest_path,
                    time_sec=time_sec,
                    frame_index=frame_index,
                )
            except ValueError as exc:
                LOGGER.warning(
                    "extract-frame failed filename=%s complete=%s error=%s",
                    filename,
                    complete,
                    exc,
                )
                shutil.rmtree(dest_dir, ignore_errors=True)
                if not complete:
                    self._send_json(
                        HTTPStatus.UNPROCESSABLE_ENTITY,
                        {"error": str(exc), "need_more": True},
                    )
                    return
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
                return

            LOGGER.info("extract-frame ok filename=%s media_id=%s size=%sx%s", filename, media_id, width, height)

            uploads[media_id] = UploadedMedia(
                path=dest_path,
                name=filename,
                media_type="video",
            )
            self._send_bytes(
                HTTPStatus.OK,
                body,
                "image/jpeg",
                {
                    "X-Frame-Width": str(width),
                    "X-Frame-Height": str(height),
                    "X-Media-Id": media_id,
                },
            )

        def _handle_proxy(self, query: str) -> None:
            params = urllib_parse.parse_qs(query)
            raw_url = params.get("url", [None])[0]
            if not raw_url:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": "Missing url parameter"})
                return

            url = urllib_parse.unquote(raw_url)
            parsed_url = urllib_parse.urlparse(url)
            LOGGER.debug("proxy request url=%s", _safe_url(url))
            if parsed_url.scheme not in {"http", "https"}:
                self._send_json(
                    HTTPStatus.BAD_REQUEST,
                    {"error": "Only http/https URLs are supported"},
                )
                return

            request = urllib_request.Request(
                url,
                headers={"User-Agent": "media-region/1.0"},
            )
            try:
                with urllib_request.urlopen(request, timeout=15) as response:
                    body = response.read(8 * 1024 * 1024)
                    content_type = response.headers.get("Content-Type", "application/octet-stream")
            except urllib_error.HTTPError as exc:
                LOGGER.warning("proxy upstream HTTP error url=%s code=%s", _safe_url(url), exc.code)
                self._send_json(
                    HTTPStatus.BAD_GATEWAY,
                    {"error": f"Upstream HTTP error: {exc.code}"},
                )
                return
            except urllib_error.URLError as exc:
                LOGGER.warning("proxy upstream URL error url=%s reason=%s", _safe_url(url), exc.reason)
                self._send_json(
                    HTTPStatus.BAD_GATEWAY,
                    {"error": f"Failed to fetch stream: {exc.reason}"},
                )
                return

            LOGGER.debug("proxy ok url=%s bytes=%s type=%s", _safe_url(url), len(body), content_type)

            self._send_bytes(HTTPStatus.OK, body, content_type)

    return AnnotateHandler


def serve(port: int, media_path: Path | None) -> None:
    init_payload = build_init_payload(media_path)
    upload_dir = Path(tempfile.gettempdir()) / "media-redact-uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    handler = create_handler(_TEMPLATE_PATH, media_path, init_payload, upload_dir)

    with ThreadingHTTPServer(("127.0.0.1", port), handler) as httpd:
        url = f"http://127.0.0.1:{port}/"
        LOGGER.info("OSD annotator running at %s", url)
        if media_path:
            LOGGER.info("Preloaded media: %s", media_path.resolve())
        else:
            LOGGER.info("No media argument — open the page to upload image/video or connect a stream.")
        LOGGER.info("Remote: forward this port and open the URL in your browser or VSCode Simple Browser.")
        try:
            webbrowser.open(url)
        except Exception:
            pass
        httpd.serve_forever()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Start a web UI to annotate redaction regions in a browser."
    )
    parser.add_argument(
        "media",
        nargs="?",
        default=None,
        help="Optional image or video path to preload",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help=f"HTTP server port (default: {DEFAULT_PORT})",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Log level (use DEBUG to troubleshoot stream connectivity)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    setup_logging(args.log_level, component="media-region")
    media_path = Path(args.media) if args.media else None
    if media_path is not None and not media_path.exists():
        LOGGER.error("Media file not found: %s", media_path)
        sys.exit(1)

    serve(args.port, media_path)


__all__ = [
    "build_init_payload",
    "DEFAULT_PORT",
    "extract_video_frame",
    "extract_stream_frame_ffmpeg",
    "_error_stage",
    "_safe_url",
    "setup_logging",
]


if __name__ == "__main__":
    main()

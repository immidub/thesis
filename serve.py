#!/usr/bin/env python3
"""Serve the repo and export combined pitch + broadcast clips with ffmpeg."""

import json
import re
import subprocess
import tempfile
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
CLIPS_DIR = REPO_ROOT / "clips"
COMBINE_STACK_WIDTH = 1280
FFMPEG_PRESET = "veryfast"
FFMPEG_CRF = "20"


def find_source_video():
    candidates = []
    for path in CLIPS_DIR.glob("*.mp4"):
        if path.name.endswith("_game.mp4"):
            continue
        if (CLIPS_DIR / (path.stem + ".webm")).exists():
            continue
        candidates.append(path)
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]
    camera = [p for p in candidates if "camera" in p.name.lower()]
    if camera:
        return camera[0]
    return max(candidates, key=lambda p: p.stat().st_size)


def safe_filename(name, suffix):
    cleaned = Path(re.sub(r"[^\w.\-]", "_", name or f"clip{suffix}")).name
    if not cleaned.endswith(suffix):
        cleaned += suffix
    return cleaned


def parse_multipart_form(content_type, body):
    boundary = None
    for part in content_type.split(";"):
        part = part.strip()
        if part.startswith("boundary="):
            boundary = part.split("=", 1)[1].strip().strip('"')
    if not boundary:
        raise ValueError("Missing multipart boundary")

    delimiter = ("--" + boundary).encode()
    fields = {}
    for chunk in body.split(delimiter):
        if not chunk or chunk in (b"--", b"--\r\n"):
            continue
        chunk = chunk.lstrip(b"\r\n")
        if b"\r\n\r\n" not in chunk:
            continue
        header_bytes, payload = chunk.split(b"\r\n\r\n", 1)
        payload = payload.rstrip(b"\r\n")
        headers = header_bytes.decode("utf-8", errors="replace")
        name = None
        for line in headers.split("\r\n"):
            if line.lower().startswith("content-disposition:"):
                match = re.search(r'name="([^"]+)"', line)
                if match:
                    name = match.group(1)
        if name:
            fields[name] = payload
    return fields


def probe_duration(path):
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return float(result.stdout.strip())


def export_combined_clip(
    source,
    raw_pitch_path,
    output_path,
    num_frames,
    target_duration_sec,
    video_start_sec,
    video_end_sec,
):
    if num_frames <= 0 or target_duration_sec <= 0:
        raise ValueError("Frame count and target duration must be positive")

    game_cut_sec = video_end_sec - video_start_sec
    if game_cut_sec <= 0:
        raise ValueError("Game clip end must be after clip start")

    pitch_fps = num_frames / target_duration_sec
    duration = f"{target_duration_sec:.6f}"
    game_cut = f"{game_cut_sec:.6f}"
    width = COMBINE_STACK_WIDTH
    last_frame = num_frames - 1

    # Pitch: ignore MediaRecorder timestamps — space exactly num_frames over target duration.
    # Game: trim broadcast segment, then time-stretch to match pitch master duration.
    game_pts_scale = target_duration_sec / game_cut_sec
    if abs(game_pts_scale - 1.0) < 1e-4:
        game_pts = "setpts=PTS-STARTPTS"
    else:
        game_pts = f"setpts={game_pts_scale:.8f}*(PTS-STARTPTS)"

    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-ss",
            f"{video_start_sec:.6f}",
            "-to",
            f"{video_end_sec:.6f}",
            "-i",
            str(source),
            "-i",
            str(raw_pitch_path),
            "-filter_complex",
            (
                f"[1:v]select='lte(n\\,{last_frame})',"
                f"setpts=N/({pitch_fps}*TB),"
                f"scale={width}:-2,"
                f"trim=duration={duration},setpts=PTS-STARTPTS[pitch];"
                f"[0:v]scale={width}:-2,"
                f"trim=duration={game_cut},"
                f"{game_pts}[game];"
                f"[game][pitch]vstack=inputs=2[v]"
            ),
            "-map",
            "[v]",
            "-t",
            duration,
            "-c:v",
            "libx264",
            "-preset",
            FFMPEG_PRESET,
            "-crf",
            FFMPEG_CRF,
            "-an",
            str(output_path),
        ],
        check=True,
        capture_output=True,
    )


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(REPO_ROOT), **kwargs)

    def do_POST(self):
        if self.path == "/api/clips/export":
            self._export_clip()
            return
        self.send_error(404)

    def _send_json(self, status, payload):
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _ffmpeg_error(self, err):
        message = err.stderr.decode("utf-8", errors="replace") if err.stderr else str(err)
        self._send_json(500, {"error": f"ffmpeg failed: {message[:400]}"})

    def _export_clip(self):
        content_type = self.headers.get("Content-Type", "")
        if "multipart/form-data" not in content_type:
            self._send_json(400, {"error": "Expected multipart/form-data"})
            return

        content_length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(content_length)

        try:
            fields = parse_multipart_form(content_type, body)
        except ValueError as err:
            self._send_json(400, {"error": str(err)})
            return

        try:
            metadata = json.loads(fields["metadata"].decode("utf-8"))
            output_filename = safe_filename(metadata.get("outputFilename"), ".mp4")
            num_frames = int(metadata["numFrames"])
            target_duration = float(metadata["targetDurationSec"])
            video_start = float(metadata["videoStartSec"])
            video_end = float(metadata["videoEndSec"])
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            self._send_json(400, {"error": "Invalid metadata"})
            return

        if "pitch" not in fields:
            self._send_json(400, {"error": "Missing pitch recording"})
            return

        pitch_bytes = fields["pitch"]

        source = find_source_video()
        if source is None:
            self._send_json(404, {"error": "No source game video found in clips/"})
            return

        CLIPS_DIR.mkdir(parents=True, exist_ok=True)
        out_path = CLIPS_DIR / output_filename

        with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as raw_file:
            raw_pitch_path = Path(raw_file.name)
            raw_file.write(pitch_bytes)

        try:
            export_combined_clip(
                source,
                raw_pitch_path,
                out_path,
                num_frames,
                target_duration,
                video_start,
                video_end,
            )
        except subprocess.CalledProcessError as err:
            self._ffmpeg_error(err)
            return
        except ValueError as err:
            self._send_json(400, {"error": str(err)})
            return
        finally:
            if raw_pitch_path.exists():
                raw_pitch_path.unlink()

        self._send_json(
            200,
            {
                "path": f"clips/{output_filename}",
                "durationSec": probe_duration(out_path),
            },
        )

    def log_message(self, format, *args):
        if args and "POST /api/clips" in args[0]:
            print(f"Clip API: {args[0]}")
        else:
            super().log_message(format, *args)


def main():
    CLIPS_DIR.mkdir(parents=True, exist_ok=True)
    source = find_source_video()
    server = ThreadingHTTPServer(("localhost", 8000), Handler)
    print(f"Serving {REPO_ROOT} at http://localhost:8000/")
    print(f"Clips saved to {CLIPS_DIR}")
    if source:
        print(f"Game video source: {source.name}")
    else:
        print("No game MP4 in clips/ — export requires a broadcast file in clips/")
    print("Open http://localhost:8000/website/index.html")
    server.serve_forever()


if __name__ == "__main__":
    main()

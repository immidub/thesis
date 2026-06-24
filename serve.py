#!/usr/bin/env python3
"""Serve the repo, save exported WebM clips, and extract game-video clips with ffmpeg."""

import json
import re
import shutil
import subprocess
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
CLIPS_DIR = REPO_ROOT / "clips"
CLIP_PLAYBACK_SPEED = 1.0
DURATION_TOLERANCE_SEC = 0.05


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


def normalize_video_duration(input_path, output_path, target_duration_sec):
    if target_duration_sec <= 0:
        raise ValueError("Target duration must be positive")

    input_duration = probe_duration(input_path)
    if input_duration <= 0:
        raise ValueError("Could not read input clip duration")

    if abs(input_duration - target_duration_sec) <= DURATION_TOLERANCE_SEC:
        if input_path.resolve() != output_path.resolve():
            shutil.copy(input_path, output_path)
        return

    scale = target_duration_sec / input_duration
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(input_path),
            "-filter:v",
            f"setpts={scale}*PTS",
            "-an",
            str(output_path),
        ],
        check=True,
        capture_output=True,
    )


def normalize_pitch_webm(input_path, output_path, num_frames, frame_rate):
    if num_frames <= 0 or frame_rate <= 0:
        raise ValueError("Frame count and frame rate must be positive")

    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(input_path),
            "-vf",
            f"fps={frame_rate}",
            "-frames:v",
            str(num_frames),
            "-an",
            str(output_path),
        ],
        check=True,
        capture_output=True,
    )


def extract_game_clip(source, output, start_sec, end_sec, playback_speed=CLIP_PLAYBACK_SPEED):
    source_duration = end_sec - start_sec
    if source_duration <= 0:
        raise ValueError("Clip end must be after clip start in the source video")

    target_duration = source_duration / playback_speed
    temp_path = output.with_suffix(".segment.mp4")

    try:
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-ss",
                f"{start_sec:.3f}",
                "-i",
                str(source),
                "-t",
                f"{source_duration:.3f}",
                "-c",
                "copy",
                str(temp_path),
            ],
            check=True,
            capture_output=True,
        )

        if abs(playback_speed - 1.0) < 1e-6:
            normalize_video_duration(temp_path, output, target_duration)
        else:
            slowed_path = output.with_suffix(".slowed.mp4")
            setpts = 1.0 / playback_speed
            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-i",
                    str(temp_path),
                    "-filter:v",
                    f"setpts={setpts}*PTS",
                    "-an",
                    str(slowed_path),
                ],
                check=True,
                capture_output=True,
            )
            normalize_video_duration(slowed_path, output, target_duration)
            if slowed_path.exists():
                slowed_path.unlink()
    finally:
        if temp_path.exists():
            temp_path.unlink()


COMBINE_STACK_WIDTH = 1280


def combine_clips(game_path, pitch_path, output_path, stack_width=COMBINE_STACK_WIDTH):
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(game_path),
            "-i",
            str(pitch_path),
            "-filter_complex",
            (
                f"[0:v]scale={stack_width}:-2[top];"
                f"[1:v]scale={stack_width}:-2[bottom];"
                "[top][bottom]vstack=inputs=2[v]"
            ),
            "-map",
            "[v]",
            "-shortest",
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
        if self.path == "/api/clips":
            self._save_webm_clip()
            return
        if self.path == "/api/clips/extract-game":
            self._extract_game_clip()
            return
        if self.path == "/api/clips/combine":
            self._combine_clips()
            return
        self.send_error(404)

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        return self.rfile.read(length)

    def _save_webm_clip(self):
        filename = self.headers.get("X-Filename", "clip.webm")
        filename = Path(re.sub(r"[^\w.\-]", "_", filename)).name
        if not filename.endswith(".webm"):
            filename += ".webm"

        target_duration = self.headers.get("X-Target-Duration")
        num_frames = self.headers.get("X-Num-Frames")
        frame_rate = self.headers.get("X-Frame-Rate")
        data = self._read_body()
        CLIPS_DIR.mkdir(parents=True, exist_ok=True)
        out_path = CLIPS_DIR / filename

        if num_frames is not None and frame_rate is not None:
            raw_path = out_path.with_suffix(".raw.webm")
            raw_path.write_bytes(data)
            try:
                normalize_pitch_webm(
                    raw_path,
                    out_path,
                    int(num_frames),
                    float(frame_rate) * CLIP_PLAYBACK_SPEED,
                )
            except (TypeError, ValueError) as err:
                self.send_error(400, str(err))
                return
            except subprocess.CalledProcessError as err:
                message = err.stderr.decode("utf-8", errors="replace") if err.stderr else str(err)
                self.send_error(500, f"ffmpeg failed: {message[:300]}")
                return
            finally:
                if raw_path.exists():
                    raw_path.unlink()
        elif target_duration is not None:
            raw_path = out_path.with_suffix(".raw.webm")
            raw_path.write_bytes(data)
            try:
                normalize_video_duration(raw_path, out_path, float(target_duration))
            except (TypeError, ValueError) as err:
                self.send_error(400, str(err))
                return
            except subprocess.CalledProcessError as err:
                message = err.stderr.decode("utf-8", errors="replace") if err.stderr else str(err)
                self.send_error(500, f"ffmpeg failed: {message[:300]}")
                return
            finally:
                if raw_path.exists():
                    raw_path.unlink()
        else:
            out_path.write_bytes(data)

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        duration = probe_duration(out_path)
        self.wfile.write(
            json.dumps({"path": f"clips/{filename}", "durationSec": duration}).encode()
        )

    def _extract_game_clip(self):
        try:
            payload = json.loads(self._read_body().decode("utf-8"))
            video_start = float(payload["videoStartSec"])
            video_end = float(payload["videoEndSec"])
            filename = Path(re.sub(r"[^\w.\-]", "_", payload.get("outputFilename", "clip_game.mp4"))).name
            if not filename.endswith(".mp4"):
                filename += ".mp4"
            playback_speed = float(payload.get("playbackSpeed", CLIP_PLAYBACK_SPEED))
            target_duration = float(payload["targetDurationSec"])
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            self.send_error(400, "Invalid request body")
            return

        source = find_source_video()
        if source is None:
            self.send_error(404, "No source game video found in clips/")
            return

        CLIPS_DIR.mkdir(parents=True, exist_ok=True)
        out_path = CLIPS_DIR / filename

        try:
            extract_game_clip(source, out_path, video_start, video_end, playback_speed)
            actual_duration = probe_duration(out_path)
            if abs(actual_duration - target_duration) > DURATION_TOLERANCE_SEC:
                temp_path = out_path.with_suffix(".tmp.mp4")
                normalize_video_duration(out_path, temp_path, target_duration)
                temp_path.replace(out_path)
        except subprocess.CalledProcessError as err:
            message = err.stderr.decode("utf-8", errors="replace") if err.stderr else str(err)
            self.send_error(500, f"ffmpeg failed: {message[:300]}")
            return
        except ValueError as err:
            self.send_error(400, str(err))
            return

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(
            json.dumps({
                "path": f"clips/{filename}",
                "source": f"clips/{source.name}",
                "durationSec": probe_duration(out_path),
            }).encode()
        )

    def _combine_clips(self):
        try:
            payload = json.loads(self._read_body().decode("utf-8"))
            game_filename = Path(re.sub(r"[^\w.\-]", "_", payload["gameFilename"])).name
            pitch_filename = Path(re.sub(r"[^\w.\-]", "_", payload["pitchFilename"])).name
            output_filename = Path(re.sub(r"[^\w.\-]", "_", payload["outputFilename"])).name
            if not output_filename.endswith(".mp4"):
                output_filename += ".mp4"
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            self.send_error(400, "Invalid request body")
            return

        game_path = CLIPS_DIR / game_filename
        pitch_path = CLIPS_DIR / pitch_filename
        out_path = CLIPS_DIR / output_filename

        if not game_path.is_file():
            self.send_error(404, f"Game clip not found: {game_filename}")
            return
        if not pitch_path.is_file():
            self.send_error(404, f"Pitch clip not found: {pitch_filename}")
            return

        try:
            combine_clips(game_path, pitch_path, out_path)
        except subprocess.CalledProcessError as err:
            message = err.stderr.decode("utf-8", errors="replace") if err.stderr else str(err)
            self.send_error(500, f"ffmpeg failed: {message[:300]}")
            return

        for path in (game_path, pitch_path):
            if path.is_file():
                path.unlink()

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(
            json.dumps({
                "path": f"clips/{output_filename}",
                "durationSec": probe_duration(out_path),
            }).encode()
        )

    def log_message(self, format, *args):
        if args and args[0].startswith("POST /api/clips"):
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
        print("No game MP4 in clips/ — pitch-only export will still work")
    print("Open http://localhost:8000/website/index.html")
    server.serve_forever()


if __name__ == "__main__":
    main()

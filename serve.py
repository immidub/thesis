#!/usr/bin/env python3
"""Serve the repo and export combined pitch + broadcast clips with ffmpeg."""

import json
import re
import subprocess
import tempfile
from email import policy
from email.parser import BytesParser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
CLIPS_DIR = REPO_ROOT / "clips"
CLIP_OUT_DIR = CLIPS_DIR / "clip"
IMAGE_OUT_DIR = CLIPS_DIR / "image"
COMBINE_STACK_WIDTH = 1280
FFMPEG_PRESET = "veryfast"
FFMPEG_CRF = "20"


def find_source_video():
    # Hardcoded for the current WC match — update this path for other matches.
    path = CLIPS_DIR / "281-M08-QAT-SUI-camera1-720p.mp4"
    return path if path.exists() else None

# cleans filename for export
def safe_filename(name, suffix):
    cleaned = Path(re.sub(r"[^\w.\-]", "_", name or f"clip{suffix}")).name
    if not cleaned.endswith(suffix):
        cleaned += suffix
    return cleaned


def parse_multipart_form(content_type, body):
    msg = BytesParser(policy=policy.default).parsebytes(
        b"Content-Type: " + content_type.encode() + b"\r\n\r\n" + body
    )
    fields = {}
    for part in msg.iter_parts():
        name = part.get_param("name", header="content-disposition")
        if name:
            fields[name] = part.get_payload(decode=True)
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

    # Combine pitch (bottom) and broadcast (top) into one MP4.
    subprocess.run(
        [
            "ffmpeg",
            "-y",  # overwrite existing output file
            "-ss",
            f"{video_start_sec:.6f}",  # seek into broadcast video
            "-to",
            f"{video_end_sec:.6f}",  # end of broadcast segment to use
            "-i",
            str(source),  # input 0: full broadcast MP4
            "-i",
            str(raw_pitch_path),  # input 1: pitch recording from the browser
            "-filter_complex",
            (
                # pitch: take first N frames, retime to target duration, scale width
                f"[1:v]select='lte(n\\,{last_frame})',"
                f"setpts=N/({pitch_fps}*TB),"
                f"scale={width}:-2,"
                f"trim=duration={duration},setpts=PTS-STARTPTS[pitch];"
                # game: scale broadcast, trim to clip length, stretch/squeeze to match pitch
                f"[0:v]scale={width}:-2,"
                f"trim=duration={game_cut},"
                f"{game_pts}[game];"
                # stack broadcast on top, pitch underneath
                f"[game][pitch]vstack=inputs=2[v]"
            ),
            "-map",
            "[v]",  # use the stacked video from filter_complex
            "-t",
            duration,  # final output length
            "-c:v",
            "libx264",  # H.264 video codec
            "-preset",
            FFMPEG_PRESET,  # encoding speed vs compression
            "-crf",
            FFMPEG_CRF,  # quality (lower = better)
            "-an",  # drop audio
            str(output_path),
        ],
        check=True,  # raise CalledProcessError if ffmpeg fails
        capture_output=True,  # keep stderr for error reporting
    )


def export_start_image(source, pitch_png_path, output_path, video_start_sec):
    """Stack one broadcast frame (top) above the pitch PNG (bottom)."""
    width = COMBINE_STACK_WIDTH
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-ss",
            f"{video_start_sec:.6f}",
            "-i",
            str(source),
            "-i",
            str(pitch_png_path),
            "-filter_complex",
            (
                f"[0:v]scale={width}:-2,setsar=1[game];"
                f"[1:v]scale={width}:-2,setsar=1[pitch];"
                f"[game][pitch]vstack=inputs=2[v]"
            ),
            "-map",
            "[v]",
            "-frames:v",
            "1",
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

    # send json response
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
        # validate content type
        content_type = self.headers.get("Content-Type", "")
        if "multipart/form-data" not in content_type:
            self._send_json(400, {"error": "Expected multipart/form-data"})
            return

        content_length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(content_length) #read body of the request

        try:
            fields = parse_multipart_form(content_type, body) #parse the multipart form
        except ValueError as err:
            self._send_json(400, {"error": str(err)})
            return

        try:
            metadata = json.loads(fields["metadata"].decode("utf-8")) #parse the metadata
            output_filename = safe_filename(metadata.get("outputFilename"), ".mp4") #clean the filename for export
            num_frames = int(metadata["numFrames"]) #number of frames in the pitch recording
            target_duration = float(metadata["targetDurationSec"]) #target duration of the clip
            video_start = float(metadata["videoStartSec"]) #start time of the clip
            video_end = float(metadata["videoEndSec"]) #end time of the clip
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            self._send_json(400, {"error": "Invalid metadata"})
            return

        if "pitch" not in fields:
            self._send_json(400, {"error": "Missing pitch recording"})
            return

        pitch_bytes = fields["pitch"] #get the pitch recording
        image_bytes = fields.get("image")

        source = find_source_video() #find the source video
        if source is None:
            self._send_json(404, {"error": "No source game video found in clips/"})
            return

        CLIP_OUT_DIR.mkdir(parents=True, exist_ok=True)
        IMAGE_OUT_DIR.mkdir(parents=True, exist_ok=True)
        out_path = CLIP_OUT_DIR / output_filename
        image_filename = safe_filename("img_" + Path(output_filename).stem, ".png")
        image_path = IMAGE_OUT_DIR / image_filename

        with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as raw_file:
            raw_pitch_path = Path(raw_file.name)
            raw_file.write(pitch_bytes) #write the pitch recording to a temporary file

        pitch_png_path = None
        try:
            export_combined_clip( #combine the pitch and game video
                source,
                raw_pitch_path,
                out_path,
                num_frames,
                target_duration,
                video_start,
                video_end,
            )
            if image_bytes:
                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as png_file:
                    pitch_png_path = Path(png_file.name)
                    png_file.write(image_bytes)
                export_start_image(source, pitch_png_path, image_path, video_start)
        except subprocess.CalledProcessError as err:
            self._ffmpeg_error(err)
            return
        except ValueError as err:
            self._send_json(400, {"error": str(err)})
            return
        finally:
            if raw_pitch_path.exists(): 
                raw_pitch_path.unlink() #delete the temporary file
            if pitch_png_path and pitch_png_path.exists():
                pitch_png_path.unlink()

        self._send_json( #send the response
            200,
            {
                "path": f"clips/clip/{output_filename}",
                "imagePath": f"clips/image/{image_filename}" if image_bytes else None,
                "durationSec": probe_duration(out_path),
            },
        )

    def log_message(self, format, *args):
        if args and "POST /api/clips" in str(args[0]):
            print(f"Clip API: {args[0]}")
        else:
            super().log_message(format, *args)


def main():
    CLIP_OUT_DIR.mkdir(parents=True, exist_ok=True)
    IMAGE_OUT_DIR.mkdir(parents=True, exist_ok=True)
    source = find_source_video() #find the source video
    server = ThreadingHTTPServer(("localhost", 8000), Handler) #start the server
    print(f"Serving {REPO_ROOT} at http://localhost:8000/")
    print(f"Clips saved to {CLIP_OUT_DIR}")
    print(f"Images saved to {IMAGE_OUT_DIR}")
    if source:
        print(f"Game video source: {source.name}")
    else:
        print("No game MP4 in clips/ — export requires a broadcast file in clips/")
    print("Open http://localhost:8000/website/index.html")
    print("Responsibility view: http://localhost:8000/website/responsibility/index.html")
    server.serve_forever()


if __name__ == "__main__":
    main()

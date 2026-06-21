"""Video watermarking via ffmpeg.

Public API:
    apply_video_watermark(video_path, website_url, brand_text, logo_file_path) -> None
"""
from __future__ import annotations

import logging
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from services.watermark import build_video_watermark_overlay

logger = logging.getLogger(__name__)


def _has_ffmpeg() -> bool:
    return shutil.which("ffmpeg") is not None


def apply_video_watermark(
    video_path: Path,
    website_url: Optional[str],
    brand_text: Optional[str] = None,
    logo_file_path: Optional[Path] = None,
) -> None:
    """Overlay the brand watermark on the bottom-right of the given video (in-place).
    Silently no-ops if ffmpeg is missing or no logo/text can be rendered.
    """
    if not (website_url or brand_text or logo_file_path):
        return
    if not _has_ffmpeg():
        logger.warning("ffmpeg not installed — video watermark skipped")
        return

    video_path = Path(video_path)
    if not video_path.exists():
        return

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        overlay_png = tmp_dir / "watermark.png"
        size = build_video_watermark_overlay(
            website_url, brand_text, logo_file_path, overlay_png
        )
        if size is None or not overlay_png.exists():
            return

        out_mp4 = tmp_dir / "out.mp4"
        # Bottom-right with a small margin (W = video width, H = video height,
        # w = overlay width, h = overlay height).
        overlay_filter = "overlay=W-w-24:H-h-24"
        cmd = [
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-i",
            str(video_path),
            "-i",
            str(overlay_png),
            "-filter_complex",
            overlay_filter,
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "23",
            "-c:a",
            "copy",
            str(out_mp4),
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, timeout=120)
            if result.returncode != 0:
                logger.error("ffmpeg failed: %s", result.stderr.decode(errors="ignore")[:500])
                return
            shutil.move(str(out_mp4), str(video_path))
        except (subprocess.TimeoutExpired, OSError):
            logger.exception("ffmpeg video watermark failed")

"""Serve book images (drawings + full-page renders + embedded images).

Tries multiple locations:
1. chapters_md_styled/images/  (preferred for new styled HTML)
2. chapters_md/images/         (legacy markdown extraction)
"""
from pathlib import Path
from fastapi import APIRouter, HTTPException, Response

from app.config import BOOK_MD_DIR

router = APIRouter(prefix="/api", tags=["book-images"])


@router.get("/book-images/{chapter_id}/{filename}")
def serve_image(chapter_id: str, filename: str):
    # Try styled dir first, then legacy
    candidates = [
        Path(BOOK_MD_DIR + "_styled") / "images" / filename,
        Path(BOOK_MD_DIR) / "images" / filename,
    ]
    for img_path in candidates:
        if img_path.exists():
            suffix = img_path.suffix.lower()
            media = {
                ".png": "image/png",
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".gif": "image/gif",
                ".webp": "image/webp",
            }.get(suffix, "application/octet-stream")
            return Response(content=img_path.read_bytes(), media_type=media)

    raise HTTPException(404, f"Image {filename} not found")
from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pillow_avif  # noqa: F401
from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image, ImageSequence, UnidentifiedImageError

from template_config import templates

MAX_FILES = 100
SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}

app = FastAPI(title="toAVIF")
app.mount("/static", StaticFiles(directory="static"), name="static")


def _read_upload_image(upload: UploadFile) -> tuple[Image.Image, str]:
    suffix = Path(upload.filename or "").suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"지원하지 않는 파일 형식입니다: {upload.filename}")

    raw_data = upload.file.read()
    if not raw_data:
        raise HTTPException(status_code=400, detail=f"비어 있는 파일입니다: {upload.filename}")

    try:
        image = Image.open(io.BytesIO(raw_data))
    except UnidentifiedImageError as exc:
        raise HTTPException(status_code=400, detail=f"이미지로 읽을 수 없습니다: {upload.filename}") from exc

    return image, Path(upload.filename or "image").stem


def _to_avif_bytes(image: Image.Image) -> bytes:
    output = io.BytesIO()

    is_animated = getattr(image, "is_animated", False) and getattr(image, "n_frames", 1) > 1
    if is_animated:
        frames: list[Image.Image] = []
        durations: list[int] = []

        for frame in ImageSequence.Iterator(image):
            frames.append(frame.convert("RGBA"))
            durations.append(frame.info.get("duration", image.info.get("duration", 80)))

        loop = image.info.get("loop", 0)
        frames[0].save(
            output,
            format="AVIF",
            save_all=True,
            append_images=frames[1:],
            duration=durations,
            loop=loop,
            quality=70,
        )
    else:
        image.convert("RGBA").save(output, format="AVIF", quality=70)

    output.seek(0)
    return output.read()


@app.get("/")
async def index(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")


@app.post("/convert")
async def convert_images(files: list[UploadFile] = File(...)):
    if len(files) == 0:
        raise HTTPException(status_code=400, detail="최소 1개의 파일이 필요합니다.")
    if len(files) > MAX_FILES:
        raise HTTPException(status_code=400, detail=f"한 번에 최대 {MAX_FILES}개 파일만 업로드할 수 있습니다.")

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        for upload in files:
            image, stem = _read_upload_image(upload)
            avif_data = _to_avif_bytes(image)
            archive.writestr(f"{stem}.avif", avif_data)
            image.close()

    zip_buffer.seek(0)
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=toavif_results.zip"},
    )

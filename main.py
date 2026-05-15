from __future__ import annotations

from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import pillow_avif  # noqa: F401 - Registers AVIF support for Pillow.
from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image, ImageSequence, UnidentifiedImageError

from template_config import templates

MAX_FILES = 100
ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp", "gif"}

app = FastAPI(title="toAVIF")
app.mount("/static", StaticFiles(directory="static"), name="static")


def _is_allowed(filename: str) -> bool:
    suffix = Path(filename).suffix.lower().lstrip(".")
    return suffix in ALLOWED_EXTENSIONS


def _safe_stem(filename: str, fallback: str) -> str:
    stem = Path(filename).stem.strip()
    return stem or fallback


def _convert_to_avif(upload: UploadFile, index: int) -> tuple[str, bytes]:
    if not upload.filename or not _is_allowed(upload.filename):
        raise HTTPException(status_code=400, detail=f"지원하지 않는 형식: {upload.filename}")

    raw_bytes = upload.file.read()
    if not raw_bytes:
        raise HTTPException(status_code=400, detail=f"빈 파일입니다: {upload.filename}")

    try:
        image = Image.open(BytesIO(raw_bytes))
    except UnidentifiedImageError as exc:
        raise HTTPException(status_code=400, detail=f"이미지를 읽을 수 없습니다: {upload.filename}") from exc

    output = BytesIO()
    stem = _safe_stem(upload.filename, f"image-{index}")
    output_name = f"{stem}.avif"

    is_animated = bool(getattr(image, "is_animated", False)) and getattr(image, "n_frames", 1) > 1

    if is_animated:
        frames: list[Image.Image] = []
        durations: list[int] = []

        for frame in ImageSequence.Iterator(image):
            frames.append(frame.convert("RGBA"))
            durations.append(frame.info.get("duration", image.info.get("duration", 100)))

        first, *rest = frames
        first.save(
            output,
            format="AVIF",
            save_all=True,
            append_images=rest,
            duration=durations,
            loop=image.info.get("loop", 0),
            quality=70,
            speed=6,
        )
    else:
        image.convert("RGBA").save(output, format="AVIF", quality=70, speed=6)

    return output_name, output.getvalue()


@app.get("/")
async def index(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")


@app.post("/api/convert")
async def convert(files: list[UploadFile] = File(...)):
    if not files:
        raise HTTPException(status_code=400, detail="최소 1개 이상의 이미지를 업로드해 주세요.")

    if len(files) > MAX_FILES:
        raise HTTPException(status_code=400, detail=f"한 번에 최대 {MAX_FILES}개까지 업로드할 수 있습니다.")

    converted_files: list[tuple[str, bytes]] = []
    for index, upload in enumerate(files, start=1):
        converted_files.append(_convert_to_avif(upload, index))

    archive_stream = BytesIO()
    with ZipFile(archive_stream, mode="w", compression=ZIP_DEFLATED) as archive:
        for filename, data in converted_files:
            archive.writestr(filename, data)

    archive_stream.seek(0)
    return StreamingResponse(
        archive_stream,
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=toavif-converted.zip"},
    )

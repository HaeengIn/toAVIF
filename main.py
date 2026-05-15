from __future__ import annotations

import io
import zipfile
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from PIL import Image, ImageSequence
import pillow_avif  # noqa: F401  # Registers AVIF with Pillow

app = FastAPI(title="toAVIF")

BASE_DIR = Path(__file__).resolve().parent
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

MAX_FILES = 100
SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}


def _is_supported(filename: str) -> bool:
    return Path(filename).suffix.lower() in SUPPORTED_EXTENSIONS


def _convert_to_avif(file_data: bytes, source_filename: str) -> tuple[str, bytes]:
    input_buffer = io.BytesIO(file_data)
    output_buffer = io.BytesIO()

    with Image.open(input_buffer) as image:
        out_name = f"{Path(source_filename).stem}-{uuid4().hex[:8]}.avif"

        is_animated = bool(getattr(image, "is_animated", False))
        if is_animated:
            frames: list[Image.Image] = []
            durations: list[int] = []

            for frame in ImageSequence.Iterator(image):
                frames.append(frame.convert("RGBA"))
                durations.append(int(frame.info.get("duration", image.info.get("duration", 100))))

            if not frames:
                raise ValueError("움직이는 이미지 프레임을 읽을 수 없습니다.")

            first_frame, *rest_frames = frames
            first_frame.save(
                output_buffer,
                format="AVIF",
                save_all=True,
                append_images=rest_frames,
                duration=durations,
                loop=int(image.info.get("loop", 0)),
                quality=72,
                speed=6,
            )
        else:
            image.convert("RGBA").save(
                output_buffer,
                format="AVIF",
                quality=72,
                speed=6,
            )

    output_buffer.seek(0)
    return out_name, output_buffer.read()


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "max_files": MAX_FILES,
            "supported_formats": ", ".join(sorted(ext.strip(".").upper() for ext in SUPPORTED_EXTENSIONS)),
        },
    )


@app.post("/convert")
async def convert(files: list[UploadFile] = File(...)) -> StreamingResponse:
    if not files:
        raise HTTPException(status_code=400, detail="파일을 하나 이상 업로드해주세요.")

    if len(files) > MAX_FILES:
        raise HTTPException(status_code=400, detail=f"한 번에 최대 {MAX_FILES}개까지만 업로드할 수 있습니다.")

    converted: list[tuple[str, bytes]] = []

    for upload in files:
        if not upload.filename:
            continue

        if not _is_supported(upload.filename):
            raise HTTPException(status_code=400, detail=f"지원하지 않는 형식입니다: {upload.filename}")

        data = await upload.read()
        if not data:
            raise HTTPException(status_code=400, detail=f"비어 있는 파일입니다: {upload.filename}")

        try:
            converted.append(_convert_to_avif(data, upload.filename))
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=400, detail=f"변환 실패 ({upload.filename}): {exc}") from exc

    if not converted:
        raise HTTPException(status_code=400, detail="처리할 수 있는 파일이 없습니다.")

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, payload in converted:
            zf.writestr(name, payload)

    zip_buffer.seek(0)
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=toAVIF-results.zip"},
    )

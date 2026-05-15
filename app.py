from __future__ import annotations

from io import BytesIO
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

import pillow_avif  # noqa: F401  # AVIF plugin registration side-effect
from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image, ImageSequence

from template_config import templates

MAX_FILES = 100
SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}

app = FastAPI(title="toAVIF")
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def index(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")


def _convert_to_avif(file: UploadFile) -> tuple[str, bytes]:
    source_name = file.filename or "image"
    suffix = Path(source_name).suffix.lower()

    if suffix not in SUPPORTED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"지원하지 않는 파일 형식입니다: {source_name}")

    raw = file.file.read()
    if not raw:
        raise HTTPException(status_code=400, detail=f"빈 파일입니다: {source_name}")

    try:
        image = Image.open(BytesIO(raw))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"이미지 파일을 읽을 수 없습니다: {source_name}") from exc

    output = BytesIO()
    stem = Path(source_name).stem

    is_animated = bool(getattr(image, "is_animated", False)) and image.n_frames > 1
    if is_animated and suffix in {".webp", ".gif"}:
        frames = [frame.convert("RGBA") for frame in ImageSequence.Iterator(image)]
        durations = [frame.info.get("duration", image.info.get("duration", 80)) for frame in ImageSequence.Iterator(image)]
        loop = image.info.get("loop", 0)

        frames[0].save(
            output,
            format="AVIF",
            save_all=True,
            append_images=frames[1:],
            duration=durations,
            loop=loop,
            quality=78,
            speed=6,
        )
    else:
        converted = image.convert("RGBA") if image.mode in {"P", "RGBA", "LA"} else image.convert("RGB")
        converted.save(output, format="AVIF", quality=78, speed=6)

    output.seek(0)
    return f"{stem}.avif", output.getvalue()


@app.post("/convert")
async def convert(files: list[UploadFile] = File(...)):
    if not files:
        raise HTTPException(status_code=400, detail="파일이 없습니다.")

    if len(files) > MAX_FILES:
        raise HTTPException(status_code=400, detail=f"한 번에 최대 {MAX_FILES}개 파일까지 업로드할 수 있습니다.")

    zip_buffer = BytesIO()
    with ZipFile(zip_buffer, mode="w", compression=ZIP_DEFLATED) as zip_file:
        for file in files:
            filename, data = _convert_to_avif(file)
            zip_file.writestr(filename, data)

    zip_buffer.seek(0)
    headers = {"Content-Disposition": 'attachment; filename="toavif-converted.zip"'}
    return StreamingResponse(zip_buffer, media_type="application/zip", headers=headers)

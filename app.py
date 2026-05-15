from __future__ import annotations

from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import pillow_avif  # noqa: F401
from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image, ImageSequence

from template_config import templates

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
MAX_FILES = 100

app = FastAPI(title="toAVIF")
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def index(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")


def _normalize_image(frame: Image.Image) -> Image.Image:
    if frame.mode in {"RGBA", "RGB"}:
        return frame
    if "A" in frame.getbands():
        return frame.convert("RGBA")
    return frame.convert("RGB")


def _convert_to_avif(file_name: str, content: bytes) -> tuple[str, bytes]:
    ext = Path(file_name).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"지원하지 않는 파일 형식입니다: {file_name}")

    try:
        src = Image.open(BytesIO(content))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"이미지를 열 수 없습니다: {file_name}") from exc

    output = BytesIO()
    out_name = f"{Path(file_name).stem}.avif"

    is_animated = bool(getattr(src, "is_animated", False)) and ext in {".gif", ".webp"}

    if is_animated:
        frames = [_normalize_image(frame.copy()) for frame in ImageSequence.Iterator(src)]
        if not frames:
            raise HTTPException(status_code=400, detail=f"프레임을 찾을 수 없습니다: {file_name}")

        duration = src.info.get("duration", 80)
        loop = src.info.get("loop", 0)
        frames[0].save(
            output,
            format="AVIF",
            save_all=True,
            append_images=frames[1:],
            duration=duration,
            loop=loop,
            quality=62,
            speed=6,
        )
    else:
        _normalize_image(src).save(output, format="AVIF", quality=62, speed=6)

    output.seek(0)
    return out_name, output.read()


@app.post("/convert")
async def convert_images(files: list[UploadFile] = File(...)):
    if not files:
        raise HTTPException(status_code=400, detail="이미지 파일을 업로드해 주세요.")

    if len(files) > MAX_FILES:
        raise HTTPException(status_code=400, detail=f"한 번에 최대 {MAX_FILES}개의 이미지만 업로드할 수 있습니다.")

    zip_buffer = BytesIO()

    with ZipFile(zip_buffer, mode="w", compression=ZIP_DEFLATED) as zip_file:
        for file in files:
            content = await file.read()
            if not content:
                raise HTTPException(status_code=400, detail=f"빈 파일은 변환할 수 없습니다: {file.filename}")

            converted_name, converted_bytes = _convert_to_avif(file.filename or "uploaded", content)
            zip_file.writestr(converted_name, converted_bytes)

    zip_buffer.seek(0)
    headers = {"Content-Disposition": 'attachment; filename="toavif-converted.zip"'}
    return StreamingResponse(zip_buffer, media_type="application/zip", headers=headers)

from __future__ import annotations

import asyncio
import io
import shutil
import uuid
from pathlib import Path
from time import time
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile

from fastapi import FastAPI, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image, ImageOps
import pillow_avif  # noqa: F401

from template_config import templates

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

BASE_DIR = Path("storage")
UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "outputs"
TURNSTILE_SECRET = "PUT_YOUR_TURNSTILE_SECRET_HERE"
TURNSTILE_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
MAX_FILES = 100
EXPIRATION_SECONDS = 3600
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
ALLOWED_MIMES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/gif",
}

for directory in (UPLOAD_DIR, OUTPUT_DIR):
    directory.mkdir(parents=True, exist_ok=True)


@app.on_event("startup")
async def startup_event() -> None:
    asyncio.create_task(cleanup_task())


@app.get("/")
async def index(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")


@app.post("/api/verify-turnstile")
async def verify_turnstile(request: Request, token: str = Form(...)) -> JSONResponse:
    if TURNSTILE_SECRET == "PUT_YOUR_TURNSTILE_SECRET_HERE":
        return JSONResponse({"success": False, "message": "서버에 Turnstile 비밀 키를 설정해주세요."}, status_code=500)

    async with asyncio.timeout(10):
        import httpx

        async with httpx.AsyncClient() as client:
            response = await client.post(
                TURNSTILE_VERIFY_URL,
                data={
                    "secret": TURNSTILE_SECRET,
                    "response": token,
                    "remoteip": request.client.host if request.client else "",
                },
            )

    result = response.json()
    return JSONResponse({"success": bool(result.get("success")), "codes": result.get("error-codes", [])})


@app.post("/api/convert")
async def convert_images(
    request: Request,
    files: list[UploadFile],
    settings: str = Form(...),
) -> JSONResponse:
    if len(files) == 0:
        raise HTTPException(status_code=400, detail="최소 1개의 파일이 필요합니다.")
    if len(files) > MAX_FILES:
        raise HTTPException(status_code=400, detail=f"최대 {MAX_FILES}개 파일만 업로드 가능합니다.")

    import json

    try:
        parsed_settings = json.loads(settings)
    except json.JSONDecodeError as error:
        raise HTTPException(status_code=400, detail="설정 데이터 형식이 잘못되었습니다.") from error

    job_id = uuid.uuid4().hex
    job_upload_dir = UPLOAD_DIR / job_id
    job_output_dir = OUTPUT_DIR / job_id
    job_upload_dir.mkdir(parents=True, exist_ok=True)
    job_output_dir.mkdir(parents=True, exist_ok=True)

    converted: list[dict[str, Any]] = []
    created_at = int(time())

    for index, file in enumerate(files):
        ext = Path(file.filename or "").suffix.lower()
        if ext not in ALLOWED_EXTENSIONS or file.content_type not in ALLOWED_MIMES:
            raise HTTPException(status_code=400, detail=f"지원하지 않는 파일 형식: {file.filename}")

        safe_name = f"{index:03d}_{Path(file.filename or f'file_{index}').stem}"
        input_path = job_upload_dir / f"{safe_name}{ext}"
        output_path = job_output_dir / f"{safe_name}.avif"

        raw = await file.read()
        input_path.write_bytes(raw)

        image_setting = parsed_settings.get(file.filename, {})
        width = image_setting.get("width")
        height = image_setting.get("height")
        quality = int(image_setting.get("quality", 60))
        strip_metadata = bool(image_setting.get("strip_metadata", False))

        with Image.open(io.BytesIO(raw)) as image:
            image = ImageOps.exif_transpose(image)
            if width or height:
                image.thumbnail((int(width or image.width), int(height or image.height)), Image.Resampling.LANCZOS)
            if image.mode not in ("RGB", "RGBA"):
                image = image.convert("RGBA" if "A" in image.getbands() else "RGB")

            save_kwargs: dict[str, Any] = {"quality": max(1, min(100, quality))}
            if not strip_metadata and "exif" in image.info:
                save_kwargs["exif"] = image.info["exif"]

            image.save(output_path, format="AVIF", **save_kwargs)

        converted.append(
            {
                "original_name": file.filename,
                "converted_name": output_path.name,
                "download_url": f"/api/download/{job_id}/{output_path.name}",
                "size": output_path.stat().st_size,
            }
        )

    zip_url = None
    if len(converted) >= 2:
        zip_path = job_output_dir / "converted_images.zip"
        with ZipFile(zip_path, "w", compression=ZIP_DEFLATED) as zip_file:
            for item in converted:
                file_path = job_output_dir / item["converted_name"]
                zip_file.write(file_path, arcname=item["converted_name"])
        zip_url = f"/api/download/{job_id}/converted_images.zip"

    return JSONResponse({"job_id": job_id, "created_at": created_at, "converted": converted, "zip_url": zip_url})


@app.get("/api/download/{job_id}/{filename}")
async def download_file(job_id: str, filename: str) -> FileResponse:
    file_path = OUTPUT_DIR / job_id / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다.")
    return FileResponse(path=file_path, filename=filename)


async def cleanup_task() -> None:
    while True:
        now = time()
        for folder in (UPLOAD_DIR, OUTPUT_DIR):
            for job_dir in folder.glob("*"):
                if not job_dir.is_dir():
                    continue
                mtime = job_dir.stat().st_mtime
                if (now - mtime) > EXPIRATION_SECONDS:
                    shutil.rmtree(job_dir, ignore_errors=True)
        await asyncio.sleep(300)

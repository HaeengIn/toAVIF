import asyncio
import io
import os
import secrets
import shutil
import time
import zipfile
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image
import pillow_avif  # noqa: F401

from template_config import templates

ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp", "gif"}
MAX_FILES = 100
TTL_SECONDS = 3600
BASE_STORAGE = Path("storage")
TURNSTILE_SITEVERIFY = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
TURNSTILE_SECRET_KEY = os.getenv("TURNSTILE_SECRET_KEY", "")

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

jobs: dict[str, dict[str, Any]] = {}
BASE_STORAGE.mkdir(parents=True, exist_ok=True)


def _job_dir(job_id: str) -> Path:
    return BASE_STORAGE / job_id


def _cleanup_job(job_id: str):
    job = jobs.pop(job_id, None)
    if not job:
        return
    dir_path = Path(job["dir"])
    if dir_path.exists():
        shutil.rmtree(dir_path, ignore_errors=True)


async def _cleanup_loop():
    while True:
        now = time.time()
        expired = [jid for jid, job in jobs.items() if now - job["created_at"] > TTL_SECONDS]
        for jid in expired:
            _cleanup_job(jid)
        await asyncio.sleep(60)


@app.on_event("startup")
async def startup_event():
    asyncio.create_task(_cleanup_loop())


@app.get("/")
async def index(request: Request):
    return templates.TemplateResponse(request=request, name="index.html", context={"turnstile_site_key": "0x4AAAAAADPkVbDAr7A4tiI7"})


async def _verify_turnstile(token: str):
    if not TURNSTILE_SECRET_KEY:
        # 개발 중에는 비밀 키가 없어도 통과 처리
        return True
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(TURNSTILE_SITEVERIFY, data={"secret": TURNSTILE_SECRET_KEY, "response": token})
        data = response.json()
        return data.get("success", False)


@app.post("/api/convert")
async def convert_images(
    files: list[UploadFile] = File(...),
    turnstile_token: str = Form(default=""),
    default_width: int | None = Form(default=None),
    default_height: int | None = Form(default=None),
    default_quality: int = Form(default=80),
    default_strip_metadata: bool = Form(default=True),
    overrides: str = Form(default="{}"),
):
    if not await _verify_turnstile(turnstile_token):
        raise HTTPException(status_code=400, detail="캡챠 인증 후 업로드 해주세요.")

    if len(files) == 0:
        raise HTTPException(status_code=400, detail="파일을 업로드 해주세요.")
    if len(files) > MAX_FILES:
        raise HTTPException(status_code=400, detail="최대 100개 이미지만 업로드할 수 있습니다.")

    import json

    override_map = json.loads(overrides or "{}")

    job_id = secrets.token_urlsafe(12)
    output_dir = _job_dir(job_id)
    output_dir.mkdir(parents=True, exist_ok=True)

    converted = []
    for idx, file in enumerate(files):
        filename = file.filename or f"image-{idx}"
        ext = filename.split(".")[-1].lower() if "." in filename else ""
        if ext not in ALLOWED_EXTENSIONS:
            shutil.rmtree(output_dir, ignore_errors=True)
            raise HTTPException(status_code=400, detail=f"지원하지 않는 확장자입니다: {filename}")

        setting = override_map.get(str(idx), {})
        width = setting.get("width", default_width)
        height = setting.get("height", default_height)
        quality = int(setting.get("quality", default_quality))
        strip_metadata = bool(setting.get("strip_metadata", default_strip_metadata))

        content = await file.read()
        image = Image.open(io.BytesIO(content))
        image = image.convert("RGB")

        if width or height:
            new_w = int(width) if width else image.width
            new_h = int(height) if height else image.height
            image = image.resize((new_w, new_h))

        output_name = f"{Path(filename).stem}.avif"
        output_path = output_dir / output_name

        save_kwargs = {"format": "AVIF", "quality": max(1, min(quality, 100))}
        if strip_metadata:
            save_kwargs["exif"] = b""
            save_kwargs["icc_profile"] = None

        image.save(output_path, **save_kwargs)
        converted.append(output_name)

    jobs[job_id] = {
        "id": job_id,
        "dir": str(output_dir),
        "files": converted,
        "created_at": time.time(),
    }

    return JSONResponse({"job_id": job_id, "files": converted})


@app.get("/api/download/{job_id}/{filename}")
async def download_file(job_id: str, filename: str):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="만료되었거나 존재하지 않는 작업입니다.")
    target = Path(job["dir"]) / filename
    if not target.exists():
        raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다.")
    return FileResponse(target, filename=filename, media_type="image/avif")


@app.get("/api/download-zip/{job_id}")
async def download_zip(job_id: str):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="만료되었거나 존재하지 않는 작업입니다.")

    zip_path = Path(job["dir"]) / "converted.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name in job["files"]:
            zf.write(Path(job["dir"]) / name, arcname=name)

    return FileResponse(zip_path, filename="converted_images.zip", media_type="application/zip")


@app.post("/api/reset/{job_id}")
async def reset_job(job_id: str):
    _cleanup_job(job_id)
    return {"ok": True}

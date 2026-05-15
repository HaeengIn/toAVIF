import io
import os
import shutil
import threading
import time
import uuid
import zipfile
from pathlib import Path

import requests
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image
from template_config import templates

BASE_DIR = Path(__file__).resolve().parent
WORK_DIR = BASE_DIR / "storage"
UPLOAD_DIR = WORK_DIR / "uploads"
OUTPUT_DIR = WORK_DIR / "outputs"
TTL_SECONDS = 60 * 60
MAX_FILES = 100
ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp", "gif"}
TURNSTILE_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
TURNSTILE_SECRET_KEY = os.getenv("TURNSTILE_SECRET_KEY", "")

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")


def _is_allowed(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def _cleanup_expired() -> None:
    while True:
        now = time.time()
        for target in (UPLOAD_DIR, OUTPUT_DIR):
            for entry in target.iterdir():
                if entry.is_dir() and now - entry.stat().st_mtime > TTL_SECONDS:
                    shutil.rmtree(entry, ignore_errors=True)
        time.sleep(300)


def _verify_turnstile(token: str, client_ip: str | None) -> bool:
    if not TURNSTILE_SECRET_KEY:
        return False

    payload = {"secret": TURNSTILE_SECRET_KEY, "response": token}
    if client_ip:
        payload["remoteip"] = client_ip

    try:
        response = requests.post(TURNSTILE_VERIFY_URL, data=payload, timeout=10)
        data = response.json()
        return bool(data.get("success"))
    except (requests.RequestException, ValueError):
        return False


threading.Thread(target=_cleanup_expired, daemon=True).start()


@app.get("/")
async def index(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")


@app.post("/api/convert")
async def convert_images(
    request: Request,
    files: list[UploadFile] = File(...),
    turnstile_token: str = Form(...),
    global_width: str | None = Form(default=None),
    global_height: str | None = Form(default=None),
    global_quality: str | None = Form(default=None),
    global_strip_metadata: bool = Form(default=True),
    per_file_settings: str | None = Form(default=None),
):
    if not _verify_turnstile(turnstile_token, request.client.host if request.client else None):
        raise HTTPException(status_code=400, detail="캡챠 인증 후 업로드 해주세요.")

    if len(files) == 0 or len(files) > MAX_FILES:
        raise HTTPException(status_code=400, detail="이미지는 1~100개까지 업로드할 수 있습니다.")

    session_id = str(uuid.uuid4())
    upload_session = UPLOAD_DIR / session_id
    output_session = OUTPUT_DIR / session_id
    upload_session.mkdir(parents=True, exist_ok=True)
    output_session.mkdir(parents=True, exist_ok=True)

    file_settings = {}
    if per_file_settings:
        import json

        file_settings = json.loads(per_file_settings)

    converted_files = []

    for file in files:
        if not _is_allowed(file.filename):
            raise HTTPException(status_code=400, detail=f"{file.filename}: 지원하지 않는 확장자입니다.")

        safe_name = Path(file.filename).name
        src_path = upload_session / safe_name
        content = await file.read()
        src_path.write_bytes(content)

        settings = file_settings.get(safe_name, {})
        width = int(settings.get("width") or global_width or 0)
        height = int(settings.get("height") or global_height or 0)
        quality = int(settings.get("quality") or global_quality or 80)
        strip_metadata = settings.get("stripMetadata", global_strip_metadata)

        dest_name = f"{Path(safe_name).stem}.avif"
        dest_path = output_session / dest_name

        with Image.open(src_path) as img:
            if width > 0 and height > 0:
                img = img.resize((width, height))
            elif width > 0:
                ratio = width / img.width
                img = img.resize((width, int(img.height * ratio)))
            elif height > 0:
                ratio = height / img.height
                img = img.resize((int(img.width * ratio), height))

            save_kwargs = {"format": "AVIF", "quality": max(1, min(100, quality))}
            if strip_metadata:
                save_kwargs["exif"] = b""

            if img.mode not in ("RGB", "RGBA"):
                img = img.convert("RGBA" if "A" in img.getbands() else "RGB")

            img.save(dest_path, **save_kwargs)

        converted_files.append(dest_name)

    zip_name = None
    if len(converted_files) >= 2:
        zip_name = f"{session_id}.zip"
        zip_path = output_session / zip_name
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for name in converted_files:
                zf.write(output_session / name, arcname=name)

    return JSONResponse(
        {
            "sessionId": session_id,
            "files": converted_files,
            "zipFile": zip_name,
            "expiresIn": TTL_SECONDS,
        }
    )


@app.get("/api/download/{session_id}/{filename}")
async def download_file(session_id: str, filename: str):
    file_path = OUTPUT_DIR / session_id / Path(filename).name
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다.")
    return FileResponse(file_path)

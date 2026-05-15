import io
import json
import shutil
import tempfile
import time
import uuid
import zipfile
from pathlib import Path

import pillow_avif  # noqa: F401
import requests
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image

from template_config import templates

app = FastAPI()
app.mount('/static', StaticFiles(directory='static'), name='static')

BASE_DIR = Path(__file__).resolve().parent
WORK_DIR = BASE_DIR / 'runtime_data'
UPLOAD_DIR = WORK_DIR / 'uploads'
OUTPUT_DIR = WORK_DIR / 'outputs'
ZIP_DIR = WORK_DIR / 'zips'

ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.gif'}
MAX_FILES = 100
EXPIRE_SECONDS = 3600
TURNSTILE_VERIFY_URL = 'https://challenges.cloudflare.com/turnstile/v0/siteverify'
TURNSTILE_SITE_KEY = '0x4AAAAAADPkVbDAr7A4tiI7'
# TODO: 실제 배포 전 비밀 키를 환경 변수로 주입하세요.
TURNSTILE_SECRET_KEY = ''

for _dir in (UPLOAD_DIR, OUTPUT_DIR, ZIP_DIR):
    _dir.mkdir(parents=True, exist_ok=True)


def cleanup_expired_files() -> None:
    now = time.time()
    for directory in (UPLOAD_DIR, OUTPUT_DIR, ZIP_DIR):
        for path in directory.iterdir():
            if path.is_file() and now - path.stat().st_mtime > EXPIRE_SECONDS:
                path.unlink(missing_ok=True)
            if path.is_dir() and now - path.stat().st_mtime > EXPIRE_SECONDS:
                shutil.rmtree(path, ignore_errors=True)


def verify_turnstile(token: str, client_ip: str | None) -> bool:
    if not token:
        return False
    if not TURNSTILE_SECRET_KEY:
        return True

    try:
        response = requests.post(
            TURNSTILE_VERIFY_URL,
            data={
                'secret': TURNSTILE_SECRET_KEY,
                'response': token,
                'remoteip': client_ip,
            },
            timeout=10,
        )
        payload = response.json()
    except Exception:
        return False

    return bool(payload.get('success'))


def normalize_target_size(width: int | None, height: int | None, img_width: int, img_height: int) -> tuple[int, int]:
    if width and height:
        return width, height
    if width and not height:
        ratio = img_height / img_width
        return width, max(1, int(round(width * ratio)))
    if height and not width:
        ratio = img_width / img_height
        return max(1, int(round(height * ratio))), height
    return img_width, img_height


@app.get('/')
async def index(request: Request):
    return templates.TemplateResponse(
        request=request,
        name='index.html',
        context={'turnstile_site_key': TURNSTILE_SITE_KEY, 'max_files': MAX_FILES},
    )


@app.post('/api/convert')
async def convert_images(
    request: Request,
    files: list[UploadFile] = File(...),
    settings_json: str = Form(...),
    remove_metadata_all: str = Form('false'),
    turnstile_token: str = Form(''),
):
    cleanup_expired_files()

    if len(files) == 0:
        raise HTTPException(status_code=400, detail='업로드된 파일이 없습니다.')
    if len(files) > MAX_FILES:
        raise HTTPException(status_code=400, detail=f'최대 {MAX_FILES}개 파일까지만 업로드할 수 있습니다.')

    client_ip = request.client.host if request.client else None
    if not verify_turnstile(turnstile_token, client_ip):
        raise HTTPException(status_code=400, detail='캡챠 인증 후 업로드 해주세요.')

    try:
        parsed_settings = json.loads(settings_json)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail='설정 값이 올바르지 않습니다.') from exc

    remove_all = remove_metadata_all.lower() == 'true'
    conversion_id = str(uuid.uuid4())
    batch_upload_dir = UPLOAD_DIR / conversion_id
    batch_output_dir = OUTPUT_DIR / conversion_id
    batch_upload_dir.mkdir(parents=True, exist_ok=True)
    batch_output_dir.mkdir(parents=True, exist_ok=True)

    converted = []

    for index, file in enumerate(files):
        suffix = Path(file.filename or '').suffix.lower()
        if suffix not in ALLOWED_EXTENSIONS:
            raise HTTPException(status_code=400, detail=f'지원하지 않는 파일 형식입니다: {file.filename}')

        raw = await file.read()
        source_path = batch_upload_dir / f'{index}_{Path(file.filename or "image").name}'
        source_path.write_bytes(raw)

        item_setting = parsed_settings.get(str(index), {})
        width = item_setting.get('width')
        height = item_setting.get('height')
        quality = item_setting.get('quality', 70)
        remove_metadata_item = item_setting.get('remove_metadata', False)

        with Image.open(io.BytesIO(raw)) as img:
            img = img.convert('RGBA')
            target_w, target_h = normalize_target_size(
                int(width) if width else None,
                int(height) if height else None,
                img.width,
                img.height,
            )
            if (target_w, target_h) != (img.width, img.height):
                img = img.resize((target_w, target_h), Image.Resampling.LANCZOS)

            output_name = f'{Path(file.filename or "image").stem}.avif'
            output_path = batch_output_dir / output_name

            save_kwargs = {'quality': max(1, min(100, int(quality)))}
            if remove_all or remove_metadata_item:
                save_kwargs['exif'] = b''
                save_kwargs['icc_profile'] = None

            img.save(output_path, format='AVIF', **save_kwargs)

        converted.append(
            {
                'original_name': file.filename,
                'converted_name': output_name,
                'download_url': f'/api/download/{conversion_id}/{output_name}',
            }
        )

    zip_url = None
    if len(converted) >= 2:
        zip_path = ZIP_DIR / f'{conversion_id}.zip'
        with zipfile.ZipFile(zip_path, 'w', compression=zipfile.ZIP_DEFLATED) as zipf:
            for item in converted:
                zipf.write(batch_output_dir / item['converted_name'], arcname=item['converted_name'])
        zip_url = f'/api/download-zip/{conversion_id}'

    return JSONResponse({'conversion_id': conversion_id, 'converted': converted, 'zip_url': zip_url})


@app.get('/api/download/{conversion_id}/{filename}')
async def download_file(conversion_id: str, filename: str):
    cleanup_expired_files()
    file_path = OUTPUT_DIR / conversion_id / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail='파일이 존재하지 않거나 만료되었습니다.')
    return FileResponse(file_path, media_type='image/avif', filename=filename)


@app.get('/api/download-zip/{conversion_id}')
async def download_zip(conversion_id: str):
    cleanup_expired_files()
    zip_path = ZIP_DIR / f'{conversion_id}.zip'
    if not zip_path.exists():
        raise HTTPException(status_code=404, detail='ZIP 파일이 존재하지 않거나 만료되었습니다.')
    return FileResponse(zip_path, media_type='application/zip', filename=f'{conversion_id}.zip')


@app.post('/api/reset/{conversion_id}')
async def reset_conversion(conversion_id: str):
    shutil.rmtree(UPLOAD_DIR / conversion_id, ignore_errors=True)
    shutil.rmtree(OUTPUT_DIR / conversion_id, ignore_errors=True)
    (ZIP_DIR / f'{conversion_id}.zip').unlink(missing_ok=True)
    return JSONResponse({'ok': True})

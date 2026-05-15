# toAVIF

FastAPI + Jinja2 기반 이미지 변환 웹 서비스입니다.

## 지원 포맷
- 입력: JPG, JPEG, PNG, WEBP, GIF
- 출력: AVIF (여러 개 업로드 시 ZIP)
- WEBP/GIF가 애니메이션이면 AVIF도 애니메이션으로 유지

## 실행 방법
```bash
uv sync
uv run uvicorn app:app --reload
```

브라우저에서 `http://127.0.0.1:8000`에 접속하세요.

## 주요 기능
- 최대 100개 파일 동시 업로드
- 드래그 & 드롭 업로드
- 현대적이고 심플한 UI

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from template_config import templates

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def index(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")
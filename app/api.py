# app/api.py
from fastapi import APIRouter, Request, UploadFile, File, HTTPException
from pydantic import BaseModel
from PIL import Image
import io

from .config import PRINT_WIDTH_PX, ReceiptCfg, now_str, APP_API_KEY
from .render import render_receipt, pil_to_base64_png
from .mqtt_client import mqtt_publish_image_base64

router = APIRouter()


def _check_api_key(req: Request):
    key = req.headers.get("x-api-key") or req.query_params.get("key")
    if key != APP_API_KEY:
        raise HTTPException(status_code=401, detail="invalid api key")


class PrintPayload(BaseModel):
    title: str = "TASKS"
    lines: list[str] = []
    cut: bool = True
    add_datetime: bool = True


class RawPayload(BaseModel):
    text: str
    add_datetime: bool = False


@router.get("/")
def ok():
    # kleine Diagnose ohne Key
    from .config import TOPIC, PUBLISH_QOS
    return {"ok": True, "topic": TOPIC, "qos": PUBLISH_QOS}


@router.post("/print")
async def print_job(p: PrintPayload, request: Request):
    _check_api_key(request)
    cfg = ReceiptCfg()
    img = render_receipt(p.title, p.lines, add_time=p.add_datetime, width_px=PRINT_WIDTH_PX, cfg=cfg)
    b64 = pil_to_base64_png(img)
    mqtt_publish_image_base64(b64, cut_paper=(1 if p.cut else 0))
    return {"ok": True}


@router.post("/api/print/template")
async def api_print_template(p: PrintPayload, request: Request):
    _check_api_key(request)
    cfg = ReceiptCfg()
    img = render_receipt(p.title, p.lines, add_time=p.add_datetime, width_px=PRINT_WIDTH_PX, cfg=cfg)
    b64 = pil_to_base64_png(img)
    mqtt_publish_image_base64(b64, cut_paper=(1 if p.cut else 0))
    return {"ok": True}


@router.post("/api/print/raw")
async def api_print_raw(p: RawPayload, request: Request):
    _check_api_key(request)
    cfg = ReceiptCfg()
    lines = (p.text + (f"\n{now_str('%Y-%m-%d %H:%M')}" if p.add_datetime else "")).splitlines()
    img = render_receipt("", lines, add_time=False, width_px=PRINT_WIDTH_PX, cfg=cfg)
    b64 = pil_to_base64_png(img)
    mqtt_publish_image_base64(b64, cut_paper=1)
    return {"ok": True}


@router.post("/api/print/image")
async def api_print_image(request: Request, file: UploadFile = File(...)):
    _check_api_key(request)
    content = await file.read()
    img = Image.open(io.BytesIO(content)).convert("L")
    w, h = img.size
    if w != PRINT_WIDTH_PX:
        img = img.resize((PRINT_WIDTH_PX, int(h * (PRINT_WIDTH_PX / w))))
    # direkt senden (kein Titel/Untertitel hier – das ist in UI/Gast abgedeckt)
    from .render import pil_to_base64_png
    b64 = pil_to_base64_png(img)
    mqtt_publish_image_base64(b64, cut_paper=1)
    return {"ok": True}

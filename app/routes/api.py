from fastapi import APIRouter, Request, UploadFile, File, Form
from pydantic import BaseModel
from PIL import Image
import io
from ..config import PRINT_WIDTH_PX, now_str, ReceiptCfg
from ..security import check_api_key
from ..render import render_receipt, render_image_with_headers, pil_to_base64_png
from ..mqtt_client import mqtt_publish_image_base64

router = APIRouter()

class PrintPayload(BaseModel):
    title: str = "TASKS"
    lines: list[str] = []
    cut: bool = True
    add_datetime: bool = True

class RawPayload(BaseModel):
    text: str
    add_datetime: bool = False

@router.get("/_health")
def health():
    return "OK"

@router.get("/")
def ok():
    from ..config import TOPIC, PUBLISH_QOS
    return {"ok": True, "topic": TOPIC, "qos": PUBLISH_QOS}

@router.post("/print")
async def print_job(p: PrintPayload, request: Request):
    check_api_key(request)
    cfg = ReceiptCfg()
    img = render_receipt(p.title, p.lines, add_time=p.add_datetime, width_px=PRINT_WIDTH_PX, cfg=cfg)
    b64 = pil_to_base64_png(img)
    mqtt_publish_image_base64(b64, cut_paper=(1 if p.cut else 0))
    return {"ok": True}

@router.post("/api/print/template")
async def api_print_template(p: PrintPayload, request: Request):
    check_api_key(request)
    cfg = ReceiptCfg()
    img = render_receipt(p.title, p.lines, add_time=p.add_datetime, width_px=PRINT_WIDTH_PX, cfg=cfg)
    b64 = pil_to_base64_png(img)
    mqtt_publish_image_base64(b64, cut_paper=(1 if p.cut else 0))
    return {"ok": True}

@router.post("/api/print/raw")
async def api_print_raw(p: RawPayload, request: Request):
    check_api_key(request)
    cfg = ReceiptCfg()
    lines = (p.text + (f"\n{now_str('%Y-%m-%d %H:%M')}" if p.add_datetime else "")).splitlines()
    img = render_receipt("", lines, add_time=False, width_px=PRINT_WIDTH_PX, cfg=cfg)
    b64 = pil_to_base64_png(img)
    mqtt_publish_image_base64(b64, cut_paper=1)
    return {"ok": True}

@router.post("/api/print/image")
async def api_print_image(
    request: Request,
    file: UploadFile = File(...),
    img_title: str | None = Form(None),
    img_subtitle: str | None = Form(None),
):
    check_api_key(request)
    content = await file.read()
    src = Image.open(io.BytesIO(content))
    cfg = ReceiptCfg()
    img = render_image_with_headers(src, PRINT_WIDTH_PX, cfg, title=img_title, subtitle=img_subtitle)
    b64 = pil_to_base64_png(img)
    mqtt_publish_image_base64(b64, cut_paper=1)
    return {"ok": True}

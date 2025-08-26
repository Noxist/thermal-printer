from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from ..config import GUEST_DB_FILE, PRINT_WIDTH_PX, ReceiptCfg, now_str
from ..render import render_receipt, render_image_with_headers, pil_to_base64_png
from ..security import require_ui_auth
from ..mqtt_client import mqtt_publish_image_base64
from PIL import Image
import io

from guest_tokens import GuestDB
GUESTS = GuestDB(GUEST_DB_FILE)

router = APIRouter()

from .ui import html_page, HTML_UI  # reuse layout

def guest_ui_html(token: str, name: str, remaining: int) -> str:
    content = f"<div class='card'>Gast: <b>{name}</b> · heute übrig: {remaining}</div>" + HTML_UI
    # Passwordfelder verstecken
    content = content.replace("{{AUTH_REQUIRED}}", "false")
    # Routen umbiegen
    content = content.replace('/ui/print/template', f'/guest/{token}/print/template')
    content = content.replace('/ui/print/raw', f'/guest/{token}/print/raw')
    content = content.replace('/ui/print/image', f'/guest/{token}/print/image')
    return content

@router.get("/guest/{token}", response_class=HTMLResponse)
def guest_ui(token: str, request: Request):
    info = GUESTS.validate(token)
    if not info:
        return html_page("Gast", "<div class='card'>Ungültiger oder deaktivierter Link.</div>")
    remaining = GUESTS.remaining_today(token)
    return html_page("Gastdruck", guest_ui_html(token, info["name"], remaining))

def _guest_consume_or_error(token: str) -> dict | None:
    return GUESTS.consume(token)

@router.post("/guest/{token}/print/template")
async def guest_print_template(
    token: str,
    title: str = Form("TASKS"),
    lines: str = Form(""),
    add_dt: bool = Form(False),
):
    tok = _guest_consume_or_error(token)
    if not tok:
        return html_page("Gastdruck", "<div class='card'>Limit erreicht oder Link ungültig.</div>")
    cfg = ReceiptCfg()
    img = render_receipt(title.strip(), [ln.rstrip() for ln in lines.splitlines()],
                         add_time=add_dt, width_px=PRINT_WIDTH_PX, cfg=cfg, sender_name=tok["name"])
    b64 = pil_to_base64_png(img); mqtt_publish_image_base64(b64, cut_paper=1)
    return RedirectResponse(f"/guest/{token}#tpl", status_code=303)

@router.post("/guest/{token}/print/raw")
async def guest_print_raw(
    token: str,
    text: str = Form(""),
    add_dt: bool = Form(False),
):
    tok = _guest_consume_or_error(token)
    if not tok:
        return html_page("Gastdruck", "<div class='card'>Limit erreicht oder Link ungültig.</div>")
    cfg = ReceiptCfg()
    lines = (text + (f"\n{now_str('%Y-%m-%d %H:%M')}" if add_dt else "")).splitlines()
    img = render_receipt("", lines, add_time=False, width_px=PRINT_WIDTH_PX, cfg=cfg, sender_name=tok["name"])
    b64 = pil_to_base64_png(img); mqtt_publish_image_base64(b64, cut_paper=1)
    return RedirectResponse(f"/guest/{token}#raw", status_code=303)

@router.post("/guest/{token}/print/image")
async def guest_print_image(
    token: str,
    file: bytes = Form(...),
    img_title: str | None = Form(None),
    img_subtitle: str | None = Form(None),
):
    tok = _guest_consume_or_error(token)
    if not tok:
        return html_page("Gastdruck", "<div class='card'>Limit erreicht oder Link ungültig.</div>")
    src = Image.open(io.BytesIO(file))
    cfg = ReceiptCfg()
    composed = render_image_with_headers(src, PRINT_WIDTH_PX, cfg, title=img_title, subtitle=img_subtitle, sender_name=tok["name"])
    b64 = pil_to_base64_png(composed); mqtt_publish_image_base64(b64, cut_paper=1)
    return RedirectResponse(f"/guest/{token}#img", status_code=303)

# --- Admin UI für Gäste ---
@router.get("/ui/guests", response_class=HTMLResponse)
def ui_guests(request: Request):
    if not require_ui_auth(request):
        return html_page("Gäste", "<div class='card'>Nicht angemeldet.</div>")
    form = """
    <section class="card">
      <h3 class="title">Neuen Gast-Link erstellen</h3>
      <form method="post" action="/ui/guests/create">
        <div class="grid">
          <div><label>Anzeige-Name auf dem Zettel</label><input type="text" name="name" value="" placeholder="z. B. Familie Müller" required></div>
          <div><label>Quota pro Tag</label><input type="number" name="quota" value="5" min="1" max="50" step="1"></div>
        </div>
        <div class="row" style="margin-top:12px; gap:12px"><button type="submit">Erstellen</button></div>
      </form>
    </section>
    """
    lst_rows = []
    for tok, info in GUESTS.list():
        rem = GUESTS.remaining_today(tok)
        link = f"/guest/{tok}"
        state = "aktiv" if info.get("active") else "inaktiv"
        lst_rows.append(
            f"<tr style='border-top:1px solid var(--line)'>"
            f"<td style='padding:8px'>{info.get('name','')}</td>"
            f"<td style='padding:8px'>{info.get('quota_per_day',5)}</td>"
            f"<td style='padding:8px'>{rem}</td>"
            f"<td style='padding:8px'>{state}</td>"
            f"<td style='padding:8px'><a class='link' href='{link}' target='_blank'>Link öffnen</a></td>"
            f"<td style='padding:8px'>"
            f"<form method='post' action='/ui/guests/revoke' style='display:inline'>"
            f"<input type='hidden' name='token' value='{tok}'>"
            f"<button class='secondary' type='submit'>Widerrufen</button>"
            f"</form></td></tr>"
        )
    table = "<section class='card'><h3 class='title'>Bestehende Links</h3>" \
            "<table style='width:100%; border-collapse:collapse'>" \
            "<thead><tr><th style='text-align:left;padding:8px'>Name</th><th style='text-align:left;padding:8px'>Quota/Tag</th>" \
            "<th style='text-align:left;padding:8px'>Heute übrig</th><th style='text-align:left;padding:8px'>Status</th>" \
            "<th style='text-align:left;padding:8px'>Link</th><th style='text-align:left;padding:8px'></th></tr></thead>" \
            "<tbody>" + "".join(lst_rows) + "</tbody></table></section>"
    return html_page("Gäste", form + table)

@router.post("/ui/guests/create", response_class=HTMLResponse)
async def ui_guests_create(request: Request):
    if not require_ui_auth(request):
        return html_page("Gäste", "<div class='card'>Nicht angemeldet.</div>")
    form = await request.form()
    name = (form.get("name") or "").strip()
    quota = int((form.get("quota") or "5").strip())
    token = GUESTS.create(name=name, quota_per_day=quota)
    link = f"/guest/{token}"
    return html_page("Gäste", f"<section class='card'>Link erstellt: <a class='link' href='{link}' target='_blank'>{link}</a></section>"
                              f"<meta http-equiv='refresh' content='1;url=/ui/guests'>")

@router.post("/ui/guests/revoke", response_class=HTMLResponse)
async def ui_guests_revoke(request: Request):
    if not require_ui_auth(request):
        return html_page("Gäste", "<div class='card'>Nicht angemeldet.</div>")
    form = await request.form()
    tok = form.get("token") or ""
    GUESTS.revoke(tok)
    return RedirectResponse("/ui/guests", status_code=303)

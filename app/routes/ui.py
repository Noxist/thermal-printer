# app/ui.py
from fastapi import APIRouter, Request, UploadFile, File, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from ..config import (
    PRINT_WIDTH_PX, ReceiptCfg, now_str, COOKIE_NAME,
    SETTINGS, _save_settings, cfg_get
)
from ..render import render_receipt, render_image_with_headers, pil_to_base64_png
from ..security import ui_auth_state, require_ui_auth, issue_cookie
from ..mqtt_client import mqtt_publish_image_base64
from PIL import Image
import io

router = APIRouter()

# ---------- Layout ----------
HTML_BASE = r"""
<!doctype html><html lang="de"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{title}</title>
<style>
  :root{ --bg:#0b0f14; --card:#121821; --muted:#98a2b3; --text:#e6edf3; --line:#1e2a38;
         --accent:#7dd3fc; --accent-2:#a78bfa; --err:#ef4444; --radius:16px; --shadow:0 6px 30px rgba(0,0,0,.35); }
  @media (prefers-color-scheme: light){
    :root{ --bg:#f6f7fb; --card:#ffffff; --text:#0b1220; --muted:#475467; --line:#e7eaf0; --shadow:0 6px 18px rgba(0,0,0,.08); }
  }
  *{box-sizing:border-box} html,body{height:100%} body{
    margin:0; font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, "Helvetica Neue", Arial, "Noto Sans";
    color:var(--text); background: radial-gradient(1200px 600px at 20% -10%, rgba(125,211,252,.15), transparent 60%),
                        radial-gradient(800px 400px at 110% 10%, rgba(167,139,250,.12), transparent 60%), var(--bg);
    line-height:1.35;
  }
  .wrap{max-width:920px; margin:0 auto; padding:clamp(16px,2.5vw,28px)}
  header.top{position:sticky; top:0; backdrop-filter:saturate(1.2) blur(8px);
             background:color-mix(in srgb, var(--bg) 75%, transparent); border-bottom:1px solid var(--line); z-index:5}
  .top-inner{display:flex; align-items:center; gap:12px; padding:12px clamp(12px,2vw,20px)}
  .title{font-weight:700; letter-spacing:.2px; font-size:1.1rem}
  .spacer{flex:1} .link{color:var(--muted); text-decoration:none; font-size:.95rem}
  .link:hover{color:var(--text); text-decoration:underline}
  .card{border:1px solid var(--line); background:color-mix(in srgb, var(--card) 92%, transparent); border-radius:var(--radius); box-shadow:var(--shadow);
        padding:clamp(14px,2.5vw,20px); margin:12px 0 18px}
  .grid{display:grid; grid-template-columns:1fr 1fr; gap:12px}
  @media (max-width:760px){ .grid{grid-template-columns:1fr} }
  .tabs{display:flex; gap:8px; flex-wrap:wrap; padding:14px 0 8px}
  .tab{border:1px solid var(--line); border-radius:999px; padding:8px 14px; cursor:pointer; user-select:none;
       background:color-mix(in srgb, var(--card) 85%, transparent); font-weight:600; font-size:.95rem}
  .tab[aria-selected="true"]{background:linear-gradient(135deg, color-mix(in srgb, var(--card) 88%, transparent), color-mix(in srgb, var(--card) 60%, transparent));
       outline:2px solid color-mix(in srgb, var(--accent) 60%, transparent); border-color:color-mix(in srgb, var(--accent) 40%, var(--line))}
  .row{display:flex; flex-wrap:wrap; align-items:center; gap:10px} .grow{flex:1 1 auto}
  label{font-weight:600; color:var(--muted); display:block; margin:8px 0 6px}
  textarea, input[type=text], input[type=password], input[type=file], input[type=number], select{
    width:100%; border:1px solid var(--line); background:transparent; color:var(--text);
    padding:12px; border-radius:12px; outline:none;
  }
  textarea{min-height:140px; resize:vertical}
  button{appearance:none; border:none; cursor:pointer; font-weight:700; padding:12px 16px; border-radius:12px;
         background:linear-gradient(135deg, var(--accent), var(--accent-2)); color:#0b1220;}
  button.secondary{background:transparent; color:var(--text); border:1px solid var(--line);}
  .hidden{display:none !important} .nav a{margin-left:12px}
</style>
<body>
<header class="top"><div class="top-inner wrap">
  <div class="title">Quittungsdruck</div><div class="spacer"></div>
  <nav class="nav">
    <a class="link" href="/ui">Drucken</a>
    <a class="link" href="/ui/guests">Gaeste</a>
    <a class="link" href="/ui/settings">Einstellungen</a>
    <a class="link" href="/ui/logout" title="Logout">Logout</a>
  </nav>
</div></header>
<main class="wrap">{content}</main>
</body></html>
"""

def html_page(title: str, content: str) -> HTMLResponse:
    return HTMLResponse(HTML_BASE.replace("{title}", title).replace("{content}", content))

# ---------- Haupt-UI ----------
HTML_UI = r"""
<div class="tabs" role="tablist" aria-label="Modus">
  <div class="tab" role="tab" id="tab-tpl" aria-controls="pane_tpl" aria-selected="true" tabindex="0">Vorlage</div>
  <div class="tab" role="tab" id="tab-raw" aria-controls="pane_raw" aria-selected="false" tabindex="-1">Raw</div>
  <div class="tab" role="tab" id="tab-img" aria-controls="pane_img" aria-selected="false" tabindex="-1">Bild</div>
</div>

<section id="pane_tpl" class="card" role="tabpanel" aria-labelledby="tab-tpl">
  <form method="post" action="/ui/print/template">
    <div class="grid">
      <div>
        <label for="title">Titel</label>
        <input id="title" type="text" name="title" value="MORGEN" autocomplete="off">
      </div>
      <div>
        <label for="lines">Zeilen (eine pro Zeile)</label>
        <textarea id="lines" name="lines" placeholder="Schriftstelle lesen – 10 Min&#10;Wasser trinken"></textarea>
      </div>
    </div>
    <div class="row" style="margin-top:12px">
      <label><input type="checkbox" name="add_dt" checked> Datum/Zeit automatisch anhaengen</label>
      <div class="grow"></div>
      <div id="auth-wrap" class="row" style="gap:10px">
        <label for="pass">UI-Passwort</label>
        <input id="pass" type="password" name="pass" placeholder="nur falls noetig" style="max-width:220px">
        <label id="remember-wrap"><input type="checkbox" name="remember"> Angemeldet bleiben</label>
      </div>
    </div>
    <div class="row" style="margin-top:12px; gap:12px">
      <button type="submit">Drucken</button>
    </div>
  </form>
</section>

<section id="pane_raw" class="card" role="tabpanel" aria-labelledby="tab-raw" hidden>
  <form method="post" action="/ui/print/raw">
    <label for="text">Freitext</label>
    <textarea id="text" name="text" placeholder="Kurzer Zettel …"></textarea>
    <div class="row" style="margin-top:12px">
      <label><input type="checkbox" name="add_dt"> Datum/Zeit anhaengen</label>
      <div class="grow"></div>
      <div id="auth-wrap2" class="row" style="gap:10px">
        <label for="pass2">UI-Passwort</label>
        <input id="pass2" type="password" name="pass" placeholder="nur falls noetig" style="max-width:220px">
        <label id="remember-wrap2"><input type="checkbox" name="remember"> Angemeldet bleiben</label>
      </div>
    </div>
    <div class="row" style="margin-top:12px; gap:12px">
      <button type="submit">Drucken</button>
    </div>
  </form>
</section>

<section id="pane_img" class="card" role="tabpanel" aria-labelledby="tab-img" hidden>
  <form method="post" action="/ui/print/image" enctype="multipart/form-data">
    <div class="grid">
      <div>
        <label for="file">Bilddatei (PNG/JPG)</label>
        <input id="file" type="file" name="file" accept=".png,.jpg,.jpeg">
      </div>
      <div>
        <label for="img_title">Titel (optional)</label>
        <input id="img_title" type="text" name="img_title" placeholder="Titel ueber dem Bild">
      </div>
    </div>
    <div class="grid" style="margin-top:8px">
      <div>
        <label for="img_subtitle">Untertitel (optional)</label>
        <input id="img_subtitle" type="text" name="img_subtitle" placeholder="Untertitel ueber dem Bild">
      </div>
    </div>
    <div class="row" style="margin-top:12px">
      <small>Bild wird in s/w konvertiert und auf {w}px Breite skaliert.</small>
      <div class="grow"></div>
      <div id="auth-wrap3" class="row" style="gap:10px">
        <label for="pass3">UI-Passwort</label>
        <input id="pass3" type="password" name="pass" placeholder="nur falls noetig" style="max-width:220px">
        <label id="remember-wrap3"><input type="checkbox" name="remember"> Angemeldet bleiben</label>
      </div>
    </div>
    <div class="row" style="margin-top:12px; gap:12px">
      <button type="submit">Drucken</button>
    </div>
  </form>
</section>

<script>
const tabs=[{id:"tpl",btn:"tab-tpl",pane:"pane_tpl"},{id:"raw",btn:"tab-raw",pane:"pane_raw"},{id:"img",btn:"tab-img",pane:"pane_img"}];
function selectTab(id){
  tabs.forEach(t=>{
    const btn=document.getElementById(t.btn),pane=document.getElementById(t.pane),active=(t.id===id);
    btn.setAttribute("aria-selected",active?"true":"false");
    btn.tabIndex=active?0:-1; pane.hidden=!active;
  });
  history.replaceState(null,"","#"+id);
}
function initFromHash(){ const h=(location.hash||"#tpl").slice(1); selectTab(tabs.some(t=>t.id===h)?h:"tpl"); }
tabs.forEach(t=>{ const el=document.getElementById(t.btn);
  el.addEventListener("click",()=>selectTab(t.id));
  el.addEventListener("keydown",e=>{ if(e.key==="Enter"||e.key===" "){ e.preventDefault(); selectTab(t.id); }});
});
window.addEventListener("hashchange",initFromHash); initFromHash();

const AUTH_REQUIRED=String("{{AUTH_REQUIRED}}").toLowerCase().trim()==="true";
["auth-wrap","auth-wrap2","auth-wrap3"].forEach(id=>{ const el=document.getElementById(id); if(el) el.classList.toggle("hidden", !AUTH_REQUIRED); });
["remember-wrap","remember-wrap2","remember-wrap3"].forEach(id=>{ const el=document.getElementById(id); if(el) el.classList.toggle("hidden", !AUTH_REQUIRED); });
</script>
""".replace("{w}", str(PRINT_WIDTH_PX))

def html(title: str, content: str) -> HTMLResponse:
    return html_page(title, content)

def page_ui(auth_required_flag: str) -> HTMLResponse:
    return html_page("Quittungsdruck", HTML_UI.replace("{{AUTH_REQUIRED}}", auth_required_flag))

@router.get("/ui", response_class=HTMLResponse)
def ui(request: Request):
    auth_required = "false" if require_ui_auth(request) else "true"
    return page_ui(auth_required)

@router.get("/ui/logout")
def ui_logout():
    r = RedirectResponse("/ui", status_code=303)
    r.delete_cookie(COOKIE_NAME, path="/")
    return r

# ---------- Settings-UI ----------
# Form-Felder (ENV-Overrides werden respektiert)
SET_KEYS = [
    ("RECEIPT_PRESET", "clean", "select", ["clean","compact","bigtitle"]),
    ("RECEIPT_MARGIN_TOP", 28, "number", None),
    ("RECEIPT_MARGIN_BOTTOM", 18, "number", None),
    ("RECEIPT_MARGIN_LEFT", 18, "number", None),
    ("RECEIPT_MARGIN_RIGHT", 18, "number", None),
    ("RECEIPT_GAP_TITLE_TEXT", 10, "number", None),
    ("RECEIPT_LINE_HEIGHT", 1.15, "number", None),
    ("RECEIPT_RULE_AFTER_TITLE", False, "checkbox", None),
    ("RECEIPT_RULE_PX", 1, "number", None),
    ("RECEIPT_RULE_PAD", 6, "number", None),

    ("RECEIPT_ALIGN_TITLE", "left", "select", ["left","center","right"]),
    ("RECEIPT_ALIGN_TEXT", "left", "select", ["left","center","right"]),
    ("RECEIPT_ALIGN_TIME", "left", "select", ["left","center","right"]),

    ("RECEIPT_TITLE_SIZE", 36, "number", None),
    ("RECEIPT_TEXT_SIZE", 28, "number", None),
    ("RECEIPT_TIME_SIZE", 24, "number", None),
    ("RECEIPT_TITLE_FONT", "DejaVuSans.ttf", "text", None),
    ("RECEIPT_TEXT_FONT", "DejaVuSans.ttf", "text", None),
    ("RECEIPT_TIME_FONT", "DejaVuSans.ttf", "text", None),

    ("RECEIPT_TIME_SHOW_MINUTES", True, "checkbox", None),
    ("RECEIPT_TIME_SHOW_SECONDS", False, "checkbox", None),
    ("RECEIPT_TIME_PREFIX", "", "text", None),
]

def _settings_effective() -> dict:
    eff = {}
    for key, default, _, _opts in SET_KEYS:
        eff[key] = cfg_get(key, default)
    return eff

def _settings_form_html() -> str:
    eff = _settings_effective()
    rows = []
    for key, default, typ, opts in SET_KEYS:
        val = eff.get(key, default)
        label = key.replace("RECEIPT_", "").replace("_", " ").title()
        if typ == "select":
            options = "".join([f'<option value="{o}"{" selected" if str(val)==str(o) else ""}>{o}</option>' for o in opts])
            field = f'<select name="{key}">{options}</select>'
        elif typ == "checkbox":
            checked = " checked" if str(val).lower() in ("1","true","yes","on","y","t") else ""
            field = f'<input type="checkbox" name="{key}" value="1"{checked}>'
        elif typ == "number":
            field = f'<input type="number" step="any" name="{key}" value="{val}">'
        else:
            field = f'<input type="text" name="{key}" value="{val}">'
        rows.append(f"<div><label>{label}</label>{field}</div>")
    form = f"""
    <section class="card">
      <form method="post" action="/ui/settings/save">
        <div class="grid">
          {''.join(rows)}
        </div>
        <div class="row" style="margin-top:12px; gap:12px">
          <button type="submit">Speichern</button>
          <a class="link" href="/ui/settings/test">Testdruck</a>
        </div>
      </form>
    </section>
    """
    return form

@router.get("/ui/settings", response_class=HTMLResponse)
def ui_settings(request: Request):
    if not require_ui_auth(request):
        return html("Einstellungen", "<div class='card'>Nicht angemeldet.</div>")
    content = "<h3 class='title'>Einstellungen</h3>" + _settings_form_html()
    return html("Einstellungen", content)

@router.post("/ui/settings/save", response_class=HTMLResponse)
async def ui_settings_save(request: Request):
    if not require_ui_auth(request):
        return html("Einstellungen", "<div class='card'>Nicht angemeldet.</div>")
    form = await request.form()
    # in SETTINGS schreiben (persistiert via _save_settings)
    for key, default, typ, _ in SET_KEYS:
        if typ == "checkbox":
            SETTINGS[key] = True if form.get(key) else False
        else:
            val = form.get(key)
            if val is None:
                SETTINGS[key] = default
            else:
                if typ == "number":
                    try:
                        SETTINGS[key] = int(val) if "." not in val else float(val)
                    except:
                        SETTINGS[key] = default
                else:
                    SETTINGS[key] = val
    _save_settings(SETTINGS)
    return RedirectResponse("/ui/settings", status_code=303)

@router.get("/ui/settings/test", response_class=HTMLResponse)
def ui_settings_test(request: Request):
    if not require_ui_auth(request):
        return html("Einstellungen", "<div class='card'>Nicht angemeldet.</div>")
    cfg = ReceiptCfg()
    sample_lines = ["Wasser trinken", "Schriftstelle lesen", "Sport – 20 Min"]
    img = render_receipt("TEST", sample_lines, add_time=True, width_px=PRINT_WIDTH_PX, cfg=cfg)
    b64 = pil_to_base64_png(img)
    mqtt_publish_image_base64(b64, cut_paper=1)
    return html("Einstellungen", "<div class='card'>Testdruck gesendet.</div>")

# ---------- Drucken ----------
def page_ui_flag(request: Request) -> str:
    return "false" if require_ui_auth(request) else "true"

def ui_handle_auth_and_cookie(request: Request, pass_: str | None, remember: bool) -> tuple[bool, bool]:
    authed, should_set_cookie = ui_auth_state(request, pass_, remember)
    if not authed: return False, False
    return True, should_set_cookie

@router.post("/ui/print/template")
async def ui_print_template(
    request: Request,
    title: str = Form("TASKS"),
    lines: str = Form(""),
    add_dt: bool = Form(False),
    pass_: str | None = Form(None, alias="pass"),
    remember: bool = Form(False)
):
    authed, set_cookie = ui_handle_auth_and_cookie(request, pass_, remember)
    if not authed:
        return html_page("Quittungsdruck", "<div class='card'>Falsches Passwort.</div>")
    cfg = ReceiptCfg()
    img = render_receipt(title.strip(), [ln.rstrip() for ln in lines.splitlines()],
                         add_time=add_dt, width_px=PRINT_WIDTH_PX, cfg=cfg)
    b64 = pil_to_base64_png(img); mqtt_publish_image_base64(b64, cut_paper=1)
    resp = RedirectResponse("/ui#tpl", status_code=303)
    if set_cookie: issue_cookie(resp)
    return resp

@router.post("/ui/print/raw")
async def ui_print_raw(
    request: Request,
    text: str = Form(""),
    add_dt: bool = Form(False),
    pass_: str | None = Form(None, alias="pass"),
    remember: bool = Form(False)
):
    authed, set_cookie = ui_handle_auth_and_cookie(request, pass_, remember)
    if not authed:
        return html_page("Quittungsdruck", "<div class='card'>Falsches Passwort.</div>")
    cfg = ReceiptCfg()
    lines = (text + (f"\n{now_str('%Y-%m-%d %H:%M')}" if add_dt else "")).splitlines()
    img = render_receipt("", lines, add_time=False, width_px=PRINT_WIDTH_PX, cfg=cfg)
    b64 = pil_to_base64_png(img); mqtt_publish_image_base64(b64, cut_paper=1)
    resp = RedirectResponse("/ui#raw", status_code=303)
    if set_cookie: issue_cookie(resp)
    return resp

@router.post("/ui/print/image")
async def ui_print_image(
    request: Request,
    file: UploadFile = File(...),
    img_title: str | None = Form(None),
    img_subtitle: str | None = Form(None),
    pass_: str | None = Form(None, alias="pass"),
    remember: bool = Form(False)
):
    authed, set_cookie = ui_handle_auth_and_cookie(request, pass_, remember)
    if not authed:
        return html_page("Quittungsdruck", "<div class='card'>Falsches Passwort.</div>")
    content = await file.read()
    src = Image.open(io.BytesIO(content))
    cfg = ReceiptCfg()
    composed = render_image_with_headers(src, PRINT_WIDTH_PX, cfg, title=img_title, subtitle=img_subtitle)
    b64 = pil_to_base64_png(composed); mqtt_publish_image_base64(b64, cut_paper=1)
    resp = RedirectResponse("/ui#img", status_code=303)
    if set_cookie: issue_cookie(resp)
    return resp

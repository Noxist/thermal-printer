import io, base64
from typing import List
from PIL import Image, ImageDraw, ImageFont
from .config import ReceiptCfg, TZ
from datetime import datetime

def pil_to_base64_png(img: Image.Image) -> str:
    buf = io.BytesIO()
    img = img.convert("1")
    img.save(buf, format="PNG", optimize=True)
    return base64.b64encode(buf.getvalue()).decode("ascii")

def _textlength(draw, text: str, font: ImageFont.FreeTypeFont) -> int:
    try: return int(draw.textlength(text, font=font))
    except Exception:
        bbox = font.getbbox(text); return bbox[2] - bbox[0]

def _wrap(draw, text: str, font: ImageFont.FreeTypeFont, max_px: int) -> List[str]:
    words = text.split()
    if not words: return [""]
    lines, cur = [], words[0]
    for w in words[1:]:
        t = f"{cur} {w}"
        if _textlength(draw, t, font) <= max_px: cur = t
        else: lines.append(cur); cur = w
    lines.append(cur); return lines

def _x_for_align(draw, text: str, font, width: int, align: str, ml: int, mr: int) -> int:
    usable = width - ml - mr; tl = _textlength(draw, text, font)
    if align == "center": return ml + max(0, (usable - tl)//2)
    if align == "right":  return width - mr - tl
    return ml

def _time_str(cfg: ReceiptCfg) -> str:
    fmt = "%Y-%m-%d %H"
    if cfg.time_show_minutes or cfg.time_show_seconds: fmt += ":%M"
    if cfg.time_show_seconds: fmt += ":%S"
    s = datetime.now(TZ).strftime(fmt)
    return (cfg.time_prefix + s).strip()

def render_receipt(
    title: str,
    lines: List[str],
    add_time: bool,
    width_px: int,
    cfg: ReceiptCfg,
    sender_name: str | None = None
) -> Image.Image:
    bg = 255
    img = Image.new("L", (width_px, 10), color=bg)
    draw = ImageDraw.Draw(img)
    cur_y = cfg.margin_top
    max_w = width_px - cfg.margin_left - cfg.margin_right

    # Titel
    title_lines = _wrap(draw, title.strip(), cfg.font_title, max_w) if title else []
    for ln in title_lines:
        x = _x_for_align(draw, ln, cfg.font_title, width_px, cfg.align_title, cfg.margin_left, cfg.margin_right)
        draw.text((x, cur_y), ln, fill=0, font=cfg.font_title)
        ascent, descent = cfg.font_title.getmetrics()
        cur_y += int((ascent + descent) * cfg.line_height_mult)

    if title_lines:
        if cfg.rule_after_title:
            cur_y += cfg.rule_pad
            draw.rectangle((cfg.margin_left, cur_y, width_px - cfg.margin_right, cur_y + cfg.rule_px), fill=0)
            cur_y += cfg.rule_px + cfg.rule_pad
        else:
            cur_y += cfg.gap_title_text

    # Sender
    if sender_name:
        tag = f"Von: {sender_name}"
        x = _x_for_align(draw, tag, cfg.font_time, width_px, cfg.align_time, cfg.margin_left, cfg.margin_right)
        draw.text((x, cur_y), tag, fill=0, font=cfg.font_time)
        ascent, descent = cfg.font_time.getmetrics()
        cur_y += int((ascent + descent) * cfg.line_height_mult)

    # Zeit
    if add_time:
        t = _time_str(cfg)
        x = _x_for_align(draw, t, cfg.font_time, width_px, cfg.align_time, cfg.margin_left, cfg.margin_right)
        draw.text((x, cur_y), t, fill=0, font=cfg.font_time)
        ascent, descent = cfg.font_time.getmetrics()
        cur_y += int((ascent + descent) * cfg.line_height_mult)

    # Body
    for raw in lines:
        if not raw.strip():
            ascent, descent = cfg.font_text.getmetrics()
            cur_y += int((ascent + descent) * cfg.line_height_mult)
            continue
        for ln in _wrap(draw, raw.strip(), cfg.font_text, max_w):
            x = _x_for_align(draw, ln, cfg.font_text, width_px, cfg.align_text, cfg.margin_left, cfg.margin_right)
            draw.text((x, cur_y), ln, fill=0, font=cfg.font_text)
            ascent, descent = cfg.font_text.getmetrics()
            cur_y += int((ascent + descent) * cfg.line_height_mult)

    cur_y += cfg.margin_bottom
    out = Image.new("L", (width_px, cur_y), color=bg)
    out.paste(img, (0, 0))
    return out

def render_image_with_headers(
    image: Image.Image,
    width_px: int,
    cfg: ReceiptCfg,
    title: str | None = None,
    subtitle: str | None = None,
    sender_name: str | None = None
) -> Image.Image:
    if image.mode != "L":
        image = image.convert("L")
    w, h = image.size
    if w != width_px:
        image = image.resize((width_px, int(h * (width_px / w))))
    header_title = title.strip() if title else ""
    header_lines = [subtitle.strip()] if (subtitle and subtitle.strip()) else []
    head = render_receipt(header_title, header_lines, add_time=False, width_px=width_px, cfg=cfg, sender_name=sender_name)
    out = Image.new("L", (width_px, head.height + image.height), color=255)
    out.paste(head, (0, 0)); out.paste(image, (0, head.height))
    return out

#!/usr/bin/env python3
"""Армянские слова: «Նուռ» (гранат) — говорящий гранат рассказывает историю слова.

Использование:  make_video.py ru|es OUT.mp4 WORKDIR [--preview]
Голос: нейросетевой Piper (tts_piper.py, модели — ../../voices.sh), запасной — eSpeak (tts_espeak.py). Если положить рядом готовые записи
диктора WORKDIR/ru_01.wav, ru_02.wav ... (по числу реплик), они будут использованы
вместо синтеза: тайминги и синхронизация губ пересчитаются автоматически.
"""
import math
import os
import subprocess
import sys
import wave
from multiprocessing import Pool

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

import tts_espeak
import tts_piper

W, H, FPS = 1280, 720, 24
WM = W + 300
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONTB = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
SR = 44100


def ss(x):
    x = np.clip(x, 0, 1)
    return x * x * (3 - 2 * x)


def arr(c):
    return np.array(c, np.float32)


def mix(a, b, k):
    return a * (1 - k) + b * k


# --------------------------------------------------------------------------
# ТЕКСТЫ
# --------------------------------------------------------------------------
CHAPTERS_RU = ["Предыстория", "Знакомство со словом", "История", "Связка", "Сегодня", "Финал"]
CHAPTERS_ES = ["Antecedentes", "La palabra", "La historia", "El puente", "Hoy", "Final"]

# (глава 0..5, реплика)
LINES = {
    "ru": [
        (0, "Здравствуйте! Я — гранат. Я родился на тёплых склонах под Араратом."),
        (0, "Мои предки росли здесь задолго до первых армянских букв."),
        (1, "По-армянски я — «нур»."),
        (1, "Учёные спорят, откуда пришло это слово. Но в рукописях оно живёт больше полутора тысяч лет."),
        (2, "А теперь история, которой я горжусь."),
        (2, "В восемнадцатом веке жил поэт и певец Саят-Нова. Он пел о любви под звуки кяманчи."),
        (2, "Почти через двести лет режиссёр Сергей Параджанов снял о нём фильм — «Цвет граната»."),
        (2, "Красный сок граната растекается по белой ткани, словно стихи. Сегодня это шедевр мирового кино."),
        (3, "С тех пор я — не просто фрукт, а знак, понятный без слов."),
        (3, "В Армении гранат дарят на удачу: много зёрен — много счастья."),
        (4, "Осенью по стране проходят праздники граната, с песнями, танцами и вином."),
        (4, "Слово, как гранат: внутри — много маленьких историй. Нужно лишь открыть."),
        (5, "Хорошо, когда знаешь."),
        (5, "Подписывайтесь на канал — впереди ещё много армянских слов, букв и фактов."),
    ],
    "es": [
        (0, "¡Hola! Soy la granada. Nací en las cálidas laderas bajo el monte Ararat."),
        (0, "Mis antepasados crecían aquí mucho antes de las primeras letras armenias."),
        (1, "En armenio me llamo «nur»."),
        (1, "Los lingüistas debaten de dónde viene esta palabra. Pero en los manuscritos vive hace más de mil quinientos años."),
        (2, "Y ahora, una historia de la que estoy orgullosa."),
        (2, "En el siglo dieciocho vivió el poeta y cantor Sayat-Nova. Cantaba al amor con el sonido de la kemancha."),
        (2, "Casi doscientos años después, el director Serguéi Parajánov filmó sobre él «El color de la granada»."),
        (2, "El jugo rojo de la granada se extiende sobre una tela blanca, como un poema. Hoy es una obra maestra del cine."),
        (3, "Desde entonces no soy solo una fruta, sino un símbolo que se entiende sin palabras."),
        (3, "En Armenia se regala una granada para la buena suerte: muchos granos, mucha felicidad."),
        (4, "En otoño hay fiestas de la granada, con canciones, bailes y vino."),
        (4, "Una palabra es como una granada: dentro hay muchas historias pequeñas. Solo hay que abrirla."),
        (5, "Qué bueno es saberlo."),
        (5, "Suscríbete al canal: aún quedan muchas palabras, letras y datos armenios."),
    ],
}
UI = {
    "ru": dict(chap=CHAPTERS_RU, translit="нур", film="1969 · «Цвет граната»", fest="Осень · праздник граната",
               slogan="Хорошо, когда знаешь", sub="Подписаться", tag="армянские слова · буквы · факты",
               sounds=["н", "у", "р"], voice="ru", wpm=112, pitch=26),
    "es": dict(chap=CHAPTERS_ES, translit="nur", film="1969 · «El color de la granada»", fest="Otoño · fiesta de la granada",
               slogan="Qué bueno es saberlo", sub="Suscribirse", tag="palabras · letras · datos armenios",
               sounds=["n", "u", "r"], voice="es", wpm=112, pitch=30),
}

# палитры: (верх неба, низ неба, солнце xy, цвет солнца)
PAL = [
    dict(top=(184, 196, 236), bot=(255, 224, 214), sun=(330, 350), suncol=(255, 206, 170)),   # рассвет
    dict(top=(168, 206, 240), bot=(255, 238, 218), sun=(300, 240), suncol=(255, 226, 170)),   # утро
    dict(top=(160, 200, 226), bot=(238, 242, 232), sun=(420, 150), suncol=(255, 242, 200)),   # ясно
    dict(top=(236, 206, 188), bot=(255, 226, 170), sun=(300, 270), suncol=(255, 200, 120)),   # золото
    dict(top=(184, 166, 214), bot=(255, 204, 196), sun=(330, 360), suncol=(255, 176, 150)),   # розовый закат
    dict(top=(140, 152, 204), bot=(250, 206, 206), sun=(560, 410), suncol=(255, 190, 170)),   # сумерки
]
for _p in PAL:
    for _k in ("top", "bot", "suncol"):
        _p[_k] = arr(_p[_k])
    _p["sun"] = arr(_p["sun"])
SCENE_PAL = [0, 1, 3, 4, 5, 2]

# --------------------------------------------------------------------------
# ПРЕДРАСЧЁТ ГОР (общий для всех языков)
# --------------------------------------------------------------------------
YY, XX = np.mgrid[0:H, 0:W].astype(np.float32)
YM, XM = np.mgrid[0:H, 0:WM].astype(np.float32)
xs = np.arange(WM, dtype=np.float32)


def blur_mask(m, r):
    im = Image.fromarray((np.clip(m, 0, 1) * 255).astype(np.uint8))
    return np.asarray(im.filter(ImageFilter.GaussianBlur(r)), np.float32) / 255.0


def ridge(base, terms):
    y = np.full(WM, base, np.float32)
    for a, f, p in terms:
        y += a * np.sin(xs * f + p)
    return y


def hill_mask(y, r):
    return blur_mask(YM >= y[None, :], r)


FAR_Y = ridge(430, [(28, 0.006, 1), (16, 0.013, 2.3), (8, 0.031, 0)])
MID_Y = ridge(520, [(18, 0.008, 0.4), (10, 0.021, 1.7), (5, 0.05, 0)])
NEAR_Y = ridge(592, [(20, 0.006, 2.2), (11, 0.017, 0.2), (4, 0.04, 0)])
FG_Y = ridge(668, [(14, 0.005, 1), (6, 0.02, 3)])
M_FAR = hill_mask(FAR_Y, 3.5)
M_NEAR = hill_mask(NEAR_Y, 1.8)
M_FG = hill_mask(FG_Y, 1.6)

BASE = 515.0
PEAKS = [(850.0, 300.0, 340.0), (1110.0, 190.0, 220.0)]


def peak_h(cx, h, w):
    s = 20.0
    u = (np.sqrt((xs - cx) ** 2 + s * s) - s) / w
    return h * np.clip(1 - u, 0, 1) ** 1.25


HGT = np.maximum(peak_h(*PEAKS[0]), peak_h(*PEAKS[1])) + 3 * np.sin(xs * 0.05)
TOP_Y = BASE - HGT
M_ARARAT = blur_mask(YM >= TOP_Y[None, :], 1.6)
nearest = peak_h(*PEAKS[1]) > peak_h(*PEAKS[0])
sy = np.where(nearest, BASE - PEAKS[1][1] + 0.36 * PEAKS[1][1], BASE - PEAKS[0][1] + 0.34 * PEAKS[0][1])
sy = sy + 9 * np.sin(xs * 0.05) + 4 * np.sin(xs * 0.13)
M_SNOW = blur_mask((YM >= TOP_Y[None, :]) & (YM <= sy[None, :]), 2.2)
cxn = np.where(nearest, PEAKS[1][0], PEAKS[0][0])
wn = np.where(nearest, PEAKS[1][2], PEAKS[0][2])
M_SHADE = blur_mask(np.clip((XM - cxn[None, :]) / (0.45 * wn[None, :]), 0, 1) * (YM >= TOP_Y[None, :]) * 0.9, 5)
M_SHADE = np.minimum(M_SHADE, M_ARARAT)

_mid = Image.fromarray(((YM >= MID_Y[None, :]) * 255).astype(np.uint8))
_d = ImageDraw.Draw(_mid)
_xc = 822
_yg = int(MID_Y[_xc])
_d.rectangle([_xc - 34, _yg - 30, _xc + 34, _yg + 6], fill=255)
_d.rectangle([_xc + 34, _yg - 14, _xc + 90, _yg + 6], fill=255)
_d.rectangle([_xc - 10, _yg - 50, _xc + 10, _yg - 30], fill=255)
_d.polygon([(_xc - 13, _yg - 50), (_xc, _yg - 76), (_xc + 13, _yg - 50)], fill=255)
for dx, hh in ((-62, 44), (-78, 34), (118, 40), (134, 30), (-300, 38), (310, 36)):
    xx = _xc + dx
    yy = int(MID_Y[xx])
    _d.ellipse([xx - 7, yy - hh, xx + 7, yy + 4], fill=255)
M_MID = np.asarray(_mid.filter(ImageFilter.GaussianBlur(1.6)), np.float32) / 255.0

MIST = (np.exp(-(((YY - 508) / 42.0) ** 2)) * 0.30).astype(np.float32)
RNG = np.random.default_rng(3)
NOISE = (RNG.standard_normal((H, W, 1)).astype(np.float32)) * 0.9
GRAD = (np.arange(H, dtype=np.float32) / H)[:, None, None]


# --------------------------------------------------------------------------
# СПРАЙТЫ
# --------------------------------------------------------------------------
def soften(im, r):
    a = np.asarray(im, np.float32) / 255.0
    pre = a[..., :3] * a[..., 3:4]
    chans = [np.asarray(Image.fromarray((pre[..., c] * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(r)),
                        np.float32) / 255.0 for c in range(3)]
    al = np.asarray(Image.fromarray((a[..., 3] * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(r)),
                    np.float32) / 255.0
    rgb = np.stack(chans, -1) / np.maximum(al[..., None], 1e-3) * 255.0
    return np.clip(rgb, 0, 255).astype(np.float32), al


def sprite(w, h, fn, blur=1.0):
    k = 2
    im = Image.new("RGBA", (w * k, h * k), (0, 0, 0, 0))
    fn(ImageDraw.Draw(im), k)
    im = im.resize((w, h), Image.LANCZOS)
    return soften(im, blur)


def circ(d, k, cx, cy, r, fill):
    d.ellipse([(cx - r) * k, (cy - r) * k, (cx + r) * k, (cy + r) * k], fill=fill)


def lerpc(a, b, f):
    return tuple(int(x * (1 - f) + y * f) for x, y in zip(a, b))


# --- говорящий гранат -------------------------------------------------------
HEAD_W, HEAD_H = 360, 400
HCX, HCY, HR = 180, 238, 140


def d_head(d, k):
    d.ellipse([(HCX - 130) * k, 372 * k, (HCX + 130) * k, 398 * k], fill=(90, 60, 80, 70))
    for i in range(70):
        f = i / 69
        col = lerpc((160, 40, 62), (226, 96, 100), f)
        circ(d, k, HCX - 18 * f, HCY - 18 * f, HR * (1 - f * 0.93), col + (255,))
    for i in range(20):
        f = i / 19
        circ(d, k, 118 - 6 * f, 170 - 6 * f, 36 * (1 - f), lerpc((226, 96, 100), (246, 156, 148), f) + (255,))
    d.polygon([(150 * k, 104 * k), (154 * k, 68 * k), (167 * k, 92 * k), (180 * k, 54 * k), (193 * k, 92 * k),
               (206 * k, 68 * k), (210 * k, 104 * k)], fill=(150, 36, 58, 255))
    d.ellipse([146 * k, 94 * k, 214 * k, 116 * k], fill=(172, 50, 72, 255))
    d.polygon([(198 * k, 82 * k), (268 * k, 44 * k), (246 * k, 98 * k)], fill=(112, 152, 100, 255))
    d.line([200 * k, 84 * k, 256 * k, 56 * k], fill=(150, 188, 136, 255), width=2 * k)


FACE_X, FACE_Y, FACE_W, FACE_H = 90, 190, 180, 150


def make_face(level, eyes):
    """level 0..11 — раскрытие рта; eyes: 0 открыты, 1 моргание, 2 подмигивание."""
    k = 2
    im = Image.new("RGBA", (FACE_W * k, FACE_H * k), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    ink = (84, 40, 72, 255)

    def eye(cx, cy, state):
        if state == "open":
            d.ellipse([(cx - 11) * k, (cy - 14) * k, (cx + 11) * k, (cy + 14) * k], fill=ink)
            circ(d, k, cx + 4, cy - 6, 4, (255, 255, 255, 255))
        else:
            d.arc([(cx - 13) * k, (cy - 10) * k, (cx + 13) * k, (cy + 10) * k], 200, 340, fill=ink, width=5 * k)
    ex1, ex2, ey = 50, 130, 28
    # румянец
    circ(d, k, 22, 82, 19, (255, 164, 164, 110))
    circ(d, k, 158, 82, 19, (255, 164, 164, 110))
    st1 = "open" if eyes != 1 else "shut"
    st2 = "open" if eyes == 0 else "shut"
    eye(ex1, ey, st1)
    eye(ex2, ey, st2)
    # брови
    d.arc([(ex1 - 16) * k, (ey - 36) * k, (ex1 + 16) * k, (ey - 12) * k], 205, 335, fill=(130, 36, 60, 255), width=3 * k)
    d.arc([(ex2 - 16) * k, (ey - 36) * k, (ex2 + 16) * k, (ey - 12) * k], 205, 335, fill=(130, 36, 60, 255), width=3 * k)
    cx, cy = 90, 92
    if level == 0:
        d.arc([(cx - 26) * k, (cy - 16) * k, (cx + 26) * k, (cy + 12) * k], 25, 155, fill=ink, width=5 * k)
    else:
        hh = 5 + level * 3.0
        ww = 24 + level * 1.7
        d.ellipse([(cx - ww / 2) * k, (cy - hh / 2) * k, (cx + ww / 2) * k, (cy + hh / 2) * k], fill=(112, 32, 58, 255))
        if hh > 16:
            d.ellipse([(cx - ww * 0.30) * k, (cy + hh * 0.02) * k, (cx + ww * 0.30) * k, (cy + hh / 2 - 1.5) * k],
                      fill=(236, 116, 126, 255))
    im = im.resize((FACE_W, FACE_H), Image.LANCZOS)
    return soften(im, 0.7)


# --- реквизит сцен ----------------------------------------------------------
def d_tree(d, k):
    d.ellipse([30 * k, 226 * k, 170 * k, 246 * k], fill=(80, 70, 70, 50))
    d.rounded_rectangle([92 * k, 130 * k, 108 * k, 236 * k], radius=6 * k, fill=(128, 98, 84, 255))
    for cx, cy, r in ((100, 96, 52), (68, 118, 38), (132, 118, 40), (100, 70, 36)):
        circ(d, k, cx, cy, r, (122, 164, 106, 255))
    for cx, cy, r in ((100, 70, 30), (82, 100, 30)):
        circ(d, k, cx - 8, cy - 8, r, (146, 184, 124, 255))
    rr = np.random.default_rng(9)
    for _ in range(9):
        a = rr.uniform(0, 6.28)
        rad = rr.uniform(8, 58)
        x, y = 100 + rad * math.cos(a) * 0.9, 98 + rad * math.sin(a) * 0.8
        circ(d, k, x, y, 9, (178, 44, 64, 255))
        circ(d, k, x - 3, y - 3, 3, (236, 120, 124, 255))


FILM_W, FILM_H = 460, 300


def d_film(d, k):
    d.rounded_rectangle([0, 0, FILM_W * k, FILM_H * k], radius=26 * k, fill=(104, 66, 92, 255))
    for i in range(12):
        x = 22 + i * 37
        d.rounded_rectangle([x * k, 10 * k, (x + 18) * k, 24 * k], radius=4 * k, fill=(252, 240, 230, 255))
        d.rounded_rectangle([x * k, (FILM_H - 24) * k, (x + 18) * k, (FILM_H - 10) * k], radius=4 * k, fill=(252, 240, 230, 255))
    d.rounded_rectangle([22 * k, 36 * k, (FILM_W - 22) * k, (FILM_H - 36) * k], radius=14 * k, fill=(252, 247, 242, 255))


def d_poet(d, k):
    ink = (96, 64, 100, 255)
    d.polygon([(70 * k, 262 * k), (86 * k, 150 * k), (130 * k, 150 * k), (146 * k, 262 * k)], fill=ink)
    circ(d, k, 108, 124, 22, (214, 168, 146, 255))
    d.polygon([(86 * k, 112 * k), (130 * k, 112 * k), (118 * k, 78 * k), (98 * k, 78 * k)], fill=ink)
    d.rounded_rectangle([82 * k, 108 * k, 134 * k, 118 * k], radius=4 * k, fill=(150, 60, 80, 255))
    circ(d, k, 172, 214, 24, (176, 112, 84, 255))
    circ(d, k, 172, 214, 9, (110, 70, 60, 255))
    d.line([172 * k, 192 * k, 196 * k, 100 * k], fill=(128, 84, 70, 255), width=7 * k)
    d.line([128 * k, 168 * k, 170 * k, 214 * k], fill=(214, 168, 146, 255), width=7 * k)
    d.line([150 * k, 150 * k, 238 * k, 238 * k], fill=(110, 80, 70, 255), width=3 * k)


def d_seed(d, k):
    circ(d, k, 12, 12, 10, (196, 36, 66, 255))
    circ(d, k, 9, 9, 3.2, (240, 120, 130, 255))


def d_garland(d, k):
    gw = 780
    pts = [(x, 12 + 50 * (1 - (2 * x / gw - 1) ** 2)) for x in range(0, gw + 1, 4)]
    d.line([(x * k, y * k) for x, y in pts], fill=(150, 112, 104, 255), width=3 * k)
    cols = [(232, 120, 128), (250, 196, 150), (186, 168, 224), (170, 214, 190), (246, 214, 130)]
    for i, x in enumerate(range(20, gw - 10, 40)):
        y = 12 + 50 * (1 - (2 * x / gw - 1) ** 2)
        if i % 5 == 2:
            circ(d, k, x, y + 20, 16, (190, 44, 66, 255))
            circ(d, k, x - 5, y + 14, 5, (238, 120, 126, 255))
            d.polygon([((x - 7) * k, (y + 6) * k), (x * k, (y + 0) * k), ((x + 7) * k, (y + 6) * k)], fill=(140, 36, 58, 255))
        else:
            c = cols[i % len(cols)]
            d.polygon([((x - 15) * k, y * k), ((x + 15) * k, y * k), (x * k, (y + 40) * k)], fill=c + (255,))


def make_cloud(seed):
    r = np.random.default_rng(seed)
    im = Image.new("L", (440, 150), 0)
    d = ImageDraw.Draw(im)
    for i in range(5):
        cx = 90 + i * 60 + r.uniform(-12, 12)
        d.ellipse([cx - r.uniform(40, 70), 90 - r.uniform(30, 52), cx + r.uniform(40, 70), 100 + r.uniform(5, 15)], fill=255)
    d.ellipse([40, 82, 400, 118], fill=255)
    return np.asarray(im.filter(ImageFilter.GaussianBlur(14)), np.float32) / 255.0 * 0.62


def make_petal(ang):
    im = Image.new("RGBA", (40, 40), (0, 0, 0, 0))
    ImageDraw.Draw(im).ellipse([8, 14, 32, 26], fill=(255, 220, 230, 255))
    return soften(im.rotate(ang, resample=Image.BICUBIC), 1.0)


# --------------------------------------------------------------------------
# ТЕКСТОВЫЕ СПРАЙТЫ
# --------------------------------------------------------------------------
def wrap(d, text, font, maxw):
    lines, cur = [], ""
    for w in text.split(" "):
        trial = (cur + " " + w).strip()
        if d.textlength(trial, font=font) <= maxw:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    lines.append(cur)
    return lines


def pill(size, radius, fill, blur=4, pad=14):
    w, h = size
    bg = Image.new("L", (w + 2 * pad, h + 2 * pad), 0)
    ImageDraw.Draw(bg).rounded_rectangle([pad, pad, pad + w, pad + h], radius=radius, fill=fill)
    bg = bg.filter(ImageFilter.GaussianBlur(blur))
    im = Image.new("RGBA", bg.size, (255, 251, 247, 0))
    im.putalpha(bg)
    return im, pad


def to_np(im):
    a = np.asarray(im, np.float32)
    return a[..., :3], a[..., 3] / 255.0


def text_card(lines_spec, w, pad=28, radius=34, fill=190):
    """lines_spec: [(text, font, color, line_h)] — уже разбитые строки."""
    h = pad * 2 + sum(lh for _, _, _, lh in lines_spec)
    bg, p = pill((w, h), radius, fill)
    txt = Image.new("RGBA", bg.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(txt)
    y = p + pad - 4
    for t, f, c, lh in lines_spec:
        d.text((p + pad, y), t, font=f, fill=c)
        y += lh
    return to_np(Image.alpha_composite(bg, txt)), (p, h)


# --------------------------------------------------------------------------
# АУДИО
# --------------------------------------------------------------------------
def ss1(x):
    return np.clip(x, 0, 1) ** 2 * (3 - 2 * np.clip(x, 0, 1))


def make_music(dur):
    sr = SR
    T = dur + 1.0
    n = int(sr * T)
    t = np.arange(n) / sr
    L = np.zeros(n)
    R = np.zeros(n)
    rng = np.random.default_rng(7)

    def put(sig, s, gl, gr):
        i0 = int(s * sr)
        i1 = min(n, i0 + len(sig))
        if i1 > i0:
            L[i0:i1] += sig[: i1 - i0] * gl
            R[i0:i1] += sig[: i1 - i0] * gr

    def env_win(d, a, r):
        x = np.arange(int(d * sr)) / sr
        return ss1(x / a) * ss1((d - x) / r)

    chords = [[146.83, 174.61, 220.00], [116.54, 146.83, 174.61], [130.81, 164.81, 196.00], [110.00, 146.83, 174.61]]
    seg = 7.5
    for k in range(int(T / seg) + 1):
        s = max(0.0, k * seg - 1.8)
        d = (k + 1) * seg + 1.8 - s
        x = np.arange(int(d * sr)) / sr + s
        env = env_win(d, 2.4, 2.4) * (1 + 0.12 * np.sin(2 * np.pi * 0.17 * x))
        for f in chords[k % 4]:
            for det, gl, gr in ((0.997, 1.0, 0.55), (1.003, 0.55, 1.0)):
                w = np.sin(2 * np.pi * f * det * x) + 0.22 * np.sin(2 * np.pi * 2 * f * det * x)
                put(w * env * 0.035, s, gl, gr)
    drone = np.sin(2 * np.pi * 73.42 * t) * (0.7 + 0.3 * np.sin(2 * np.pi * 0.05 * t)) * 0.03
    L += drone
    R += drone
    notes = [440.0, 349.23, 392.0, 329.63, 293.66]
    ts = 4.0
    i = 0
    while ts < dur - 8:
        d = 7.5
        x = np.arange(int(d * sr)) / sr
        f = notes[i % len(notes)]
        vib = 1 + 0.004 * np.sin(2 * np.pi * 4.8 * x) * ss1(x / 2.0)
        ph = 2 * np.pi * np.cumsum(f * vib) / sr
        w = np.sin(ph) + 0.30 * np.sin(3 * ph) + 0.10 * np.sin(5 * ph)
        put(w * env_win(d, 1.8, 2.5) * 0.026, ts, 0.8, 0.8)
        ts += 11.0
        i += 1
    scale = [293.66, 329.63, 349.23, 392.0, 440.0, 466.16, 523.25, 587.33]
    idx = 4
    cur = 2.5
    while cur < dur - 3:
        idx = int(np.clip(idx + rng.choice([-2, -1, -1, 1, 1, 2]), 0, len(scale) - 1))
        f = scale[idx]
        x = np.arange(int(5.0 * sr)) / sr
        e = (1 - np.exp(-x / 0.004)) * np.exp(-x / 1.2)
        w = np.sin(2 * np.pi * f * x) + 0.35 * np.sin(4 * np.pi * f * x) * np.exp(-x / 0.5) \
            + 0.12 * np.sin(6 * np.pi * f * x) * np.exp(-x / 0.3)
        pan = rng.uniform(0.35, 0.9)
        put(w * e * 0.05, cur, pan, 1.25 - pan)
        cur += float(rng.choice([1.5, 2.0, 2.0, 3.0, 4.0]))

    def reverb(x, seed):
        r = np.random.default_rng(seed)
        li = int(2.8 * sr)
        ir = r.standard_normal(li) * np.exp(-np.arange(li) / (0.75 * sr))
        ir[: int(0.02 * sr)] *= np.linspace(0, 1, int(0.02 * sr))
        size = 1 << int(np.ceil(np.log2(len(x) + li)))
        y = np.fft.irfft(np.fft.rfft(x, size) * np.fft.rfft(ir, size), size)[: len(x)]
        return y / (np.abs(y).max() + 1e-9) * np.abs(x).max()
    L = 0.55 * L + 0.7 * reverb(L, 1)
    R = 0.55 * R + 0.7 * reverb(R, 2)
    m = max(np.abs(L).max(), np.abs(R).max())
    n_out = int(sr * dur)
    return L[:n_out] / m, R[:n_out] / m


def build_timeline(lang, work):
    ui = UI[lang]
    segs = []
    for i, (ch, text) in enumerate(LINES[lang]):
        custom = os.path.join(work, f"{lang}_{i + 1:02d}.wav")
        if os.path.exists(custom):
            with wave.open(custom) as wf:
                raw = np.frombuffer(wf.readframes(wf.getnframes()), "<i2").astype(np.float32) / 32768
                if wf.getnchannels() == 2:
                    raw = raw.reshape(-1, 2).mean(1)
                y = raw
                sr = wf.getframerate()
            y = np.interp(np.arange(0, len(y), sr / tts_espeak.SR), np.arange(len(y)), y).astype(np.float32)
        else:
            if tts_piper.available(lang):
                y = tts_piper.soften(tts_piper.synth(text, lang))
            else:  # запасной синтетический голос
                x = tts_espeak.synth(text, ui["voice"], ui["wpm"], ui["pitch"])
                y = tts_espeak.soften(x)
        segs.append((ch, text, y))
    t = 1.8
    starts, prev = [], None
    for ch, text, y in segs:
        if prev is not None:
            t += 1.1 if ch != prev else 0.45
        starts.append(t)
        t += len(y) / tts_espeak.SR
        prev = ch
    dur = t + 3.2
    return segs, starts, dur


def build_audio(segs, starts, dur):
    sr = SR
    voice = np.zeros(int(dur * sr) + sr, np.float32)
    for (ch, text, y), s in zip(segs, starts):
        y44 = np.interp(np.arange(0, len(y) - 1, tts_espeak.SR / sr), np.arange(len(y)), y).astype(np.float32)
        i0 = int(s * sr)
        voice[i0:i0 + len(y44)] += y44
    voice = voice[: int(dur * sr)]
    L, R = make_music(dur)
    # «просадка» музыки под голос
    win = int(0.25 * sr)
    e = np.convolve(np.abs(voice), np.ones(win) / win, mode="same")
    e = np.convolve(e, np.ones(win) / win, mode="same")
    duck = 1 - 0.5 * np.clip(e / (np.percentile(e[e > 0.01], 80) + 1e-9), 0, 1)
    t = np.arange(len(voice)) / sr
    fade = ss1(t / 2.5) * ss1((dur - t) / 3.0)
    mg = 0.20
    outL = L * mg * duck * fade + voice * 0.92
    outR = R * mg * duck * fade + voice * 0.92
    pk = max(np.abs(outL).max(), np.abs(outR).max())
    if pk > 0.97:
        outL, outR = outL / pk * 0.97, outR / pk * 0.97
    return voice, np.stack([outL, outR], 1)


def mouth_track(voice, n):
    spf = SR // FPS
    rms = np.array([np.sqrt(np.mean(voice[i * spf:(i + 1) * spf] ** 2)) if i * spf < len(voice) else 0.0 for i in range(n)])
    ref = np.percentile(rms[rms > 0.01], 92) if (rms > 0.01).any() else 1.0
    lvl = np.clip(rms / ref, 0, 1) ** 0.75
    lvl[rms < 0.012] = 0
    out = np.zeros(n)
    for i in range(n):
        out[i] = 0.6 * lvl[i] + 0.4 * (out[i - 1] if i else 0)
    return np.round(out * 11).astype(int), rms


# --------------------------------------------------------------------------
# ГЛОБАЛЬНОЕ СОСТОЯНИЕ ДЛЯ ВОРКЕРОВ (заполняется в setup)
# --------------------------------------------------------------------------
G = {}


def setup(lang, work):
    ui = UI[lang]
    segs, starts, dur = build_timeline(lang, work)
    voice, stereo = build_audio(segs, starts, dur)
    n = int(round(dur * FPS))
    mouth, rms = mouth_track(voice, n)

    # главы: границы
    first = {}
    last = {}
    for i, (ch, _, y) in enumerate(segs):
        first.setdefault(ch, starts[i])
        last[ch] = starts[i] + len(y) / tts_espeak.SR
    bounds = [0.0]
    for ch in range(1, 6):
        bounds.append((last[ch - 1] + first[ch]) / 2)
    bounds.append(dur)
    SC = [dict(t0=bounds[i], t1=bounds[i + 1], pal=SCENE_PAL[i]) for i in range(6)]

    fnt = lambda s, b=False: ImageFont.truetype(FONTB if b else FONT, s)
    tmp = ImageDraw.Draw(Image.new("RGBA", (10, 10)))

    # субтитры
    subs = []
    for i, (ch, text, y) in enumerate(segs):
        f = fnt(30)
        lines = wrap(tmp, text, f, 690)
        spec = [(ln, f, (74, 60, 86, 255), 40) for ln in lines]
        (rgb, a), (pd, h) = text_card(spec, 740)
        subs.append(dict(rgb=rgb, a=a, x=36 - pd, y=H - 34 - h - pd, t0=starts[i], t1=starts[i] + len(y) / tts_espeak.SR))

    # плашка слова
    wf_, tf_ = fnt(104, True), fnt(38)
    spec = [("Նուռ", wf_, (96, 58, 100, 255), 128), (ui["translit"], tf_, (166, 98, 84, 255), 48)]
    (wrgb, wa), (pd, h) = text_card(spec, 300, pad=24, radius=34, fill=170)
    wordcard = dict(rgb=wrgb, a=wa, x=40 - pd, y=60 - pd)

    # плашки глав
    chips = []
    for i, name in enumerate(ui["chap"]):
        f = fnt(21, True)
        txt = f"{i + 1} · {name}"
        w = int(tmp.textlength(txt, font=f)) + 36
        bg, p = pill((w, 38), 19, 175, blur=2, pad=6)
        t = Image.new("RGBA", bg.size, (0, 0, 0, 0))
        ImageDraw.Draw(t).text((p + 18, p + 5), txt, font=f, fill=(96, 58, 100, 255))
        rgb, a = to_np(Image.alpha_composite(bg, t))
        chips.append(dict(rgb=rgb, a=a, x=40 - p, y=16 - p))

    # пузыри букв (глава 2)
    bubbles = []
    for j, (g, snd) in enumerate(zip(["Ն", "ու", "ռ"], ui["sounds"])):
        bg, p = pill((128, 128), 64, 190, blur=3, pad=8)
        t = Image.new("RGBA", bg.size, (0, 0, 0, 0))
        dd = ImageDraw.Draw(t)
        f = fnt(70, True)
        w = dd.textlength(g, font=f)
        dd.text(((bg.size[0] - w) / 2, p + 14), g, font=f, fill=(96, 58, 100, 255))
        f2 = fnt(26)
        w2 = dd.textlength(snd, font=f2)
        dd.text(((bg.size[0] - w2) / 2, p + 96), snd, font=f2, fill=(166, 98, 84, 255))
        rgb, a = to_np(Image.alpha_composite(bg, t))
        bubbles.append(dict(rgb=rgb, a=a, x=420 + j * 150, y=46 - p + 0))

    # подпись под плёнкой и фестиваль
    def tag(text, size=24):
        f = fnt(size, True)
        w = int(tmp.textlength(text, font=f)) + 40
        bg, p = pill((w, 46), 23, 190, blur=2, pad=6)
        t = Image.new("RGBA", bg.size, (0, 0, 0, 0))
        ImageDraw.Draw(t).text((p + 20, p + 8), text, font=f, fill=(96, 58, 100, 255))
        return to_np(Image.alpha_composite(bg, t)), (w, p)
    (film_rgb, film_a), (fw_, fp_) = tag(ui["film"])
    (fest_rgb, fest_a), (fsw_, fsp_) = tag(ui["fest"])

    # слоган
    f = fnt(64 if lang == "ru" else 60, True)
    sw = int(tmp.textlength(ui["slogan"], font=f)) + 80
    spec_h = 84
    bg, p = pill((sw, spec_h + 54), 40, 200, blur=5, pad=14)
    t = Image.new("RGBA", bg.size, (0, 0, 0, 0))
    dd = ImageDraw.Draw(t)
    dd.text((p + 40, p + 10), ui["slogan"], font=f, fill=(96, 58, 100, 255))
    f3 = fnt(24)
    dd.text((p + 42, p + 94), ui["tag"], font=f3, fill=(166, 98, 84, 255))
    s_rgb, s_a = to_np(Image.alpha_composite(bg, t))
    slogan = dict(rgb=s_rgb, a=s_a, x=60 - p, y=130 - p, w=sw)

    # кнопка подписки
    btxt = ui["sub"]
    f4 = fnt(30, True)
    bw = int(tmp.textlength(btxt, font=f4)) + 130
    bim = Image.new("RGBA", (bw + 20, 90), (0, 0, 0, 0))
    bd = ImageDraw.Draw(bim)
    bd.rounded_rectangle([10, 10, 10 + bw, 74], radius=32, fill=(214, 60, 74, 255))
    bd.text((10 + 28, 10 + 14), btxt, font=f4, fill=(255, 250, 248, 255))
    cx = 10 + bw - 44
    bd.ellipse([cx - 14, 26, cx + 14, 52], fill=(255, 250, 248, 255))
    bd.polygon([(cx - 18, 52), (cx + 18, 52), (cx + 12, 40), (cx - 12, 40)], fill=(255, 250, 248, 255))
    bd.ellipse([cx - 5, 53, cx + 5, 63], fill=(255, 250, 248, 255))
    b_rgb, b_a = soften(bim, 0.8)
    button = dict(rgb=b_rgb, a=b_a, x=48, y=H - 34 - 120 - 90 - 30)

    # лицо: 12 уровней × 3 состояния глаз
    faces = {(lv, e): make_face(lv, e) for lv in range(12) for e in range(3)}
    # реквизит
    head = sprite(HEAD_W, HEAD_H, d_head, 1.0)
    tree = sprite(200, 250, d_tree, 1.0)
    film_base = sprite(FILM_W, FILM_H, d_film, 1.0)
    poet = sprite(FILM_W, FILM_H, d_poet, 0.9)
    seed = sprite(24, 24, d_seed, 0.6)
    garland = sprite(780, 120, d_garland, 0.9)

    # пятно сока: «карта времени прихода»
    sh, sw_ = FILM_H - 72, FILM_W - 44
    yy, xx = np.mgrid[0:sh, 0:sw_].astype(np.float32)
    nz = np.zeros((sh, sw_), np.float32)
    rr = np.random.default_rng(21)
    for a_, f_, p_, q_ in [(0.06, 0.018, 1, 2), (0.03, 0.035, 2, 1)]:
        nz += a_ * (np.sin(xx * f_ + p_ + yy * 0.011) + np.sin(yy * f_ * 1.3 + q_))
    R_ = np.hypot(xx - sw_ * 0.74, yy - sh * 0.62) / 330.0
    T = R_ + nz
    T = (T - T.min()) / (T.max() - T.min())
    stain_T = T
    stain_R = (R_ - R_.min()) / (R_.max() - R_.min())

    clouds = [(make_cloud(s), y, sp, x0) for s, y, sp, x0 in
              ((1, 70, 7.0, 100), (2, 150, 5.0, 520), (3, 230, 9.0, 900), (4, 110, 4.0, 1200), (5, 40, 6.0, -100))]
    petal_rot = [make_petal(a) for a in (0, 45, 90, 135)]
    petals = [dict(x=float(RNG.uniform(0, W + 60)), y=float(RNG.uniform(0, H + 60)),
                   vx=float(RNG.uniform(14, 30)), vy=float(RNG.uniform(18, 38)),
                   ph=float(RNG.uniform(0, 6.28)), am=float(RNG.uniform(14, 34)),
                   a=float(RNG.uniform(0.5, 0.85))) for _ in range(24)]
    seeds = [dict(x=float(RNG.uniform(-60, 60)), ph=float(RNG.uniform(0, 1)), sp=float(RNG.uniform(0.10, 0.2)),
                  dx=float(RNG.uniform(-260, 120)), am=float(RNG.uniform(10, 30))) for _ in range(26)]

    G.update(dict(lang=lang, ui=ui, dur=dur, N=n, SC=SC, subs=subs, wordcard=wordcard, chips=chips, bubbles=bubbles,
                  film=(film_rgb, film_a, fw_, fp_), fest=(fest_rgb, fest_a, fsw_, fsp_), slogan=slogan, button=button,
                  faces=faces, head=head, tree=tree, film_base=film_base, poet=poet, seed=seed, garland=garland,
                  stain_T=stain_T, stain_R=stain_R, clouds=clouds, petal_rot=petal_rot, petals=petals, seeds=seeds, mouth=mouth,
                  rms=rms, starts=starts, segs_dur=[len(y) / tts_espeak.SR for _, _, y in segs], stereo=stereo))


# --------------------------------------------------------------------------
# КАДР
# --------------------------------------------------------------------------
def pal_at(t):
    SC = G["SC"]
    i = next((k for k, s in enumerate(SC) if s["t0"] <= t < s["t1"]), len(SC) - 1)
    cw = 1.2

    def P(k):
        return PAL[SC[k]["pal"]]

    def blend(a, b, k):
        return {key: mix(a[key], b[key], k) for key in a}
    if i < len(SC) - 1 and t > SC[i]["t1"] - cw:
        return blend(P(i), P(i + 1), float(ss((t - (SC[i]["t1"] - cw)) / (2 * cw))))
    if i > 0 and t < SC[i]["t0"] + cw:
        return blend(P(i - 1), P(i), float(ss((t - (SC[i]["t0"] - cw)) / (2 * cw))))
    return P(i)


def blit(img, rgb, a, x, y, k=1.0):
    h, w = a.shape
    x0, y0, x1, y1 = max(x, 0), max(y, 0), min(x + w, W), min(y + h, H)
    if x1 <= x0 or y1 <= y0:
        return
    sa = (a[y0 - y:y1 - y, x0 - x:x1 - x] * k)[..., None]
    sr = rgb if rgb.ndim == 1 else rgb[y0 - y:y1 - y, x0 - x:x1 - x]
    reg = img[y0:y1, x0:x1]
    reg[:] = reg * (1 - sa) + sr * sa


def layer(img, mask, color, shift):
    o = int(shift)
    f = shift - o
    a = (mask[:, o:o + W] * (1 - f) + mask[:, o + 1:o + 1 + W] * f)[..., None]
    img[:] = img * (1 - a) + color * a


def scene_vis(sc, t, fin=1.2, fout=1.0):
    return float(ss((t - sc["t0"] - 0.2) / fin) * ss((sc["t1"] - t) / fout))


def frame(i):
    t = i / FPS
    SC = G["SC"]
    DUR = G["dur"]
    cur = next((k for k, s in enumerate(SC) if s["t0"] <= t < s["t1"]), 5)
    p = pal_at(t)
    top, bot = p["top"], p["bot"]
    img = np.repeat(top * (1 - GRAD) + bot * GRAD, W, axis=1).astype(np.float32)

    sx, sy_ = p["sun"][0] + 20 * math.sin(t / 9.0), p["sun"][1]
    d2 = (XX - sx) ** 2 + (YY - sy_) ** 2
    glow = np.clip(0.55 * np.exp(-d2 / (2 * 200 ** 2)) + 0.95 * np.exp(-d2 / (2 * 36 ** 2)), 0, 1)[..., None]
    img = img * (1 - glow * 0.75) + p["suncol"] * glow * 0.75

    pr = t / DUR - 0.5
    hz = lambda base, k: mix(arr(base), bot, k)
    layer(img, M_FAR, hz((176, 176, 212), 0.45), 150 + 20 * pr)
    layer(img, M_ARARAT, hz((142, 146, 192), 0.30), 150 + 14 * pr)
    layer(img, M_SHADE * 0.30, hz((92, 96, 150), 0.25), 150 + 14 * pr)
    layer(img, M_SNOW, mix(arr((255, 252, 255)), bot, 0.18), 150 + 14 * pr)

    cc = mix(arr((255, 255, 255)), bot, 0.22)
    for spr, cy, sp, x0 in G["clouds"]:
        cx = int((x0 + sp * t + 300) % (W + 700) - 440)
        blit(img, cc, spr, cx, cy + int(4 * math.sin(t / 5 + cy)))
    mist = MIST[..., None]
    img = img * (1 - mist) + mix(arr((255, 255, 255)), bot, 0.5) * mist
    layer(img, M_MID, hz((150, 184, 170), 0.30), 150 + 40 * pr)
    layer(img, M_NEAR, hz((186, 192, 130), 0.14), 150 + 70 * pr)

    # --- реквизит по главам
    v0 = scene_vis(SC[0], t)
    if v0 > 0.002:  # гранатовые деревья
        rgb, a = G["tree"]
        for j, (x, y) in enumerate(((20, 372), (230, 392), (440, 366))):
            blit(img, rgb, a, x + int(3 * math.sin(t * 0.7 + j)), y + int((1 - v0) * 16), v0)
    v1 = scene_vis(SC[1], t)
    if v1 > 0.002:  # буквы-пузыри
        for j, b in enumerate(G["bubbles"]):
            k = float(ss((t - SC[1]["t0"] - 1.4 - j * 0.9) / 0.7)) * v1
            if k > 0.002:
                blit(img, b["rgb"], b["a"], b["x"], int(b["y"] + (1 - k) * 22 + 6 * math.sin(t * 1.3 + j)), k)
    v2 = scene_vis(SC[2], t)
    if v2 > 0.002:  # плёнка
        fx, fy = 470, 100
        rgb, a = G["film_base"]
        blit(img, rgb, a, fx, fy, v2)
        # пятно сока
        pstain = float(np.clip((t - SC[2]["t0"] - 5.0) / 14.0, 0, 1)) * 0.82
        T = G["stain_T"]
        sa = ss((pstain - T) / 0.10) * 0.92
        sa = np.asarray(Image.fromarray((sa * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(2.2)), np.float32) / 255.0
        sh, sw_ = sa.shape
        col = np.empty((sh, sw_, 3), np.float32)
        dark = ss((pstain - G["stain_R"]) / 0.9)[..., None]
        col[:] = mix(arr((214, 52, 72)), arr((150, 24, 54)), dark)
        blit(img, col, sa.astype(np.float32), fx + 22, fy + 36, v2)
        rgb, a = G["poet"]
        blit(img, rgb, a, fx, fy, v2)
        frgb, fa, fw_, fp_ = G["film"]
        blit(img, frgb, fa, fx + (FILM_W - fw_) // 2 - fp_, fy + FILM_H + 6, v2)
    v4 = scene_vis(SC[4], t)
    if v4 > 0.002:  # гирлянда
        rgb, a = G["garland"]
        blit(img, rgb, a, 500 + int(5 * math.sin(t * 0.8)), 0, v4)
        frgb, fa, fw_, fp_ = G["fest"]
        blit(img, frgb, fa, 560 - fp_, 150, v4 * float(ss((t - SC[4]["t0"] - 1.0) / 1.0)))

    layer(img, M_FG, hz((156, 176, 114), 0.06), 150 + 110 * pr)

    # --- говорящий гранат
    hv = float(ss(t / 1.2))
    lvl = int(G["mouth"][min(i, G["N"] - 1)])
    speak = lvl / 11.0
    bob = 5 * math.sin(2 * math.pi * t / 4.2) + 4 * speak
    hx, hy = 905, 318 + int(bob) + int((1 - hv) * 30)
    hrgb, ha = G["head"]
    blit(img, hrgb, ha, hx, hy, hv)
    blink_phase = (t % 3.6)
    eyes = 1 if (blink_phase < 0.14 and t > 0.8) else 0
    sc_slogan = SC[5]
    ss_t = G["starts"][12]
    if ss_t + 0.5 < t < ss_t + 1.3:  # подмигивание на слогане
        eyes = 2
    frgb, fa = G["faces"][(lvl, eyes)]
    blit(img, frgb, fa, hx + FACE_X, hy + FACE_Y + int(1.5 * speak), hv)

    # семена из граната (главы 4–5)
    for ch in (3, 4):
        vv = scene_vis(SC[ch], t, fin=1.5, fout=1.5)
        if vv > 0.002:
            rgb, a = G["seed"]
            for s in G["seeds"][: (26 if ch == 3 else 14)]:
                u = (t * s["sp"] + s["ph"]) % 1.0
                sxp = hx + 150 + s["x"] + s["dx"] * u + s["am"] * math.sin(u * 9 + s["ph"] * 6)
                syp = hy + 40 - u * 380
                blit(img, rgb, a, int(sxp), int(syp), vv * math.sin(math.pi * u) ** 0.6)

    # --- слоган и кнопка (глава 6)
    v5 = scene_vis(SC[5], t, fin=1.0, fout=1.4)
    sg = G["slogan"]
    k5 = float(ss((t - G["starts"][12] + 0.2) / 0.9)) * float(ss((DUR - 1.6 - t) / 1.0))
    if k5 > 0.002:
        blit(img, sg["rgb"], sg["a"], sg["x"], int(sg["y"] + (1 - k5) * 14), k5)
    kb = float(ss((t - G["starts"][13] + 0.3) / 0.8)) * float(ss((DUR - 1.6 - t) / 1.0))
    if kb > 0.002:
        bt = G["button"]
        pulse = 1 + 0.03 * math.sin(t * 5)
        blit(img, bt["rgb"], bt["a"], bt["x"], int(bt["y"] + 3 * math.sin(t * 5)), kb * min(1.0, pulse))

    # --- плашка слова и глава
    if cur in (1, 2, 3, 4):
        wk = scene_vis(SC[cur], t, fin=0.8, fout=0.6) if cur in (1, 4) else 1.0
        wk = float(ss((t - SC[1]["t0"] - 0.8) / 0.9)) * float(ss((SC[4]["t1"] - 0.2 - t) / 0.8))
        wc = G["wordcard"]
        blit(img, wc["rgb"], wc["a"], wc["x"], wc["y"] + int((1 - wk) * 10), wk)
    chip = G["chips"][cur]
    ck = float(ss((t - SC[cur]["t0"] - 0.3) / 0.7)) * float(ss((SC[cur]["t1"] - 0.1 - t) / 0.6)) if cur < 5 \
        else float(ss((t - SC[cur]["t0"] - 0.3) / 0.7)) * float(ss((DUR - 1.8 - t) / 0.8))
    blit(img, chip["rgb"], chip["a"], chip["x"], chip["y"], ck)

    # --- субтитры
    for s in G["subs"]:
        k = float(ss((t - s["t0"] + 0.1) / 0.25)) * float(ss((s["t1"] + 0.35 - t) / 0.3))
        if k > 0.002:
            blit(img, s["rgb"], s["a"], s["x"], int(s["y"] + (1 - k) * 8), k)

    # --- лепестки
    for j, pt in enumerate(G["petals"]):
        px = (pt["x"] + pt["vx"] * t + pt["am"] * math.sin(t * 0.8 + pt["ph"])) % (W + 60) - 30
        py = (pt["y"] + pt["vy"] * t) % (H + 60) - 30
        rgb, a = G["petal_rot"][int(t * 1.5 + j) % 4]
        blit(img, rgb, a, int(px), int(py), pt["a"])

    f = float(ss(t / 1.0) * ss((DUR - t) / 1.8))
    img = mix(arr((252, 246, 246)), img, f)
    img += NOISE
    return np.clip(img, 0, 255).astype(np.uint8).tobytes()


def main():
    lang, out, work = sys.argv[1], sys.argv[2], sys.argv[3]
    os.makedirs(work, exist_ok=True)
    setup(lang, work)
    n = G["N"]
    print(f"[{lang}] длительность {G['dur']:.1f} с, кадров {n}", flush=True)
    for i, (s, d) in enumerate(zip(G["starts"], G["segs_dur"])):
        print(f"  реплика {i + 1:02d}: {s:6.2f}–{s + d:6.2f}", flush=True)
    if "--preview" in sys.argv:
        for k, sec in enumerate([float(x) for x in os.environ.get("PREV", "4,12,22,30,40,52,66,78").split(",")]):
            if sec * FPS < n:
                Image.frombytes("RGB", (W, H), frame(int(sec * FPS))).save(f"{out}_{int(sec):03d}.png")
        return
    wav = os.path.join(work, f"mix_{lang}.wav")
    with wave.open(wav, "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes((G["stereo"] * 32767).astype("<i2").tobytes())
    ff = subprocess.Popen(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
         "-r", str(FPS), "-i", "-", "-i", wav, "-c:v", "libx264", "-preset", "medium", "-crf", "20",
         "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", out],
        stdin=subprocess.PIPE)
    with Pool(4) as pool:
        for k, fr in enumerate(pool.imap(frame, range(n), chunksize=6)):
            ff.stdin.write(fr)
            if k % 300 == 0:
                print(f"{k}/{n}", flush=True)
    ff.stdin.close()
    ff.wait()


if __name__ == "__main__":
    main()

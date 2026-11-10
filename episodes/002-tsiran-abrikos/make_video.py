#!/usr/bin/env python3
"""Армянские слова, выпуск 002: «Ծիրան» (абрикос) — абрикос рассказывает историю слова и дудука.

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
LINES_SHORT = {
    "ru": [
        (0, "Здравствуйте! Я — абрикос. Я вырос в садах у подножия Арарата."),
        (0, "Римляне называли меня «армянским яблоком»."),
        (1, "По-армянски я — «циран». Слово звучит тепло, как спелый плод."),
        (2, "Из моего дерева делают дудук — «циранапох»: «абрикосовая дудка»."),
        (2, "Мастер Дживан Гаспарян сделал её голос известным всему миру."),
        (2, "А ЮНЕСКО берегит дудук как нематериальное наследие."),
        (3, "Так обычный плод стал голосом целой страны."),
        (4, "Летом в Ереване проходит кинофестиваль «Золотой абрикос»."),
        (4, "Слово, как абрикос: снаружи сладкое, а внутри — косточка истории."),
        (5, "Хорошо, когда знаешь."),
        (5, "Подписывайтесь на канал — впереди ещё много армянских слов!"),
    ],
    "es": [
        (0, "¡Hola! Soy el albaricoque. Crecí en los huertos al pie del Ararat."),
        (0, "Los romanos me llamaban «manzana armenia»."),
        (1, "En armenio me llamo «tsirán». Suena cálido, como una fruta madura."),
        (2, "De mi madera se hace el duduk, «tsiranapogh»: la flauta de albaricoque."),
        (2, "El maestro Djivan Gasparyan llevó su voz por todo el mundo."),
        (2, "Y la UNESCO protege el duduk como patrimonio inmaterial."),
        (3, "Así, una simple fruta se volvió la voz de un país."),
        (4, "En verano, Ereván celebra el festival de cine Albaricoque de Oro."),
        (4, "Una palabra es como un albaricoque: dulce por fuera y, por dentro, un hueso de historia."),
        (5, "Qué bueno es saberlo."),
        (5, "¡Suscríbete! Aún quedan muchas palabras armenias."),
    ],
}
SHORT = True  # выпуск 002 рассчитан на формат 45 с
SPEED = float(os.environ.get("HAYEREN_SPEED", "1.5" if SHORT else "1.0"))
if SHORT:
    LINES = LINES_SHORT
UI = {
    "ru": dict(chap=CHAPTERS_RU, translit="циран", film="Дудук · наследие ЮНЕСКО", fest="Лето · «Золотой абрикос»",
               slogan="Хорошо, когда знаешь", sub="Подписаться", tag="армянские слова · буквы · факты",
               sounds=["ц", "и", "р", "а", "н"], voice="ru", wpm=112, pitch=26),
    "es": dict(chap=CHAPTERS_ES, translit="tsirán", film="Duduk · patrimonio UNESCO", fest="Verano · «Albaricoque de Oro»",
               slogan="Qué bueno es saberlo", sub="Suscribirse", tag="palabras · letras · datos armenios",
               sounds=["ts", "i", "r", "a", "n"], voice="es", wpm=112, pitch=30),
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


def sprite(w, h, fn, blur=1.0, scale=1.0):
    k = 2
    im = Image.new("RGBA", (w * k, h * k), (0, 0, 0, 0))
    fn(ImageDraw.Draw(im), k)
    im = im.resize((int(round(w * scale)), int(round(h * scale))), Image.LANCZOS)
    return soften(im, blur)


def circ(d, k, cx, cy, r, fill):
    d.ellipse([(cx - r) * k, (cy - r) * k, (cx + r) * k, (cy + r) * k], fill=fill)


def lerpc(a, b, f):
    return tuple(int(x * (1 - f) + y * f) for x, y in zip(a, b))


# --- говорящий герой (3D-шейдинг) -------------------------------------------
HEAD_W, HEAD_H = 360, 400
MS = 0.8  # масштаб маскота
HCX, HCY, HR = 180, 238, 140
FACE_X, FACE_Y, FACE_W, FACE_H = 90, 190, 180, 150
LIGHT = np.array([-0.5, -0.6, 0.62], np.float32)
LIGHT /= np.linalg.norm(LIGHT)
HALF = LIGHT + np.array([0, 0, 1], np.float32)
HALF /= np.linalg.norm(HALF)
STYLES = {
    "pomegranate": dict(dark=(104, 18, 44), mid=(194, 50, 74), light=(244, 128, 122), rim=(255, 150, 130),
                        blush=(255, 150, 150)),
    "apricot": dict(dark=(190, 86, 20), mid=(248, 160, 46), light=(255, 218, 124), rim=(255, 236, 170),
                    blush=(244, 96, 70)),
}
MASCOT = os.environ.get("HAYEREN_MASCOT", "apricot")


def shade(nx, ny, nz, dark, mid, light, rimc, spec=0.5, rim=0.4, gloss=46):
    dark, mid, light, rimc = arr(dark), arr(mid), arr(light), arr(rimc)
    lam = np.clip(nx * LIGHT[0] + ny * LIGHT[1] + nz * LIGHT[2], 0, 1) ** 0.85
    t1 = np.clip(lam * 2, 0, 1)[..., None]
    t2 = np.clip(lam * 2 - 1, 0, 1)[..., None]
    col = dark + (mid - dark) * t1 + (light - mid) * t2
    ndh = np.clip(nx * HALF[0] + ny * HALF[1] + nz * HALF[2], 0, 1)
    sp = (ndh ** gloss * spec)[..., None]
    col = col * (1 - sp) + 255.0 * sp
    rd = np.clip(nx * 0.65 + ny * 0.55, 0, 1)
    rm = ((1 - nz) ** 2.2 * rim * rd)[..., None]
    col = col + rimc * rm
    return np.clip(col, 0, 255)


def over(drgb, da, srgb, sa):
    oa = sa + da * (1 - sa)
    orgb = (srgb * sa[..., None] + drgb * (da * (1 - sa))[..., None]) / np.maximum(oa, 1e-6)[..., None]
    return orgb, oa


def ellipsoid(h, w, cx, cy, rx, ry, pal, spec=0.5, rim=0.4, gloss=46, tex=None):
    Y, X = np.mgrid[0:h, 0:w].astype(np.float32)
    x, y = (X - cx) / rx, (Y - cy) / ry
    rr = x * x + y * y
    nz = np.sqrt(np.clip(1 - rr, 0, 1))
    rgb = shade(x, y, nz, pal["dark"], pal["mid"], pal["light"], pal["rim"], spec, rim, gloss)
    if tex is not None:
        rgb = rgb * (1 + tex)[..., None]
    alpha = np.clip((1 - np.sqrt(rr)) * min(rx, ry) * 0.9, 0, 1).astype(np.float32)
    return rgb.astype(np.float32), alpha, x, y


def to_pil(rgb, a):
    out = np.dstack([np.clip(rgb, 0, 255), np.clip(a, 0, 1) * 255]).astype(np.uint8)
    return Image.fromarray(out, "RGBA")


def make_head_sprite(style):
    st = STYLES[style]
    k = 2
    w, h = HEAD_W * k, HEAD_H * k
    rgb = np.zeros((h, w, 3), np.float32)
    al = np.zeros((h, w), np.float32)
    Y, X = np.mgrid[0:h, 0:w].astype(np.float32)
    # мягкая тень на земле
    sh = 0.32 * np.exp(-(((X - w / 2) / (250.0)) ** 2 + ((Y - 782) / 24.0) ** 2) * 1.6)
    rgb, al = over(rgb, al, np.full((h, w, 3), (70, 46, 74), np.float32), sh.astype(np.float32))
    # ножки
    feet = dict(dark=(86, 14, 38), mid=(150, 34, 58), light=(210, 80, 90), rim=(255, 140, 120))
    if style == "apricot":
        feet = dict(dark=(150, 66, 16), mid=(214, 120, 34), light=(250, 180, 90), rim=(255, 226, 150))
    for fx in (264, 456):
        r_, a_, _, _ = ellipsoid(h, w, fx, 748, 70, 40, feet, spec=0.35)
        rgb, al = over(rgb, al, r_, a_)
    # тело
    rr_ = np.random.default_rng(5).standard_normal((50, 45)).astype(np.float32)
    tex = np.asarray(Image.fromarray(((rr_ - rr_.min()) / (rr_.max() - rr_.min()) * 255).astype(np.uint8))
                     .resize((w, h), Image.BICUBIC), np.float32) / 255.0
    tex = (tex - 0.5) * 0.07
    body, ba, x, y = ellipsoid(h, w, HCX * k, HCY * k, HR * k, HR * k, st, spec=0.55, rim=0.45, gloss=40, tex=tex)
    if style == "apricot":
        g = np.exp(-((x - (0.10 + 0.07 * y)) / 0.05) ** 2) * (np.abs(y) < 0.92)
        body = body * (1 - 0.20 * g)[..., None]
        bl = np.exp(-(((x + 0.40) / 0.55) ** 2 + ((y - 0.15) / 0.60) ** 2))[..., None] * 0.50
        body = body * (1 - bl) + arr(st["blush"]) * bl
    else:
        bl = np.exp(-(((x - 0.1) / 0.8) ** 2 + ((y + 0.85) / 0.25) ** 2))[..., None] * 0.35  # затемнение у короны
        body = body * (1 - bl) + arr((90, 14, 40)) * bl
    rgb, al = over(rgb, al, body, ba)
    # верхушка (корона/черешок и листья)
    top = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(top)
    if style == "pomegranate":
        d.polygon([(150 * k, 106 * k), (153 * k, 66 * k), (167 * k, 92 * k), (180 * k, 52 * k), (193 * k, 92 * k),
                   (207 * k, 66 * k), (210 * k, 106 * k)], fill=(118, 24, 50, 255))
        d.polygon([(158 * k, 106 * k), (160 * k, 78 * k), (169 * k, 95 * k), (180 * k, 64 * k), (191 * k, 95 * k),
                   (200 * k, 78 * k), (202 * k, 106 * k)], fill=(176, 50, 74, 255))
        d.ellipse([146 * k, 94 * k, 214 * k, 118 * k], fill=(150, 38, 62, 255))
        d.ellipse([154 * k, 96 * k, 190 * k, 108 * k], fill=(204, 80, 98, 255))
        d.polygon([(198 * k, 84 * k), (270 * k, 44 * k), (246 * k, 100 * k)], fill=(84, 126, 80, 255))
        d.polygon([(204 * k, 84 * k), (262 * k, 52 * k), (244 * k, 90 * k)], fill=(128, 178, 112, 255))
        d.line([204 * k, 86 * k, 258 * k, 58 * k], fill=(168, 210, 150, 255), width=2 * k)
    else:
        d.line([180 * k, 108 * k, 190 * k, 62 * k], fill=(104, 70, 46, 255), width=9 * k)
        d.line([180 * k, 108 * k, 190 * k, 62 * k], fill=(150, 108, 76, 255), width=4 * k)
        d.polygon([(190 * k, 78 * k), (262 * k, 40 * k), (242 * k, 98 * k)], fill=(84, 126, 80, 255))
        d.polygon([(196 * k, 78 * k), (254 * k, 50 * k), (240 * k, 90 * k)], fill=(130, 180, 112, 255))
        d.polygon([(182 * k, 86 * k), (122 * k, 54 * k), (140 * k, 98 * k)], fill=(84, 126, 80, 255))
        d.polygon([(178 * k, 86 * k), (130 * k, 62 * k), (142 * k, 92 * k)], fill=(130, 180, 112, 255))
    ta = np.asarray(top, np.float32)
    rgb, al = over(rgb, al, ta[..., :3], ta[..., 3] / 255.0)
    im = to_pil(rgb, al).resize((int(HEAD_W * MS), int(HEAD_H * MS)), Image.LANCZOS)
    return soften(im, 0.45)


def make_face(level, eyes, style="pomegranate"):
    """level 0..11 — раскрытие рта; eyes: 0 открыты, 1 моргание, 2 подмигивание."""
    k = 2
    fw, fh = int(FACE_W * MS), int(FACE_H * MS)
    im = Image.new("RGBA", (FACE_W * k, FACE_H * k), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    ink = (74, 34, 62, 255)

    def eye(cx, cy, state):
        if state == "open":
            d.ellipse([(cx - 12) * k, (cy - 16) * k, (cx + 12) * k, (cy + 16) * k], fill=(54, 26, 52, 255))
            d.ellipse([(cx - 8) * k, (cy - 2) * k, (cx + 8) * k, (cy + 14) * k], fill=(110, 60, 94, 255))
            circ(d, k, cx + 4, cy - 7, 5.4, (255, 255, 255, 255))
            circ(d, k, cx - 4, cy + 7, 2.4, (255, 255, 255, 255))
        else:
            d.arc([(cx - 13) * k, (cy - 10) * k, (cx + 13) * k, (cy + 10) * k], 200, 340, fill=ink, width=5 * k)
    ex1, ex2, ey = 50, 130, 28
    eye(ex1, ey, "open" if eyes != 1 else "shut")
    eye(ex2, ey, "open" if eyes == 0 else "shut")
    brow = (128, 40, 56, 255) if style == "pomegranate" else (150, 74, 30, 255)
    d.arc([(ex1 - 16) * k, (ey - 38) * k, (ex1 + 16) * k, (ey - 14) * k], 205, 335, fill=brow, width=3 * k)
    d.arc([(ex2 - 16) * k, (ey - 38) * k, (ex2 + 16) * k, (ey - 14) * k], 205, 335, fill=brow, width=3 * k)
    cx, cy = 90, 92
    if level == 0:
        d.arc([(cx - 26) * k, (cy - 16) * k, (cx + 26) * k, (cy + 12) * k], 25, 155, fill=ink, width=5 * k)
    else:
        hh = 5 + level * 3.0
        ww = 24 + level * 1.7
        d.ellipse([(cx - ww / 2) * k, (cy - hh / 2) * k, (cx + ww / 2) * k, (cy + hh / 2) * k], fill=(104, 28, 52, 255))
        if hh > 16:
            d.ellipse([(cx - ww * 0.30) * k, (cy + hh * 0.02) * k, (cx + ww * 0.30) * k, (cy + hh / 2 - 1.5) * k],
                      fill=(238, 120, 128, 255))
    top = np.asarray(im.resize((fw, fh), Image.LANCZOS), np.float32)
    ta = top[..., 3] / 255.0
    # румянец — мягкий «аэрограф»
    Y, X = np.mgrid[0:fh, 0:fw].astype(np.float32)
    ba = np.zeros((fh, fw), np.float32)
    for bx in (32, 148):
        ba = np.maximum(ba, 0.55 * np.exp(-(((X - bx * MS) / (15 * MS)) ** 2 + ((Y - 84 * MS) / (10 * MS)) ** 2)))
    ba = ba * (ss(X / 14) * ss((fw - 1 - X) / 14) * ss(Y / 14) * ss((fh - 1 - Y) / 14)).astype(np.float32)
    brgb = np.full((fh, fw, 3), STYLES[style]["blush"], np.float32)
    rgb, a = over(brgb, ba, top[..., :3], ta)
    return rgb.astype(np.float32), a.astype(np.float32)


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
        circ(d, k, x, y, 9, (240, 142, 34, 255))
        circ(d, k, x - 3, y - 3, 3, (255, 210, 120, 255))


FILM_W, FILM_H = 460, 300


def d_film(d, k):
    d.rounded_rectangle([0, 0, FILM_W * k, FILM_H * k], radius=30 * k, fill=(116, 66, 88, 255))
    d.rounded_rectangle([12 * k, 12 * k, (FILM_W - 12) * k, (FILM_H - 12) * k], radius=24 * k, fill=(236, 190, 140, 255))
    d.rounded_rectangle([22 * k, 36 * k, (FILM_W - 22) * k, (FILM_H - 36) * k], radius=14 * k, fill=(252, 244, 232, 255))


def d_poet(d, k):  # дудук: деревянная флейта с язычком и отверстиями
    wood = [(150, 92, 52), (176, 112, 64), (206, 146, 88)]
    x0, y0, x1, y1 = 120, 232, 330, 120
    import math as _m
    ang = _m.atan2(y1 - y0, x1 - x0)
    n = 60
    for layer, (col, wd) in enumerate(zip(wood, (30, 24, 14))):
        for i in range(n + 1):
            u = i / n
            cx, cy = x0 + (x1 - x0) * u, y0 + (y1 - y0) * u
            r = wd / 2 * (1 - 0.18 * u) - (0 if layer == 0 else 1.5 * u)
            circ(d, k, cx - layer * 1.2, cy - layer * 1.2, r, col + (255,))
    for u in (0.3, 0.42, 0.54, 0.66, 0.78):
        cx, cy = x0 + (x1 - x0) * u, y0 + (y1 - y0) * u
        circ(d, k, cx, cy, 4.2, (70, 40, 30, 255))
    for i in range(14):  # язычок
        u = i / 13
        cx, cy = x0 - 18 * u * _m.cos(ang) , y0 - 18 * u * _m.sin(ang)
        circ(d, k, cx, cy, 7 - 2 * u, (226, 190, 120, 255))


def make_aril():
    pal = dict(dark=(196, 90, 20), mid=(250, 164, 48), light=(255, 224, 140), rim=(255, 236, 170))
    r_, a_, _, _ = ellipsoid(80, 80, 40, 40, 24, 24, pal, spec=0.6, rim=0.3, gloss=30)
    im = to_pil(r_, a_).resize((34, 34), Image.LANCZOS)
    return soften(im, 0.4)


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
            circ(d, k, x, y + 20, 16, (240, 148, 40, 255))
            circ(d, k, x - 5, y + 14, 5, (255, 214, 130, 255))
            d.ellipse([(x - 3) * k, (y + 2) * k, (x + 9) * k, (y + 9) * k], fill=(110, 160, 96, 255))
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



# --- руки маскота -----------------------------------------------------------
ARM_L = 112  # половина холста руки (в «дизайн»-единицах); центр холста = плечо


def make_arm_variants(style):
    st = STYLES[style]
    k = 2
    size = 2 * ARM_L * k
    c = ARM_L * k
    rgb = np.zeros((size, size, 3), np.float32)
    al = np.zeros((size, size), np.float32)
    Y, X = np.mgrid[0:size, 0:size].astype(np.float32)
    rad, ln = 15 * k, 40 * k
    py = np.clip(Y, c, c + ln)
    dx, dy = X - c, Y - py
    v = np.hypot(dx, dy) / rad
    nz = np.sqrt(np.clip(1 - v * v, 0, 1))
    pal = dict(dark=tuple(int(x * 0.9) for x in st["dark"]), mid=st["mid"], light=st["light"], rim=st["rim"])
    arm = shade(dx / rad, dy / rad, nz, pal["dark"], pal["mid"], pal["light"], pal["rim"], spec=0.35, rim=0.3)
    aa = np.clip((1 - v) * rad * 0.9, 0, 1).astype(np.float32)
    rgb, al = over(rgb, al, arm.astype(np.float32), aa)
    glove = dict(dark=(214, 172, 160), mid=(255, 238, 226), light=(255, 253, 248), rim=(255, 220, 200))
    # большой пальчик и «варежка»
    tr, ta, _, _ = ellipsoid(size, size, c - 18 * k, c + ln + 2 * k, 10 * k, 11 * k, glove, spec=0.3)
    rgb, al = over(rgb, al, tr, ta)
    hr_, ha_, _, _ = ellipsoid(size, size, c, c + ln + 10 * k, 24 * k, 22 * k, glove, spec=0.4, rim=0.3)
    rgb, al = over(rgb, al, hr_, ha_)
    base = to_pil(rgb, al)
    right, left = [], []
    for ang in range(0, 181, 6):
        im = base.rotate(ang, resample=Image.BICUBIC, center=(c, c))
        im = im.resize((int(2 * ARM_L * MS), int(2 * ARM_L * MS)), Image.LANCZOS)
        r_, a_ = soften(im, 0.45)
        right.append((r_, a_))
        left.append((r_[:, ::-1].copy(), a_[:, ::-1].copy()))
    return right, left


# --- фоны глав --------------------------------------------------------------
def soft_disc(r, power=0.7):
    n = int(r * 2 + 4)
    yy, xx = np.mgrid[0:n, 0:n].astype(np.float32)
    d = np.hypot(xx - n / 2, yy - n / 2) / r
    return (np.clip(1 - d ** 2, 0, 1) ** power).astype(np.float32)


def make_bg_assets():
    A = {}
    # пергамент + армянские буквы
    g = (np.arange(H, dtype=np.float32) / H)[:, None, None]
    base = arr((248, 238, 214)) * (1 - g) + arr((230, 204, 170)) * g
    base = np.repeat(base, W, axis=1)
    v = np.hypot((XX - W / 2) / (W * 0.62), (YY - H / 2) / (H * 0.7))
    base = base * (1 - 0.20 * np.clip(v, 0, 1.4) ** 2)[..., None]
    m = Image.new("L", (W, H), 0)
    dm = ImageDraw.Draw(m)
    dm.rounded_rectangle([26, 26, W - 26, H - 26], radius=34, outline=150, width=3)
    dm.rounded_rectangle([42, 42, W - 42, H - 42], radius=26, outline=90, width=2)
    mm = (np.asarray(m.filter(ImageFilter.GaussianBlur(0.8)), np.float32) / 255.0)[..., None]
    A["parch"] = base * (1 - mm) + arr((170, 120, 90)) * mm
    rr = np.random.default_rng(31)
    letters = []
    for ch in "ԱԲԳԴԵԶԷԹԺԻԼԽ":
        size = int(rr.integers(150, 240))
        f = ImageFont.truetype(FONTB, size)
        im = Image.new("L", (size + 40, int(size * 1.5)), 0)
        ImageDraw.Draw(im).text((20, 10), ch, font=f, fill=255)
        a = np.asarray(im.filter(ImageFilter.GaussianBlur(1.2)), np.float32) / 255.0 * 0.085
        letters.append(dict(a=a, x=float(rr.uniform(-60, W - 100)), y=float(rr.uniform(0, H + 200)),
                            sp=float(rr.uniform(6, 14)), sw=float(rr.uniform(8, 24)), ph=float(rr.uniform(0, 6.28))))
    A["letters"] = letters
    # театр: занавес + прожектор
    x = XX[0:1, :]
    fold = 0.5 + 0.5 * np.sin(x * 0.05 + 1.4 * np.sin(x * 0.011))
    cur = arr((92, 44, 78)) * (0.62 + 0.38 * fold[..., None])
    cur = np.repeat(cur, H, axis=0)
    cur = cur * (1 - 0.28 * np.clip(YY / H, 0, 1) ** 2)[..., None]
    floor = (YY > 610)[..., None].astype(np.float32)
    wood = arr((74, 40, 62)) * (0.8 + 0.2 * np.sin(XX * 0.03)[..., None])
    A["theater_base"] = (cur * (1 - floor) + wood * floor).astype(np.float32)
    cone = np.exp(-(((XX - 700) / (110 + 0.5 * YY)) ** 2)) * (1 - np.clip(YY / 760.0, 0, 1)) ** 0.5
    A["theater_cone"] = (cone[..., None] * arr((255, 232, 196)) * 0.55).astype(np.float32)
    A["dust"] = soft_disc(3, 1.0) * 0.6
    A["dust_p"] = [dict(x=float(rr.uniform(430, 980)), y=float(rr.uniform(0, H)), sp=float(rr.uniform(6, 18)),
                        sw=float(rr.uniform(6, 20)), ph=float(rr.uniform(0, 6.28))) for _ in range(12)]
    # тёплые лучи и искорки (глава «Связка»)
    top, bot = arr((255, 230, 208)), arr((244, 168, 176))
    b_ = np.repeat(top * (1 - g) + bot * g, W, axis=1)
    A["light_base"] = b_.astype(np.float32)

    def star(r):
        n = int(r * 2 + 4)
        yy, xx = np.mgrid[0:n, 0:n].astype(np.float32)
        x, y = (xx - n / 2) / r, (yy - n / 2) / r
        return (np.exp(-np.abs(x) * np.abs(y) * 22) * np.exp(-(x * x + y * y) * 1.6)).astype(np.float32)
    A["stars"] = [star(r) for r in (10, 16, 24)]
    A["star_p"] = [dict(k=int(rr.integers(0, 3)), x=float(rr.uniform(0, W)), y=float(rr.uniform(0, H)),
                        sp=float(rr.uniform(4, 12)), ph=float(rr.uniform(0, 6.28)), tw=float(rr.uniform(0.8, 2.2)))
                   for _ in range(22)]
    return A


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
# ГАЛЕРЕЯ: ваши фото/кадры (папка assets рядом со скриптом или HAYEREN_ASSETS)
# --------------------------------------------------------------------------
def load_gallery():
    d = os.environ.get("HAYEREN_ASSETS", os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets"))
    if not os.path.isdir(d):
        return [], None
    ww, hh = FILM_W - 44, FILM_H - 72
    mask = Image.new("L", (ww, hh), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, ww - 1, hh - 1], radius=12, fill=255)
    mask = np.asarray(mask.filter(ImageFilter.GaussianBlur(0.8)), np.float32) / 255.0
    out = []
    for fn in sorted(os.listdir(d)):
        if fn.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
            im = Image.open(os.path.join(d, fn)).convert("RGB")
            sc = max(ww * 1.18 / im.width, hh * 1.18 / im.height)
            im = im.resize((int(im.width * sc), int(im.height * sc)), Image.LANCZOS)
            out.append(np.asarray(im, np.float32))
    return out, mask


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
                y = tts_piper.soften(tts_piper.synth(text, lang, 1.14 / SPEED))
            else:  # запасной синтетический голос
                x = tts_espeak.synth(text, ui["voice"], min(int(ui["wpm"] * SPEED), 340), ui["pitch"])
                y = tts_espeak.soften(x)
        segs.append((ch, text, y))
    t = 1.2 if SHORT else 1.8
    starts, prev = [], None
    for ch, text, y in segs:
        if prev is not None:
            t += (0.7 if ch != prev else 0.28) if SHORT else (1.1 if ch != prev else 0.45)
        starts.append(t)
        t += len(y) / tts_espeak.SR
        prev = ch
    dur = t + (2.2 if SHORT else 3.2)
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
    wf_, tf_ = fnt(84, True), fnt(38)
    spec = [("Ծիրան", wf_, (96, 58, 100, 255), 112), (ui["translit"], tf_, (166, 98, 84, 255), 48)]
    (wrgb, wa), (pd, h) = text_card(spec, 330, pad=24, radius=34, fill=170)
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
    for j, (g, snd) in enumerate(zip(["Ծ", "ի", "ր", "ա", "ն"], ui["sounds"])):
        bg, p = pill((112, 140), 24, 225, blur=2, pad=8)
        t = Image.new("RGBA", bg.size, (0, 0, 0, 0))
        dd = ImageDraw.Draw(t)
        f = fnt(64, True)
        w = dd.textlength(g, font=f)
        dd.text(((bg.size[0] - w) / 2, p + 14), g, font=f, fill=(96, 58, 100, 255))
        f2 = fnt(26)
        w2 = dd.textlength(snd, font=f2)
        dd.text(((bg.size[0] - w2) / 2, p + 100), snd, font=f2, fill=(166, 98, 84, 255))
        rgb, a = to_np(Image.alpha_composite(bg, t))
        bubbles.append(dict(rgb=rgb, a=a, x=400 + j * 136, y=46 - p + 0))

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
    faces = {(lv, e): make_face(lv, e, MASCOT) for lv in range(12) for e in range(3)}
    arms_r, arms_l = make_arm_variants(MASCOT)
    assets = make_bg_assets()
    # реквизит
    head = make_head_sprite(MASCOT)
    tree = sprite(200, 250, d_tree, 1.0)
    film_base = sprite(FILM_W, FILM_H, d_film, 1.0)
    poet = sprite(FILM_W, FILM_H, d_poet, 0.9)
    seed = make_aril()
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

    notes = []
    for ch_ in ("♪", "♫"):
        im_ = Image.new("RGBA", (60, 68), (0, 0, 0, 0))
        ImageDraw.Draw(im_).text((6, 2), ch_, font=ImageFont.truetype(FONTB, 50), fill=(110, 60, 100, 255))
        notes.append(soften(im_, 0.5))
    clouds = [(make_cloud(s), y, sp, x0) for s, y, sp, x0 in
              ((1, 70, 7.0, 100), (2, 150, 5.0, 520), (3, 230, 9.0, 900), (4, 110, 4.0, 1200), (5, 40, 6.0, -100))]
    petal_rot = [make_petal(a) for a in (0, 45, 90, 135)]
    petals = [dict(x=float(RNG.uniform(0, W + 60)), y=float(RNG.uniform(0, H + 60)),
                   vx=float(RNG.uniform(14, 30)), vy=float(RNG.uniform(18, 38)),
                   ph=float(RNG.uniform(0, 6.28)), am=float(RNG.uniform(14, 34)),
                   a=float(RNG.uniform(0.5, 0.85))) for _ in range(24)]
    seeds = [dict(x=float(RNG.uniform(-60, 60)), ph=float(RNG.uniform(0, 1)), sp=float(RNG.uniform(0.10, 0.2)),
                  dx=float(RNG.uniform(-260, 120)), am=float(RNG.uniform(10, 30))) for _ in range(26)]

    gallery, gmask = load_gallery()
    slog_i = next(i for i, (ch, _, _) in enumerate(segs) if ch == 5)
    btn_i = len(segs) - 1
    speak_s = np.convolve(mouth / 11.0, np.ones(7) / 7, mode="same")
    G.update(dict(notes=notes, gallery=gallery, gmask=gmask, slog_i=slog_i, btn_i=btn_i, speak_s=speak_s, arms_r=arms_r, arms_l=arms_l, assets=assets))
    G.update(dict(lang=lang, ui=ui, dur=dur, N=n, SC=SC, subs=subs, wordcard=wordcard, chips=chips, bubbles=bubbles,
                  film=(film_rgb, film_a, fw_, fp_), fest=(fest_rgb, fest_a, fsw_, fsp_), slogan=slogan, button=button,
                  faces=faces, head=head, tree=tree, film_base=film_base, poet=poet, seed=seed, garland=garland,
                  stain_T=stain_T, stain_R=stain_R, clouds=clouds, petal_rot=petal_rot, petals=petals, seeds=seeds, mouth=mouth,
                  rms=rms, starts=starts, segs_dur=[len(y) / tts_espeak.SR for _, _, y in segs], stereo=stereo))


# --------------------------------------------------------------------------
# КАДР
# --------------------------------------------------------------------------
BG_KIND = ["mountain", "parchment", "theater", "light", "mountain", "mountain"]
PANS = {0: (-0.9, -0.1), 4: (0.9, 0.1), 5: (0.0, 0.5)}  # «камера»: панорама по ходу главы
RANGES = dict(far=60, ararat=90, mid=120, near=140, fg=150)
CW = 0.7  # длительность перекрёстного перехода фонов


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
    shift = float(np.clip(shift, 1.0, 298.5))
    o = int(shift)
    f = shift - o
    a = (mask[:, o:o + W] * (1 - f) + mask[:, o + 1:o + 1 + W] * f)[..., None]
    img[:] = img * (1 - a) + color * a


def scene_vis(sc, t, fin=1.2, fout=1.0):
    return float(ss((t - sc["t0"] - 0.2) / fin) * ss((sc["t1"] - t) / fout))


def bg_mountain(si, t):
    SC = G["SC"]
    sc = SC[si]
    p = PAL[sc["pal"]]
    top, bot = p["top"], p["bot"]
    prog = float(np.clip((t - sc["t0"]) / max(sc["t1"] - sc["t0"], 1e-3), 0, 1))
    a0, a1 = PANS.get(si, (0.0, 0.0))
    pan = a0 + (a1 - a0) * prog
    sh = lambda r: 150 + r * pan
    img = np.repeat(top * (1 - GRAD) + bot * GRAD, W, axis=1).astype(np.float32)
    sx, sy_ = p["sun"][0] + 20 * math.sin(t / 9.0) - 30 * pan, p["sun"][1]
    d2 = (XX - sx) ** 2 + (YY - sy_) ** 2
    glow = np.clip(0.55 * np.exp(-d2 / (2 * 200 ** 2)) + 0.95 * np.exp(-d2 / (2 * 36 ** 2)), 0, 1)[..., None]
    img = img * (1 - glow * 0.75) + p["suncol"] * glow * 0.75
    hz = lambda base, k: mix(arr(base), bot, k)
    layer(img, M_FAR, hz((176, 176, 212), 0.45), sh(RANGES["far"]))
    layer(img, M_ARARAT, hz((142, 146, 192), 0.30), sh(RANGES["ararat"]))
    layer(img, M_SHADE * 0.30, hz((92, 96, 150), 0.25), sh(RANGES["ararat"]))
    layer(img, M_SNOW, mix(arr((255, 252, 255)), bot, 0.18), sh(RANGES["ararat"]))
    cc = mix(arr((255, 255, 255)), bot, 0.22)
    for spr, cy, sp, x0 in G["clouds"]:
        cx = int((x0 + sp * t + 300) % (W + 700) - 440)
        blit(img, cc, spr, cx, cy + int(4 * math.sin(t / 5 + cy)))
    mist = MIST[..., None]
    img = img * (1 - mist) + mix(arr((255, 255, 255)), bot, 0.5) * mist
    layer(img, M_MID, hz((150, 184, 170), 0.30), sh(RANGES["mid"]))
    layer(img, M_NEAR, hz((186, 192, 130), 0.14), sh(RANGES["near"]))
    if si == 0:  # гранатовые деревья
        rgb, a = G["tree"]
        for j, (x, y) in enumerate(((20, 372), (230, 392), (440, 366))):
            blit(img, rgb, a, int(x - pan * 70 + 3 * math.sin(t * 0.7 + j)), y)
    layer(img, M_FG, hz((156, 176, 114), 0.06), sh(RANGES["fg"]))
    if si == 4:  # праздничная гирлянда и фонари
        rgb, a = G["garland"]
        blit(img, rgb, a, int(500 + 5 * math.sin(t * 0.8)), 0)
        frgb, fa, fw_, fp_ = G["fest"]
        blit(img, frgb, fa, 560 - fp_, 200, float(ss((t - sc["t0"] - 1.0) / 1.0)))
    return img


def bg_parchment(t):
    A = G["assets"]
    img = A["parch"].copy()
    for L in A["letters"]:
        y = (L["y"] - L["sp"] * t) % (H + 320) - 160
        blit(img, arr((110, 60, 100)), L["a"], int(L["x"] + L["sw"] * math.sin(t * 0.4 + L["ph"])), int(y))
    return img


def bg_theater(t):
    A = G["assets"]
    img = A["theater_base"] + A["theater_cone"] * (0.94 + 0.06 * math.sin(t * 6.3))
    for d in A["dust_p"]:
        y = (d["y"] - d["sp"] * t) % (H + 40) - 20
        blit(img, arr((255, 240, 210)), A["dust"], int(d["x"] + d["sw"] * math.sin(t * 0.6 + d["ph"])), int(y),
             0.7 + 0.3 * math.sin(t * 2 + d["ph"]))
    return img


def bg_light(t):
    A = G["assets"]
    img = A["light_base"].copy()
    u = XX * 0.62 + YY * 0.78
    beams = np.zeros((H, W), np.float32)
    for c0, wd, sp in ((300, 70, 18), (640, 110, -14), (980, 80, 22), (1300, 120, -10)):
        beams += np.exp(-(((u - c0 - sp * t) % 1500 - 750 + 750 - 750) / wd) ** 2)
    img = img + beams[..., None] * arr((255, 240, 210)) * 0.10
    for st_ in A["star_p"]:
        spr = A["stars"][st_["k"]]
        y = (st_["y"] - st_["sp"] * t) % (H + 60) - 30
        tw = 0.5 + 0.5 * math.sin(t * st_["tw"] + st_["ph"])
        blit(img, arr((255, 246, 224)), spr, int(st_["x"] - spr.shape[1] / 2), int(y - spr.shape[0] / 2), 0.25 + 0.75 * tw)
    return img


def render_bg(i, t):
    k = BG_KIND[i]
    return bg_mountain(i, t) if k == "mountain" else {"parchment": bg_parchment, "theater": bg_theater,
                                                      "light": bg_light}[k](t)


def bg_at(t):
    SC = G["SC"]
    i = next((k for k, s in enumerate(SC) if s["t0"] <= t < s["t1"]), len(SC) - 1)
    if i < len(SC) - 1 and t > SC[i]["t1"] - CW:
        s_ = float(ss((t - (SC[i]["t1"] - CW)) / (2 * CW)))
        return mix(render_bg(i, t), render_bg(i + 1, t), s_)
    if i > 0 and t < SC[i]["t0"] + CW:
        s_ = float(ss((t - (SC[i]["t0"] - CW)) / (2 * CW)))
        return mix(render_bg(i - 1, t), render_bg(i, t), s_)
    return render_bg(i, t)


# --- маскот: перемещение и жесты --------------------------------------------
def win(t, a, b, r=0.35):
    return float(ss((t - a) / r) * ss((b - t) / r))


def mascot_x(t):
    SC = G["SC"]
    kf = [(0.0, 1500), (2.2, 1050), (SC[1]["t0"] + 0.3, 1050), (SC[1]["t0"] + 2.6, 910),
          (SC[2]["t0"] + 0.2, 910), (SC[2]["t0"] + 2.4, 1130), (SC[3]["t0"] + 0.3, 1130),
          (SC[3]["t0"] + 2.6, 920), (SC[4]["t0"] + 0.5, 920), (SC[4]["t0"] + 1.6, 1010)]
    t4 = SC[4]["t0"] + 1.6
    if t < t4:
        for (ta, xa), (tb, xb) in zip(kf, kf[1:]):
            if t <= tb:
                return xa + (xb - xa) * float(ss((t - ta) / max(tb - ta, 1e-6)))
        return kf[-1][1]
    dance = lambda tt: 1010 + 125 * math.sin(2 * math.pi * (tt - t4) / 5.5)
    t5 = SC[5]["t0"]
    if t < t5:
        return dance(t)
    return mix(dance(t5), 1020.0, float(ss((t - t5) / 1.4)))


def mascot_arms(t, speak):
    SC, st, sd = G["SC"], G["starts"], G["segs_dur"]
    sl, bt = G["slog_i"], G["btn_i"]
    sp = 2 * math.pi
    L = 20 + 6 * math.sin(sp * 0.45 * t + 1) + 24 * speak * math.sin(sp * 1.4 * t)
    R = 20 + 6 * math.sin(sp * 0.45 * t) + 20 * speak * math.sin(sp * 1.1 * t + 1.3)
    w = win(t, 1.0, 4.4)  # приветствие
    R += w * (138 + 30 * math.sin(sp * 2.6 * t) - R)
    w = win(t, SC[1]["t0"] + 1.3, SC[1]["t0"] + 5.8)  # указывает на буквы
    L += w * (100 + 6 * math.sin(sp * 1.2 * t) - L)
    w = win(t, SC[2]["t0"] + 0.6, SC[2]["t1"] - 0.6)  # указывает на плёнку
    L += w * (88 + 7 * math.sin(sp * 1.2 * t) - L)
    w = win(t, SC[4]["t0"] + 0.6, SC[5]["t0"])  # танец
    L += w * (95 + 45 * math.sin(sp * 1.3 * t) - L)
    R += w * (95 + 45 * math.sin(sp * 1.3 * t + math.pi) - R)
    w = win(t, st[sl] - 0.1, st[sl] + sd[sl] + 0.3)  # ликует на слогане
    L += w * (150 + 20 * math.sin(sp * 2.2 * t) - L)
    R += w * (150 + 20 * math.sin(sp * 2.2 * t + 0.8) - R)
    w = win(t, st[bt] - 0.1, st[bt] + sd[bt] - 0.8)  # зовёт подписаться
    R += w * (138 + 30 * math.sin(sp * 2.6 * t) - R)
    L += w * (98 - L)
    return float(np.clip(L, 0, 180)), float(np.clip(R, 0, 180))


def draw_mascot(img, t, i):
    SC = G["SC"]
    speak = float(G["speak_s"][min(i, G["N"] - 1)])
    x = mascot_x(t)
    vx = abs(mascot_x(t + 0.05) - mascot_x(t - 0.05)) / 0.1
    dancing = SC[4]["t0"] + 1.6 < t < SC[5]["t0"]
    amp = (20 if dancing else min(vx / 40.0, 1.0) * 20) + 5 * speak + 2
    hop = amp * abs(math.sin(2 * math.pi * 1.15 * t))
    hv = float(ss(t / 0.5))
    hw, hh = int(HEAD_W * MS), int(HEAD_H * MS)
    hx, hy = int(x - hw / 2), int(700 - hh - hop)
    hrgb, ha = G["head"]
    blit(img, hrgb, ha, hx, hy, hv)
    lvl = int(G["mouth"][min(i, G["N"] - 1)])
    eyes = 1 if ((t % 3.6) < 0.14 and t > 0.8) else 0
    sl = G["slog_i"]
    if G["starts"][sl] + 0.5 < t < G["starts"][sl] + 1.3:
        eyes = 2
    frgb, fa = G["faces"][(lvl, eyes)]
    blit(img, frgb, fa, hx + int(FACE_X * MS), hy + int((FACE_Y + 1.5 * speak) * MS), hv)
    aL, aR = mascot_arms(t, speak)
    rgbL, aLa = G["arms_l"][int(round(aL / 6))]
    rgbR, aRa = G["arms_r"][int(round(aR / 6))]
    half = int(ARM_L * MS)
    blit(img, rgbL, aLa, hx + int(62 * MS) - half, hy + int(258 * MS) - half, hv)
    blit(img, rgbR, aRa, hx + int(298 * MS) - half, hy + int(258 * MS) - half, hv)
    return hx, hy, hw


def frame(i):
    t = i / FPS
    SC = G["SC"]
    DUR = G["dur"]
    cur = next((k for k, s in enumerate(SC) if s["t0"] <= t < s["t1"]), 5)
    img = bg_at(t).astype(np.float32)

    # --- реквизит глав
    v1 = scene_vis(SC[1], t)
    if v1 > 0.002:  # буквы-пузыри
        for j, b in enumerate(G["bubbles"]):
            k = float(ss((t - SC[1]["t0"] - 0.7 - j * 0.45) / 0.5)) * v1
            if k > 0.002:
                blit(img, b["rgb"], b["a"], b["x"], int(b["y"] + (1 - k) * 22 + 6 * math.sin(t * 1.3 + j)), k)
    v2 = scene_vis(SC[2], t)
    if v2 > 0.002:  # плёнка
        fx, fy = 470, 100
        rgb, a = G["film_base"]
        blit(img, rgb, a, fx, fy, v2)
        if G["gallery"]:  # ваши фото и кадры: плавная смена с лёгким «Кеном Бёрнсом»
            gl, ww, hh = G["gallery"], FILM_W - 44, FILM_H - 72
            n = len(gl)
            ta, tb = SC[2]["t0"] + 0.4, SC[2]["t1"] - 0.4
            pos = float(np.clip((t - ta) / (tb - ta), 0, 0.9999)) * n
            i0 = int(pos)
            f_ = pos - i0

            def crop(ix, ff):
                im = gl[ix]
                ox = int((im.shape[1] - ww) * (ff if ix % 2 == 0 else 1 - ff))
                oy = int((im.shape[0] - hh) * 0.5)
                return im[oy:oy + hh, ox:ox + ww]
            cur_ = crop(i0, f_)
            if i0 < n - 1:
                cur_ = mix(cur_, crop(i0 + 1, 0.0), float(ss((f_ - 0.82) / 0.18)))
            blit(img, cur_, G["gmask"], fx + 22, fy + 36, v2)
        else:  # иллюстрация по умолчанию: дудук и поднимающиеся ноты
            rgb, a = G["poet"]
            blit(img, rgb, a, fx, fy + int(3 * math.sin(t * 1.6)), v2)
            for j in range(7):
                u = (t * 0.32 + j / 7.0) % 1.0
                nx_ = fx + 150 + 230 * u + 14 * math.sin(u * 9 + j)
                ny_ = fy + 190 - 150 * u + 10 * math.sin(t * 2 + j)
                nrgb, na = G["notes"][j % 2]
                blit(img, nrgb, na, int(nx_), int(ny_), v2 * math.sin(math.pi * u) ** 0.7)
        frgb, fa, fw_, fp_ = G["film"]
        blit(img, frgb, fa, fx + (FILM_W - fw_) // 2 - fp_, fy + FILM_H + 6, v2)

    # --- маскот
    hx, hy, hw = draw_mascot(img, t, i)

    # семена из граната (главы 4–5)
    for ch in (3, 4):
        vv = scene_vis(SC[ch], t, fin=1.5, fout=1.5)
        if vv > 0.002:
            rgb, a = G["seed"]
            for s in G["seeds"][: (18 if ch == 3 else 10)]:
                u = (t * s["sp"] + s["ph"]) % 1.0
                sxp = hx + hw / 2 + s["x"] + s["dx"] * u + s["am"] * math.sin(u * 9 + s["ph"] * 6)
                syp = hy + 40 - u * 380
                blit(img, rgb, a, int(sxp), int(syp), vv * math.sin(math.pi * u) ** 0.6)

    # --- слоган и кнопка
    sg = G["slogan"]
    k5 = float(ss((t - G["starts"][G["slog_i"]] + 0.2) / 0.9)) * float(ss((DUR - 1.4 - t) / 1.0))
    if k5 > 0.002:
        blit(img, sg["rgb"], sg["a"], sg["x"], int(sg["y"] + (1 - k5) * 14), k5)
    kb = float(ss((t - G["starts"][G["btn_i"]] + 0.3) / 0.8)) * float(ss((DUR - 1.4 - t) / 1.0))
    if kb > 0.002:
        bt = G["button"]
        pulse = 1 + 0.03 * math.sin(t * 5)
        blit(img, bt["rgb"], bt["a"], bt["x"], int(bt["y"] + 3 * math.sin(t * 5)), kb * min(1.0, pulse))

    # --- плашка слова и глава
    if cur in (1, 2, 3, 4):
        wk = float(ss((t - SC[1]["t0"] - 0.8) / 0.9)) * float(ss((SC[4]["t1"] - 0.2 - t) / 0.8))
        wc = G["wordcard"]
        blit(img, wc["rgb"], wc["a"], wc["x"], wc["y"] + int((1 - wk) * 10), wk)
    chip = G["chips"][cur]
    ck = float(ss((t - SC[cur]["t0"] - 0.3) / 0.7)) * float(ss((SC[cur]["t1"] - 0.1 - t) / 0.6)) if cur < 5 \
        else float(ss((t - SC[cur]["t0"] - 0.3) / 0.7)) * float(ss((DUR - 1.6 - t) / 0.8))
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

    f = float(ss(t / 1.0) * ss((DUR - t) / 1.6))
    img = mix(arr((252, 246, 246)), img, f)
    img += NOISE
    return np.clip(img, 0, 255).astype(np.uint8).tobytes()


def main():
    args = [x for x in sys.argv[1:] if not x.startswith('--')]
    lang, out, work = args[0], args[1], args[2]
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

"""Нейросетевой голос (Piper). Модели: см. ../../voices.sh

Каталог с моделями задаётся переменной HAYEREN_VOICES (по умолчанию ./voices).
Голоса по умолчанию — мужские: ru_RU-denis-medium, es_MX-claude-high.
Другой голос: HAYEREN_VOICE_RU=ru_RU-dmitri-medium, HAYEREN_VOICE_ES=es_ES-davefx-medium.
"""
import os
import numpy as np

SR = 22050
DEFAULT = {"ru": "ru_RU-denis-medium", "es": "es_MX-claude-high"}
_cache = {}


def model_path(lang):
    d = os.environ.get("HAYEREN_VOICES", "voices")
    name = os.environ.get(f"HAYEREN_VOICE_{lang.upper()}", DEFAULT[lang])
    return os.path.join(d, name + ".onnx")


def available(lang):
    return os.path.exists(model_path(lang))


def synth(text, lang, length_scale=1.14):
    """length_scale > 1 — медленнее и плавнее; noise_* ниже — ровнее интонация."""
    from piper import PiperVoice, SynthesisConfig
    p = model_path(lang)
    if p not in _cache:
        _cache[p] = PiperVoice.load(p)
    v = _cache[p]
    assert v.config.sample_rate == SR, "ожидается 22050 Гц"
    cfg = SynthesisConfig(length_scale=length_scale, noise_scale=0.45, noise_w_scale=0.55)
    x = np.concatenate([c.audio_float_array for c in v.synthesize(text, cfg)]).astype(np.float32)
    return x


def soften(x, sr=SR):
    """Лёгкая «шёлковость»: мягкий срез верхов, тепло на низах, короткий реверб, плавные края."""
    n = len(x)
    size = 1 << int(np.ceil(np.log2(n + 1)))
    X = np.fft.rfft(x, size)
    f = np.fft.rfftfreq(size, 1 / sr)
    g = 1.0 / np.sqrt(1 + (f / 7500.0) ** 4)
    g *= 1 + 0.18 * np.exp(-((f - 180.0) / 130.0) ** 2)
    y = np.fft.irfft(X * g, size)[:n]
    rr = np.random.default_rng(11)
    li = int(0.5 * sr)
    ir = rr.standard_normal(li) * np.exp(-np.arange(li) / (0.11 * sr))
    ir[0] = 0
    sz = 1 << int(np.ceil(np.log2(n + li)))
    wet = np.fft.irfft(np.fft.rfft(y, sz) * np.fft.rfft(ir, sz), sz)[:n]
    wet *= 0.09 * np.abs(y).max() / (np.abs(wet).max() + 1e-9)
    y = y + wet
    k = int(0.02 * sr)
    y[:k] *= np.linspace(0, 1, k)
    y[-k:] *= np.linspace(1, 0, k)
    return (y / (np.abs(y).max() + 1e-9) * 0.9).astype(np.float32)

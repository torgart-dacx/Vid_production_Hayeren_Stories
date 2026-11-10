"""Локальный синтез речи через eSpeak NG (ctypes) + «смягчающая» обработка.

Это запасной голос: нейросетевые модели (Piper и т.п.) в окружении недоступны.
Любой синтезированный WAV можно заменить на запись настоящего диктора —
тайминги видео считаются по длине аудио автоматически.
"""
import ctypes
import numpy as np
import espeakng_loader

_lib = None
_buf = []
CB = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.POINTER(ctypes.c_short), ctypes.c_int, ctypes.c_void_p)


def _cb(wav, n, ev):
    if wav and n > 0:
        _buf.append(np.ctypeslib.as_array(wav, shape=(n,)).copy())
    return 0


_cb_c = CB(_cb)
SR = 22050


def _init():
    global _lib
    if _lib is None:
        _lib = ctypes.CDLL(espeakng_loader.get_library_path())
        _lib.espeak_Initialize.restype = ctypes.c_int
        sr = _lib.espeak_Initialize(1, 0, espeakng_loader.get_data_path().encode(), 0)
        assert sr > 0, "espeak init failed"
        _lib.espeak_SetSynthCallback(_cb_c)
    return _lib


def synth(text, voice="ru", wpm=118, pitch=28, rng=30):
    lib = _init()
    _buf.clear()
    assert lib.espeak_SetVoiceByName(voice.encode()) == 0, voice
    lib.espeak_SetParameter(1, wpm, 0)    # rate
    lib.espeak_SetParameter(3, pitch, 0)  # pitch
    lib.espeak_SetParameter(4, rng, 0)    # pitch range (меньше = ровнее)
    b = text.encode("utf-8")
    lib.espeak_Synth(b, len(b) + 1, 0, 0, 0, 1, None, None)
    lib.espeak_Synchronize()
    x = np.concatenate(_buf).astype(np.float32) / 32768.0 if _buf else np.zeros(1, np.float32)
    return x


def soften(x, sr=SR):
    """Делает голос теплее и глаже: срез верхов, лёгкий «корпус» и короткий реверб."""
    n = len(x)
    X = np.fft.rfft(x, 1 << int(np.ceil(np.log2(n * 1.0 + 1))))
    f = np.fft.rfftfreq((len(X) - 1) * 2, 1 / sr)
    g = 1.0 / np.sqrt(1 + (f / 3600.0) ** 4)               # ФНЧ ~3.6 кГц
    g *= 1 + 0.55 * np.exp(-((f - 190.0) / 120.0) ** 2)    # тепло на ~190 Гц
    g *= 1 + 0.25 * np.exp(-((f - 420.0) / 200.0) ** 2)
    y = np.fft.irfft(X * g)[:n]
    # мягкая компрессия/сатурация
    y = np.tanh(1.6 * y) / np.tanh(1.6)
    # короткий реверб
    rr = np.random.default_rng(11)
    li = int(0.55 * sr)
    ir = rr.standard_normal(li) * np.exp(-np.arange(li) / (0.12 * sr))
    ir[0] = 0
    size = 1 << int(np.ceil(np.log2(n + li)))
    wet = np.fft.irfft(np.fft.rfft(y, size) * np.fft.rfft(ir, size), size)[:n]
    wet *= 0.16 * np.abs(y).max() / (np.abs(wet).max() + 1e-9)
    y = y + np.concatenate([wet, np.zeros(0)])
    return (y / (np.abs(y).max() + 1e-9) * 0.9).astype(np.float32)

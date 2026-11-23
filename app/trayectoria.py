# -*- coding: utf-8 -*-
"""Recorrido estimado de un video DJI cuyo GPS viene redondeado a 4 decimales (celdas de unos 11 m).
Busca la trayectoria suave que respeta la celda grabada, la distancia al despegue y la velocidad. Es una ESTIMACION."""
import numpy as np
CELDA = 5e-5

def _tramo(t):
    from scipy.optimize import least_squares
    n = len(t); la0, lo0 = t[:, 1].mean(), t[:, 2].mean()
    kx, ky = 111320 * np.cos(np.radians(la0)), 110574
    X = np.c_[(t[:, 2] - lo0) * kx, (t[:, 1] - la0) * ky]; H = np.array([CELDA * kx, CELDA * ky])
    w = min(9, (n - 1) // 2 * 2 - 1); P0 = X
    if w >= 3:
        P0 = np.c_[tuple(np.convolve(np.pad(X[:, i], w // 2, "edge"), np.ones(w) / w, "valid") for i in (0, 1))]
    dt = np.diff(t[:, 0])[:, None]; vm = (t[1:, 4] + t[:-1, 4]) / 2
    def f(z):
        P, h = z[:2 * n].reshape(n, 2), z[2 * n:]; V = np.diff(P, axis=0) / dt
        return np.concatenate([(np.maximum(np.abs(P - X) - H, 0) / .3).ravel(), (np.diff(V, axis=0) / .3).ravel(),
                               (np.sqrt((V ** 2).sum(1) + 1e-4) - vm) / .3, (P - X).ravel() / 60, (np.sqrt(((P - h) ** 2).sum(1) + 1e-6) - t[:, 3]) / .3])
    o = least_squares(f, np.r_[P0.ravel(), P0[np.argmin(t[:, 3])]], max_nfev=60)
    P, h = o.x[:2 * n].reshape(n, 2), o.x[2 * n:]
    # si el ajuste no explica los datos no se usa
    if np.percentile(np.abs(np.hypot(*(P - h).T) - t[:, 3]), 95) > 1 or np.maximum(np.abs(P - X) - H, 0).max() > 2: return None
    return np.c_[la0 + P[:, 1] / ky, lo0 + P[:, 0] / kx]

def estimar(tel):
    """tel: [{s, lat, lon, casa, vel}] en orden. Devuelve [(lat, lon)] o None si no es confiable."""
    t = np.array([[p["s"], p["lat"], p["lon"], p["casa"], p["vel"]] for p in tel], float)
    if len(t) < 5 or (np.diff(t[:, 0]) <= 0).any(): return None
    if t[:, 4].max() < .2: return [(float(np.median(t[:, 1])), float(np.median(t[:, 2])))] * len(t)
    out, k = [], max(1, round(len(t) / 180))
    for parte in np.array_split(t, k):
        r = _tramo(parte) if len(parte) >= 5 else None
        if r is None: return None
        out += [(float(a), float(b)) for a, b in r]
    return out

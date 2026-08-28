import time

_hits = {}


def allow(key, min_interval=25, max_per_window=5, window=900):
    now = time.time()
    bucket = _hits.setdefault(key, [])
    bucket[:] = [ts for ts in bucket if now - ts < window]
    if bucket and now - bucket[-1] < min_interval:
        wait = int(min_interval - (now - bucket[-1])) + 1
        return False, f"Patientez {wait} s avant de renvoyer un code."
    if len(bucket) >= max_per_window:
        return False, "Trop de demandes. Réessayez dans quelques minutes."
    bucket.append(now)
    return True, None

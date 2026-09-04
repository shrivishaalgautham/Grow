SESSION_MINUTES = 375
MIN_ELAPSED_FRACTION = 0.05
APPROXIMATE_BEFORE_MINUTES = 45


def relative_volume(
    volume_today: float, avg_volume_20d: float, minutes_since_open: int | None
) -> tuple[float, bool]:
    if avg_volume_20d <= 0:
        return 0.0, False
    if minutes_since_open is None:
        return volume_today / avg_volume_20d, False
    elapsed = min(max(minutes_since_open / SESSION_MINUTES, MIN_ELAPSED_FRACTION), 1.0)
    rvol = volume_today / (avg_volume_20d * elapsed)
    return rvol, minutes_since_open < APPROXIMATE_BEFORE_MINUTES

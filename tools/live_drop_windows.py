"""Respect drop-frame availability without changing reward amounts or past inventory."""
from datetime import datetime, timezone


def frame_active(frame, now):
    def instant(value):
        if not value:
            return None
        result = datetime.fromisoformat(value.replace('Z', '+00:00'))
        return result if result.tzinfo else result.replace(tzinfo=timezone.utc)
    try:
        start, end = instant(frame.start_date), instant(frame.end_date)
    except (ValueError, TypeError, AttributeError):
        return False
    return (start is None or start <= now) and (end is None or now < end)


def install():
    from routes import lives
    original = lives.resolve_frames
    if getattr(original, '_preservation_windows', False):
        return

    def resolve(*args, **kwargs):
        now = datetime.now(timezone.utc)
        return [frame for frame in original(*args, **kwargs) if frame_active(frame, now)]

    resolve._preservation_windows = True
    lives.resolve_frames = resolve

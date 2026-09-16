"""Serial output is opt-in: disconnected USB must not slow normal operation."""
import config


def log(*args, **kwargs):
    if getattr(config, 'SERIAL_LOG_ENABLED', False):
        print(*args, **kwargs)

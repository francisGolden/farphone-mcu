"""Quiet audio stop; power down the speaker after playback."""
import time
from libs.diagnostic_log import log

# ES8311 DAC mute bits, as used by Espressif's es8311_set_mute.
# https://github.com/espressif/esp-adf/blob/release/v2.x/components/esp_codec_dev/device/es8311/es8311.c
_codec_bus = None


def _set_codec_mute(muted):
    global _codec_bus
    try:
        if _codec_bus is None:
            from hardware import I2C, Pin
            _codec_bus = I2C(1, scl=Pin(48), sda=Pin(47), freq=100000)
        value = _codec_bus.readfrom_mem(0x18, 0x31, 1)[0]
        value = (value | 0x60) if muted else (value & 0x9F)
        _codec_bus.writeto_mem(0x18, 0x31, bytes([value]))
        return True
    except (ImportError, AttributeError, OSError, ValueError) as exc:
        log('[Audio] Codec mute unavailable:', type(exc).__name__)
        _codec_bus = None
        return False


def begin_output(speaker):
    if speaker.begin() is False:
        raise OSError('Speaker initialization failed')
    # Restore the codec after the previous hardware mute.
    _set_codec_mute(False)


def quiet_shutdown(speaker):
    # Allow queued output to settle at zero volume before stopping I2S.
    try:
        speaker.setVolume(0)
        _set_codec_mute(True)
        time.sleep_ms(60)
    finally:
        try:
            speaker.stop()
            time.sleep_ms(20)
        finally:
            speaker.end()


def play_buffered_wav(speaker, path, volume=240):
    """Keep the complete WAV buffer alive through playback and teardown."""
    with open(path, 'rb') as source:
        wav_data = source.read()
    try:
        begin_output(speaker)
        speaker.setVolume(volume)
        if speaker.playWav(wav_data) is False:
            raise OSError('WAV playback rejected')
        started = time.ticks_ms()
        while speaker.isPlaying():
            if time.ticks_diff(time.ticks_ms(), started) >= 10000:
                raise OSError('WAV playback timed out')
            time.sleep_ms(10)
    finally:
        quiet_shutdown(speaker)
        # end() has released the driver before the buffer leaves scope.

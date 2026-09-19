"""Run manually on StickS3 with Tamarix stopped; never launched by the app."""
import time
import M5
from M5 import Lcd, Speaker


def stage(label, delay_ms=2500):
    print('[Audio test]', label)
    Lcd.clear(0x000000)
    Lcd.setFont(Lcd.FONTS.DejaVu12)
    Lcd.setTextColor(0xFFFFFF, 0x000000)
    for index, line in enumerate(label.split('\n')):
        Lcd.setCursor(4, 30 + index * 22)
        Lcd.print(line)
    started = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), started) < delay_ms:
        M5.update()
        time.sleep_ms(20)


def trial(kind):
    stage(kind + '\nStarting... ', 1000)
    wav_data = None
    if Speaker.begin() is False:
        raise RuntimeError('Speaker initialization failed')
    Speaker.setVolume(0 if kind == 'WAV MUTED' else 120)
    if kind == 'WAV FILE':
        if Speaker.playWavFile('res/audio/seeds.wav') is False:
            raise RuntimeError('WAV playback rejected')
    elif kind in ('WAV BUFFER', 'WAV MUTED'):
        with open('res/audio/seeds.wav', 'rb') as source:
            wav_data = source.read()
        if Speaker.playWav(wav_data) is False:
            raise RuntimeError('Buffered playback rejected')
    else:
        Speaker.tone(880, 700)
    started = time.ticks_ms()
    while Speaker.isPlaying():
        if time.ticks_diff(time.ticks_ms(), started) > 10000:
            raise RuntimeError('Playback timed out')
        M5.update()
        time.sleep_ms(10)
    # Deliberately separate operations so the noise can be attributed.
    stage(kind + '\n1. Sound ended\nSpeaker still on')
    stage(kind + '\n2. Volume zero', 0)
    Speaker.setVolume(0)
    time.sleep_ms(2500)
    stage(kind + '\n3. Output stopped', 0)
    Speaker.stop()
    time.sleep_ms(2500)
    stage(kind + '\n4. Speaker off', 0)
    Speaker.end()
    time.sleep_ms(2500)
    wav_data = None


M5.begin()
Lcd.setBrightness(80)
try:
    Speaker.end()
    stage('Audio diagnostic\nListen for noise', 1500)
    trial('TONE')
    trial('WAV FILE')
    trial('WAV BUFFER')
    trial('WAV MUTED')
    stage('Done\nNote test + stage', 1000)
finally:
    try:
        Speaker.setVolume(0)
        Speaker.stop()
    finally:
        Speaker.end()

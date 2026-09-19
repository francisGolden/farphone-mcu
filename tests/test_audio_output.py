import unittest
from unittest.mock import Mock, patch
from libs.audio_output import quiet_shutdown


class AudioOutputTests(unittest.TestCase):
    def setUp(self):
        patcher = patch('libs.audio_output._set_codec_mute', return_value=True)
        self.mute = patcher.start()
        self.addCleanup(patcher.stop)

    def test_mutes_and_stops_with_power_off(self):
        speaker = Mock()
        events = Mock()
        events.attach_mock(speaker, 'speaker')
        with patch('libs.audio_output.time') as clock:
            events.attach_mock(clock, 'clock')
            quiet_shutdown(speaker)
        from unittest.mock import call
        self.assertEqual(events.mock_calls, [call.speaker.setVolume(0),
            call.clock.sleep_ms(60), call.speaker.stop(),
            call.clock.sleep_ms(20), call.speaker.end()])

    def test_stop_still_runs_if_muting_fails(self):
        speaker = Mock()
        speaker.setVolume.side_effect = OSError('mute failed')
        with patch('libs.audio_output.time'):
            with self.assertRaises(OSError):
                quiet_shutdown(speaker)
        speaker.stop.assert_called_once()
        speaker.end.assert_called_once()

    def test_buffered_wav_waits_for_completion_then_shuts_down(self):
        from libs.audio_output import play_buffered_wav
        from unittest.mock import mock_open
        speaker = Mock()
        speaker.isPlaying.side_effect = [True, True, False]
        with patch('builtins.open', mock_open(read_data=b'RIFF-test')):
            with patch('libs.audio_output.time') as clock:
                clock.ticks_ms.return_value = 0
                clock.ticks_diff.return_value = 0
                play_buffered_wav(speaker, 'sample.wav', 120)
        speaker.playWav.assert_called_once_with(b'RIFF-test')
        speaker.playWavFile.assert_not_called()
        self.assertEqual(speaker.isPlaying.call_count, 3)
        speaker.end.assert_called_once()

    def test_rejected_buffered_wav_still_shuts_down(self):
        from libs.audio_output import play_buffered_wav
        from unittest.mock import mock_open
        speaker = Mock()
        speaker.playWav.return_value = False
        with patch('builtins.open', mock_open(read_data=b'RIFF-test')):
            with patch('libs.audio_output.time'):
                with self.assertRaises(OSError):
                    play_buffered_wav(speaker, 'sample.wav')
        speaker.end.assert_called_once()

    def test_codec_mute_is_applied_before_power_off(self):
        speaker = Mock()
        speaker.end.side_effect = lambda: self.mute.assert_called_with(True)
        with patch('libs.audio_output.time'):
            quiet_shutdown(speaker)
        speaker.end.assert_called_once()

    def test_codec_unmuted_on_next_start(self):
        from libs.audio_output import begin_output
        speaker = Mock()
        begin_output(speaker)
        self.mute.assert_called_once_with(False)


class CodecMuteTests(unittest.TestCase):
    def test_mute_preserves_other_codec_register_bits(self):
        from libs.audio_output import _set_codec_mute
        bus = Mock()
        bus.readfrom_mem.return_value = b'\x85'
        with patch('libs.audio_output._codec_bus', bus):
            self.assertTrue(_set_codec_mute(True))
            bus.writeto_mem.assert_called_with(0x18, 0x31, b'\xe5')
            bus.readfrom_mem.return_value = b'\xe5'
            self.assertTrue(_set_codec_mute(False))
            bus.writeto_mem.assert_called_with(0x18, 0x31, b'\x85')

    def test_bus_failure_does_not_prevent_power_off(self):
        bus, speaker = Mock(), Mock()
        bus.readfrom_mem.side_effect = OSError('bus unavailable')
        with patch('libs.audio_output._codec_bus', bus):
            with patch('libs.audio_output.time'):
                quiet_shutdown(speaker)
        speaker.end.assert_called_once()

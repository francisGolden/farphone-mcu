import ast
import json
import math
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import Mock, patch
from libs import offline_storage as storage

ROOT = Path(__file__).resolve().parents[1]


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / 'pending.json'
        self.patch = patch.object(storage, 'STORAGE_FILE', str(self.path))
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.directory.cleanup()

    def test_write_failure_preserves_previous_queue(self):
        first = storage.queue_session(10, 'seed')
        before = self.path.read_bytes()
        with patch.object(storage.json, 'dump', side_effect=OSError('disk full')):
            with self.assertRaises(OSError):
                storage.queue_session(20, 'seed')
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(storage.get_pending_syncs()[0]['eventId'], first)

    def test_corrupt_or_invalid_queue_is_preserved(self):
        for contents in ('[{', '[1]', '{}', '[{"seedIdentifier":"s","xpEarned":-1}]'):
            self.path.write_text(contents)
            with self.assertRaises(ValueError):
                storage.queue_session(1, 'seed')
            self.assertEqual(self.path.read_text(), contents)

    def test_acknowledges_only_the_selected_event(self):
        one = storage.queue_session(10, 'seed')
        two = storage.queue_session(10, 'seed')
        self.assertNotEqual(one, two)
        storage.acknowledge_event(one)
        self.assertEqual([i['eventId'] for i in storage.get_pending_syncs()], [two])

    def test_legacy_timestamp_removed_from_memory_and_disk(self):
        for timestamp in (None, '2026-09-16T10:00:00Z'):
            event = dict(eventId='keep-id', seedIdentifier='seed', xpEarned=10,
                         durationSeconds=60, peekCount=1, firstPeekSec=53)
            self.path.write_text(json.dumps([dict(event, timestamp=timestamp)]))
            self.assertEqual(storage.get_pending_syncs(), [event])
            self.assertEqual(json.loads(self.path.read_text()), [event])

    def test_timestamp_migration_failure_preserves_original(self):
        original = '[{"seedIdentifier":"seed","timestamp":null}]'
        self.path.write_text(original)
        with patch.object(storage.os, 'rename', side_effect=OSError('write failed')):
            with self.assertRaises(OSError):
                storage.get_pending_syncs()
        self.assertEqual(self.path.read_text(), original)

    def test_write_excludes_timestamp_without_mutating_caller(self):
        event = dict(seedIdentifier='seed', timestamp=None)
        storage.replace_pending_syncs([event])
        self.assertEqual(json.loads(self.path.read_text()), [dict(seedIdentifier='seed')])
        self.assertIn('timestamp', event)

    def test_legacy_queue_and_capacity(self):
        self.path.write_text('[{"seedIdentifier":"old","xpEarned":5}]')
        self.assertEqual(storage.get_pending_syncs()[0]['xpEarned'], 5)
        with patch.object(storage, 'MAX_EVENTS', 1):
            with self.assertRaises(OSError):
                storage.queue_session(1, 'new')
        self.assertEqual(len(storage.get_pending_syncs()), 1)


class SyncTests(unittest.TestCase):
    def load(self):
        ns = {}
        with patch.dict(sys.modules, {'network': types.SimpleNamespace(STA_IF=0, WLAN=lambda _: Mock())}):
            exec(compile((ROOT/'libs/network/network_client.py').read_text(), 'network', 'exec'), ns)
        ns.update(connect_wifi=Mock(return_value=True), disconnect_wifi=Mock(),
                  send_harvest_raw=Mock(return_value=True), fetch_user_raw=Mock(),
                  acknowledge_event=Mock(), replace_pending_syncs=Mock())
        return ns

    def test_harvest_payload_has_no_timestamp(self):
        ns = self.load()
        # Use the actual sender rather than the sync test's stub.
        tree = ast.parse((ROOT/'libs/network/network_client.py').read_text())
        fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                  and n.name == 'send_harvest_raw')
        request = Mock(return_value=('HTTP/1.1 200 OK', '{}'))
        ns['_raw_tcp_request'] = request
        exec(compile(ast.Module(body=[fn], type_ignores=[]), 'sender', 'exec'), ns)
        self.assertTrue(ns['send_harvest_raw']('u','s','p',250,'SUCCESSFUL',60,1,53))
        self.assertEqual(request.call_args.kwargs['payload'], dict(
            userId='u', seedIdentifier='s', plantIdentifier='p', xpEarned=250,
            harvestOutcome='SUCCESSFUL', durationSeconds=60, peekCount=1, firstPeekSec=53))

    def test_profile_timeout_does_not_requeue_acknowledged_event(self):
        ns = self.load()
        ns['fetch_user_raw'].side_effect = OSError('timeout')
        result = ns['sync_session_event']('u','s','p',10,'SUCCESSFUL',60,event_id='local-id')
        self.assertIs(result, True)
        ns['acknowledge_event'].assert_called_once_with('local-id')
        ns['send_harvest_raw'].assert_called_once_with('u','s','p',10,'SUCCESSFUL',60,0,None)
        ns['disconnect_wifi'].assert_called_once()

    def test_failed_post_is_not_acknowledged(self):
        ns = self.load()
        ns['send_harvest_raw'].return_value = False
        self.assertFalse(ns['sync_session_event']('u','s','p',10,'SUCCESSFUL',60,event_id='id'))
        ns['acknowledge_event'].assert_not_called()
        ns['fetch_user_raw'].assert_not_called()

    def test_each_offline_ack_is_persisted_before_next_post(self):
        ns = self.load()
        first = dict(seedIdentifier='one', eventId='a')
        second = dict(seedIdentifier='two', eventId='b')
        ns['get_pending_syncs'] = lambda: [first, second]
        def post(*args):
            if args[1] == 'two':
                ns['replace_pending_syncs'].assert_called_once_with([second])
                raise OSError('timeout')
            return True
        ns['send_harvest_raw'].side_effect = post
        ns['initial_sync']('u')
        ns['replace_pending_syncs'].assert_called_once_with([second])
        ns['disconnect_wifi'].assert_called_once()


class MotionTests(unittest.TestCase):
    def test_immediate_detection_for_gentle_level_movement(self):
        ns = {}
        exec((ROOT/'libs/motion_detector.py').read_text(), ns)
        ns['time'] = types.SimpleNamespace(ticks_ms=lambda: 0,
                                          ticks_diff=lambda a, b: a-b)
        detector = ns['SmartMotionDetector'](
            alpha=0.95, energy_threshold=0.01, sustain_ms=0,
            tilt_threshold_rad=0.0175)
        detector.reset_reference((0, 0, 1))
        for _ in range(25):
            self.assertFalse(detector.update((0, 0, 1)))
        self.assertTrue(detector.update((0, 0, 1.02)))

    def test_positive_duration_still_rejects_brief_movement(self):
        ns = {}
        exec((ROOT/'libs/motion_detector.py').read_text(), ns)
        now = [0]
        ns['time'] = types.SimpleNamespace(ticks_ms=lambda: now[0],
                                          ticks_diff=lambda a, b: a-b)
        detector = ns['SmartMotionDetector'](
            alpha=0.95, energy_threshold=0.01, sustain_ms=240)
        detector.reset_reference((0, 0, 1))
        self.assertFalse(detector.update((0, 0, 1.02)))
        now[0] = 40
        self.assertFalse(detector.update((0, 0, 1)))
        self.assertIsNone(detector.motion_start_ms)
        now[0] = 80
        self.assertFalse(detector.update((0, 0, 1.04)))
        now[0] = 320
        self.assertTrue(detector.update((0, 0, 1.04)))

    def test_invalid_calibration_and_missing_sample(self):
        ns = {}
        exec((ROOT/'libs/motion_detector.py').read_text(), ns)
        ns['time'] = types.SimpleNamespace(ticks_ms=lambda: 0,
                                          ticks_diff=lambda a, b: a-b)
        detector = ns['SmartMotionDetector']()
        for invalid in (None, (0,0,0), (float('nan'),0,1)):
            with self.assertRaises(ValueError):
                detector.reset_reference(invalid)
        detector.reset_reference((0,0,1))
        self.assertFalse(detector.update(None))
        self.assertFalse(detector.update((0,0,1)))
        for _ in range(20):
            detected = detector.update((1,0,0))
            if detected:
                break
        self.assertTrue(detected)

    def test_gravity_filter_preserves_sample_magnitude(self):
        ns = {}
        exec((ROOT/'libs/motion_detector.py').read_text(), ns)
        detector = ns['SmartMotionDetector']()
        detector.reset_reference((0,0,0.98))
        self.assertEqual(detector.gravity, [0,0,0.98])
        self.assertEqual(detector.ref_gravity, [0,0,1])

class SessionPersistenceTests(unittest.TestCase):
    def setup_session(self, sync_result=False, storage_error=False):
        tree = ast.parse((ROOT/'libs/session.py').read_text())
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef))
        order = []
        def queue(*args):
            order.append('persist')
            if storage_error:
                raise OSError('full')
            return 'local-id'
        lcd = Mock()
        clock = types.SimpleNamespace(ticks_ms=lambda: 5000, ticks_diff=lambda a,b:a-b,
                                      sleep_ms=lambda _: None)
        sync = Mock(return_value=sync_result)
        ns = dict(time=clock, M5=types.SimpleNamespace(Lcd=lcd), Lcd=lcd,
                  STATE_IDLE='IDLE', STATE_FOCUS='FOCUS', STATE_INTERRUPTED='INTERRUPTED',
                  STATE_HARVEST_PENDING='HARVEST_PENDING',
                  SEEDS_CATALOG=[dict(id='seed', target_sec=60, bonus_base=10)],
                  queue_session=queue, sync_session_event=sync,
                  draw_mystery_sprout=Mock(), draw_revealed_plant=Mock(), print=Mock())
        exec(compile(ast.Module(body=[cls],type_ignores=[]),'session','exec'), ns)
        ui = Mock()
        session = ns['SessionManager']('user', Mock(), lambda:(0,0,1), Mock(),
                  lambda _:order.append('audio'), ui, Mock(), Mock(),
                  lambda _:dict(id='plant', name='Plant', rarity='COM', xp_mul=1))
        app = dict(selected_seed_idx=0, total_points=100, user_name='User', is_display_on=True)
        return session, app, order, sync

    def test_breach_rite_precedes_network_sync(self):
        session, app, order, sync = self.setup_session(sync_result=True)
        session.session_start_ms = 0
        session.trigger_breach_alert = lambda **kwargs: order.append('rite')
        sync.side_effect = lambda *args, **kwargs: order.append('sync') or True
        session.interrupt_session(app)
        self.assertEqual(order, ['persist', 'rite', 'sync'])
        self.assertEqual(session.current_state, 'IDLE')

    def test_harvest_persisted_before_animation_and_only_once(self):
        session, app, order, sync = self.setup_session()
        session.complete_session(app)
        self.assertEqual(order, ['persist'])
        sync.assert_not_called()
        self.assertEqual(session.current_state, 'HARVEST_PENDING')
        self.assertFalse(app['is_display_on'])
        session.complete_session(app)  # A repeated completion cannot add another reward.
        session.reveal_harvest(app)
        session.reveal_harvest(app)  # The interaction cannot replay the reward.
        self.assertEqual(session.current_state, 'IDLE')
        self.assertEqual(order, ['persist', 'audio', 'audio'])
        sync.assert_called_once()
        self.assertEqual(order.count('persist'), 1)
        self.assertEqual(sync.call_args.kwargs['event_id'], 'local-id')
        self.assertEqual(app['total_points'], 110)

    def test_storage_failure_does_not_send_unpersisted_reward(self):
        session, app, order, sync = self.setup_session(storage_error=True)
        session.complete_session(app)
        sync.assert_not_called()
        self.assertEqual(order, ['persist'])
        self.assertEqual(app['total_points'], 100)

    def test_invalid_imu_does_not_start_focus(self):
        session, app, order, sync = self.setup_session()
        session.current_state = 'REVIEW'
        session.read_accel = lambda: None
        session.start_session(app)
        self.assertEqual(session.current_state, 'REVIEW')
        session.detector.reset_reference.assert_not_called()


class HarvestDeadlineTests(unittest.TestCase):
    setup_session = SessionPersistenceTests.setup_session

    def test_deadline_movement_reveals_instead_of_breach(self):
        session, app, order, sync = self.setup_session()
        session.current_state = 'FOCUS'
        session.session_start_ms = 0
        session.detector.update.return_value = True
        session.interrupt_session = Mock()
        tree = ast.parse((ROOT/'apps/tamarix.py').read_text())
        loop = next(n for n in tree.body if isinstance(n, ast.While))
        # Execute the real main-loop deadline and pending-input branches together.
        start = next(i for i, n in enumerate(loop.body)
                     if isinstance(n, ast.If) and isinstance(n.test, ast.Compare)
                     and isinstance(n.test.comparators[0], ast.Name)
                     and n.test.comparators[0].id == 'STATE_FOCUS')
        nodes = loop.body[start:start+3]
        single_loop = ast.For(target=ast.Name(id='_', ctx=ast.Store()),
                             iter=ast.Tuple(elts=[ast.Constant(0)], ctx=ast.Load()),
                             body=nodes, orelse=[])
        code = ast.fix_missing_locations(ast.Module(body=[single_loop], type_ignores=[]))
        ns = dict(session=session, app_state=app, now=60000, last_sensor_ok_ms=59960,
                  acc_sample=(1,0,0), time=types.SimpleNamespace(ticks_diff=lambda a,b:a-b),
                  SEEDS_CATALOG=[dict(target_sec=60)], STATE_FOCUS='FOCUS',
                  STATE_HARVEST_PENDING='HARVEST_PENDING', detector=session.detector,
                  BtnA=Mock(wasPressed=Mock(return_value=False)),
                  BtnB=Mock(wasPressed=Mock(return_value=False)),
                  stop_battery_tone=Mock(), battery_tone_until=None,
                  battery_notice_until=None, read_accel=lambda:(1,0,0), idle_gravity=[0,0,1],
                  M5=Mock(), cpu_power=Mock(), harvest_led=Mock(), ui=Mock(is_display_on=True))
        exec(compile(code, 'main-loop', 'exec'), ns)
        session.interrupt_session.assert_not_called()
        self.assertEqual(order, ['persist', 'audio', 'audio'])
        self.assertEqual(app['total_points'], 110)
        self.assertEqual(session.peek_count, 0)
        self.assertEqual(session.current_state, 'IDLE')

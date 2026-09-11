import unittest
from unittest.mock import Mock
from audio_devices import InputWatch,InputChanged,refresh


class DeviceTests(unittest.TestCase):
    def test_default_change_interrupts_capture_without_enumeration(self):
        watch=InputWatch(query=Mock(side_effect=[10,20]),clock=Mock(side_effect=[0,1.1]))
        with self.assertRaises(InputChanged):watch.check()

    def test_device_observation_throttled(self):
        query=Mock(return_value=10)
        watch=InputWatch(query=query,clock=Mock(side_effect=[0,.1,.9,1.1]))
        watch.check();watch.check();watch.check();self.assertEqual(query.call_count,2)

    def test_unknown_query_does_not_force_device_switch(self):
        watch=InputWatch(query=Mock(side_effect=[10,None,10]),clock=Mock(side_effect=[0,2,4]))
        watch.check();watch.check()

    def test_refresh_pairs_lifecycle_in_order(self):
        sd=Mock();sd._initialized=1
        refresh(sd)
        self.assertEqual([x[0] for x in sd.mock_calls],['_terminate','_initialize'])

    def test_recover_failed_initialization_without_extra_terminate(self):
        sd=Mock();sd._initialized=0
        refresh(sd);sd._terminate.assert_not_called();sd._initialize.assert_called_once()

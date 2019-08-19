# -*- coding: utf-8 -*-

from __future__ import unicode_literals

import datetime
import unittest

from python_caltrain import Caltrain, TransitType


class TestCaltrain(unittest.TestCase):

    def test_expected_next_train_week_day(self):
        c = Caltrain()
        next_trips = c.next_trips(
            'sf', 'sunnyvale', after=datetime.datetime(2019, 8, 19, 20, 0, 0))

        self.assertGreater(len(next_trips), 1)
        next_trip = next_trips[0]

        self.assertIsNotNone(next_trip)
        self.assertEqual(datetime.time(20, 30), next_trip.departure)
        self.assertEqual(datetime.time(21, 49), next_trip.arrival)
        self.assertEqual(datetime.timedelta(hours=1, minutes=19), next_trip.duration)
        self.assertEqual(TransitType.local, next_trip.train.kind)
        self.assertEqual('192', next_trip.train.name)

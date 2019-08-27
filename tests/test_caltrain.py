# -*- coding: utf-8 -*-

from __future__ import unicode_literals

import datetime
import unittest
import os

from python_caltrain import Caltrain, TransitType


class TestNextTrain(unittest.TestCase):
    def test_expected_next_train_week_day(self):
        c = Caltrain()
        next_trips = c.next_trips(
            "sf", "sunnyvale", after=datetime.datetime(2019, 8, 19, 20, 0, 0)
        )

        self.assertGreater(len(next_trips), 1)
        next_trip = next_trips[0]

        self.assertIsNotNone(next_trip)
        self.assertEqual(datetime.time(20, 30), next_trip.departure)
        self.assertEqual(datetime.time(21, 49), next_trip.arrival)
        self.assertEqual(datetime.timedelta(hours=1, minutes=19), next_trip.duration)
        self.assertEqual(TransitType.local, next_trip.train.kind)
        self.assertEqual("192", next_trip.train.name)

    def test_expected_next_train_weekend(self):
        c = Caltrain()
        next_trips = c.next_trips(
            "palo alto", "san bruno", after=datetime.datetime(2019, 8, 24, 11, 0, 0)
        )

        self.assertGreater(len(next_trips), 1)
        next_trip = next_trips[0]

        self.assertIsNotNone(next_trip)
        self.assertEqual(datetime.time(12, 12), next_trip.departure)
        self.assertEqual(datetime.time(12, 58), next_trip.arrival)
        self.assertEqual(datetime.timedelta(minutes=46), next_trip.duration)
        self.assertEqual(TransitType.local, next_trip.train.kind)
        self.assertEqual("427", next_trip.train.name)

    def test_expected_next_train_holiday(self):
        c = Caltrain()
        next_trips = c.next_trips(
            "hillsdale",
            "san jose diridon",
            after=datetime.datetime(2019, 9, 2, 12, 23, 0),
        )

        self.assertGreater(len(next_trips), 1)
        next_trip = next_trips[0]

        self.assertIsNotNone(next_trip)
        self.assertEqual(datetime.time(12, 30), next_trip.departure)
        self.assertEqual(datetime.time(13, 13), next_trip.arrival)
        self.assertEqual(datetime.timedelta(minutes=43), next_trip.duration)
        self.assertEqual(TransitType.baby_bullet, next_trip.train.kind)
        self.assertEqual("802", next_trip.train.name)

        # This should be identical to the Sunday schedule.
        sunday_trips = c.next_trips(
            "hillsdale",
            "san jose diridon",
            after=datetime.datetime(2019, 9, 1, 12, 23, 0),
        )

        for i, (a, e) in enumerate(zip(next_trips, sunday_trips)):
            self.assertEqual(e, a, "elements at index {} differ".format(i))

    def test_expected_next_train_event(self):
        c = Caltrain()
        next_trips = c.next_trips(
            "san jose diridon",
            "san francisco",
            after=datetime.datetime(2019, 5, 26, 9, 30, 0),
        )

        self.assertGreater(len(next_trips), 1)

        # Event train
        self.assertIsNotNone(next_trips[0])
        self.assertEqual(datetime.time(9, 41), next_trips[0].departure)
        self.assertEqual(datetime.time(10, 45), next_trips[0].arrival)
        self.assertEqual(datetime.timedelta(hours=1, minutes=4), next_trips[0].duration)
        self.assertEqual(TransitType.weekend_game_train, next_trips[0].train.kind)
        self.assertEqual("609", next_trips[0].train.name)

        # Regular train
        self.assertIsNotNone(next_trips[1])
        self.assertEqual(datetime.time(9, 51), next_trips[1].departure)
        self.assertEqual(datetime.time(11, 0), next_trips[1].arrival)
        self.assertEqual(datetime.timedelta(hours=1, minutes=9), next_trips[1].duration)
        self.assertEqual(TransitType.baby_bullet, next_trips[1].train.kind)
        self.assertEqual("801", next_trips[1].train.name)


class TestFare(unittest.TestCase):
    def test_expected_cost(self):
        c = Caltrain()
        self.assertEqual((3, 75), c.fare_between("sunnyvale", "sunnyvale"))
        self.assertEqual((6, 0), c.fare_between("sunnyvale", "lawrence"))
        self.assertEqual((8, 25), c.fare_between("sunnyvale", "capitol"))
        self.assertEqual((10, 50), c.fare_between("sunnyvale", "gilroy"))


class TestAlternateFile(unittest.TestCase):
    def test_explicit_gtfs(self):
        here = os.path.abspath(os.path.dirname(__file__))
        c = Caltrain(
            os.path.join(here, "../python_caltrain/data/caltrain_gtfs_latest.zip")
        )

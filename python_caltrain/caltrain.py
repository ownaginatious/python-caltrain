#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import unicode_literals

import csv
from collections import namedtuple
from datetime import datetime, timedelta
import os
import pkg_resources
import re
import sys
from zipfile import ZipFile
from enum import Enum, unique
from io import TextIOWrapper

Train = namedtuple('Train', ['name', 'kind', 'direction',
                             'stops', 'service_window'])
Station = namedtuple('Station', ['name', 'zone'])
Stop = namedtuple('Stop', ['arrival', 'arrival_day',
                           'departure', 'departure_day',
                           'stop_number'])
ServiceWindow = namedtuple('ServiceWindow', ['start', 'end', 'days'])
Trip = namedtuple('Trip', ['departure', 'arrival', 'duration', 'train'])

_BASE_DATE = datetime(1970, 1, 1, 0, 0, 0, 0)


def _sanitize_name(name):
    """
    Pre-sanitization to increase the likelihood of finding
    a matching station.

    :param name: the station name
    :type name: str or unicode

    :returns: sanitized station name
    """
    return ''.join(re.split('[^A-Za-z0-9]', name)).lower()\
             .replace('station', '').strip()


def _resolve_time(t):
    """
    Resolves the time string into datetime.time. This method
    is needed because Caltrain arrival/departure time hours
    can exceed 23 (e.g. 24, 25), to signify trains that arrive
    after 12 AM. The 'day' variable is incremented from 0 in
    these situations, and the time resolved back to a valid
    datetime.time (e.g. 24:30:00 becomes days=1, 00:30:00).

    :param t: the time to resolve
    :type t: str or unicode

    :returns: tuple of days and datetime.time
    """
    hour, minute, second = [int(x) for x in t.split(":")]
    day, hour = divmod(hour, 24)
    r = _BASE_DATE + timedelta(hours=hour,
                               minutes=minute,
                               seconds=second)
    return day, r.time()


def _resolve_duration(start, end):
    """
    Resolves the duration between two times. Departure/arrival
    times that exceed 24 hours or cross a day boundary are correctly
    resolved.

    :param start: the time to resolve
    :type start: Stop
    :param end: the time to resolve
    :type end: Stop

    :returns: tuple of days and datetime.time
    """
    start_time = _BASE_DATE + timedelta(hours=start.departure.hour,
                                        minutes=start.departure.minute,
                                        seconds=start.departure.second,
                                        days=start.departure_day)
    end_time = _BASE_DATE + timedelta(hours=end.arrival.hour,
                                      minutes=end.arrival.minute,
                                      seconds=end.arrival.second,
                                      days=end.departure_day)
    return end_time - start_time


_STATIONS_RE = re.compile(r'^(.+) Caltrain( Station)?$')

_RENAME_MAP = {
    'SO. SAN FRANCISCO': 'SOUTH SAN FRANCISCO',
    'MT VIEW': 'MOUNTAIN VIEW'
}

_DEFAULT_GTFS_FILE = 'data/caltrain_gtfs_latest.zip'
_ALIAS_MAP_RAW = {
    'SAN FRANCISCO': ('SF', 'SAN FRAN'),
    'SOUTH SAN FRANCISCO': ('S SAN FRANCISCO', 'SOUTH SF',
                            'SOUTH SAN FRAN', 'S SAN FRAN',
                            'S SAN FRANCISCO', 'S SF', 'SO SF',
                            'SO SAN FRANCISCO', 'SO SAN FRAN'),
    '22ND ST': ('TWENTY-SECOND STREET', 'TWENTY-SECOND ST',
                '22ND STREET', '22ND', 'TWENTY-SECOND', '22'),
    'MOUNTAIN VIEW': 'MT VIEW'
}

_ALIAS_MAP = {}

for k, v in _ALIAS_MAP_RAW.items():
    if not isinstance(v, list) and not isinstance(v, tuple):
        v = (v,)
    for x in v:
        _ALIAS_MAP[_sanitize_name(x)] = _sanitize_name(k)


@unique
class Direction(Enum):
    north = 0
    south = 1


@unique
class TransitType(Enum):
    baby_bullet = "bu"
    limited = "li"
    local = "lo"
    tamien_sanjose = "tasj"

    def __str__(self):
        return self.name.replace('_', ' ').title()


class UnexpectedGTFSLayoutError(Exception):
    pass


class UnknownStationError(Exception):
    pass


class Caltrain(object):

    def __init__(self, gtfs_path=None):

        self.version = None
        self.trains = {}
        self.stations = {}
        self._unambiguous_stations = {}
        self._service_windows = {}
        self._fares = {}

        self.load_from_gtfs(gtfs_path)

    def load_from_gtfs(self, gtfs_path=None):
        """
        Resolves the duration between two times. Departure/arrival
        times that exceed 24 hours or cross a day boundary are correctly
        resolved.

        :param start: the time to resolve
        :type start: Stop
        :param end: the time to resolve
        :type end: Stop

        :returns: tuple of days and datetime.time
        """
        # Use the default path if not specified.
        if gtfs_path is None:
            gtfs_path = pkg_resources\
                .resource_stream(__name__, _DEFAULT_GTFS_FILE)

        z = ZipFile(gtfs_path)

        self.trains, self.stations = {}, {}
        self._service_windows, self._fares = {}, {}

        # Attempt to get the version data.
        folders = set(f.split('/')[0] for f in z.namelist())
        if len(folders) > 1:
            raise UnexpectedGTFSLayoutError(
                'Multiple top-level dirs: %s' % str(folders))
        self.version = list(folders)[0]

        # -------------------
        # 1. Record fare data
        # -------------------

        fare_lookup = {}

        # Create a map if (start, dest) -> price
        with z.open(self.version + '/fare_attributes.txt', 'rU') as csvfile:
            fare_reader = csv.DictReader(TextIOWrapper(csvfile))
            for r in fare_reader:
                fare_lookup[r['fare_id']] = \
                    tuple(int(x) for x in r['price'].split('.'))

        # Read in the fare IDs from station X to station Y.
        with z.open(self.version + '/fare_rules.txt', 'rU') as csvfile:
            fare_reader = csv.DictReader(TextIOWrapper(csvfile))
            for r in fare_reader:
                k = (int(r['origin_id']), int(r['destination_id']))
                self._fares[k] = fare_lookup[r['fare_id']]

        # ------------------------
        # 2. Record calendar dates
        # ------------------------

        # Record the days when certain trains are active.
        with z.open(self.version + '/calendar.txt', 'rU') as csvfile:
            calendar_reader = csv.reader(TextIOWrapper(csvfile))
            next(calendar_reader)
            for r in calendar_reader:
                self._service_windows[r[0]] = ServiceWindow(
                    start=datetime.strptime(r[-2], '%Y%m%d').date(),
                    end=datetime.strptime(r[-1], '%Y%m%d').date(),
                    days=set(i for i, j in enumerate(r[1:8]) if int(j) == 1)
                )

        # ------------------
        # 3. Record stations
        # ------------------
        with z.open(self.version + '/stops.txt', 'rU') as csvfile:
            trip_reader = csv.DictReader(TextIOWrapper(csvfile))
            for r in trip_reader:
                # Non-numeric stop IDs are useless information as
                # can be observed and should therefore be skipped.
                if not r['stop_id'].isdigit():
                    continue
                stop_name = _STATIONS_RE.match(r['stop_name'])\
                    .group(1).strip().upper()
                self.stations[r['stop_id']] = {
                    'name': _RENAME_MAP.get(stop_name, stop_name).title(),
                    'zone': int(r['zone_id'])
                }

        # ---------------------------
        # 4. Record train definitions
        # ---------------------------
        with z.open(self.version + '/trips.txt', 'rU') as csvfile:
            train_reader = csv.DictReader(TextIOWrapper(csvfile))
            for r in train_reader:
                train_dir = int(r['direction_id'])
                transit_type = TransitType(r['route_id'].lower()
                                           .split('-')[0].strip())
                self.trains[r['trip_id']] = Train(
                    name=r['trip_id'],
                    kind=transit_type,
                    direction=Direction(train_dir),
                    stops={},
                    service_window=self._service_windows[r['service_id']]
                )

        self.stations = dict((k,
                             Station(v['name'], v['zone']))
                             for k, v in self.stations.items())

        # -----------------------
        # 5. Record trip stations
        # -----------------------
        with z.open(self.version + '/stop_times.txt', 'rU') as csvfile:
            stop_times_reader = csv.DictReader(TextIOWrapper(csvfile))
            for r in stop_times_reader:
                stop_id = r['stop_id']
                train = self.trains[r['trip_id']]
                arrival_day, arrival = _resolve_time(r['arrival_time'])
                departure_day, departure = _resolve_time(r['departure_time'])
                train.stops[self.stations[r['stop_id']]] =\
                    Stop(arrival=arrival, arrival_day=arrival_day,
                         departure=departure, departure_day=departure_day,
                         stop_number=int(r['stop_sequence']))

        # For display
        self.stations = \
            dict(('_'.join(re.split('[^A-Za-z0-9]', v.name)).lower(), v)
                 for _, v in self.stations.items())

        # For station lookup by string
        self._unambiguous_stations = dict((k.replace('_', ''), v)
                                          for k, v in self.stations.items())

    def get_station(self, name):
        """
        Attempts to resolves a station name from a string into an
        actual station. An UnknownStationError is thrown if no
        Station can be derived

        :param name: the name to resolve
        :type name: str or unicode

        :returns: the resolved Station object
        """
        sanitized = _sanitize_name(name)
        sanitized = _ALIAS_MAP.get(sanitized, sanitized)
        station = self._unambiguous_stations.get(sanitized, None)
        if station:
            return station
        else:
            raise UnknownStationError(name)

    def fare_between(self, a, b):
        """
        Returns the fare to travel between stations a and b. Caltrain fare
        is always dependent on the distance and not the train type.

        :param a: the starting station
        :type a: str or unicode or Station
        :param b: the destination station
        :type b: str or unicode or Station

        :returns: tuple of the dollar and cents cost
        """
        a = self.get_station(a) if not isinstance(a, Station) else a
        b = self.get_station(b) if not isinstance(b, Station) else b
        return self._fares[(a.zone, b.zone)]

    def next_trips(self, a, b, after=datetime.now()):
        """
        Returns a list of possible trips to get from stations a to b
        following the after date. These are ordered from soonest to
        latest and terminate at the end of the Caltrain's "service day".

        :param a: the starting station
        :type a: str or unicode or Station
        :param b: the destination station
        :type b: str or unicode or Station
        :param after: the time to find the next trips after (default datetime.now())
        :type after: datetime

        :returns: a list of possible trips
        """
        a = self.get_station(a) if not isinstance(a, Station) else a
        b = self.get_station(b) if not isinstance(b, Station) else b

        possibilities = []

        for name, train in self.trains.items():

            sw = train.service_window

            # Check to see if the train's stops contains our stations and is available.
            if after.date() < sw.start or after.date() > sw.end or \
               after.weekday() not in sw.days or \
               a not in train.stops or b not in train.stops:
                continue

            stop_a = train.stops[a]
            stop_b = train.stops[b]

            # Check to make sure this train is headed in the right direction.
            if stop_a.stop_number > stop_b.stop_number:
                continue

            # Check to make sure this train has not left yet.
            if stop_a.departure < after.time():
                continue

            possibilities += [Trip(
                                departure=stop_a.departure,
                                arrival=stop_b.arrival,
                                duration=_resolve_duration(stop_a, stop_b),
                                train=train
                              )]

        possibilities.sort(key=lambda x: x.departure)
        return possibilities

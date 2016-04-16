import csv
from collections import namedtuple
from datetime import datetime, timedelta
import os
import pkg_resources
import re
import sys
from zipfile import ZipFile
from enum import Enum
from io import TextIOWrapper

Trip = namedtuple('Trip', ['tid', 'kind', 'direction',
                           'stops', 'service_window'])
Station = namedtuple('Station', ['name', 'zone'])
Stop = namedtuple('Stop', ['arrival', 'arrival_day',
                           'departure', 'departure_day',
                           'stop_number'])
ServiceWindow = namedtuple('ServiceWindow', ['start', 'end', 'days'])

_BASE_DATE = datetime(1970, 1, 1, 0, 0, 0, 0)


def _sanitize_name(name):
    return ''.join(re.split('[^A-Za-z0-9]', name)).lower()\
             .replace('station', '').strip()


def _resolve_time(t):
    hour, minute, second = [int(x) for x in t.split(":")]
    day, hour = divmod(hour, 24)
    r = _BASE_DATE + timedelta(hours=hour,
                               minutes=minute,
                               seconds=second)
    return day, r.time()


def _resolve_duration(start, end):
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


class Direction(Enum):
    north = 0
    south = 1


class TransitType(Enum):
    baby_bullet = "bu"
    limited = "li"
    local = "lo"
    tamien_sanjose = "tasj"


class UnexpectedGTFSLayoutError(Exception):
    pass


class UnknownStationError(Exception):
    pass


class Caltrain(object):

    def __init__(self, gtfs_path=None):

        self.version = None
        self.trips = {}
        self.stations = {}
        self._unambiguous_stations = {}
        self._service_windows = {}
        self._fairs = {}

        self.load_from_gtfs(gtfs_path)

    def load_from_gtfs(self, gtfs_path=None):

        # Use the default path if not specified.
        if gtfs_path is None:
            gtfs_path = pkg_resources\
                .resource_stream(__name__, _DEFAULT_GTFS_FILE)

        z = ZipFile(gtfs_path)

        self.trips, self.stations = {}, {}
        self._service_windows, self._fairs = {}, {}

        # Attempt to get the version data.
        folders = set(f.split('/')[0] for f in z.namelist())
        if len(folders) > 1:
            raise UnexpectedGTFSLayoutError(
                'Multiple top-level dirs: %s' % str(folders))
        self.version = list(folders)[0]

        # -------------------
        # 1. Record fare data
        # -------------------

        fair_lookup = {}

        # Create a map if (start, dest) -> price
        with z.open(self.version + '/fare_attributes.txt', 'rU') as csvfile:
            fair_reader = csv.DictReader(TextIOWrapper(csvfile))
            for r in fair_reader:
                fair_lookup[r['fare_id']] = \
                    tuple(int(x) for x in r['price'].split('.'))

        # Read in the fare IDs from station X to station Y.
        with z.open(self.version + '/fare_rules.txt', 'rU') as csvfile:
            fair_reader = csv.DictReader(TextIOWrapper(csvfile))
            for r in fair_reader:
                k = (int(r['origin_id']), int(r['destination_id']))
                self._fairs[k] = fair_lookup[r['fare_id']]

        # ------------------------
        # 2. Record calendar dates
        # ------------------------

        # Record the days when certain Caltrain trips are active.
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
                # This is meaningless information as far as can be observed
                # and should be skipped.
                if not r['stop_id'].isdigit():
                    continue
                stop_name = _STATIONS_RE.match(r['stop_name'])\
                    .group(1).strip().upper()
                self.stations[r['stop_id']] = {
                    'name': _RENAME_MAP.get(stop_name, stop_name).title(),
                    'zone': int(r['zone_id'])
                }

        # ---------------------------
        # 4. Record trips definitions
        # ---------------------------
        with z.open(self.version + '/trips.txt', 'rU') as csvfile:
            trip_reader = csv.DictReader(TextIOWrapper(csvfile))
            for r in trip_reader:
                trip_dir = int(r['direction_id'])
                transit_type = TransitType(r['route_id'].lower()
                                           .split('-')[0].strip())
                self.trips[r['trip_id']] = Trip(
                    tid=r['trip_id'],
                    kind=transit_type,
                    direction=(Direction.north, Direction.south)[trip_dir],
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
            trip_reader = csv.DictReader(TextIOWrapper(csvfile))
            for r in trip_reader:
                stop_id = r['stop_id']
                trip = self.trips[r['trip_id']]
                arrival_day, arrival = _resolve_time(r['arrival_time'])
                departure_day, departure = _resolve_time(r['departure_time'])
                trip.stops[self.stations[r['stop_id']]] =\
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
        sanitized = _sanitize_name(name)
        sanitized = _ALIAS_MAP.get(sanitized, sanitized)
        station = self._unambiguous_stations.get(sanitized, None)
        if station:
            return station
        else:
            raise UnknownStationError(name)

    def fair_between(self, a, b):
        a = self.get_station(a) if not isinstance(a, Station) else a
        b = self.get_station(b) if not isinstance(b, Station) else b
        return self._fairs[(a.zone, b.zone)]

    def next_trip(self, a, b, after=datetime.now()):

        a = self.get_station(a) if not isinstance(a, Station) else a
        b = self.get_station(b) if not isinstance(b, Station) else b

        possibilities = []

        for name, trip in self.trips.items():

            sw = trip.service_window

            # Check to see if the trip contains our stations and is available.
            if after.date() < sw.start or after.date() > sw.end or \
               after.weekday() not in sw.days or \
               a not in trip.stops or b not in trip.stops:
                continue

            stop_a = trip.stops[a]
            stop_b = trip.stops[b]

            # Check to make sure this train is headed in the right direction.
            if stop_a.stop_number > stop_b.stop_number:
                continue

            # Check to make sure this train has not left yet.
            if stop_a.departure < after.time():
                continue

            possibilities += [(name, stop_a.departure, stop_b.arrival,
                               _resolve_duration(stop_a, stop_b),
                               trip.kind)]

        possibilities.sort(key=lambda x: x[1])
        return possibilities

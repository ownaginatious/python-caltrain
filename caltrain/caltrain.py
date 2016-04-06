import csv
from collections import namedtuple
from datetime import datetime
import re
import sys
from zipfile import ZipFile
from enum import Enum
from io import TextIOWrapper

Trip = namedtuple('Trip', ['id', 'type', 'direction',
                           'stops', 'service_window'])
Station = namedtuple('Station', ['name', 'zone'])
Stop = namedtuple('Stop', ['arrival', 'departure'])
ServiceWindow = namedtuple('ServiceWindow', ['start', 'end', 'days'])
TransitType = namedtuple('TransitType', ['type'])


def _sanitize_name(name):
    return ''.join(re.split('[^A-Za-z0-9]', name)).lower()

_ZONE_OFFSET = 3328

_STATIONS_RE = re.compile(r'CALTRAIN - (.+) STATION')

_RENAME_MAP = {
    'S SAN FRANCISCO': 'SOUTH SAN FRANCISCO'
}

_ALIAS_MAP_RAW = {
    'SAN FRANCISCO': ('SF', 'SAN FRAN'),
    'SOUTH SAN FRANCISCO': ('S SAN FRANCISCO', 'SOUTH SF',
                            'SOUTH SAN FRAN', 'S SAN FRAN',
                            'S SAN FRANCISCO', 'S SF'),
    '22ND ST': ('TWENTY-SECOND STREET', 'TWENTY-SECOND ST',
                '22ND STREET', '22ND', 'TWENTY-SECOND', '22')
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


class UnknownStationError(Exception):
    pass


class Caltrain(object):

    def __init__(self, gtfs_path=None):

        self.trips = {}
        self.stations = {}
        self._unambiguous_stations = {}
        self._service_windows = {}
        self._fairs = {}

        if gtfs_path:
            self.load_from_gtfs(gtfs_path)

    def load_from_gtfs(self, gtfs_path):

        z = ZipFile(gtfs_path)

        self.trips, self.stations = {}, {}
        self._service_windows, self._fairs = {}, {}

        fair_trip_by_id = {}

        # -------------------
        # 1. Record fare data
        # -------------------

        # Read in the fare IDs from station X to station Y.
        with z.open('fare_rules.txt', 'rU') as csvfile:
            fair_reader = csv.DictReader(TextIOWrapper(csvfile))
            for r in fair_reader:
                fair_trip_by_id[r['fare_id']] = (
                    int(r[' origin_id']) - _ZONE_OFFSET,
                    int(r[' destination_id']) - _ZONE_OFFSET
                )

        # Create a map if (start, dest) -> price
        with z.open('fare_attributes.txt', 'rU') as csvfile:
            fair_reader = csv.DictReader(TextIOWrapper(csvfile))
            for r in fair_reader:
                self._fairs[fair_trip_by_id[r['fare_id']]] = \
                    tuple(int(x) for x in r['price'].split('.'))

        # ------------------------
        # 2. Record calendar dates
        # ------------------------

        # Record the days when certain Caltrain trips are active.
        with z.open('calendar.txt', 'rU') as csvfile:
            calendar_reader = csv.reader(TextIOWrapper(csvfile))
            next(calendar_reader)
            for r in calendar_reader:
                self._service_windows[r[0]] = ServiceWindow(
                    start=datetime.strptime(r[-2], '%Y%m%d').date(),
                    end=datetime.strptime(r[-1], '%Y%m%d').date(),
                    days=set(i for i, j in enumerate(r[1:8]) if int(j) == 1)
                )

        ignored_stops = set()

        # ------------------
        # 3. Record stations
        # ------------------
        with z.open('stops.txt', 'rU') as csvfile:
            trip_reader = csv.DictReader(TextIOWrapper(csvfile))
            for r in trip_reader:
                if 'CALTRAIN' not in r['stop_name']:
                    ignored_stops.add(r['stop_id'])
                    continue
                stop_name = _STATIONS_RE.match(r['stop_name']).group(1).strip()
                self.stations[r['stop_id']] = {
                    'name': _RENAME_MAP.get(stop_name, stop_name).title(),
                    'zone': int(r['zone_id']) - _ZONE_OFFSET
                }

        # ---------------------------
        # 4. Record trips definitions
        # ---------------------------
        with z.open('trips.txt', 'rU') as csvfile:
            transit_types = {}
            trip_reader = csv.DictReader(TextIOWrapper(csvfile))
            for r in trip_reader:
                trip_dir = int(r['direction_id'])
                transit_type = r['route_id'].title().strip()
                if transit_type not in transit_types:
                    transit_types[transit_type] = \
                        TransitType(type=transit_type)
                self.trips[r['trip_id']] = Trip(
                    id=r['trip_id'],
                    type=transit_types[transit_type],
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
        with z.open('stop_times.txt', 'rU') as csvfile:
            trip_reader = csv.DictReader(TextIOWrapper(csvfile))
            for r in trip_reader:
                stop_id = r['stop_id']
                if stop_id in ignored_stops:
                    continue
                trip = self.trips[r['trip_id']]
                arrival = datetime.strptime(r['arrival_time'],
                                            '%H:%M:%S').time(),
                departure = datetime.strptime(r['departure_time'],
                                              '%H:%M:%S').time()
                trip.stops[self.stations[r['stop_id']]] =\
                    Stop(arrival=arrival, departure=departure)

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
            if after < sw.start or after > sw.end or \
               after.weekday() not in sw.days or \
               a not in trip.stops or b not in trip.stops:
                continue

            leave_from_a = trip.stops[a].departure
            arrive_at_b = trip.stops[b].arrival

            # Check to make sure this train is headed in the right direction.
            if leave_from_a > arrive_at_b:
                continue

            # Check to make sure this train has not left yet.
            if leave_from_a < (after.hour, after.minute):
                continue

            possibilities += [(name, leave_from_a, arrive_at_b, trip.type)]

        possibilities.sort(key=lambda x: x[1])
        return possibilities

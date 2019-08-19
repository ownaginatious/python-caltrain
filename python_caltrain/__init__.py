from .caltrain import (
    Caltrain, Train, Trip, TransitType, Station, Stop, Direction, UnknownStationError,
    UnexpectedGTFSLayoutError)

from ._version import get_versions
__version__ = get_versions()['version']
del get_versions

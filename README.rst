python-caltrain
===============

|PyPI Version| |Python Versions| |Coverage| |Build Status|

A library for working with raw Bay Area Caltrain scheduling data in
Python.

What is the purpose of ``python-caltrain``?
-------------------------------------------

The purpose of this library is for easily making queries against the
Caltrain schedule such as:

-  The cost of travel from *Sunnyvale* to *South San Francisco* station.
-  The next train(s) from *22nd Street* to *San Jose*.
-  The duration of travel between *San Mateo* and *Menlo Park* on a
   *Limited* train.

Does this library require an internet connection?
-------------------------------------------------

``python-caltrain`` does **not** require an internet connection, making
it easy to embed into offline applications. It relies on the `Caltrain
GTFS
file <http://www.caltrain.com/Assets/GTFS/caltrain/Caltrain-GTFS.zip>`__,
which is updated usually a couple of times per year at most. This
library will update in accordance with announcements from Caltrain. The
version number is **year.month.rev** to signify how recent it is.

e.g. ``2016.4.0`` means the library is at revision 0 and uses the *April
2016* GTFS file.

How do I get it?
----------------

Install via pip:

::

    pip install python-caltrain

How do I use it?
----------------

Let's find the next train from Sunnyvale to San Francisco 4th and King.

.. code:: python

    >> from python_caltrain import Caltrain
    >> c = Caltrain()
    >> n = c.next_trips('sunnyvale', 'sf')[0]
    >> n.departure
    datetime.time(11, 26)
    >> n.arrival
    datetime.time(12, 43)
    >> n.duration
    datetime.timedelta(0, 4620)

Next train is at 12:43 PM from sunnyvale. Let's see what train number
that is.

.. code:: python

    >> n.train.name
    '143'

What kind of train is it?

.. code:: python

    >> str(n.train.kind)
    'Local'

Can you print a summary of the trip?

.. code:: python

    >> str(n)
    [Local 143] Departs: 11:26:00, Arrives: 12:43:00 (1:17:00)

Does that train stop at San Mateo? If so, when?

.. code:: python

    >> san_mateo = c.get_station('san mateo')
    >> san_mateo in n.train.stops
    True
    >> n.train.stops[san_mateo].arrival
    datetime.time(12, 8)

How much is this trip going to cost?

.. code:: python

    >> c.fare_between('sunnyvale', 'san francisco')
    (7, 75)

My goodness, that's quite expensive...

What if I want to know the next train after some point in the past or
future?

.. code:: python

    >> from datetime import datetime
    >> d = ... # Your date time here
    >> n = c.next_trips('sunnyvale', 'sf', after=d)

Station names do not need to be sanitized. The
``Caltrain.get_station(...)``, ``Caltrain.next_trip(...)``, and
``Caltrain.fare_between(...)`` functions all perform sanitization
themselves and can automatically resolve alternate common names for
stations.

For example, ``sf``, ``sanfrancisco``, ``san fran``,
``san francisco station`` are all understood as the same station. Same
with ``22nd``, ``Twenty-Second``, ``twenty second street``, and
``22nd str``.

.. |PyPI Version| image:: https://badge.fury.io/py/python-caltrain.svg
    :target: https://badge.fury.io/py/python-caltrain

.. |Python Versions| image:: https://img.shields.io/pypi/pyversions/python-caltrain.svg
    :target: https://github.com/ownaginatious/python-caltrain/blob/master/setup.py

.. |Build Status| image:: https://travis-ci.org/ownaginatious/python-caltrain.svg?branch=master
    :target: https://travis-ci.org/ownaginatious/python-caltrain/

.. |Coverage| image:: https://codecov.io/gh/ownaginatious/python-caltrain/branch/master/graph/badge.svg
  :target: https://codecov.io/gh/ownaginatious/python-caltrain

# -*- coding: utf-8 -*-
"""
Created on Tue May 11 15:31:31 2021

:copyright: 
    Jared Peacock (jpeacock@usgs.gov)

:license: MIT

"""
# =============================================================================
# Imports
# =============================================================================
from pathlib import Path
import pandas as pd
import numpy as np
import logging
from datetime import datetime

from mth5.timeseries import ChannelTS, RunTS
from mt_metadata.timeseries import Station, Run
from mt_metadata.utils.mttime import MTime

# =============================================================================
def lemi_date_parser(year, month, day, hour, minute, second):
    """
    convenience function to parse the date-time columns that are output by
    lemi

    :param year: DESCRIPTION
    :type year: TYPE
    :param month: DESCRIPTION
    :type month: TYPE
    :param day: DESCRIPTION
    :type day: TYPE
    :param hour: DESCRIPTION
    :type hour: TYPE
    :param minute: DESCRIPTION
    :type minute: TYPE
    :param second: DESCRIPTION
    :type second: TYPE
    :return: DESCRIPTION
    :rtype: TYPE

    """

    return pd.to_datetime(
        datetime(
            int(year),
            int(month),
            int(day),
            int(hour),
            int(minute),
            int(second),
        )
    )


def lemi_position_parser(position):
    """
    convenience function to parse the location strings
    :param position: DESCRIPTION
    :type position: TYPE
    :return: DESCRIPTION
    :rtype: TYPE

    """
    pos = f"{float(position) / 100}".split(".")
    degrees = int(pos[0])
    decimals = float(f"{pos[1][0:2]}.{pos[1][2:]}") / 60

    location = degrees + decimals
    return location


def lemi_hemisphere_parser(hemisphere):
    """
    convert hemisphere into a value [-1, 1]

    :param hemisphere: DESCRIPTION
    :type hemisphere: TYPE
    :return: DESCRIPTION
    :rtype: TYPE

    """
    if hemisphere in ["S", "W"]:
        return -1
    return 1


class LEMI424:
    """
    Read in a LEMI424 file, this is a place holder until IRIS finalizes
    their reader.

    """

    def __init__(self, fn=None):
        self.logger = logging.getLogger(
            f"{__name__}.{self.__class__.__name__}"
        )
        self.fn = fn
        self._has_data = False
        self.sample_rate = 1.0
        self.chunk_size = 10000
        self.column_names = [
            "year",
            "month",
            "day",
            "hour",
            "minute",
            "second",
            "bx",
            "by",
            "bz",
            "temperature_e",
            "temperature_h",
            "e1",
            "e2",
            "e3",
            "e4",
            "battery",
            "elevation",
            "latitude",
            "lat_hemisphere",
            "longitude",
            "lon_hemisphere",
            "n_satellites",
            "gps_fix",
            "tdiff",
        ]

        if self.fn:
            self.read()

    def __str__(self):
        lines = ["LEMI 424 data", "-" * 20]
        lines.append(f"start:      {self.start.isoformat()}")
        lines.append(f"end:        {self.end.isoformat()}")
        lines.append(f"N samples:  {self.n_samples}")
        lines.append(f"latitude:   {self.latitude} (degrees)")
        lines.append(f"longitude:  {self.longitude} (degrees)")
        lines.append(f"elevation:  {self.elevation} m")

        return "\n".join(lines)

    def __repr__(self):
        return self.__str__()

    @property
    def fn(self):
        return self._fn

    @fn.setter
    def fn(self, value):
        if value is not None:
            value = Path(value)
            if not value.exists():
                raise IOError(f"Could not find {value}")
        self._fn = value

    @property
    def start(self):
        if self._has_data:
            return MTime(self._df.index[0])

    @property
    def end(self):
        if self._has_data:
            return MTime(self._df.index[-1])

    @property
    def latitude(self):
        if self._has_data:

            return (
                self._df.latitude.median() * self._df.lat_hemisphere.median()
            )

    @property
    def longitude(self):
        if self._has_data:
            return (
                self._df.longitude.median() * self._df.lon_hemisphere.median()
            )

    @property
    def elevation(self):
        if self._has_data:
            return self._df.elevation.median()

    @property
    def n_samples(self):
        if self._has_data:
            return self._df.shape[0]

    @property
    def gps_lock(self):
        if self._has_data:
            return self._df.gps_fix.values

    @property
    def station_metadata(self):
        s = Station()
        if self._has_data:
            s.location.latitude = self.latitude
            s.location.longitude = self.longitude
            s.location.elevation = self.elevation
            s.time_period.start = self.start
            s.time_period.end = self.end
        return s

    @property
    def run_metadata(self):
        r = Run()
        r.sample_rate = self.sample_rate
        r.data_logger.model = "LEMI424"
        r.data_logger.manufacturer = "LEMI"
        if self._has_data:
            r.data_logger.power_source.voltage.start = self._df.battery.max()
            r.data_logger.power_source.voltage.end = self._df.battery.min()
            r.time_period.start = self.start
            r.time_period.end = self.end

    def read(self, fn=None):
        """
        Read a LEMI424 file using pandas

        :param fn: DESCRIPTION, defaults to None
        :type fn: TYPE, optional
        :return: DESCRIPTION
        :rtype: TYPE

        """
        if fn is not None:
            self.fn = fn

        if not self.fn.exists():
            msg = "Could not find file %s"
            self.logger.error(msg, self.fn)
            raise IOError(msg % self.fn)

        self._df = pd.read_csv(
            self.fn,
            delimiter="\s+",
            names=self.column_names,
            parse_dates={
                "date": ["year", "month", "day", "hour", "minute", "second"]
            },
            date_parser=lemi_date_parser,
            converters={
                "latitude": lemi_position_parser,
                "longitude": lemi_position_parser,
                "lat_hemisphere": lemi_hemisphere_parser,
                "lon_hemisphere": lemi_hemisphere_parser,
            },
            index_col="date",
        )

        self._has_data = True

    def to_run_ts(self, fn=None, e_channels=["e1", "e2"]):
        """
        Return a RunTS object from the data

        :param fn: DESCRIPTION, defaults to None
        :type fn: TYPE, optional
        :return: DESCRIPTION
        :rtype: TYPE

        """
        ch_list = []
        for comp in (
            ["bx", "by", "bz"]
            + e_channels
            + ["temperature_e", "temperature_h"]
        ):
            if comp[0] in ["h", "b"]:
                ch = ChannelTS("magnetic")
            elif comp[0] in ["e"]:
                ch = ChannelTS("electric")
            else:
                ch = ChannelTS("auxiliary")

            ch.sample_rate = self.sample_rate
            ch.start = self.start
            ch.ts = self._df[comp].values
            ch.component = comp
            ch_list.append(ch)

        return RunTS(
            array_list=ch_list,
            station_metadata=self.station_metadata,
            run_metadata=self.run_metadata,
        )


# =============================================================================
# define the reader
# =============================================================================
def read_lemi424(fn, e_channels=["e1", "e2"], logger_file_handler=None):
    """
    Read a LEMI 424 TXT file.

    :param fn: input file name
    :type fn: string or Path
    :param e_channels: A list of electric channels to read,
    defaults to ["e1", "e2"]
    :type e_channels: list of strings, optional
    :return: A RunTS object with appropriate metadata
    :rtype: :class:`mth5.timeseries.RunTS`

    """

    txt_obj = LEMI424()
    if logger_file_handler:
        txt_obj.logger.addHandler(logger_file_handler)
    txt_obj.read(fn)
    return txt_obj.to_run_ts(e_channels=e_channels)

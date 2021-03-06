# -*- coding: utf-8 -*-
"""
Task related test facilities.
"""

import datetime
import io
import json
import os
import tempfile
import unittest

from unittest import mock

from lxml import etree

from eidangservices import settings
from eidangservices.federator.server.task import (
    ETask, StationXMLNetworkCombinerTask, SplitAndAlignTask,
    WFCatalogSplitAndAlignTask, Result)
from eidangservices.utils import Route
from eidangservices.utils.request import RequestsError
from eidangservices.utils.sncl import Stream, StreamEpoch


# -----------------------------------------------------------------------------
class Response:

    def __init__(self, status_code=500, data=None):
        self.status_code = status_code
        self.data = data


class HTTP413(RequestsError):

    def __init__(self):
        self.response = Response(status_code=413,
                                 data='RequestTooLarge')


class HTTP500(RequestsError):

    def __init__(self):
        self.response = Response(status_code=500,
                                 data='InternalServerError')


# -----------------------------------------------------------------------------
# CombinerTask related test cases
class StationXMLNetworkCombinerTaskTestCase(unittest.TestCase):

    @staticmethod
    def create_task(*args, **kwargs):
        return StationXMLNetworkCombinerTask(*args, **kwargs)

    @staticmethod
    def serialize_net_elements(task):
        serialized = []
        for net_element, sta_elements in task._network_elements.values():
            serialized.append(
                task._serialize_net_element(net_element, sta_elements))

        return b''.join(serialized)

    @mock.patch('eidangservices.federator.server.task.'
                'StationXMLNetworkCombinerTask.MAX_THREADS_DOWNLOADING',
                new_callable=mock.PropertyMock)
    def test_extract_net_elements(self, mock_max_threads):
        mock_max_threads.return_value = 5
        mock_open = mock.mock_open(read_data=b'<?xml version="1.0" encoding="UTF-8"?><FDSNStationXML xmlns="http://www.fdsn.org/xml/station/1" schemaVersion="1.0"><Source>EIDA</Source><Created>2018-12-04T08:54:16.697388</Created><Network xmlns="http://www.fdsn.org/xml/station/1" code="CH" startDate="1980-01-01T00:00:00" restrictedStatus="open"><Description>National Seismic Networks of Switzerland</Description><Station code="BALST" startDate="2000-06-16T00:00:00" restrictedStatus="open"><Latitude>47.33578</Latitude><Longitude>7.69498</Longitude><Elevation>863</Elevation><Site><Name>Balsthal, SO</Name><Country>Switzerland</Country></Site><CreationDate>2000-06-16T00:00:00</CreationDate><Channel code="HHZ" startDate="2004-04-05T00:00:00" restrictedStatus="open" locationCode=""><Latitude>47.33578</Latitude><Longitude>7.69498</Longitude><Elevation>863</Elevation><Depth>4.5</Depth><Azimuth>0</Azimuth><Dip>-90</Dip><SampleRate>120</SampleRate><SampleRateRatio><NumberSamples>120</NumberSamples><NumberSeconds>1</NumberSeconds></SampleRateRatio><StorageFormat>Steim2</StorageFormat><ClockDrift>0</ClockDrift><Sensor resourceId="smi:ch.ethz.sed/Sensor/20150105111040.231924.93"><Type>Streckeisen STS2_gen3</Type><Manufacturer>Streckeisen</Manufacturer><Model>STS2_gen3</Model></Sensor><DataLogger resourceId="smi:ch.ethz.sed/Datalogger/20150105111040.23247.95"><Type>Nanometrics HRD24</Type><Manufacturer>Nanometrics</Manufacturer><Model>HRD24</Model></DataLogger><Response><InstrumentSensitivity><Value>627615000</Value><Frequency>1</Frequency><InputUnits><Name>M/S</Name></InputUnits><OutputUnits><Name/></OutputUnits></InstrumentSensitivity></Response></Channel></Station><Station code="DAVOX" startDate="2002-07-24T00:00:00" restrictedStatus="open"><Latitude>46.7805</Latitude><Longitude>9.87952</Longitude><Elevation>1830</Elevation><Site><Name>Davos, Dischmatal, GR</Name><Country>Switzerland</Country></Site><CreationDate>2002-07-24T00:00:00</CreationDate><Channel code="HHZ" startDate="2004-02-20T00:00:00" restrictedStatus="open" locationCode=""><Latitude>46.7805</Latitude><Longitude>9.87952</Longitude><Elevation>1830</Elevation><Depth>1.5</Depth><Azimuth>0</Azimuth><Dip>-90</Dip><SampleRate>120</SampleRate><SampleRateRatio><NumberSamples>120</NumberSamples><NumberSeconds>1</NumberSeconds></SampleRateRatio><StorageFormat>Steim2</StorageFormat><ClockDrift>0</ClockDrift><Sensor resourceId="smi:ch.ethz.sed/Sensor/20150105111043.257077.132"><Type>Streckeisen STS2_gen3</Type><Manufacturer>Streckeisen</Manufacturer><Model>STS2_gen3</Model></Sensor><DataLogger resourceId="smi:ch.ethz.sed/Datalogger/20150105111043.257697.134"><Type>Nanometrics Trident</Type><Manufacturer>Nanometrics</Manufacturer><Model>Trident</Model></DataLogger><Response><InstrumentSensitivity><Value>600000000</Value><Frequency>1</Frequency><InputUnits><Name>M/S</Name></InputUnits><OutputUnits><Name/></OutputUnits></InstrumentSensitivity></Response></Channel></Station></Network></FDSNStationXML>')  # noqa

        routes = [Route(url='http://eida.ethz.ch/fdsnws/station/1/query',
                        streams=[StreamEpoch(
                            Stream(network='CH', station='BALST', location='',
                                   channel='HHZ'),
                            starttime=datetime.datetime(2018, 1, 1),
                            endtime=datetime.datetime(2018, 1, 2))]),
                  Route(url='http://eida.ethz.ch/fdsnws/station/1/query',
                        streams=[StreamEpoch(
                            Stream(network='CH', station='DAVOX', location='',
                                   channel='HHZ'),
                            starttime=datetime.datetime(2018, 1, 1),
                            endtime=datetime.datetime(2018, 1, 2))])]

        query_params = {'format': 'xml',
                        'level': 'channel'}

        t = self.create_task(routes, query_params)
        # XXX(damb): Using *open* from future requires mocking the function
        # within the module it is actually used.
        with mock.patch(
                'eidangservices.federator.server.task.open', mock_open):
            net_element = next(t._extract_net_elements(
                path_xml='/path/to/station.xml'))

            # check the order of the sta elements
            self.assertEqual(
                net_element[0].tag,
                settings.STATIONXML_NAMESPACES[0] + 'Description')
            self.assertEqual(net_element[1].get('code'), 'BALST')
            self.assertEqual(net_element[2].get('code'), 'DAVOX')

        mock_max_threads.has_calls()

    @mock.patch('eidangservices.federator.server.task.'
                'StationXMLNetworkCombinerTask.MAX_THREADS_DOWNLOADING',
                new_callable=mock.PropertyMock)
    def test_merge_sta_element_sta_append(self, mock_max_threads):
        mock_max_threads.return_value = 5

        routes = [Route(url='http://eida.ethz.ch/fdsnws/station/1/query',
                        streams=[StreamEpoch(
                            Stream(network='CH', station='DAVOX', location='',
                                   channel='HHZ'),
                            starttime=datetime.datetime(2018, 1, 1),
                            endtime=datetime.datetime(2018, 1, 2))]),
                  Route(url='http://eida.ethz.ch/fdsnws/station/1/query',
                        streams=[StreamEpoch(
                            Stream(network='CH', station='BALST', location='',
                                   channel='HHZ'),
                            starttime=datetime.datetime(2018, 1, 1),
                            endtime=datetime.datetime(2018, 1, 2))])]

        query_params = {'format': 'xml',
                        'level': 'channel'}

        davox_xml = b'<Network code="CH" startDate="1980-01-01T00:00:00" restrictedStatus="open"><Description>National Seismic Networks of Switzerland</Description><Station code="DAVOX" startDate="2002-07-24T00:00:00" restrictedStatus="open"><Latitude>46.7805</Latitude><Longitude>9.87952</Longitude><Elevation>1830</Elevation><Site><Name>Davos, Dischmatal, GR</Name><Country>Switzerland</Country></Site><CreationDate>2002-07-24T00:00:00</CreationDate><Channel code="HHZ" startDate="2004-02-20T00:00:00" restrictedStatus="open" locationCode=""><Latitude>46.7805</Latitude><Longitude>9.87952</Longitude><Elevation>1830</Elevation><Depth>1.5</Depth><Azimuth>0</Azimuth><Dip>-90</Dip><SampleRate>120</SampleRate><SampleRateRatio><NumberSamples>120</NumberSamples><NumberSeconds>1</NumberSeconds></SampleRateRatio><StorageFormat>Steim2</StorageFormat><ClockDrift>0</ClockDrift><Sensor resourceId="smi:ch.ethz.sed/Sensor/20150105111043.257077.132"><Type>Streckeisen STS2_gen3</Type><Manufacturer>Streckeisen</Manufacturer><Model>STS2_gen3</Model></Sensor><DataLogger resourceId="smi:ch.ethz.sed/Datalogger/20150105111043.257697.134"><Type>Nanometrics Trident</Type><Manufacturer>Nanometrics</Manufacturer><Model>Trident</Model></DataLogger><Response><InstrumentSensitivity><Value>600000000</Value><Frequency>1</Frequency><InputUnits><Name>M/S</Name></InputUnits><OutputUnits><Name/></OutputUnits></InstrumentSensitivity></Response></Channel></Station></Network>'  # noqa
        balst_xml = b'<Network code="CH" startDate="1980-01-01T00:00:00" restrictedStatus="open"><Description>National Seismic Networks of Switzerland</Description><Station code="BALST" startDate="2000-06-16T00:00:00" restrictedStatus="open"><Latitude>47.33578</Latitude><Longitude>7.69498</Longitude><Elevation>863</Elevation><Site><Name>Balsthal, SO</Name><Country>Switzerland</Country></Site><CreationDate>2000-06-16T00:00:00</CreationDate><Channel code="HHZ" startDate="2004-04-05T00:00:00" restrictedStatus="open" locationCode=""><Latitude>47.33578</Latitude><Longitude>7.69498</Longitude><Elevation>863</Elevation><Depth>4.5</Depth><Azimuth>0</Azimuth><Dip>-90</Dip><SampleRate>120</SampleRate><SampleRateRatio><NumberSamples>120</NumberSamples><NumberSeconds>1</NumberSeconds></SampleRateRatio><StorageFormat>Steim2</StorageFormat><ClockDrift>0</ClockDrift><Sensor resourceId="smi:ch.ethz.sed/Sensor/20150105111040.231924.93"><Type>Streckeisen STS2_gen3</Type><Manufacturer>Streckeisen</Manufacturer><Model>STS2_gen3</Model></Sensor><DataLogger resourceId="smi:ch.ethz.sed/Datalogger/20150105111040.23247.95"><Type>Nanometrics HRD24</Type><Manufacturer>Nanometrics</Manufacturer><Model>HRD24</Model></DataLogger><Response><InstrumentSensitivity><Value>627615000</Value><Frequency>1</Frequency><InputUnits><Name>M/S</Name></InputUnits><OutputUnits><Name/></OutputUnits></InstrumentSensitivity></Response></Channel></Station></Network>'  # noqa
        ch_davox = etree.fromstring(davox_xml)
        ch_balst = etree.fromstring(balst_xml)

        t = self.create_task(routes, query_params)
        namespaces = ('',)
        t._merge_net_element(ch_davox, level='channel', namespaces=namespaces)
        t._merge_net_element(ch_balst, level='channel', namespaces=namespaces)

        reference_xml = b'<Network code="CH" startDate="1980-01-01T00:00:00" restrictedStatus="open"><Description>National Seismic Networks of Switzerland</Description><Station code="DAVOX" startDate="2002-07-24T00:00:00" restrictedStatus="open"><Latitude>46.7805</Latitude><Longitude>9.87952</Longitude><Elevation>1830</Elevation><Site><Name>Davos, Dischmatal, GR</Name><Country>Switzerland</Country></Site><CreationDate>2002-07-24T00:00:00</CreationDate><Channel code="HHZ" startDate="2004-02-20T00:00:00" restrictedStatus="open" locationCode=""><Latitude>46.7805</Latitude><Longitude>9.87952</Longitude><Elevation>1830</Elevation><Depth>1.5</Depth><Azimuth>0</Azimuth><Dip>-90</Dip><SampleRate>120</SampleRate><SampleRateRatio><NumberSamples>120</NumberSamples><NumberSeconds>1</NumberSeconds></SampleRateRatio><StorageFormat>Steim2</StorageFormat><ClockDrift>0</ClockDrift><Sensor resourceId="smi:ch.ethz.sed/Sensor/20150105111043.257077.132"><Type>Streckeisen STS2_gen3</Type><Manufacturer>Streckeisen</Manufacturer><Model>STS2_gen3</Model></Sensor><DataLogger resourceId="smi:ch.ethz.sed/Datalogger/20150105111043.257697.134"><Type>Nanometrics Trident</Type><Manufacturer>Nanometrics</Manufacturer><Model>Trident</Model></DataLogger><Response><InstrumentSensitivity><Value>600000000</Value><Frequency>1</Frequency><InputUnits><Name>M/S</Name></InputUnits><OutputUnits><Name/></OutputUnits></InstrumentSensitivity></Response></Channel></Station><Station code="BALST" startDate="2000-06-16T00:00:00" restrictedStatus="open"><Latitude>47.33578</Latitude><Longitude>7.69498</Longitude><Elevation>863</Elevation><Site><Name>Balsthal, SO</Name><Country>Switzerland</Country></Site><CreationDate>2000-06-16T00:00:00</CreationDate><Channel code="HHZ" startDate="2004-04-05T00:00:00" restrictedStatus="open" locationCode=""><Latitude>47.33578</Latitude><Longitude>7.69498</Longitude><Elevation>863</Elevation><Depth>4.5</Depth><Azimuth>0</Azimuth><Dip>-90</Dip><SampleRate>120</SampleRate><SampleRateRatio><NumberSamples>120</NumberSamples><NumberSeconds>1</NumberSeconds></SampleRateRatio><StorageFormat>Steim2</StorageFormat><ClockDrift>0</ClockDrift><Sensor resourceId="smi:ch.ethz.sed/Sensor/20150105111040.231924.93"><Type>Streckeisen STS2_gen3</Type><Manufacturer>Streckeisen</Manufacturer><Model>STS2_gen3</Model></Sensor><DataLogger resourceId="smi:ch.ethz.sed/Datalogger/20150105111040.23247.95"><Type>Nanometrics HRD24</Type><Manufacturer>Nanometrics</Manufacturer><Model>HRD24</Model></DataLogger><Response><InstrumentSensitivity><Value>627615000</Value><Frequency>1</Frequency><InputUnits><Name>M/S</Name></InputUnits><OutputUnits><Name/></OutputUnits></InstrumentSensitivity></Response></Channel></Station></Network>'  # noqa

        self.assertEqual(self.serialize_net_elements(t), reference_xml)
        mock_max_threads.has_calls()

    @mock.patch('eidangservices.federator.server.task.'
                'StationXMLNetworkCombinerTask.MAX_THREADS_DOWNLOADING',
                new_callable=mock.PropertyMock)
    def test_merge_sta_element_sta_extend(self, mock_max_threads):
        mock_max_threads.return_value = 5

        routes = [Route(url='http://eida.ethz.ch/fdsnws/station/1/query',
                        streams=[StreamEpoch(
                            Stream(network='CH', station='DAVOX', location='',
                                   channel='HHZ'),
                            starttime=datetime.datetime(2018, 1, 1),
                            endtime=datetime.datetime(2018, 1, 2))]),
                  Route(url='http://eida.ethz.ch/fdsnws/station/1/query',
                        streams=[StreamEpoch(
                            Stream(network='CH', station='DAVOX', location='',
                                   channel='BHZ'),
                            starttime=datetime.datetime(2018, 1, 1),
                            endtime=datetime.datetime(2018, 1, 2))])]

        query_params = {'format': 'xml',
                        'level': 'channel'}

        davox_bhz_xml = b'<Network code="CH" startDate="1980-01-01T00:00:00" restrictedStatus="open"><Description>National Seismic Networks of Switzerland</Description><Station code="DAVOX" startDate="2002-07-24T00:00:00" restrictedStatus="open"><Latitude>46.7805</Latitude><Longitude>9.87952</Longitude><Elevation>1830</Elevation><Site><Name>Davos, Dischmatal, GR</Name><Country>Switzerland</Country></Site><CreationDate>2002-07-24T00:00:00</CreationDate><Channel code="BHZ" startDate="2004-02-20T00:00:00" restrictedStatus="open" locationCode=""><Latitude>46.7805</Latitude><Longitude>9.87952</Longitude><Elevation>1830</Elevation><Depth>1.5</Depth><Azimuth>0</Azimuth><Dip>-90</Dip><SampleRate>40</SampleRate><SampleRateRatio><NumberSamples>40</NumberSamples><NumberSeconds>1</NumberSeconds></SampleRateRatio><StorageFormat>Steim2</StorageFormat><ClockDrift>0</ClockDrift><Sensor resourceId="smi:ch.ethz.sed/Sensor/20150105111043.257077.132"><Type>Streckeisen STS2_gen3</Type><Manufacturer>Streckeisen</Manufacturer><Model>STS2_gen3</Model></Sensor><DataLogger resourceId="smi:ch.ethz.sed/Datalogger/20150105111043.248921.110"><Type>Nanometrics Trident</Type><Manufacturer>Nanometrics</Manufacturer><Model>Trident</Model></DataLogger><Response><InstrumentSensitivity><Value>600000000</Value><Frequency>1</Frequency><InputUnits><Name>M/S</Name></InputUnits><OutputUnits><Name/></OutputUnits></InstrumentSensitivity></Response></Channel></Station></Network>'  # noqa
        davox_hhz_xml = b'<Network code="CH" startDate="1980-01-01T00:00:00" restrictedStatus="open"><Description>National Seismic Networks of Switzerland</Description><Station code="DAVOX" startDate="2002-07-24T00:00:00" restrictedStatus="open"><Latitude>46.7805</Latitude><Longitude>9.87952</Longitude><Elevation>1830</Elevation><Site><Name>Davos, Dischmatal, GR</Name><Country>Switzerland</Country></Site><CreationDate>2002-07-24T00:00:00</CreationDate><Channel code="HHZ" startDate="2004-02-20T00:00:00" restrictedStatus="open" locationCode=""><Latitude>46.7805</Latitude><Longitude>9.87952</Longitude><Elevation>1830</Elevation><Depth>1.5</Depth><Azimuth>0</Azimuth><Dip>-90</Dip><SampleRate>120</SampleRate><SampleRateRatio><NumberSamples>120</NumberSamples><NumberSeconds>1</NumberSeconds></SampleRateRatio><StorageFormat>Steim2</StorageFormat><ClockDrift>0</ClockDrift><Sensor resourceId="smi:ch.ethz.sed/Sensor/20150105111043.257077.132"><Type>Streckeisen STS2_gen3</Type><Manufacturer>Streckeisen</Manufacturer><Model>STS2_gen3</Model></Sensor><DataLogger resourceId="smi:ch.ethz.sed/Datalogger/20150105111043.257697.134"><Type>Nanometrics Trident</Type><Manufacturer>Nanometrics</Manufacturer><Model>Trident</Model></DataLogger><Response><InstrumentSensitivity><Value>600000000</Value><Frequency>1</Frequency><InputUnits><Name>M/S</Name></InputUnits><OutputUnits><Name/></OutputUnits></InstrumentSensitivity></Response></Channel></Station></Network>'  # noqa

        t = self.create_task(routes, query_params)

        davox_bhz = etree.fromstring(davox_bhz_xml)
        davox_hhz = etree.fromstring(davox_hhz_xml)

        t = self.create_task(routes, query_params)
        namespaces = ('',)
        t._merge_net_element(davox_bhz, level='channel', namespaces=namespaces)
        t._merge_net_element(davox_hhz, level='channel', namespaces=namespaces)

        reference_xml = b'<Network code="CH" startDate="1980-01-01T00:00:00" restrictedStatus="open"><Description>National Seismic Networks of Switzerland</Description><Station code="DAVOX" startDate="2002-07-24T00:00:00" restrictedStatus="open"><Latitude>46.7805</Latitude><Longitude>9.87952</Longitude><Elevation>1830</Elevation><Site><Name>Davos, Dischmatal, GR</Name><Country>Switzerland</Country></Site><CreationDate>2002-07-24T00:00:00</CreationDate><Channel code="BHZ" startDate="2004-02-20T00:00:00" restrictedStatus="open" locationCode=""><Latitude>46.7805</Latitude><Longitude>9.87952</Longitude><Elevation>1830</Elevation><Depth>1.5</Depth><Azimuth>0</Azimuth><Dip>-90</Dip><SampleRate>40</SampleRate><SampleRateRatio><NumberSamples>40</NumberSamples><NumberSeconds>1</NumberSeconds></SampleRateRatio><StorageFormat>Steim2</StorageFormat><ClockDrift>0</ClockDrift><Sensor resourceId="smi:ch.ethz.sed/Sensor/20150105111043.257077.132"><Type>Streckeisen STS2_gen3</Type><Manufacturer>Streckeisen</Manufacturer><Model>STS2_gen3</Model></Sensor><DataLogger resourceId="smi:ch.ethz.sed/Datalogger/20150105111043.248921.110"><Type>Nanometrics Trident</Type><Manufacturer>Nanometrics</Manufacturer><Model>Trident</Model></DataLogger><Response><InstrumentSensitivity><Value>600000000</Value><Frequency>1</Frequency><InputUnits><Name>M/S</Name></InputUnits><OutputUnits><Name/></OutputUnits></InstrumentSensitivity></Response></Channel><Channel code="HHZ" startDate="2004-02-20T00:00:00" restrictedStatus="open" locationCode=""><Latitude>46.7805</Latitude><Longitude>9.87952</Longitude><Elevation>1830</Elevation><Depth>1.5</Depth><Azimuth>0</Azimuth><Dip>-90</Dip><SampleRate>120</SampleRate><SampleRateRatio><NumberSamples>120</NumberSamples><NumberSeconds>1</NumberSeconds></SampleRateRatio><StorageFormat>Steim2</StorageFormat><ClockDrift>0</ClockDrift><Sensor resourceId="smi:ch.ethz.sed/Sensor/20150105111043.257077.132"><Type>Streckeisen STS2_gen3</Type><Manufacturer>Streckeisen</Manufacturer><Model>STS2_gen3</Model></Sensor><DataLogger resourceId="smi:ch.ethz.sed/Datalogger/20150105111043.257697.134"><Type>Nanometrics Trident</Type><Manufacturer>Nanometrics</Manufacturer><Model>Trident</Model></DataLogger><Response><InstrumentSensitivity><Value>600000000</Value><Frequency>1</Frequency><InputUnits><Name>M/S</Name></InputUnits><OutputUnits><Name/></OutputUnits></InstrumentSensitivity></Response></Channel></Station></Network>'  # noqa

        self.assertEqual(self.serialize_net_elements(t), reference_xml)
        mock_max_threads.has_calls()


# -----------------------------------------------------------------------------
# SplitAndAlign task related test cases
class SplitAndAlignTaskTestCase(unittest.TestCase):

    def setUp(self):
        self.stream = Stream(network='CH', station='DAVOX', location='',
                             channel='HHZ')
        self.url = 'http://eida.ethz.ch/fdsnws/dataselect/1/query'
        self.query_params = {}

    def tearDown(self):
        self.url = None
        self.query_params = None

    def test_split_once(self):
        stream_epoch = StreamEpoch(
            stream=self.stream,
            starttime=datetime.datetime(2018, 1, 1),
            endtime=datetime.datetime(2018, 1, 8))

        reference_result = [
            StreamEpoch(
                stream=self.stream,
                starttime=datetime.datetime(2018, 1, 1),
                endtime=datetime.datetime(2018, 1, 4, 12)),
            StreamEpoch(
                stream=self.stream,
                starttime=datetime.datetime(2018, 1, 4, 12),
                endtime=datetime.datetime(2018, 1, 8))]

        # NOTE(damb): Use the same stream epoch both for testing the splitting
        # method as well as for task initialization. In case of just testing
        # splitting we could have used any arbitrary stream epoch for task
        # initialization.

        t = SplitAndAlignTask(self.url, stream_epoch, self.query_params)
        self.assertEqual(t.split(stream_epoch, t.DEFAULT_SPLITTING_CONST),
                         reference_result)
        self.assertEqual(t.stream_epochs, reference_result)

    def test_split_multiple(self):
        stream_epoch_orig = StreamEpoch(
            stream=self.stream,
            starttime=datetime.datetime(2018, 1, 1),
            endtime=datetime.datetime(2018, 1, 8))

        sub_reference_result = [
            StreamEpoch(
                stream=self.stream,
                starttime=datetime.datetime(2018, 1, 1),
                endtime=datetime.datetime(2018, 1, 2, 18)),
            StreamEpoch(
                stream=self.stream,
                starttime=datetime.datetime(2018, 1, 2, 18),
                endtime=datetime.datetime(2018, 1, 4, 12))]
        reference_result = (
            sub_reference_result +
            [StreamEpoch(
                stream=self.stream,
                starttime=datetime.datetime(2018, 1, 4, 12),
                endtime=datetime.datetime(2018, 1, 8))])

        # NOTE(damb): Use the same stream epoch both for testing the splitting
        # method as well as for task initialization. In case of just testing
        # splitting we could have used any arbitrary stream epoch for task
        # initialization.

        t = SplitAndAlignTask(self.url, stream_epoch_orig, self.query_params)
        stream_epochs = t.split(stream_epoch_orig, t.DEFAULT_SPLITTING_CONST)
        sub_stream_epochs = t.split(stream_epochs[0],
                                    t.DEFAULT_SPLITTING_CONST)

        self.assertEqual(sub_stream_epochs, sub_reference_result)
        self.assertEqual(t.stream_epochs, reference_result)


class WFCatalogSAATaskTestCase(unittest.TestCase):

    def setUp(self):
        _, self.path_tempfile = tempfile.mkstemp()

        self.stream = Stream(network='CH', station='DAVOX', location='',
                             channel='HHZ')
        self.url = 'http://eida.ethz.ch/fdsnws/dataselect/1/query'
        self.query_params = {}

    def tearDown(self):
        try:
            os.remove(self.path_tempfile)
        except OSError:
            pass
        self.path_tempfile = None

    @mock.patch.object(
        WFCatalogSplitAndAlignTask, 'get_cretry_budget_error_ratio',
        return_value=0)
    @mock.patch.object(
        WFCatalogSplitAndAlignTask, 'update_cretry_budget')
    @mock.patch('eidangservices.federator.server.task.raw_request')
    @mock.patch('eidangservices.federator.server.task.get_temp_filepath')
    def test_split_missing(
        self, mock_get_temp_filepath, mock_raw_request, mock_method_update,
            mock_method_eratio):

        err = HTTP500()
        mock_get_temp_filepath.return_value = self.path_tempfile
        mock_raw_request.side_effect = [
            io.BytesIO(b'[{"version":"1.0.0","producer":{"name":"SED","agent":"ObsPy mSEED-QC","created":"2018-01-10T18:19:25.563Z"},"station":"DAVOX","network":"CH","location":"","channel":"LHZ","num_gaps":0,"num_overlaps":2,"sum_gaps":0,"sum_overlaps":161,"max_gap":null,"max_overlap":161,"record_length":[512],"sample_rate":[1],"percent_availability":100,"encoding":["STEIM2"],"num_records":313,"start_time":"2018-01-01T00:00:00.000Z","end_time":"2018-01-02T00:00:00.000Z","format":"miniSEED","quality":"D"}]'), # noqa
            err]

        reference_result = Result.error('EndpointError',
                                        err.response.status_code,
                                        data=err.response.data,
                                        warning=str(err),
                                        extras={'type_task': ETask.SPLITALIGN})

        stream_epoch_orig = StreamEpoch(
            stream=self.stream,
            starttime=datetime.datetime(2018, 1, 1),
            endtime=datetime.datetime(2018, 1, 3))

        task = WFCatalogSplitAndAlignTask(self.url, stream_epoch_orig,
                                          self.query_params)

        result = task()
        self.assertEqual(result, reference_result)
        mock_raw_request.has_calls()

    @mock.patch.object(
        WFCatalogSplitAndAlignTask, 'get_cretry_budget_error_ratio',
        return_value=0)
    @mock.patch.object(
        WFCatalogSplitAndAlignTask, 'update_cretry_budget')
    @mock.patch('eidangservices.federator.server.task.raw_request')
    @mock.patch('eidangservices.federator.server.task.get_temp_filepath')
    def test_split_single_without_overlap(
        self, mock_get_temp_filepath, mock_raw_request, mock_method_update,
            mock_method_eratio):

        mock_get_temp_filepath.return_value = self.path_tempfile
        mock_raw_request.side_effect = [
            io.BytesIO(b'[{"version":"1.0.0","producer":{"name":"SED","agent":"ObsPy mSEED-QC","created":"2018-01-10T18:19:25.563Z"},"station":"DAVOX","network":"CH","location":"","channel":"LHZ","num_gaps":0,"num_overlaps":2,"sum_gaps":0,"sum_overlaps":161,"max_gap":null,"max_overlap":161,"record_length":[512],"sample_rate":[1],"percent_availability":100,"encoding":["STEIM2"],"num_records":313,"start_time":"2018-01-01T00:00:00.000Z","end_time":"2018-01-02T00:00:00.000Z","format":"miniSEED","quality":"D"}]'), # noqa
            io.BytesIO(b'[{"version":"1.0.0","producer":{"name":"SED","agent":"ObsPy mSEED-QC","created":"2018-01-10T18:19:43.021Z"},"station":"DAVOX","network":"CH","location":"","channel":"LHZ","num_gaps":0,"num_overlaps":2,"sum_gaps":0,"sum_overlaps":251,"max_gap":null,"max_overlap":251,"record_length":[512],"sample_rate":[1],"percent_availability":100,"encoding":["STEIM2"],"num_records":301,"start_time":"2018-01-02T00:00:00.000Z","end_time":"2018-01-03T00:00:00.000Z","format":"miniSEED","quality":"D"}]')] # noqa

        reference_result = json.loads(
            '[{"version":"1.0.0","producer":{"name":"SED","agent":"ObsPy mSEED-QC","created":"2018-01-10T18:19:25.563Z"},"station":"DAVOX","network":"CH","location":"","channel":"LHZ","num_gaps":0,"num_overlaps":2,"sum_gaps":0,"sum_overlaps":161,"max_gap":null,"max_overlap":161,"record_length":[512],"sample_rate":[1],"percent_availability":100,"encoding":["STEIM2"],"num_records":313,"start_time":"2018-01-01T00:00:00.000Z","end_time":"2018-01-02T00:00:00.000Z","format":"miniSEED","quality":"D"},{"version":"1.0.0","producer":{"name":"SED","agent":"ObsPy mSEED-QC","created":"2018-01-10T18:19:43.021Z"},"station":"DAVOX","network":"CH","location":"","channel":"LHZ","num_gaps":0,"num_overlaps":2,"sum_gaps":0,"sum_overlaps":251,"max_gap":null,"max_overlap":251,"record_length":[512],"sample_rate":[1],"percent_availability":100,"encoding":["STEIM2"],"num_records":301,"start_time":"2018-01-02T00:00:00.000Z","end_time":"2018-01-03T00:00:00.000Z","format":"miniSEED","quality":"D"}]') # noqa

        stream_epoch_orig = StreamEpoch(
            stream=self.stream,
            starttime=datetime.datetime(2018, 1, 1),
            endtime=datetime.datetime(2018, 1, 3))

        result = WFCatalogSplitAndAlignTask(self.url, stream_epoch_orig,
                                            self.query_params)()
        data = None
        with open(result.data, 'rb') as ifd:
            data = json.loads(ifd.read().decode('utf-8'))

        self.assertEqual(data, reference_result)
        mock_raw_request.has_calls()

    @mock.patch.object(
        WFCatalogSplitAndAlignTask, 'get_cretry_budget_error_ratio',
        return_value=0)
    @mock.patch.object(
        WFCatalogSplitAndAlignTask, 'update_cretry_budget')
    @mock.patch('eidangservices.federator.server.task.raw_request')
    @mock.patch('eidangservices.federator.server.task.get_temp_filepath')
    def test_split_single_with_overlap(
        self, mock_get_temp_filepath, mock_raw_request, mock_method_update,
            mock_method_eratio):

        mock_get_temp_filepath.return_value = self.path_tempfile
        mock_raw_request.side_effect = [
            io.BytesIO(b'[{"version":"1.0.0","producer":{"name":"SED","agent":"ObsPy mSEED-QC","created":"2018-01-10T18:19:25.563Z"},"station":"DAVOX","network":"CH","location":"","channel":"LHZ","num_gaps":0,"num_overlaps":2,"sum_gaps":0,"sum_overlaps":161,"max_gap":null,"max_overlap":161,"record_length":[512],"sample_rate":[1],"percent_availability":100,"encoding":["STEIM2"],"num_records":313,"start_time":"2018-01-01T00:00:00.000Z","end_time":"2018-01-02T00:00:00.000Z","format":"miniSEED","quality":"D"},{"version":"1.0.0","producer":{"name":"SED","agent":"ObsPy mSEED-QC","created":"2018-01-10T18:19:43.021Z"},"station":"DAVOX","network":"CH","location":"","channel":"LHZ","num_gaps":0,"num_overlaps":2,"sum_gaps":0,"sum_overlaps":251,"max_gap":null,"max_overlap":251,"record_length":[512],"sample_rate":[1],"percent_availability":100,"encoding":["STEIM2"],"num_records":301,"start_time":"2018-01-02T00:00:00.000Z","end_time":"2018-01-03T00:00:00.000Z","format":"miniSEED","quality":"D"}]'), # noqa
            io.BytesIO(b'[{"version":"1.0.0","producer":{"name":"SED","agent":"ObsPy mSEED-QC","created":"2018-01-10T18:19:43.021Z"},"station":"DAVOX","network":"CH","location":"","channel":"LHZ","num_gaps":0,"num_overlaps":2,"sum_gaps":0,"sum_overlaps":251,"max_gap":null,"max_overlap":251,"record_length":[512],"sample_rate":[1],"percent_availability":100,"encoding":["STEIM2"],"num_records":301,"start_time":"2018-01-02T00:00:00.000Z","end_time":"2018-01-03T00:00:00.000Z","format":"miniSEED","quality":"D"}]')] # noqa

        reference_result = json.loads(
            '[{"version":"1.0.0","producer":{"name":"SED","agent":"ObsPy mSEED-QC","created":"2018-01-10T18:19:25.563Z"},"station":"DAVOX","network":"CH","location":"","channel":"LHZ","num_gaps":0,"num_overlaps":2,"sum_gaps":0,"sum_overlaps":161,"max_gap":null,"max_overlap":161,"record_length":[512],"sample_rate":[1],"percent_availability":100,"encoding":["STEIM2"],"num_records":313,"start_time":"2018-01-01T00:00:00.000Z","end_time":"2018-01-02T00:00:00.000Z","format":"miniSEED","quality":"D"},{"version":"1.0.0","producer":{"name":"SED","agent":"ObsPy mSEED-QC","created":"2018-01-10T18:19:43.021Z"},"station":"DAVOX","network":"CH","location":"","channel":"LHZ","num_gaps":0,"num_overlaps":2,"sum_gaps":0,"sum_overlaps":251,"max_gap":null,"max_overlap":251,"record_length":[512],"sample_rate":[1],"percent_availability":100,"encoding":["STEIM2"],"num_records":301,"start_time":"2018-01-02T00:00:00.000Z","end_time":"2018-01-03T00:00:00.000Z","format":"miniSEED","quality":"D"}]') # noqa

        stream_epoch_orig = StreamEpoch(
            stream=self.stream,
            starttime=datetime.datetime(2018, 1, 1),
            endtime=datetime.datetime(2018, 1, 3))

        result = WFCatalogSplitAndAlignTask(self.url, stream_epoch_orig,
                                            self.query_params)()
        data = None
        with open(result.data, 'rb') as ifd:
            data = json.loads(ifd.read().decode('utf-8'))

        self.assertEqual(data, reference_result)
        mock_raw_request.has_calls()

    @mock.patch.object(
        WFCatalogSplitAndAlignTask, 'get_cretry_budget_error_ratio',
        return_value=0)
    @mock.patch.object(
        WFCatalogSplitAndAlignTask, 'update_cretry_budget')
    @mock.patch('eidangservices.federator.server.task.raw_request')
    @mock.patch('eidangservices.federator.server.task.get_temp_filepath')
    def test_split_multiple_without_overlap(
        self, mock_get_temp_filepath, mock_raw_request, mock_method_update,
            mock_method_eratio):
        # NOTE(damb): We do not care about stream epoch splitting. We simply
        # test the task's aligning facilities.
        mock_get_temp_filepath.return_value = self.path_tempfile
        mock_raw_request.side_effect = [
            HTTP413(),
            io.BytesIO(b'[{"version":"1.0.0","producer":{"name":"SED","agent":"ObsPy mSEED-QC","created":"2018-01-10T18:19:25.563Z"},"station":"DAVOX","network":"CH","location":"","channel":"LHZ","num_gaps":0,"num_overlaps":2,"sum_gaps":0,"sum_overlaps":161,"max_gap":null,"max_overlap":161,"record_length":[512],"sample_rate":[1],"percent_availability":100,"encoding":["STEIM2"],"num_records":313,"start_time":"2018-01-01T00:00:00.000Z","end_time":"2018-01-02T00:00:00.000Z","format":"miniSEED","quality":"D"}]'), # noqa
            io.BytesIO(b'[{"version":"1.0.0","producer":{"name":"SED","agent":"ObsPy mSEED-QC","created":"2018-01-10T18:19:43.021Z"},"station":"DAVOX","network":"CH","location":"","channel":"LHZ","num_gaps":0,"num_overlaps":2,"sum_gaps":0,"sum_overlaps":251,"max_gap":null,"max_overlap":251,"record_length":[512],"sample_rate":[1],"percent_availability":100,"encoding":["STEIM2"],"num_records":301,"start_time":"2018-01-02T00:00:00.000Z","end_time":"2018-01-03T00:00:00.000Z","format":"miniSEED","quality":"D"}]'), # noqa
            io.BytesIO(b'[{"version":"1.0.0","producer":{"name":"SED","agent":"ObsPy mSEED-QC","created":"2018-01-10T18:19:59.201Z"},"station":"DAVOX","network":"CH","location":"","channel":"LHZ","num_gaps":0,"num_overlaps":1,"sum_gaps":0,"sum_overlaps":175,"max_gap":null,"max_overlap":175,"record_length":[512],"sample_rate":[1],"percent_availability":100,"encoding":["STEIM2"],"num_records":352,"start_time":"2018-01-03T00:00:00.000Z","end_time":"2018-01-04T00:00:00.000Z","format":"miniSEED","quality":"D"},{"version":"1.0.0","producer":{"name":"SED","agent":"ObsPy mSEED-QC","created":"2018-01-11T10:16:43.104Z"},"station":"DAVOX","network":"CH","location":"","channel":"LHZ","num_gaps":0,"num_overlaps":1,"sum_gaps":0,"sum_overlaps":0,"max_gap":null,"max_overlap":0,"record_length":[512],"sample_rate":[1],"percent_availability":100,"encoding":["STEIM2"],"num_records":320,"start_time":"2018-01-04T00:00:00.000Z","end_time":"2018-01-05T00:00:00.000Z","format":"miniSEED","quality":"D"}]')] # noqa

        reference_result = json.loads(
            '[{"version":"1.0.0","producer":{"name":"SED","agent":"ObsPy mSEED-QC","created":"2018-01-10T18:19:25.563Z"},"station":"DAVOX","network":"CH","location":"","channel":"LHZ","num_gaps":0,"num_overlaps":2,"sum_gaps":0,"sum_overlaps":161,"max_gap":null,"max_overlap":161,"record_length":[512],"sample_rate":[1],"percent_availability":100,"encoding":["STEIM2"],"num_records":313,"start_time":"2018-01-01T00:00:00.000Z","end_time":"2018-01-02T00:00:00.000Z","format":"miniSEED","quality":"D"},{"version":"1.0.0","producer":{"name":"SED","agent":"ObsPy mSEED-QC","created":"2018-01-10T18:19:43.021Z"},"station":"DAVOX","network":"CH","location":"","channel":"LHZ","num_gaps":0,"num_overlaps":2,"sum_gaps":0,"sum_overlaps":251,"max_gap":null,"max_overlap":251,"record_length":[512],"sample_rate":[1],"percent_availability":100,"encoding":["STEIM2"],"num_records":301,"start_time":"2018-01-02T00:00:00.000Z","end_time":"2018-01-03T00:00:00.000Z","format":"miniSEED","quality":"D"},{"version":"1.0.0","producer":{"name":"SED","agent":"ObsPy mSEED-QC","created":"2018-01-10T18:19:59.201Z"},"station":"DAVOX","network":"CH","location":"","channel":"LHZ","num_gaps":0,"num_overlaps":1,"sum_gaps":0,"sum_overlaps":175,"max_gap":null,"max_overlap":175,"record_length":[512],"sample_rate":[1],"percent_availability":100,"encoding":["STEIM2"],"num_records":352,"start_time":"2018-01-03T00:00:00.000Z","end_time":"2018-01-04T00:00:00.000Z","format":"miniSEED","quality":"D"},{"version":"1.0.0","producer":{"name":"SED","agent":"ObsPy mSEED-QC","created":"2018-01-11T10:16:43.104Z"},"station":"DAVOX","network":"CH","location":"","channel":"LHZ","num_gaps":0,"num_overlaps":1,"sum_gaps":0,"sum_overlaps":0,"max_gap":null,"max_overlap":0,"record_length":[512],"sample_rate":[1],"percent_availability":100,"encoding":["STEIM2"],"num_records":320,"start_time":"2018-01-04T00:00:00.000Z","end_time":"2018-01-05T00:00:00.000Z","format":"miniSEED","quality":"D"}]') # noqa

        stream_epoch_orig = StreamEpoch(
            stream=self.stream,
            starttime=datetime.datetime(2018, 1, 1),
            endtime=datetime.datetime(2018, 1, 5))

        result = WFCatalogSplitAndAlignTask(self.url, stream_epoch_orig,
                                            self.query_params)()
        data = None
        with open(result.data, 'rb') as ifd:
            data = json.loads(ifd.read().decode('utf-8'))

        self.assertEqual(data, reference_result)
        mock_raw_request.has_calls()

    @mock.patch.object(
        WFCatalogSplitAndAlignTask, 'get_cretry_budget_error_ratio',
        return_value=0)
    @mock.patch.object(
        WFCatalogSplitAndAlignTask, 'update_cretry_budget')
    @mock.patch('eidangservices.federator.server.task.raw_request')
    @mock.patch('eidangservices.federator.server.task.get_temp_filepath')
    def test_split_multiple_with_overlap(
        self, mock_get_temp_filepath, mock_raw_request, mock_method_update,
            mock_method_eratio):
        # NOTE(damb): We do not care about stream epoch splitting. We simply
        # test the task's aligning facilities.
        mock_get_temp_filepath.return_value = self.path_tempfile
        mock_raw_request.side_effect = [
            HTTP413(),
            io.BytesIO(b'[{"version":"1.0.0","producer":{"name":"SED","agent":"ObsPy mSEED-QC","created":"2018-01-10T18:19:25.563Z"},"station":"DAVOX","network":"CH","location":"","channel":"LHZ","num_gaps":0,"num_overlaps":2,"sum_gaps":0,"sum_overlaps":161,"max_gap":null,"max_overlap":161,"record_length":[512],"sample_rate":[1],"percent_availability":100,"encoding":["STEIM2"],"num_records":313,"start_time":"2018-01-01T00:00:00.000Z","end_time":"2018-01-02T00:00:00.000Z","format":"miniSEED","quality":"D"},{"version":"1.0.0","producer":{"name":"SED","agent":"ObsPy mSEED-QC","created":"2018-01-10T18:19:43.021Z"},"station":"DAVOX","network":"CH","location":"","channel":"LHZ","num_gaps":0,"num_overlaps":2,"sum_gaps":0,"sum_overlaps":251,"max_gap":null,"max_overlap":251,"record_length":[512],"sample_rate":[1],"percent_availability":100,"encoding":["STEIM2"],"num_records":301,"start_time":"2018-01-02T00:00:00.000Z","end_time":"2018-01-03T00:00:00.000Z","format":"miniSEED","quality":"D"}]'), # noqa
            io.BytesIO(b'[{"version":"1.0.0","producer":{"name":"SED","agent":"ObsPy mSEED-QC","created":"2018-01-10T18:19:43.021Z"},"station":"DAVOX","network":"CH","location":"","channel":"LHZ","num_gaps":0,"num_overlaps":2,"sum_gaps":0,"sum_overlaps":251,"max_gap":null,"max_overlap":251,"record_length":[512],"sample_rate":[1],"percent_availability":100,"encoding":["STEIM2"],"num_records":301,"start_time":"2018-01-02T00:00:00.000Z","end_time":"2018-01-03T00:00:00.000Z","format":"miniSEED","quality":"D"}]'), # noqa
            io.BytesIO(b'[{"version":"1.0.0","producer":{"name":"SED","agent":"ObsPy mSEED-QC","created":"2018-01-10T18:19:59.201Z"},"station":"DAVOX","network":"CH","location":"","channel":"LHZ","num_gaps":0,"num_overlaps":1,"sum_gaps":0,"sum_overlaps":175,"max_gap":null,"max_overlap":175,"record_length":[512],"sample_rate":[1],"percent_availability":100,"encoding":["STEIM2"],"num_records":352,"start_time":"2018-01-03T00:00:00.000Z","end_time":"2018-01-04T00:00:00.000Z","format":"miniSEED","quality":"D"},{"version":"1.0.0","producer":{"name":"SED","agent":"ObsPy mSEED-QC","created":"2018-01-11T10:16:43.104Z"},"station":"DAVOX","network":"CH","location":"","channel":"LHZ","num_gaps":0,"num_overlaps":1,"sum_gaps":0,"sum_overlaps":0,"max_gap":null,"max_overlap":0,"record_length":[512],"sample_rate":[1],"percent_availability":100,"encoding":["STEIM2"],"num_records":320,"start_time":"2018-01-04T00:00:00.000Z","end_time":"2018-01-05T00:00:00.000Z","format":"miniSEED","quality":"D"}]')] # noqa

        reference_result = json.loads(
            '[{"version":"1.0.0","producer":{"name":"SED","agent":"ObsPy mSEED-QC","created":"2018-01-10T18:19:25.563Z"},"station":"DAVOX","network":"CH","location":"","channel":"LHZ","num_gaps":0,"num_overlaps":2,"sum_gaps":0,"sum_overlaps":161,"max_gap":null,"max_overlap":161,"record_length":[512],"sample_rate":[1],"percent_availability":100,"encoding":["STEIM2"],"num_records":313,"start_time":"2018-01-01T00:00:00.000Z","end_time":"2018-01-02T00:00:00.000Z","format":"miniSEED","quality":"D"},{"version":"1.0.0","producer":{"name":"SED","agent":"ObsPy mSEED-QC","created":"2018-01-10T18:19:43.021Z"},"station":"DAVOX","network":"CH","location":"","channel":"LHZ","num_gaps":0,"num_overlaps":2,"sum_gaps":0,"sum_overlaps":251,"max_gap":null,"max_overlap":251,"record_length":[512],"sample_rate":[1],"percent_availability":100,"encoding":["STEIM2"],"num_records":301,"start_time":"2018-01-02T00:00:00.000Z","end_time":"2018-01-03T00:00:00.000Z","format":"miniSEED","quality":"D"},{"version":"1.0.0","producer":{"name":"SED","agent":"ObsPy mSEED-QC","created":"2018-01-10T18:19:59.201Z"},"station":"DAVOX","network":"CH","location":"","channel":"LHZ","num_gaps":0,"num_overlaps":1,"sum_gaps":0,"sum_overlaps":175,"max_gap":null,"max_overlap":175,"record_length":[512],"sample_rate":[1],"percent_availability":100,"encoding":["STEIM2"],"num_records":352,"start_time":"2018-01-03T00:00:00.000Z","end_time":"2018-01-04T00:00:00.000Z","format":"miniSEED","quality":"D"},{"version":"1.0.0","producer":{"name":"SED","agent":"ObsPy mSEED-QC","created":"2018-01-11T10:16:43.104Z"},"station":"DAVOX","network":"CH","location":"","channel":"LHZ","num_gaps":0,"num_overlaps":1,"sum_gaps":0,"sum_overlaps":0,"max_gap":null,"max_overlap":0,"record_length":[512],"sample_rate":[1],"percent_availability":100,"encoding":["STEIM2"],"num_records":320,"start_time":"2018-01-04T00:00:00.000Z","end_time":"2018-01-05T00:00:00.000Z","format":"miniSEED","quality":"D"}]') # noqa

        stream_epoch_orig = StreamEpoch(
            stream=self.stream,
            starttime=datetime.datetime(2018, 1, 1),
            endtime=datetime.datetime(2018, 1, 5))

        result = WFCatalogSplitAndAlignTask(self.url, stream_epoch_orig,
                                            self.query_params)()
        data = None
        with open(result.data, 'rb') as ifd:
            data = json.loads(ifd.read().decode('utf-8'))

        self.assertEqual(data, reference_result)
        mock_raw_request.has_calls()


# -----------------------------------------------------------------------------
if __name__ == '__main__':
    unittest.main()

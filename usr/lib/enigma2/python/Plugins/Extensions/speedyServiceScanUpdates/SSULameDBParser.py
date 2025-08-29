# -*- coding: utf-8 -*-
import sys
import re
from enigma import eDVBDB, eServiceReference

PY2 = sys.version_info[0] == 2
PY3 = sys.version_info[0] == 3

FLAG_SERVICE_NEW_FOUND = 64

class SSULameDBParser:
    def __init__(self, filename):
        self.filename = filename
        self.version = 4
        self.services = {}
        self.transponders = {}
        self.parse(self.load())

    def load(self):
        try:
            print("[ServiceScanUpdates] Reading file: " + self.filename)
            import codecs
            with codecs.open(self.filename, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
            if lines and "/3/" in lines[0]:
                self.version = 3
            elif lines and "/4/" in lines[0]:
                self.version = 4
            else:
                print("[ServiceScanUpdates] Unsupported lamedb version")
                lines = None
            return lines
        except Exception as e:
            print("[ServiceScanUpdates] Exception reading lamedb: " + str(e))
            return None

    def parse(self, lines):
        if not lines:
            return

        reading_transponders = False
        reading_services = False
        tmp = []
        self.transponders.clear()
        self.services.clear()

        print("[ServiceScanUpdates] Parsing content of file: " + self.filename)
        for line in lines:
            line = line.rstrip('\n')
            if PY2:
                line = line.encode('utf-8')

            if line == "end":
                reading_transponders = False
                reading_services = False
                tmp = []
                continue

            if line == "transponders":
                reading_transponders = True
                tmp = []
                continue

            if line == "services":
                reading_services = True
                tmp = []
                continue

            if reading_transponders:
                if line == "/":
                    self.transponders[tmp[0]] = tmp[1].replace("\t", "").replace(" ", ":")
                    tmp = []
                else:
                    tmp.append(line)

            elif reading_services:
                if line.startswith("p:"):
                    parts = tmp[0].split(':')
                    if len(parts) not in (6, 7):
                        tmp = []
                        continue

                    if len(parts) == 6:
                        service_id, dvb_namespace, transport_stream_id, original_network_id, service_type, service_number = parts
                    else:
                        service_id, dvb_namespace, transport_stream_id, original_network_id, service_type, service_number, source_id = parts

                    transponder = "%s:%s:%s" % (dvb_namespace, transport_stream_id, original_network_id)

                    service_id = re.sub("^0+", "", service_id)
                    dvb_namespace = re.sub("^0+", "", dvb_namespace)
                    transport_stream_id = re.sub("^0+", "", transport_stream_id)
                    original_network_id = re.sub("^0+", "", original_network_id)
                    service_type = format(int(service_type), "x")
                    service_ref = "1:0:%s:%s:%s:%s:%s:0:0:0:" % (service_type.upper(), service_id.upper(), transport_stream_id.upper(), original_network_id.upper(), dvb_namespace.upper())

                    self.services[service_ref] = {
                        'service_id': service_id,
                        'dvb_namespace': dvb_namespace,
                        'transport_stream_id': transport_stream_id,
                        'original_network_id': original_network_id,
                        'service_type': service_type,
                        'service_number': service_number,
                        'transponder': transponder,
                        'service_name': tmp[1]
                    }

                    provdata = []
                    for tmpdata in line.split(','):
                        psdata = tmpdata.split(':')
                        if psdata[0] == "p":
                            self.services[service_ref]['provider'] = psdata[1]
                        elif len(psdata) > 1:
                            psdata[1] = re.sub("^0+", "", psdata[1])
                            provdata.append({psdata[0]: psdata[1]})
                    self.services[service_ref]['provider_data'] = provdata
                    tmp = []
                else:
                    tmp.append(line)

    def getServiceBySRef(self, service_ref):
        return self.services.get(service_ref)

    def getServices(self):
        return self.services

    @staticmethod
    def _get_service_type(service_ref):
        parts = service_ref.split(':')
        if len(parts) > 2 and parts[2]:
            try:
                return int(parts[2], 16)
            except ValueError:
                return None
        return None

    @classmethod
    def isVideoService(cls, service_ref):
        service_type = cls._get_service_type(service_ref)
        return service_type in (1, 4, 5, 6, 11, 22, 23, 24, 17, 25, 26, 27, 28, 29, 30, 31)

    @classmethod
    def isRadioService(cls, service_ref):
        service_type = cls._get_service_type(service_ref)
        return service_type in (2, 10)

    @classmethod
    def isDataService(cls, service_ref):
        service_type = cls._get_service_type(service_ref)
        return service_type in (3, 12, 13, 14, 15, 16, 128, 129)

    @staticmethod
    def hasNewFlag(service_ref):
        return bool(eDVBDB.getInstance().getFlag(eServiceReference(str(service_ref))) & FLAG_SERVICE_NEW_FOUND)
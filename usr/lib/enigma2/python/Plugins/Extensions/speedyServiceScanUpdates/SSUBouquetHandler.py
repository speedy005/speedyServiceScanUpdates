# -*- coding: utf-8 -*-
from __future__ import print_function, unicode_literals  # Für Py2 Unicode-Kompatibilität
from enigma import eDVBDB
from Tools.Directories import fileExists, resolveFilename, SCOPE_CONFIG
import time
import os
from datetime import datetime
import codecs
from gettext import gettext as _

class SSUBouquetHandler:
    SSU_BOUQUET_PREFIX = "userbouquet.ServiceScanUpdates"

    def __init__(self):
        self.service_scan_timestamp = int(time.time())
        self.config_dir = str(resolveFilename(SCOPE_CONFIG))  # Py2/3 kompatibel
        self.ssu_bouquet_filepath_prefix = os.path.join(self.config_dir, self.SSU_BOUQUET_PREFIX)
        self.index_bouquet_filepath_prefix = os.path.join(self.config_dir, "bouquets")

    @staticmethod
    def reloadBouquets():
        eDVBDB.getInstance().reloadBouquets()

    def doesSSUBouquetFileExists(self, bouquet_type):
        filepath = os.path.join(self.config_dir, "{}.{}".format(self.SSU_BOUQUET_PREFIX, bouquet_type))
        return fileExists(filepath)

    def getSSUIndexBouquetLine(self, bouquet_type):
        return '#SERVICE 1:7:{}:0:0:0:0:0:0:0:FROM BOUQUET "{}.{}" ORDER BY bouquet\n'.format(
            1 if bouquet_type == "tv" else 2,
            self.SSU_BOUQUET_PREFIX,
            bouquet_type
        )

    def addToIndexBouquet(self, bouquet_type):
        filepath = "{}.{}".format(self.index_bouquet_filepath_prefix, bouquet_type)
        print(_("[speedyServiceScanUpdates] Add SSU bouquet to index file [{}]").format(filepath))

        if not fileExists(filepath):
            print(_("[speedyServiceScanUpdates] Index file not found: {}").format(filepath))
            return

        with codecs.open(filepath, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()

        bouquet_line = self.getSSUIndexBouquetLine(bouquet_type)
        if bouquet_line not in lines:
            lines.append(bouquet_line)
            with codecs.open(filepath, "w", encoding="utf-8") as f:
                f.writelines(lines)

    def addMarker(self):
        datetime_string = datetime.fromtimestamp(self.service_scan_timestamp).strftime("%d.%m.%Y - %H:%M")
        return "#SERVICE 1:64:0:0:0:0:0:0:0:0:\n#DESCRIPTION ------- {} -------\n".format(datetime_string)

    def createSSUBouquet(self, services, bouquet_type):
        filepath = os.path.join(self.config_dir, "{}.{}".format(self.SSU_BOUQUET_PREFIX, bouquet_type))
        print(_("[speedyServiceScanUpdates] Create SSU bouquet [{}]").format(filepath))

        ssu_bouquet_list = [
            _("#NAME Service Scan Updates\n"),
            self.addMarker()
        ] + ["#SERVICE {}\n".format(service) for service in services]

        with codecs.open(filepath, "w", encoding="utf-8") as f:
            f.writelines(ssu_bouquet_list)

        time.sleep(0.2)
        self.addToIndexBouquet(bouquet_type)
        self.reloadBouquets()

        print(_("[speedyServiceScanUpdates] SSU bouquet created and added to index."))

    def appendToSSUBouquet(self, services, bouquet_type, append_at_end=False):
        filepath = os.path.join(self.config_dir, "{}.{}".format(self.SSU_BOUQUET_PREFIX, bouquet_type))
        print(_("[speedyServiceScanUpdates] Append to SSU bouquet [{}]").format(filepath))

        if not fileExists(filepath):
            print(_("[speedyServiceScanUpdates] SSU bouquet file not found: {}").format(filepath))
            return

        with codecs.open(filepath, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()

        marker = self.addMarker()
        new_block = [marker] + ["#SERVICE {}\n".format(s) for s in services]

        if marker not in lines:
            if append_at_end:
                lines.extend(new_block)
            else:
                for idx, line in enumerate(lines):
                    if line.startswith("#NAME "):
                        insert_pos = idx + 1
                        if insert_pos < len(lines) and lines[insert_pos].strip() == "":
                            insert_pos += 1
                        lines[insert_pos:insert_pos] = new_block
                        break

            with codecs.open(filepath, "w", encoding="utf-8") as f:
                f.writelines(lines)

            time.sleep(0.2)
            self.addToIndexBouquet(bouquet_type)
            self.reloadBouquets()

            print(_("[speedyServiceScanUpdates] SSU bouquet updated with new services."))
        else:
            print(_("[speedyServiceScanUpdates] Marker already exists, no new block added."))

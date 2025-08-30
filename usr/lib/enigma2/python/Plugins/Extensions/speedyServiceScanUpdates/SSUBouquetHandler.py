# -*- coding: utf-8 -*-
from enigma import eDVBDB
from Tools.Directories import fileExists, resolveFilename, SCOPE_CONFIG
import time
import os
from datetime import datetime
import codecs  # für UTF-8 Handling

try:
    from Screens.ChannelSelection import ChannelSelection
except ImportError:
    ChannelSelection = None


class SSUBouquetHandler:
    SSU_BOUQUET_PREFIX = "userbouquet.servicescanupdates"  # alles lowercase!

    def __init__(self):
        self.service_scan_timestamp = int(time.time())
        self.config_dir = resolveFilename(SCOPE_CONFIG)
        self.ssu_bouquet_filepath_prefix = os.path.join(self.config_dir, self.SSU_BOUQUET_PREFIX)
        self.index_bouquet_filepath_prefix = os.path.join(self.config_dir, "bouquets")

    @staticmethod
    def reloadBouquets():
        db = eDVBDB.getInstance()
        db.reloadBouquets()
        db.reloadServicelist()  # wichtig, sonst sieht man neue Bouquets oft nicht
        if ChannelSelection and ChannelSelection.instance:
            ChannelSelection.instance.reloadBouquets()

    def doesSSUBouquetFileExists(self, bouquet_type):
        filepath = os.path.join(self.config_dir, "%s.%s" % (self.SSU_BOUQUET_PREFIX, bouquet_type))
        return fileExists(filepath)

    def getSSUIndexBouquetLine(self, bouquet_type):
        return '#SERVICE 1:7:%d:0:0:0:0:0:0:0:FROM BOUQUET "%s.%s" ORDER BY bouquet\n' % (
            1 if bouquet_type == "tv" else 2,
            self.SSU_BOUQUET_PREFIX,
            bouquet_type
        )

    def addToIndexBouquet(self, bouquet_type):
        filepath = "%s.%s" % (self.index_bouquet_filepath_prefix, bouquet_type)
        print("[speedyServiceScanUpdates] Adding SSU bouquet to index file [%s]" % filepath)

        if not fileExists(filepath):
            print("[speedyServiceScanUpdates] Index file not found: %s" % filepath)
            return

        with codecs.open(filepath, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()

        bouquet_line = self.getSSUIndexBouquetLine(bouquet_type)
        if bouquet_line not in lines:
            if not lines[-1].endswith("\n"):
                lines[-1] += "\n"
            lines.append(bouquet_line)
            with codecs.open(filepath, "w", encoding="utf-8") as f:
                f.writelines(lines)
            print("[speedyServiceScanUpdates] SSU bouquet added to index.")

    def addMarker(self):
        datetime_string = datetime.fromtimestamp(self.service_scan_timestamp).strftime("%d.%m.%Y - %H:%M")
        return [
            "#SERVICE 1:64:0:0:0:0:0:0:0:0:\n",
            "#DESCRIPTION ------- %s -------\n" % datetime_string
        ]

    def createSSUBouquet(self, services, bouquet_type):
        filepath = os.path.join(self.config_dir, "%s.%s" % (self.SSU_BOUQUET_PREFIX, bouquet_type))
        print("[speedyServiceScanUpdates] Creating SSU bouquet [%s]" % filepath)

        ssu_bouquet_list = ["#NAME Service Scan Updates\n"] + self.addMarker()
        ssu_bouquet_list += ["#SERVICE %s\n" % service for service in services]

        with codecs.open(filepath, "w", encoding="utf-8") as f:
            f.writelines(ssu_bouquet_list)

        self.addToIndexBouquet(bouquet_type)
        time.sleep(0.2)
        self.reloadBouquets()

    def appendToSSUBouquet(self, services, bouquet_type, append_at_end=False):
        filepath = os.path.join(self.config_dir, "%s.%s" % (self.SSU_BOUQUET_PREFIX, bouquet_type))
        print("[speedyServiceScanUpdates] Appending to SSU bouquet [%s]" % filepath)

        if not fileExists(filepath):
            print("[speedyServiceScanUpdates] SSU bouquet file not found: %s" % filepath)
            return

        with codecs.open(filepath, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()

        marker_block = self.addMarker()
        marker_string = "".join(marker_block)
        if marker_string not in "".join(lines):
            new_block = marker_block + ["#SERVICE %s\n" % s for s in services]
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

        self.addToIndexBouquet(bouquet_type)
        time.sleep(0.2)
        self.reloadBouquets()

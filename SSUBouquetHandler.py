# -*- coding: utf-8 -*-
from enigma import eDVBDB
from Tools.Directories import fileExists, resolveFilename, SCOPE_CONFIG
import time
import os
from datetime import datetime
import codecs  # Required for UTF-8 file handling in Python 2.7


class SSUBouquetHandler:
    SSU_BOUQUET_PREFIX = "userbouquet.ServiceScanUpdates"

    def __init__(self):
        self.service_scan_timestamp = int(time.time())
        self.config_dir = resolveFilename(SCOPE_CONFIG)
        self.ssu_bouquet_filepath_prefix = os.path.join(self.config_dir, self.SSU_BOUQUET_PREFIX)
        self.index_bouquet_filepath_prefix = os.path.join(self.config_dir, "bouquets")

    @staticmethod
    def reloadBouquets():
        eDVBDB.getInstance().reloadBouquets()

    def doesSSUBouquetFileExists(self, bouquet_type):
        filepath = os.path.join(self.config_dir, "%s.%s" % (self.SSU_BOUQUET_PREFIX, bouquet_type))
        return fileExists(filepath)

    def getSSUIndexBouquetLine(self, bouquet_type):
        # Return type as string (bytes) for Python 2.7 compatibility
        return '#SERVICE 1:7:%d:0:0:0:0:0:0:0:FROM BOUQUET "%s.%s" ORDER BY bouquet\n' % (
            1 if bouquet_type == "tv" else 2,
            self.SSU_BOUQUET_PREFIX,
            bouquet_type
        )

    def addToIndexBouquet(self, bouquet_type):
        filepath = "%s.%s" % (self.index_bouquet_filepath_prefix, bouquet_type)
        print("[speedyServiceScanUpdates] Add SSU bouquet to index file [%s]" % filepath)

        if not fileExists(filepath):
            print("[speedyServiceScanUpdates] Index file not found: %s" % filepath)
            return

        # Read/write using codecs for UTF-8 handling
        with codecs.open(filepath, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()

        bouquet_line = self.getSSUIndexBouquetLine(bouquet_type)
        if bouquet_line not in lines:
            lines.append(bouquet_line)
            with codecs.open(filepath, "w", encoding="utf-8") as f:
                f.writelines(lines)

    def addMarker(self):
        datetime_string = datetime.fromtimestamp(self.service_scan_timestamp).strftime("%d.%m.%Y - %H:%M")
        return "#SERVICE 1:64:0:0:0:0:0:0:0:0:\n#DESCRIPTION ------- %s -------\n" % datetime_string

    def createSSUBouquet(self, services, bouquet_type):
        filepath = os.path.join(self.config_dir, "%s.%s" % (self.SSU_BOUQUET_PREFIX, bouquet_type))
        print("[speedyServiceScanUpdates] Create SSU bouquet [%s]" % filepath)

        ssu_bouquet_list = [
            "#NAME Service Scan Updates\n",
            self.addMarker()
        ] + ["#SERVICE %s\n" % service for service in services]

        # Write using codecs for UTF-8
        with codecs.open(filepath, "w", encoding="utf-8") as f:
            f.writelines(ssu_bouquet_list)

        time.sleep(0.2)
        self.reloadBouquets()

    def appendToSSUBouquet(self, services, bouquet_type, append_at_end=False):
        filepath = os.path.join(self.config_dir, "%s.%s" % (self.SSU_BOUQUET_PREFIX, bouquet_type))
        print("[speedyServiceScanUpdates] Append to SSU bouquet [%s]" % filepath)

        if not fileExists(filepath):
            print("[speedyServiceScanUpdates] SSU bouquet file not found: %s" % filepath)
            return

        # Read with error handling for corrupted files
        with codecs.open(filepath, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()

        marker = self.addMarker()
        # Check marker existence using string comparison
        if marker not in lines:
            new_block = [marker] + ["#SERVICE %s\n" % s for s in services]
            if append_at_end:
                lines.extend(new_block)
            else:
                # Insert after #NAME line
                for idx, line in enumerate(lines):
                    if line.startswith("#NAME "):
                        insert_pos = idx + 1
                        # Preserve existing newline after #NAME if needed
                        if lines[insert_pos].strip() == "":
                            insert_pos += 1
                        lines[insert_pos:insert_pos] = new_block
                        break

        # Write back using UTF-8 encoding
        with codecs.open(filepath, "w", encoding="utf-8") as f:
            f.writelines(lines)

        time.sleep(0.2)
        self.reloadBouquets()

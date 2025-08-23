# -*- coding: utf-8 -*-
from __future__ import print_function

import os
import sys
import zipfile
import shutil
import importlib

version = "1.2"
# Python 2 compatible urllib
try:
    import urllib2 as urllib_request
except ImportError:
    import urllib.request as urllib_request

from Plugins.Plugin import PluginDescriptor
from Components.config import config
from Tools.Directories import resolveFilename, SCOPE_CONFIG
from Screens.MessageBox import MessageBox
from Components.ConfigList import ConfigListScreen

# Compatible import for ServiceScan
try:
    from Screens.ServiceScan import ServiceScan  # Python 3
except ImportError:
    from Components.ServiceScan import ServiceScan  # Python 2

from . import _
from .SSULameDBParser import SSULameDBParser

# Correct screen import
try:
    from SSUSetupScreen import SSUUpdateScreen   # Python 2 absolute import
except ImportError:
    from .SSUSetupScreen import SSUUpdateScreen  # Python 3 relative import

PY2 = sys.version_info[0] == 2
PY3 = sys.version_info[0] == 3

# Globale Variablen
baseServiceScan_execBegin = None
baseServiceScan_execEnd = None
preScanDB = None

def dictHasKey(dictionary, key):
    if PY2:
        return dictionary.has_key(key)
    else:
        return key in dictionary

def safeClose(db):
    if hasattr(db, "close"):
        db.close()

def ServiceScan_execBegin(self):
    flags = None
    try:
        flags = self.scanList[self.run]["flags"]
    except (AttributeError, KeyError, IndexError, TypeError):
        flags = "N/A"
    print("[speedyServiceScanUpdates] ServiceScan_execBegin [%s]" % str(flags))

    global preScanDB
    if not preScanDB and (config.plugins.speedyservicescanupdates.add_new_tv_services.value or
                          config.plugins.speedyservicescanupdates.add_new_radio_services.value):
        preScanDB = SSULameDBParser(resolveFilename(SCOPE_CONFIG) + "/lamedb")
    baseServiceScan_execBegin(self)

def ServiceScan_execEnd(self, onClose=True):
    flags = None
    try:
        flags = self.scanList[self.run]["flags"]
    except (AttributeError, KeyError, IndexError, TypeError):
        flags = "N/A"

    # Sicherstellen, dass self.state existiert
    state_val = getattr(self, "state", -1)
    print("[speedyServiceScanUpdates] ServiceScan_execEnd (%d) [%s]" % (state_val, str(flags)))

    # Auch hier getattr nutzen, um Absturz zu vermeiden
    if getattr(self, "state", None) == getattr(self, "DONE", None):
        if config.plugins.speedyservicescanupdates.add_new_tv_services.value or \
           config.plugins.speedyservicescanupdates.add_new_radio_services.value:

            postScanDB = SSULameDBParser(resolveFilename(SCOPE_CONFIG) + "/lamedb")
            postScanServices = postScanDB.getServices()
            safeClose(postScanDB)  # <- Hier statt direktem postScanDB.close()

            global preScanDB
            if preScanDB:
                preScanServices = preScanDB.getServices()
                newTVServices = []
                newRadioServices = []

                # Neue Services finden
                for service_ref in postScanServices.keys():
                    if not dictHasKey(preScanServices, service_ref):
                        if SSULameDBParser.isVideoService(service_ref):
                            newTVServices.append(service_ref)
                        elif SSULameDBParser.isRadioService(service_ref):
                            newRadioServices.append(service_ref)

                from .SSUBouquetHandler import SSUBouquetHandler
                bouquet_handler = SSUBouquetHandler()

                # TV-Services
                print("[speedyServiceScanUpdates] Found %d new TV services" % len(newTVServices))
                if newTVServices and config.plugins.speedyservicescanupdates.add_new_tv_services.value:
                    bouquet_handler.addToIndexBouquet("tv")
                    if config.plugins.speedyservicescanupdates.clear_bouquet.value:
                        bouquet_handler.createSSUBouquet(newTVServices, "tv")
                    else:
                        if bouquet_handler.doesSSUBouquetFileExists("tv"):
                            bouquet_handler.appendToSSUBouquet(newTVServices, "tv")
                        else:
                            bouquet_handler.createSSUBouquet(newTVServices, "tv")

                # Radio-Services
                print("[speedyServiceScanUpdates] Found %d new radio services" % len(newRadioServices))
                if newRadioServices and config.plugins.speedyservicescanupdates.add_new_radio_services.value:
                    bouquet_handler.addToIndexBouquet("radio")
                    if config.plugins.speedyservicescanupdates.clear_bouquet.value:
                        bouquet_handler.createSSUBouquet(newRadioServices, "radio")
                    else:
                        if bouquet_handler.doesSSUBouquetFileExists("radio"):
                            bouquet_handler.appendToSSUBouquet(newRadioServices, "radio")
                        else:
                            bouquet_handler.createSSUBouquet(newRadioServices, "radio")

                bouquet_handler.reloadBouquets()
                # Reset pre scan db
                preScanDB = None

    baseServiceScan_execEnd(self)

# Versionsprüfung und Updatecheck
def get_current_version():
    version_file = "/usr/lib/enigma2/python/Plugins/Extensions/speedyServiceScanUpdates/version"
    try:
        with open(version_file, 'r') as f:
            return f.read().strip()
    except Exception as e:
        print("Fehler beim Lesen der Versionsdatei: %s" % str(e))
        return "0.0"

def parse_version(version):
    """Hilfsfunktion, um Versionsnummern in Tupel zu zerlegen und zu vergleichen."""
    parts = version.split(".")
    if len(parts) == 2:  # Falls nur zwei Teile (z.B. "3.5")
        parts.append("0")  # Patch-Teil hinzufügen (z.B. "3.5" ? "3.5.0")
    return tuple(map(int, parts))

def check_for_update(current_version):
    try:
        # URL für die neueste Version im main-Branch
        url = "https://raw.githubusercontent.com/speedy005/speedyServiceScanUpdates/main/version"
        print("[speedyServiceScanUpdates] Checking for updates at: %s" % url)

        response = urllib_request.urlopen(url).read().strip()
        latest_version = response

        print("[speedyServiceScanUpdates] Aktuelle Version: %s, Neueste Version: %s" % (current_version, latest_version))

        if parse_version(latest_version) > parse_version(current_version):
            print("[speedyServiceScanUpdates] Ein Update ist verfügbar!")
            # URL auf die main.zip umstellen
            download_url = "https://github.com/speedy005/speedyServiceScanUpdates/archive/refs/heads/main.zip"
            return latest_version, download_url
        else:
            print("[speedyServiceScanUpdates] Keine neue Version verfügbar.")
            return None, None

    except Exception as e:
        print("[speedyServiceScanUpdates] Fehler bei der Updateprüfung: %s" % str(e))
        return None, None

def prompt_for_update(session, latest_version, download_url):
    """Fragt den Benutzer, ob das Update installiert werden soll."""
    def update_installed_callback(choice):
        if choice:
            download_and_install_update(download_url)
        else:
            print("User chose not to update.")

    # Uberprüfe, ob die MessageBox korrekt angezeigt wird
    print("[speedyServiceScanUpdates] Showing update prompt...")
    session.openWithCallback(update_installed_callback, MessageBox,
        "A new version %s is available. Do you want to install it?" % latest_version,
        MessageBox.TYPE_YESNO)

def download_and_extract_zip(url, download_path, extract_path):
    try:
        print("Downloading from %s..." % url)
        req = urllib_request.urlopen(url)
        with open(download_path, "wb") as f:
            f.write(req.read())
        print("Download complete: %s" % download_path)

        print("Extracting to %s..." % extract_path)
        zip_ref = zipfile.ZipFile(download_path, 'r')
        zip_ref.extractall(extract_path)
        zip_ref.close()
        print("Extraction complete.")
    except Exception as e:
        print("Error: %s" % str(e))

# Autostart Hook
def autostart(reason, **kwargs):
    if reason == 0 and "session" in kwargs:
        global baseServiceScan_execBegin, baseServiceScan_execEnd
        if baseServiceScan_execBegin is None:
            baseServiceScan_execBegin = ServiceScan.execBegin
        ServiceScan.execBegin = ServiceScan_execBegin

        if baseServiceScan_execEnd is None:
            baseServiceScan_execEnd = ServiceScan.execEnd
        ServiceScan.execEnd = ServiceScan_execEnd

# Menü und Setup
def SSUMain(session, **kwargs):
    from .SSUSetupScreen import SSUSetupScreen
    session.open(SSUSetupScreen)

def SSUMenuItem(menuid, **kwargs):
    if menuid == "scan":
        return [("speedy ServiceScanUpdates " + _("Setup"), SSUMain, "servicescanupdates", None)]
    return []

def menu(menuid, **kwargs):
    if menuid == "mainmenu":
        return [(_("speedy ServiceScanUpdates") + " " + _("Setup"), SSUMain, "speedyservicescanupdates_mainmenu", 50)]
    return []

# Plugin Descriptor
def Plugins(**kwargs):
    current_version = get_current_version()
    latest_version, download_url = check_for_update(current_version)
    session = kwargs.get('session')
    
    if latest_version and session:
        prompt_for_update(session, latest_version, download_url)
    return [
        PluginDescriptor(where=[PluginDescriptor.WHERE_SESSIONSTART, PluginDescriptor.WHERE_AUTOSTART],
                         fnc=autostart),
        PluginDescriptor(name="speedy ServiceScanUpdates " + _("Setup"),
                         description=_("Updates during service scan"),
                         where=PluginDescriptor.WHERE_PLUGINMENU,
                         icon="plugin.png",
                         fnc=SSUMain),
        PluginDescriptor(name="speedy ServiceScanUpdates " + _("Setup"),
                         description=_("Updates during service scan"),
                         where=PluginDescriptor.WHERE_EXTENSIONSMENU,
                         icon="plugin.png",
                         fnc=SSUMain),
        PluginDescriptor(where=PluginDescriptor.WHERE_MENU, fnc=menu),
        PluginDescriptor(where=PluginDescriptor.WHERE_MENU, fnc=SSUMenuItem)
    ]

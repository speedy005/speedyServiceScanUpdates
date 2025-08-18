# -*- coding: utf-8 -*-
from __future__ import print_function, unicode_literals  # Kompatibilität mit Python 2 und 3

import os
import sys
import json
import urllib
import zipfile
import shutil
from packaging import version
import importlib
import subprocess

from Plugins.Plugin import PluginDescriptor
from Components.config import config
from Tools.Directories import resolveFilename, SCOPE_CONFIG
from Screens.MessageBox import MessageBox
from Components.ConfigList import ConfigListScreen

try:
    from Screens.ServiceScan import ServiceScan  # Python 3
except ImportError:
    import urllib.request  # Für Python 2
    from Components.ServiceScan import ServiceScan  # Python 2

from . import _
from .SSULameDBParser import SSULameDBParser

# Version
PLUGIN_VERSION = '3.0'  # Aktuelle Plugin-Version

# Globale Variablen
baseServiceScan_execBegin = None
baseServiceScan_execEnd = None
preScanDB = None

def dictHasKey(dictionary, key):
    return key in dictionary

def safeClose(db):
    if hasattr(db, "close"):
        db.close()

def ServiceScan_execBegin(self):
    flags = getattr(self.scanList[self.run], "flags", "N/A") if hasattr(self, "scanList") else "N/A"
    print("[speedyServiceScanUpdates] ServiceScan_execBegin [{}]".format(flags))

    global preScanDB
    if not preScanDB and (config.plugins.speedyservicescanupdates.add_new_tv_services.value or
                          config.plugins.speedyservicescanupdates.add_new_radio_services.value):
        preScanDB = SSULameDBParser(resolveFilename(SCOPE_CONFIG) + "/lamedb")

    baseServiceScan_execBegin(self)

def ServiceScan_execEnd(self, onClose=True):
    flags = getattr(self.scanList[self.run], "flags", "N/A") if hasattr(self, "scanList") else "N/A"
    state_val = getattr(self, "state", -1)
    print("[speedyServiceScanUpdates] ServiceScan_execEnd ({}) [{}]".format(state_val, flags))

    if getattr(self, "state", None) == getattr(self, "DONE", None):
        if config.plugins.speedyservicescanupdates.add_new_tv_services.value or \
           config.plugins.speedyservicescanupdates.add_new_radio_services.value:

            postScanDB = SSULameDBParser(resolveFilename(SCOPE_CONFIG) + "/lamedb")
            postScanServices = postScanDB.getServices()
            safeClose(postScanDB)

            global preScanDB
            if preScanDB:
                preScanServices = preScanDB.getServices()
                newTVServices = []
                newRadioServices = []

                for service_ref in postScanServices.keys():
                    if not dictHasKey(preScanServices, service_ref):
                        if SSULameDBParser.isVideoService(service_ref):
                            newTVServices.append(service_ref)
                        elif SSULameDBParser.isRadioService(service_ref):
                            newRadioServices.append(service_ref)

                from .SSUBouquetHandler import SSUBouquetHandler
                bouquet_handler = SSUBouquetHandler()

                if newTVServices and config.plugins.speedyservicescanupdates.add_new_tv_services.value:
                    bouquet_handler.addToIndexBouquet("tv")
                    if config.plugins.speedyservicescanupdates.clear_bouquet.value:
                        bouquet_handler.createSSUBouquet(newTVServices, "tv")
                    else:
                        if bouquet_handler.doesSSUBouquetFileExists("tv"):
                            bouquet_handler.appendToSSUBouquet(newTVServices, "tv")
                        else:
                            bouquet_handler.createSSUBouquet(newTVServices, "tv")

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
                preScanDB = None

    baseServiceScan_execEnd(self)

# Versionsprüfung und Updatecheck
def get_current_version():
    version_file = "/usr/lib/enigma2/python/Plugins/Extensions/speedyServiceScanUpdates/version.txt"
    try:
        with open(version_file, 'r') as f:
            return f.read().strip()
    except Exception as e:
        print("Fehler beim Lesen der Versionsdatei: {}".format(e))
        return "0.0"

def check_for_update(current_version, session):
    try:
        url = "https://raw.githubusercontent.com/speedy005/speedyServiceScanUpdates/main/version.txt"
        if sys.version_info[0] < 3:
            response = urllib.urlopen(url)  # Python 2
        else:
            with urllib.request.urlopen(url) as response:  # Python 3
                response = response.read().decode().strip()

        latest_version = response

        print("[speedyServiceScanUpdates] Aktuelle Version: {}, Neueste Version: {}".format(current_version, latest_version))

        if version.parse(latest_version) > version.parse(current_version):
            print("[speedyServiceScanUpdates] Ein Update ist verfügbar!")
            return latest_version, "https://github.com/speedy005/speedyServiceScanUpdates/archive/refs/tags/{}.zip".format(latest_version)
        else:
            print("[speedyServiceScanUpdates] Keine neue Version verfügbar.")
            return None, None

    except Exception as e:
        print("[speedyServiceScanUpdates] Fehler bei der Updateprüfung: {}".format(e))
        return None, None

def prompt_for_update(session, latest_version, download_url):
    def update_installed_callback(choice):
        if choice:
            download_and_install_update(download_url)
        else:
            print("User chose not to update.")

    session.openWithCallback(update_installed_callback, MessageBox,
                             "A new version {} is available. Do you want to install it?".format(latest_version),
                             MessageBox.TYPE_YESNO)

def download_and_install_update(download_url):
    try:
        download_path = "/tmp/plugin_update.zip"
        extract_path = "/tmp/speedyServiceScanUpdates_update/"

        urllib.request.urlretrieve(download_url, download_path)

        # Alte Extraktion entfernen
        if os.path.exists(extract_path):
            shutil.rmtree(extract_path)

        # ZIP entpacken
        with zipfile.ZipFile(download_path, 'r') as zip_ref:
            zip_ref.extractall(extract_path)

        # Plugin-Dateien ersetzen
        plugin_source_path = os.path.join(extract_path, os.listdir(extract_path)[0])
        plugin_dest_path = "/usr/lib/enigma2/python/Plugins/Extensions/speedyServiceScanUpdates"

        for item in os.listdir(plugin_source_path):
            s_item = os.path.join(plugin_source_path, item)
            d_item = os.path.join(plugin_dest_path, item)
            if os.path.exists(d_item):
                if os.path.isdir(d_item):
                    shutil.rmtree(d_item)
                else:
                    os.remove(d_item)
            if os.path.isdir(s_item):
                shutil.copytree(s_item, d_item)
            else:
                shutil.copy2(s_item, d_item)

        # Plugin neu laden
        if "Plugins.Extensions.speedyServiceScanUpdates" in sys.modules:
            importlib.reload(sys.modules["Plugins.Extensions.speedyServiceScanUpdates"])

        print("[speedyServiceScanUpdates] Update erfolgreich installiert!")

    except Exception as e:
        print("Fehler beim Update: {}".format(e))

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

        # Versionsprüfung beim Start durchführen
        current_version = get_current_version()
        latest_version, download_url = check_for_update(current_version, kwargs['session'])
        if latest_version:
            prompt_for_update(kwargs['session'], latest_version, download_url)

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


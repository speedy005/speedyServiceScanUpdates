# -*- coding: utf-8 -*-
from __future__ import print_function

import os
import sys
import zipfile
import shutil
import tempfile
import importlib

version = "3.5"

# Python 2 kompatible urllib
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

PY2 = sys.version_info[0] == 2
PY3 = sys.version_info[0] == 3

# Globale Variablen
baseServiceScan_execBegin = None
baseServiceScan_execEnd = None
preScanDB = None

# --- Funktionen für ServiceScan Wrapper ---
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

    state_val = getattr(self, "state", -1)
    print("[speedyServiceScanUpdates] ServiceScan_execEnd (%d) [%s]" % (state_val, str(flags)))

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

# --- Update-Funktionen ---
VERSION_FILE = "/usr/lib/enigma2/python/Plugins/Extensions/speedyServiceScanUpdates/version.txt"
GITHUB_VERSION_URL = "https://raw.githubusercontent.com/speedy005/speedyServiceScanUpdates/main/version.txt"
GITHUB_ZIP_URL = "https://github.com/speedy005/speedyServiceScanUpdates/archive/refs/heads/main.zip"
PLUGIN_PATH = "/usr/lib/enigma2/python/Plugins/Extensions/speedyServiceScanUpdates/"

def get_current_version():
    try:
        with open(VERSION_FILE, 'r') as f:
            return f.read().strip()
    except Exception as e:
        print("[speedyServiceScanUpdates] Fehler beim Lesen der lokalen Version:", e)
        return "0.0"

def parse_version(version):
    parts = version.split(".")
    while len(parts) < 3:
        parts.append("0")
    return tuple(map(int, parts))

def get_remote_version():
    try:
        response = urllib_request.urlopen(GITHUB_VERSION_URL).read()
        if PY3:
            response = response.decode("utf-8")
        return response.strip().split()[0]
    except Exception as e:
        print("[speedyServiceScanUpdates] Fehler beim Abrufen der Remote-Version:", e)
        return None

def download_and_install_update(session):
    try:
        tmp_dir = tempfile.mkdtemp()
        zip_path = os.path.join(tmp_dir, "plugin_update.zip")

        print("[speedyServiceScanUpdates] Downloading update...")
        req = urllib_request.urlopen(GITHUB_ZIP_URL)
        with open(zip_path, "wb") as f:
            f.write(req.read())
        print("[speedyServiceScanUpdates] Download complete:", zip_path)

        print("[speedyServiceScanUpdates] Extracting update...")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(tmp_dir)

        extracted_folder = os.path.join(tmp_dir, "speedyServiceScanUpdates-main",
                                       "usr", "lib", "enigma2", "python", "Plugins", "Extensions",
                                       "speedyServiceScanUpdates")
        for item in os.listdir(extracted_folder):
            s = os.path.join(extracted_folder, item)
            d = os.path.join(PLUGIN_PATH, item)
            if os.path.isdir(s):
                if os.path.exists(d):
                    shutil.rmtree(d)
                shutil.copytree(s, d)
            else:
                shutil.copy2(s, d)

        print("[speedyServiceScanUpdates] Update installed successfully!")
    except Exception as e:
        print("[speedyServiceScanUpdates] Fehler beim Update:", e)

def check_for_update(session):
    current_version = get_current_version()
    remote_version = get_remote_version()
    if not remote_version:
        return
    print("[speedyServiceScanUpdates] Local version:", current_version, "Remote version:", remote_version)
    if parse_version(remote_version) > parse_version(current_version):
        def callback(choice):
            if choice:
                download_and_install_update(session)
            else:
                print("[speedyServiceScanUpdates] User canceled update.")
        session.openWithCallback(callback, MessageBox,
            "A new version %s is available. Do you want to install it?" % remote_version,
            MessageBox.TYPE_YESNO)
    else:
        print("[speedyServiceScanUpdates] No update available.")

# --- Autostart Hook ---
def autostart(reason, **kwargs):
    if reason == 0 and "session" in kwargs:
        global baseServiceScan_execBegin, baseServiceScan_execEnd
        session = kwargs["session"]

        if baseServiceScan_execBegin is None:
            baseServiceScan_execBegin = ServiceScan.execBegin
        ServiceScan.execBegin = ServiceScan_execBegin

        if baseServiceScan_execEnd is None:
            baseServiceScan_execEnd = ServiceScan.execEnd
        ServiceScan.execEnd = ServiceScan_execEnd

        # Updateprüfung beim Start
        check_for_update(session)

# --- Menü & Setup ---
def SSUMain(session, **kwargs):
    from .SSUSetupScreen import SSUSetupScreen
    session.open(SSUSetupScreen)

def SSUMenuItem(menuid, **kwargs):
    if menuid == "scan":
        return [("speedy ServiceScanUpdates " + _("Setup"), SSUMain, "servicescanupdates", None)]
    return []

def menu(menuid, **kwargs):
    if menuid == "mainmenu":
        return [(_("speedy ServiceScanUpdates") + " " + _("Setup"), SSUMain,
                 "speedyservicescanupdates_mainmenu", 50)]
    return []

# --- Plugin Descriptor ---
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

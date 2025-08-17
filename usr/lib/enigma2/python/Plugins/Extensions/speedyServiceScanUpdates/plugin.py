# -*- coding: utf-8 -*-
from __future__ import print_function

from Plugins.Plugin import PluginDescriptor
from Components.config import config

# Kompatibler Import für ServiceScan
try:
    from Screens.ServiceScan import ServiceScan
except ImportError:
    from Components.ServiceScan import ServiceScan

from Tools.Directories import resolveFilename, SCOPE_CONFIG
from . import _

from .SSULameDBParser import SSULameDBParser

import sys
import json
import urllib.request
import zipfile
import os
from packaging import version
from Screens.MessageBox import MessageBox

# Import für ConfigListScreen hinzufügen
from Components.ConfigList import ConfigListScreen

# Weitere notwendige Initialisierungen
PY2 = sys.version_info[0] == 2
PY3 = sys.version_info[0] == 3

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

    state_val = getattr(self, "state", -1)
    print("[speedyServiceScanUpdates] ServiceScan_execEnd (%d) [%s]" % (state_val, str(flags)))

    if getattr(self, "state", None) == getattr(self, "DONE", None):
        if config.plugins.speedyservicescanupdates.add_new_tv_services.value or config.plugins.servicescanupdates.add_new_radio_services.value:
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

                print("[speedyServiceScanUpdates] Found %d new TV services" % len(newTVServices))
                if config.plugins.speedyservicescanupdates.add_new_tv_services.value and len(newTVServices) > 0:
                    bouquet_handler.addToIndexBouquet("tv")
                    if config.plugins.speedyservicescanupdates.clear_bouquet.value:
                        bouquet_handler.createSSUBouquet(newTVServices, "tv")
                    else:
                        if bouquet_handler.doesSSUBouquetFileExists("tv"):
                            bouquet_handler.appendToSSUBouquet(newTVServices, "tv")
                        else:
                            bouquet_handler.createSSUBouquet(newTVServices, "tv")

                print("[speedyServiceScanUpdates] Found %d new radio services" % len(newRadioServices))
                if config.plugins.speedyservicescanupdates.add_new_radio_services.value and len(newRadioServices) > 0:
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


# Funktion zum Auslesen der aktuellen Version aus der version.txt
def get_current_version():
    version_file = "/usr/lib/enigma2/python/Plugins/Extensions/speedyServiceScanUpdates/version.txt"
    try:
        with open(version_file, 'r') as f:
            version = f.read().strip()
            return version
    except Exception as e:
        print(f"Fehler beim Lesen der Versionsdatei: {e}")
        return "0.0"


def check_for_update(current_version):
    try:
        url = "https://raw.githubusercontent.com/speedy005/speedyServiceScanUpdates/main/version.txt"
        response = urllib.request.urlopen(url)
        data = json.loads(response.read())

        # Debugging: Überprüfe die Antwort von GitHub
        print(f"[speedyServiceScanUpdates] GitHub API Antwort: {data}")

        latest_version = data['tag_name']
        download_url = data['assets'][0]['browser_download_url']

        # Debugging: Zeige die Versionen an
        print(f"[speedyServiceScanUpdates] Aktuelle Version: {current_version}, Neueste Version: {latest_version}")

        if version.parse(latest_version) > version.parse(current_version):
            print(f"[speedyServiceScanUpdates] Ein Update ist verfügbar!")
            return latest_version, download_url
        else:
            print(f"[speedyServiceScanUpdates] Keine neue Version verfügbar.")
            return None, None

    except Exception as e:
        print(f"[speedyServiceScanUpdates] Fehler bei der Überprüfung des Updates: {e}")
        return None, None


def prompt_for_update(session, latest_version, download_url):
    print(f"[speedyServiceScanUpdates] Update verfügbar: {latest_version}")
    
    def update_installed_callback(choice):
        if choice:
            print("Downloading and installing the update...")
            download_and_install_update(download_url)
        else:
            print("User chose not to update.")

    session.openWithCallback(update_installed_callback, MessageBox,
                            f"A new version {latest_version} is available. Do you want to install it?", MessageBox.TYPE_YESNO)


def download_and_install_update(download_url):
    try:
        download_path = "/tmp/plugin_update.zip"
        urllib.request.urlretrieve(download_url, download_path)
        print(f"Downloaded update to {download_path}")

        with zipfile.ZipFile(download_path, 'r') as zip_ref:
            zip_ref.extractall("/tmp/")
            print("Update extracted.")

        os.rename("/tmp/speedyServiceScanUpdates", "/usr/lib/enigma2/python/Plugins/Extensions/speedyServiceScanUpdates")
        print("Update installed successfully.")

        restart_plugin()

    except Exception as e:
        print(f"Error during update installation: {e}")


def restart_plugin():
    print("Restarting the plugin to apply the update...")
    os.system("init 6")  # Box Neustart


def autostart(reason, **kwargs):
    if reason == 0 and "session" in kwargs:
        global baseServiceScan_execBegin
        if baseServiceScan_execBegin is None:
            baseServiceScan_execBegin = ServiceScan.execBegin
        ServiceScan.execBegin = ServiceScan_execBegin

        global baseServiceScan_execEnd
        if baseServiceScan_execEnd is None:
            baseServiceScan_execEnd = ServiceScan.execEnd
        ServiceScan.execEnd = ServiceScan_execEnd


def SSUMain(session, **kwargs):
    from .SSUSetupScreen import SSUSetupScreen
    session.open(SSUSetupScreen)


def SSUMenuItem(menuid, **kwargs):
    if menuid == "scan":
        return [("speedy ServiceScanUpdates " + _("Setup"), SSUMain, "servicescanupdates", None)]
    else:
        return []


def menu(menuid, **kwargs):
    if menuid == "mainmenu":
        return [(_("speedy ServiceScanUpdates") + " " + _("Setup"), SSUMain, "speedyservicescanupdates_mainmenu", 50)]
    return []


def Plugins(**kwargs):
    current_version = get_current_version()  # Hol die aktuelle Version aus der version.txt

    # Überprüfe, ob eine neuere Version verfügbar ist
    latest_version, download_url = check_for_update(current_version)
    if latest_version:
        prompt_for_update(kwargs['session'], latest_version, download_url)

    return [
        PluginDescriptor(
            where=[PluginDescriptor.WHERE_SESSIONSTART, PluginDescriptor.WHERE_AUTOSTART],
            fnc=autostart
        ),
        PluginDescriptor(
            name="speedy ServiceScanUpdates " + _("Setup"),
            description=_("Updates during service scan"),
            where=PluginDescriptor.WHERE_PLUGINMENU,
            icon="plugin.png",
            fnc=SSUMain
        ),
        PluginDescriptor(
            name="speedy ServiceScanUpdates " + _("Setup"),
            description=_("Updates during service scan"),
            where=PluginDescriptor.WHERE_EXTENSIONSMENU,
            icon="plugin.png",
            fnc=SSUMain
        ),
        PluginDescriptor(
            where=PluginDescriptor.WHERE_MENU,
            fnc=menu
        ),
        PluginDescriptor(
            where=PluginDescriptor.WHERE_MENU,
            fnc=SSUMenuItem
        )
    ]

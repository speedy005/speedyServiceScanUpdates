# -*- coding: utf-8 -*-
from __future__ import print_function

import os
import sys
import zipfile
import shutil
import tempfile
import re
import traceback

version = "3.5"

# Python 2 compatible urllib
try:
    import urllib2 as urllib_request
except Exception:
    import urllib.request as urllib_request

from Plugins.Plugin import PluginDescriptor
from .SSUChangelogScreen import SSUChangelogScreen
from distutils.dir_util import copy_tree
from Components.config import config
from Tools.Directories import resolveFilename, SCOPE_CONFIG
from Screens.MessageBox import MessageBox
from Screens.Standby import TryQuitMainloop
from Components.ConfigList import ConfigListScreen

# Compatible import for ServiceScan
try:
    from Screens.ServiceScan import ServiceScan  # Python 3
except Exception:
    from Components.ServiceScan import ServiceScan  # Python 2

# enigma timer (for delayed opening of MessageBox)
try:
    from enigma import eTimer
except Exception:
    eTimer = None

from . import _
from .SSULameDBParser import SSULameDBParser

PY2 = sys.version_info[0] == 2
PY3 = sys.version_info[0] == 3

# Global variables
baseServiceScan_execBegin = None
baseServiceScan_execEnd = None
preScanDB = None

# --- Logging ---
LOGFILE = "/tmp/speedyServiceScanUpdates.log"

def log(msg):
    try:
        with open(LOGFILE, "a") as f:
            f.write(msg + "\n")
    except Exception:
        pass
    try:
        print(msg)
    except Exception:
        pass

# --- Functions for ServiceScan Wrapper ---
def dictHasKey(dictionary, key):
    if PY2:
        return dictionary.has_key(key)
    else:
        return key in dictionary

def safeClose(db):
    if hasattr(db, "close"):
        try:
            db.close()
        except Exception:
            pass

def ServiceScan_execBegin(self):
    flags = None
    try:
        flags = self.scanList[self.run]["flags"]
    except (AttributeError, KeyError, IndexError, TypeError):
        flags = "N/A"
    log("[speedyServiceScanUpdates] ServiceScan_execBegin [%s]" % str(flags))

    global preScanDB
    try:
        if not preScanDB and (config.plugins.speedyservicescanupdates.add_new_tv_services.value or
                              config.plugins.speedyservicescanupdates.add_new_radio_services.value):
            preScanDB = SSULameDBParser(resolveFilename(SCOPE_CONFIG) + "/lamedb")
    except Exception as e:
        log("[speedyServiceScanUpdates] Error loading preScanDB: %s" % e)
    try:
        baseServiceScan_execBegin(self)
    except Exception as e:
        log("[speedyServiceScanUpdates] Error calling baseServiceScan_execBegin: %s" % e)

def ServiceScan_execEnd(self, onClose=True):
    flags = None
    try:
        flags = self.scanList[self.run]["flags"]
    except (AttributeError, KeyError, IndexError, TypeError):
        flags = "N/A"

    state_val = getattr(self, "state", -1)
    log("[speedyServiceScanUpdates] ServiceScan_execEnd (%d) [%s]" % (state_val, str(flags)))

    try:
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
    except Exception as e:
        log("[speedyServiceScanUpdates] Error in ServiceScan_execEnd: %s" % e)

    try:
        baseServiceScan_execEnd(self)
    except Exception as e:
        log("[speedyServiceScanUpdates] Error calling baseServiceScan_execEnd: %s" % e)

# --- Update Functions ---
VERSION_FILE = "/usr/lib/enigma2/python/Plugins/Extensions/speedyServiceScanUpdates/version.txt"
LAST_UPDATE_FILE = "/usr/lib/enigma2/python/Plugins/Extensions/speedyServiceScanUpdates/last_update_version.txt"
GITHUB_VERSION_URL = "https://raw.githubusercontent.com/speedy005/speedyServiceScanUpdates/main/version.txt"
GITHUB_CHANGELOG_URL = "https://raw.githubusercontent.com/speedy005/speedyServiceScanUpdates/main/changelog.txt"
GITHUB_ZIP_URL = "https://github.com/speedy005/speedyServiceScanUpdates/archive/refs/heads/main.zip"
PLUGIN_PATH = "/usr/lib/enigma2/python/Plugins/Extensions/speedyServiceScanUpdates/"

def get_current_version():
    try:
        with open(VERSION_FILE, 'r') as f:
            ver = f.read().strip()
            log("[speedyServiceScanUpdates] Local version: %s" % ver)
            return ver
    except Exception as e:
        log("[speedyServiceScanUpdates] Error reading local version: %s" % e)
        return "0.0"

def parse_version(version):
    if not version:
        return (0, 0, 0)
    try:
        v = version.strip().lower()
        if v.startswith("v"):
            v = v[1:]
        parts = re.findall(r"\d+", v)
        while len(parts) < 3:
            parts.append("0")
        return tuple(map(int, parts[:3]))
    except Exception as e:
        log("[speedyServiceScanUpdates] Error parsing version '%s': %s" % (version, e))
        return (0, 0, 0)

def get_remote_version():
    try:
        response = urllib_request.urlopen(GITHUB_VERSION_URL).read()
        if PY3:
            response = response.decode("utf-8")
        remote_ver = response.strip().split()[0]
        log("[speedyServiceScanUpdates] Remote version from GitHub: %s" % remote_ver)
        return remote_ver
    except Exception as e:
        log("[speedyServiceScanUpdates] Error fetching remote version: %s" % e)
        return None

def download_and_install_update(session):
    tmp_dir = None
    try:
        tmp_dir = tempfile.mkdtemp()
        zip_path = os.path.join(tmp_dir, "plugin_update.zip")

        log("[speedyServiceScanUpdates] Downloading update...")
        req = urllib_request.urlopen(GITHUB_ZIP_URL)
        data = req.read()
        with open(zip_path, "wb") as f:
            f.write(data)
        log("[speedyServiceScanUpdates] Download complete: %s" % zip_path)

        log("[speedyServiceScanUpdates] Extracting update...")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(tmp_dir)

        # Search for plugin folder in extracted ZIP
        new_plugin_folder = None
        for root, dirs, files in os.walk(tmp_dir):
            if root.endswith(os.path.join(
                "usr", "lib", "enigma2", "python", "Plugins", "Extensions", "speedyServiceScanUpdates"
            )):
                new_plugin_folder = root
                break

        if not new_plugin_folder:
            raise Exception("Extracted plugin directory not found!")

        # Delete old plugin folder
        if os.path.exists(PLUGIN_PATH):
            log("[speedyServiceScanUpdates] Deleting old plugin folder: %s" % PLUGIN_PATH)
            shutil.rmtree(PLUGIN_PATH, ignore_errors=True)

        # Copy all contents of the new plugin folder
        log("[speedyServiceScanUpdates] Copying new plugin folder to: %s" % PLUGIN_PATH)
        copy_tree(new_plugin_folder, PLUGIN_PATH)

        # Update version
        remote_version = get_remote_version()
        if remote_version:
            try:
                with open(VERSION_FILE, "w") as vf:
                    vf.write(remote_version + "\n")
                # Save that changelog has not yet been shown
                with open(LAST_UPDATE_FILE, "w") as lf:
                    lf.write(remote_version + "\n")
                log("[speedyServiceScanUpdates] Updated local version.txt to %s" % remote_version)
            except Exception as e:
                log("[speedyServiceScanUpdates] Could not write version.txt: %s" % e)

        log("[speedyServiceScanUpdates] Update installed successfully!")

        # GUI restart
        def restartGUI(answer):
            try:
                if answer:
                    log("[speedyServiceScanUpdates] Restarting GUI...")
                    session.open(TryQuitMainloop, 3)
                else:
                    log("[speedyServiceScanUpdates] User chose not to restart GUI.")
            except Exception as e:
                log("[speedyServiceScanUpdates] Error calling restart: %s" % e)

        try:
            session.openWithCallback(
                restartGUI, MessageBox,
                "Update installed successfully!\nDo you want to restart the GUI now?",
                MessageBox.TYPE_YESNO
            )
        except Exception as e:
            log("[speedyServiceScanUpdates] Could not open restart MessageBox: %s" % e)

    except Exception as e:
        log("[speedyServiceScanUpdates] Error during update: %s" % e)
        traceback.print_exc()
        try:
            session.open(MessageBox, "Error during update:\n%s" % str(e), MessageBox.TYPE_ERROR)
        except Exception:
            pass

    finally:
        if tmp_dir:
            try:
                shutil.rmtree(tmp_dir, ignore_errors=True)
            except Exception:
                pass

def show_changelog_if_needed(session):
    """
    Checks whether to show changelog (after update)
    """
    last_version = None
    try:
        if os.path.exists(LAST_UPDATE_FILE):
            with open(LAST_UPDATE_FILE, "r") as f:
                last_version = f.read().strip()
    except Exception:
        pass

    current_version = get_current_version()

    if last_version and last_version == current_version:
        try:
            # Load changelog from GitHub
            changelog_data = urllib_request.urlopen(GITHUB_CHANGELOG_URL).read()
            if PY3:
                changelog_data = changelog_data.decode("utf-8")
            # Show MessageBox
            session.open(MessageBox, "Changelog:\n\n%s" % changelog_data, MessageBox.TYPE_INFO)
        except Exception as e:
            log("[speedyServiceScanUpdates] Error loading changelog: %s" % e)

        # Delete file so changelog is shown only once
        try:
            os.remove(LAST_UPDATE_FILE)
        except Exception:
            pass

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

        log("[speedyServiceScanUpdates] Autostart: ServiceScan wrapper active, skipping update check on start.")

# --- Menu & Setup ---
def SSUMain(session, **kwargs):
    from .SSUSetupScreen import SSUSetupScreen

    try:
        # Show changelog if needed
        show_changelog_if_needed(session)
        session.open(SSUSetupScreen)
    except Exception as e:
        log("[speedyServiceScanUpdates] Error opening SetupScreen: %s" % e)

def precheck_update_and_open(session, **kwargs):
    from .SSUSetupScreen import SSUSetupScreen

    def open_plugin():
        try:
            show_changelog_if_needed(session)
            session.open(SSUSetupScreen)
        except Exception as e:
            log("[speedyServiceScanUpdates] Error opening SetupScreen: %s" % e)

    try:
        current_version = get_current_version()
        remote_version = get_remote_version()

        if remote_version and parse_version(remote_version) > parse_version(current_version):
            # Update available → show MessageBox
            def callback(choice):
                if choice:
                    log("[speedyServiceScanUpdates] User confirmed update → starting download")
                    download_and_install_update(session)
                else:
                    log("[speedyServiceScanUpdates] User declined update.")
                    open_plugin()  # Open plugin anyway

            session.openWithCallback(
                callback, MessageBox,
                "A new version %s is available.\nDo you want to install the update?" % remote_version,
                MessageBox.TYPE_YESNO
            )
        else:
            # No update → open plugin immediately (possibly show changelog)
            open_plugin()

    except Exception as e:
        log("[speedyServiceScanUpdates] Error during update check: %s" % e)
        open_plugin()

def SSUMenuItem(menuid, **kwargs):
    if menuid == "scan":
        return [("speedy ServiceScanUpdates " + _("Setup"), precheck_update_and_open, "servicescanupdates", None)]
    return []

def menu(menuid, **kwargs):
    if menuid == "mainmenu":
        return [(_("speedyServiceScanUpdates") + " " + _("Setup"), precheck_update_and_open,
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
                         fnc=precheck_update_and_open),
        PluginDescriptor(name="speedy ServiceScanUpdates " + _("Setup"),
                         description=_("Updates during service scan"),
                         where=PluginDescriptor.WHERE_EXTENSIONSMENU,
                         icon="plugin.png",
                         fnc=precheck_update_and_open),
        PluginDescriptor(where=PluginDescriptor.WHERE_MENU, fnc=menu),
        PluginDescriptor(where=PluginDescriptor.WHERE_MENU, fnc=SSUMenuItem)
    ]

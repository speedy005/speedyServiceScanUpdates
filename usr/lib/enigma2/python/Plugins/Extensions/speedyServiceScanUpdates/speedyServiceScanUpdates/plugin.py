# -*- coding: utf-8 -*-
from __future__ import print_function

import os
import sys
import zipfile
import shutil
import tempfile
import importlib
import re
import traceback

version = "3.5"

# Python 2 kompatible urllib
try:
    import urllib2 as urllib_request
except Exception:
    import urllib.request as urllib_request

from Plugins.Plugin import PluginDescriptor
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

# enigma timer (für verzögertes Öffnen der MessageBox)
try:
    from enigma import eTimer
except Exception:
    eTimer = None

from . import _
from .SSULameDBParser import SSULameDBParser

PY2 = sys.version_info[0] == 2
PY3 = sys.version_info[0] == 3

# Globale Variablen
baseServiceScan_execBegin = None
baseServiceScan_execEnd = None
preScanDB = None

# --- Logging ---
LOGFILE = "/tmp/speedyServiceScanUpdates.log"

def log(msg):
    """Schreibt Debug-Logs nach /tmp/speedyServiceScanUpdates.log und auf die Konsole."""
    try:
        with open(LOGFILE, "a") as f:
            f.write(msg + "\n")
    except Exception:
        pass
    try:
        print(msg)
    except Exception:
        pass

# --- Funktionen für ServiceScan Wrapper ---
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
        log("[speedyServiceScanUpdates] Fehler beim Laden preScanDB: %s" % e)
    try:
        baseServiceScan_execBegin(self)
    except Exception as e:
        log("[speedyServiceScanUpdates] Fehler beim Aufruf baseServiceScan_execBegin: %s" % e)

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
        log("[speedyServiceScanUpdates] Fehler in ServiceScan_execEnd: %s" % e)

    try:
        baseServiceScan_execEnd(self)
    except Exception as e:
        log("[speedyServiceScanUpdates] Fehler beim Aufruf baseServiceScan_execEnd: %s" % e)

# --- Update-Funktionen ---
VERSION_FILE = "/usr/lib/enigma2/python/Plugins/Extensions/speedyServiceScanUpdates/version.txt"
GITHUB_VERSION_URL = "https://raw.githubusercontent.com/speedy005/speedyServiceScanUpdates/main/version.txt"
GITHUB_ZIP_URL = "https://github.com/speedy005/speedyServiceScanUpdates/archive/refs/heads/main.zip"
PLUGIN_PATH = "/usr/lib/enigma2/python/Plugins/Extensions/speedyServiceScanUpdates/"

def get_current_version():
    try:
        with open(VERSION_FILE, 'r') as f:
            ver = f.read().strip()
            log("[speedyServiceScanUpdates] Lokale Version: %s" % ver)
            return ver
    except Exception as e:
        log("[speedyServiceScanUpdates] Fehler beim Lesen der lokalen Version: %s" % e)
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
        log("[speedyServiceScanUpdates] Fehler beim Parsen der Version '%s': %s" % (version, e))
        return (0, 0, 0)

def get_remote_version():
    try:
        response = urllib_request.urlopen(GITHUB_VERSION_URL).read()
        if PY3:
            try:
                response = response.decode("utf-8")
            except Exception:
                pass
        remote_ver = response.strip().split()[0]
        log("[speedyServiceScanUpdates] Remote-Version vom GitHub: %s" % remote_ver)
        return remote_ver
    except Exception as e:
        log("[speedyServiceScanUpdates] Fehler beim Abrufen der Remote-Version: %s" % e)
        return None

def download_and_install_update(session):
    try:
        tmp_dir = tempfile.mkdtemp()
        zip_path = os.path.join(tmp_dir, "plugin_update.zip")

        log("[speedyServiceScanUpdates] Lade Update herunter...")
        req = urllib_request.urlopen(GITHUB_ZIP_URL)
        with open(zip_path, "wb") as f:
            f.write(req.read())
        log("[speedyServiceScanUpdates] Download abgeschlossen: %s" % zip_path)

        log("[speedyServiceScanUpdates] Entpacke Update...")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(tmp_dir)

        extracted_root = None
        for name in os.listdir(tmp_dir):
            if name.startswith("speedyServiceScanUpdates"):
                candidate = os.path.join(tmp_dir, name,
                                         "usr", "lib", "enigma2", "python", "Plugins", "Extensions",
                                         "speedyServiceScanUpdates")
                if os.path.exists(candidate):
                    extracted_root = candidate
                    break

        if not extracted_root or not os.path.exists(extracted_root):
            raise Exception("Entpacktes Plugin-Verzeichnis nicht gefunden!")

        log("[speedyServiceScanUpdates] Kopiere Dateien nach: %s" % PLUGIN_PATH)
        for item in os.listdir(extracted_root):
            s = os.path.join(extracted_root, item)
            d = os.path.join(PLUGIN_PATH, item)
            try:
                if os.path.isdir(s):
                    if os.path.exists(d):
                        shutil.rmtree(d)
                    shutil.copytree(s, d)
                else:
                    shutil.copy2(s, d)
            except Exception as e:
                log("[speedyServiceScanUpdates] Fehler beim Kopieren %s -> %s : %s" % (s, d, e))

        # Version.txt aktualisieren
        remote_version = get_remote_version()
        if remote_version:
            try:
                with open(VERSION_FILE, "w") as vf:
                    vf.write(remote_version + "\n")
                log("[speedyServiceScanUpdates] Lokale version.txt aktualisiert auf %s" % remote_version)
            except Exception as e:
                log("[speedyServiceScanUpdates] Konnte version.txt nicht schreiben: %s" % e)

        log("[speedyServiceScanUpdates] Update erfolgreich installiert!")

        # GUI-Neustart anbieten
        def restartGUI(answer):
            try:
                if answer:
                    log("[speedyServiceScanUpdates] Starte GUI neu...")
                    session.open(TryQuitMainloop, 3)
                else:
                    log("[speedyServiceScanUpdates] Benutzer möchte GUI nicht neustarten.")
            except Exception as e:
                log("[speedyServiceScanUpdates] Fehler beim Neustart-Aufruf: %s" % e)

        try:
            session.openWithCallback(
                restartGUI, MessageBox,
                "Update erfolgreich installiert!\nSoll die GUI jetzt neu gestartet werden?",
                MessageBox.TYPE_YESNO
            )
        except Exception as e:
            log("[speedyServiceScanUpdates] Konnte Restart-MessageBox nicht öffnen: %s" % e)

    except Exception as e:
        log("[speedyServiceScanUpdates] Fehler beim Update: %s" % e)
        traceback.print_exc()
        try:
            session.open(MessageBox, "Fehler beim Update:\n%s" % str(e), MessageBox.TYPE_ERROR)
        except Exception:
            pass

def check_for_update(session):
    current_version = get_current_version()
    remote_version = get_remote_version()

    if not remote_version:
        log("[speedyServiceScanUpdates] Keine Remote-Version gefunden.")
        return False

    log("[speedyServiceScanUpdates] Lokale Version: %s" % current_version)
    log("[speedyServiceScanUpdates] Remote Version: %s" % remote_version)

    try:
        if parse_version(remote_version) > parse_version(current_version):
            log("[speedyServiceScanUpdates] Update verfügbar: %s" % remote_version)

            def ask_update():
                def callback(choice):
                    if choice:
                        log("[speedyServiceScanUpdates] Benutzer bestätigt Update → starte Download")
                        download_and_install_update(session)
                    else:
                        log("[speedyServiceScanUpdates] Benutzer hat Update abgelehnt.")

                try:
                    session.openWithCallback(
                        callback, MessageBox,
                        "Eine neue Version %s ist verfügbar.\nMöchten Sie das Update installieren?" % remote_version,
                        MessageBox.TYPE_YESNO
                    )
                except Exception as e:
                    log("[speedyServiceScanUpdates] Konnte Update-MessageBox nicht öffnen: %s" % e)

            ask_update()
            return True  # Update vorhanden
        else:
            log("[speedyServiceScanUpdates] Kein Update verfügbar.")
            return False
    except Exception as e:
        log("[speedyServiceScanUpdates] Fehler beim Vergleich der Versionen: %s" % e)
        return False


# --- Autostart Hook ---
def autostart(reason, **kwargs):
    if reason == 0 and "session" in kwargs:
        global baseServiceScan_execBegin, baseServiceScan_execEnd
        session = kwargs["session"]

        # ServiceScan Wrapping bleibt aktiv
        if baseServiceScan_execBegin is None:
            baseServiceScan_execBegin = ServiceScan.execBegin
        ServiceScan.execBegin = ServiceScan_execBegin

        if baseServiceScan_execEnd is None:
            baseServiceScan_execEnd = ServiceScan.execEnd
        ServiceScan.execEnd = ServiceScan_execEnd

        log("[speedyServiceScanUpdates] Autostart: ServiceScan Wrapper aktiv, Updateprüfung entfällt beim Start.")


# --- Menü & Setup ---
def SSUMain(session, **kwargs):
    from .SSUSetupScreen import SSUSetupScreen

    try:
        session.open(SSUSetupScreen)
    except Exception as e:
        log("[speedyServiceScanUpdates] Fehler beim Öffnen des SetupScreens: %s" % e)


def precheck_update_and_open(session, **kwargs):
    """
    Updateprüfung vor Öffnen des SetupScreens.
    MessageBox erscheint sofort über dem vorherigen Screen.
    """
    from .SSUSetupScreen import SSUSetupScreen

    def open_plugin():
        try:
            session.open(SSUSetupScreen)
        except Exception as e:
            log("[speedyServiceScanUpdates] Fehler beim Öffnen des SetupScreens: %s" % e)

    try:
        current_version = get_current_version()
        remote_version = get_remote_version()

        if remote_version and parse_version(remote_version) > parse_version(current_version):
            # Update verfügbar → MessageBox anzeigen
            def callback(choice):
                if choice:
                    log("[speedyServiceScanUpdates] Benutzer bestätigt Update → starte Download")
                    download_and_install_update(session)
                else:
                    log("[speedyServiceScanUpdates] Benutzer hat Update abgelehnt.")
                    open_plugin()  # Plugin trotzdem öffnen

            session.openWithCallback(
                callback, MessageBox,
                "Eine neue Version %s ist verfügbar.\nMöchten Sie das Update installieren?" % remote_version,
                MessageBox.TYPE_YESNO
            )
        else:
            # Kein Update → Plugin sofort öffnen
            open_plugin()

    except Exception as e:
        log("[speedyServiceScanUpdates] Fehler bei Updateprüfung: %s" % e)
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




# -*- coding: utf-8 -*-
import os
import shutil
import requests
from enigma import ePixmap, eLabel, getDesktop, eTimer
from Screens.Screen import Screen
from Screens.MessageBox import MessageBox
from Screens.Standby import TryQuitMainloop
from Components.ConfigList import ConfigListScreen
from Components.ActionMap import ActionMap
from Components.Button import Button
from Components.Label import Label
from Components.ProgressBar import ProgressBar
from Tools.Directories import resolveFilename, SCOPE_CONFIG

# Lokale Übersetzungen
from . import _

# ===== Constants / Paths =====
UPDATE_URL = "https://github.com/speedy005/speedyServiceScanUpdates/archive/refs/heads/main.zip"
DOWNLOAD_PATH = "/tmp/ServiceScanUpdates-main.zip"
EXTRACT_DIR = "/tmp/ServiceScanUpdates"
TARGET_DIR = "/usr/lib/enigma2/python/Plugins/Extensions/speedyServiceScanUpdates"
TEMP_UPDATE_FILE = "/tmp/temp_update.zip"  # Temporäre Update-Datei

# ===== Config =====
# Sicherstellen, dass die Plugin-Konfigurations-Subsektion existiert
if not hasattr(config, "plugins"):
    config.plugins = type("obj", (), {})()

# --- Plugin-Pfad dynamisch ermitteln (Extensions oder SystemPlugins) ---
plugin_path = None
for base in (
    "/usr/lib/enigma2/python/Plugins/Extensions",
    "/usr/lib/enigma2/python/Plugins/SystemPlugins"
):
    possible = os.path.join(base, "speedyServiceScanUpdates")  # Plugin-Ordnername
    if os.path.isdir(possible):
        plugin_path = possible
        break

def read_version():
    if not plugin_path:
        return "Unknown version"
    vf = os.path.join(plugin_path, "version")
    try:
        with open(vf, "r") as f:
            return f.read().strip()
    except Exception:
        return "Unknown version"

version = read_version()

# ===== Utility =====
def _safe_msg(session, text, mtype=MessageBox.TYPE_INFO, timeout=5):
    try:
        session.open(MessageBox, text, type=mtype, timeout=timeout)
    except Exception:
        pass

def _exists(path):
    try:
        return os.path.exists(path)
    except Exception:
        return False

class SSUUpdateScreen(Screen, ConfigListScreen):
    def __init__(self, session):
        # Konstruktoren der Elternklassen aufrufen
        Screen.__init__(self, session)
        ConfigListScreen.__init__(self, [], session=session)
        self.session = session
        
        # Bildschirmauflösung abfragen
        w, h = self._screen_size()
        
        # Debugging-Ausgabe für Bildschirmgrößen
        print(f"Screen width: {w}, Screen height: {h}")

        # Bestimmen der Bildschirmbreite basierend auf der Auflösung
        sz_w = 1180 if w >= 1920 and h >= 1080 else 1050
        print(f"sz_w is set to: {sz_w}")

        # Skin für verschiedene Auflösungen festlegen
        if w >= 1920 and h >= 1080:
            self.skin_update = """
            <screen name="SSUSetupScreen" position="center,170" size="1200,820" title="speedy Service Scan Updates" backgroundColor="black">
                <ePixmap pixmap="skin_default/buttons/red.png" position="10,5" size="5,70" scale="stretch" alphatest="on" />
                <ePixmap pixmap="skin_default/buttons/green.png" position="314,5" size="5,70" scale="stretch" alphatest="on" />
                <eLabel text="HELP" position="1110,753" size="80,35" backgroundColor="#777777" valign="center" halign="center" font="Regular;24" zPosition="5" />
                <widget name="key_red" position="19,8" zPosition="1" size="295,70" font="Regular;30" halign="center" valign="center" backgroundColor="#9f1313" transparent="1" shadowColor="black" shadowOffset="-2,-2" />
                <widget name="key_green" position="324,5" zPosition="1" size="300,70" font="Regular;30" halign="center" valign="center" foregroundColor="green" backgroundColor="#1f771f" transparent="1" shadowColor="black" shadowOffset="-2,-2" />
                <widget name="config" position="10,90" itemHeight="35" size="1180,500" enableWrapAround="1" scrollbarMode="showOnDemand" />
                <ePixmap pixmap="skin_default/div-h.png" position="10,650" zPosition="2" size="1180,2" />
                <ePixmap pixmap="skin_default/buttons/yellow.png" position="630,7" size="5,70" scale="stretch" alphatest="on" />
                <widget name="key_yellow" foregroundColor="yellow" position="638,6" size="300,70" font="Regular;30" halign="center" valign="center" />
                <widget name="version" position="444,593" size="150,50" font="Regular;30" valign="center" halign="left" />
                <ePixmap pixmap="skin_default/buttons/blue.png" position="945,7" size="5,70" scale="stretch" alphatest="on" />
                <widget name="key_blue" position="954,8" foregroundColor="blue" size="250,70" font="Regular;30" halign="center" valign="center" />
                <widget name="help" position="10,655" size="1180,140" font="Regular;32" />
                <ePixmap pixmap="skin_default/buttons/vkey_exit.png" position="1041,761" size="35,25" scale="stretch" alphatest="on" zPosition="6" />
            </screen>"""
        else:
            self.skin_update = """
            <screen name="SSUUpdateScreen" position="410,170" size="1100,820" title="speedy Service Scan Updates">
                <widget name="progress" position="10,100" size="1050,50" />
                <widget name="status" position="10,160" size="1050,50" font="Regular;30" valign="center" halign="center" />
                <widget name="progresstext" position="10,220" size="1050,50" font="Regular;30" valign="center" halign="center" />
                <widget name="key_red" position="13,2" size="250,70" font="Regular;30" halign="center" valign="center" />
                <widget name="key_green" foregroundColor="green" position="277,3" size="250,70" font="Regular;30" halign="center" valign="center" />
                <widget name="key_yellow" foregroundColor="yellow" position="538,4" size="250,70" font="Regular;30" halign="center" valign="center" />
                <widget name="key_blue" position="798,5" foregroundColor="blue" size="250,70" font="Regular;30" halign="center" valign="center" />
                <widget name="version" position="364,752" size="300,50" font="Regular;30" valign="center" halign="center" />
                <ePixmap pixmap="skin_default/buttons/red.png" position="0,0" size="5,75" scale="stretch" alphatest="on" />
                <ePixmap pixmap="skin_default/buttons/green.png" position="265,3" size="5,70" scale="stretch" alphatest="on" />
                <ePixmap pixmap="skin_default/buttons/yellow.png" position="530,0" size="5,70" scale="stretch" alphatest="on" />
                <ePixmap pixmap="skin_default/buttons/blue.png" position="790,7" size="5,70" scale="stretch" alphatest="on" />
            </screen>"""

        # Den Skin auf das aktuelle Objekt anwenden
        self.skin = self.skin_update

        # Titel festlegen
        self.setTitle(_("speedy Service Scan Updates"))

        # Initialisierungen und weitere Logik
        self['status'] = Label(_("Checking for updates..."))
        self['progress'] = ProgressBar()
        self['progresstext'] = Label("")
        self['key_red'] = Button(_("Exit"))
        self['key_green'] = Button(_("Start"))
        self['key_yellow'] = Button(_("Cancel"))
        self['key_blue'] = Button(_("Check Update"))
        self['version'] = Label(version)
        self['actions'] = ActionMap(['ColorActions', 'OkCancelActions'], {
            'red': self.exit,
            'green': self.start_update,
            'yellow': self.cancel,
            'blue': self.check_update,
            'ok': self.start_update,
            'cancel': self.exit
        }, -1)

        self.download_complete = False
        self.update_installed = False

        # Timer für GUI-Updates
        self.timer = eTimer()
        self.timer.callback.append(self._update_gui)
        self.timer.start(100, True)

    def _update_gui(self):
        # Diese Methode wird alle 100ms aufgerufen
        self['progress'].setValue(self.download_progress)
        self['progresstext'].setText(f"{self.download_progress}%")

    def exit(self):
        print("Der Update-Bildschirm wird geschlossen...")
        self.close()

    def _finish_update(self):
        try:
            if not os.path.isdir(EXTRACT_DIR):
                self['status'].setText(_("Error: Extracted directory not found."))
                return
            if not os.path.isdir(TARGET_DIR):
                os.makedirs(TARGET_DIR)

            update_folder = os.path.join(EXTRACT_DIR, "usr", "lib", "enigma2", "python", "Plugins", "Extensions", "speedyServiceScanUpdate")

            if not os.path.isdir(update_folder):
                self['status'].setText(_("Error: Update folder not found."))
                return

            for item in os.listdir(update_folder):
                s = os.path.join(update_folder, item)
                d = os.path.join(TARGET_DIR, item)
                try:
                    if os.path.isdir(s):
                        if os.path.exists(d):
                            shutil.rmtree(d)
                        shutil.copytree(s, d)
                    else:
                        shutil.copy2(s, d)
                except Exception as e:
                    print(f"Fehler beim Kopieren: {str(e)}")
                    pass

            if not os.path.exists(TARGET_DIR):
                raise IOError("Target dir missing after extraction")

            self['status'].setText(_("Update completed successfully."))
            self.update_installed = True

            self.session.openWithCallback(self.restartGUI, MessageBox, _("Update complete. Do you want to restart the GUI?"), MessageBox.TYPE_YESNO)

        except Exception as e:
            print(f"Fehler in _finish_update: {str(e)}")
            self['status'].setText(_("Failed to complete update."))

    def check_update(self):
        if self._requests_missing():
            return
        self['status'].setText(_("Checking for updates..."))
        try:
            r = requests.head(UPDATE_URL, timeout=10)
            if r.status_code == 200:
                self['status'].setText(_("Update available"))
            else:
                self['status'].setText(_("No update available"))
        except Exception as e:
            print(f"Fehler beim Überprüfen des Updates: {str(e)}")
            self['status'].setText(_("Update check failed."))

    def start_update(self):
        if self._requests_missing():
            return
        self['status'].setText(_("Downloading update..."))
        try:
            r = requests.get(UPDATE_URL, stream=True, timeout=20)
            if r.status_code == 200:
                total_size = int(r.headers.get('Content-Length', 0))
                self.download_progress = 0
                with open(TEMP_UPDATE_FILE, 'wb') as f:
                    for data in r.iter_content(chunk_size=1024):
                        if data:
                            f.write(data)
                            self.download_progress += len(data) * 100 // total_size
                            self._update_gui()  # GUI während des Downloads aktualisieren
                self._finish_update()
            else:
                self['status'].setText(_("Download failed"))
        except Exception as e:
            print(f"Fehler beim Download des Updates: {str(e)}")
            self['status'].setText(_("Download failed"))
    
    def cancel(self):
        self['status'].setText(_("Update canceled"))
        self.close()

    def _screen_size(self):
        # Hier kannst du die Bildschirmauflösung korrekt abfragen
        return 1920, 1080  # Zum Testen auf eine Standardauflösung setzen

    def restartGUI(self, answer):
        if answer:
            self.session.open(TryQuitMainloop, 3)
        else:
            self.close()

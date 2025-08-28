# -*- coding: utf-8 -*-
from __future__ import print_function
import os
import shutil
import zipfile
import tempfile
import traceback

try:
    import requests
except ImportError:
    requests = None

from enigma import ePixmap, getDesktop, eTimer
from Screens.Screen import Screen
from Screens.MessageBox import MessageBox
from Screens.Standby import TryQuitMainloop
from Components.ConfigList import ConfigListScreen
from Components.ActionMap import ActionMap
from Components.Button import Button
from Components.Label import Label
from Components.ProgressBar import ProgressBar
from Components.config import config, ConfigSubsection, ConfigYesNo, getConfigListEntry
from Plugins.Plugin import PluginDescriptor
from Tools.Directories import resolveFilename, SCOPE_CONFIG
from . import _

# ===== Plugin-Pfade =====
PLUGIN_PATH = "/usr/lib/enigma2/python/Plugins/Extensions/speedyServiceScanUpdates"
UPDATE_URL = "https://github.com/speedy005/speedyServiceScanUpdates/archive/refs/heads/main.zip"
VERSION_FILE = os.path.join(PLUGIN_PATH, "version.txt")
DOWNLOAD_PATH = "/tmp/ServiceScanUpdates-main.zip"
EXTRACT_DIR = "/tmp/ServiceScanUpdates"

# ===== Config =====
config.plugins.speedyservicescanupdates = ConfigSubsection()
config.plugins.speedyservicescanupdates.add_new_tv_services = ConfigYesNo(default=True)
config.plugins.speedyservicescanupdates.add_new_radio_services = ConfigYesNo(default=True)
config.plugins.speedyservicescanupdates.clear_bouquet = ConfigYesNo(default=False)

# ===== Versionslesen =====
def read_version():
    try:
        with open(VERSION_FILE, "r") as f:
            return f.read().strip()
    except Exception:
        return "0.0.0"

version = read_version()

# ===== Hilfsfunktionen =====
def _safe_msg(session, text, mtype=None, timeout=5):
    try:
        session.open(MessageBox, text, type=mtype or MessageBox.TYPE_INFO, timeout=timeout)
    except Exception:
        pass

def copytree(src, dst):
    if not os.path.exists(dst):
        os.makedirs(dst)
    for item in os.listdir(src):
        s = os.path.join(src, item)
        d = os.path.join(dst, item)
        if os.path.isdir(s):
            copytree(s, d)
        else:
            shutil.copy2(s, d)

def update_progress(gui_label, progress):
    gui_label.setText("{}%".format(min(progress, 100)))

# ===== Update-Funktionen =====
def finish_update(session):
    update_folder = os.path.join(EXTRACT_DIR, "speedyServiceScanUpdates-main", "speedyServiceScanUpdates")
    if not os.path.isdir(update_folder):
        _safe_msg(session, "Fehler: Ordner speedyServiceScanUpdates nicht gefunden.")
        return
    copytree(update_folder, PLUGIN_PATH)
    _safe_msg(session, "Update erfolgreich abgeschlossen. GUI neu starten?")

def check_update(gui_label):
    if not requests:
        gui_label.setText("Requests-Modul fehlt")
        return
    gui_label.setText("Prüfe auf Updates...")
    try:
        r = requests.get("https://raw.githubusercontent.com/speedy005/speedyServiceScanUpdates/main/version.txt", timeout=10)
        if r.status_code == 200:
            remote_version = r.text.strip()
            if remote_version > version:
                gui_label.setText("Update verfügbar")
            else:
                gui_label.setText("Kein Update verfügbar")
        else:
            gui_label.setText("Kein Update verfügbar")
    except Exception as e:
        print("Fehler beim Update-Check:", str(e))
        gui_label.setText("Update-Check fehlgeschlagen.")

def start_update(gui_label, session=None):
    if not requests:
        gui_label.setText("Requests-Modul fehlt")
        return

    gui_label.setText("Update wird heruntergeladen...")
    try:
        r = requests.get(UPDATE_URL, stream=True, timeout=20)
        if r.status_code == 200:
            total_size = int(r.headers.get('Content-Length', 0))
            downloaded = 0
            with open(DOWNLOAD_PATH, 'wb') as f:
                for data in r.iter_content(chunk_size=1024):
                    if data:
                        f.write(data)
                        downloaded += len(data)
                        update_progress(gui_label, downloaded * 100 // max(total_size, 1))
            with zipfile.ZipFile(DOWNLOAD_PATH, 'r') as zip_ref:
                zip_ref.extractall(EXTRACT_DIR)
            finish_update(session)
        else:
            gui_label.setText("Download fehlgeschlagen")
    except Exception as e:
        print("Fehler beim Download:", str(e))
        gui_label.setText("Download fehlgeschlagen")

# ===== SSUUpdateScreen =====
class SSUUpdateScreen(Screen):
    def __init__(self, session):
        Screen.__init__(self, session)
        self.session = session
        desktop = getDesktop(0)
        width = desktop.size().width()

        # Skin abhängig von der Auflösung
        if width >= 1920:
            self.skin = """<screen name="SSUUpdateScreen" position="center,170" size="1200,820" title="speedy Service Scan Updates">
                <widget name="progress" position="10,100" size="1180,50" />
                <widget name="status" position="12,160" size="1180,50" font="Regular;30" valign="center" halign="center" />
                <widget name="progresstext" position="10,220" size="1180,50" font="Regular;30" valign="center" halign="center" />
                <widget name="key_red" position="3,4" size="295,70" font="Regular;30" halign="center" valign="center" />
                <widget name="key_green" foregroundColor="green" position="305,3" size="300,70" font="Regular;30" halign="center" valign="center" />
                <widget name="key_yellow" foregroundColor="yellow" position="609,3" size="300,70" font="Regular;30" halign="center" valign="center" />
                <widget name="key_blue" foregroundColor="blue" position="917,4" size="295,70" font="Regular;30" halign="center" valign="center" />
                <widget name="version" position="488,769" size="200,30" font="Regular;30" valign="center" halign="center" />
                <eLabel text="HELP" position="1110,753" size="80,35" backgroundColor="#777777" valign="center" halign="center" font="Regular;24" zPosition="5" />
                <ePixmap pixmap="skin_default/buttons/vkey_exit.png" position="1041,761" size="35,25" scale="stretch" alphatest="on" zPosition="6" />
                <ePixmap pixmap="skin_default/buttons/blue.png" position="909,5" size="5,70" scale="stretch" alphatest="on" />
                <ePixmap pixmap="skin_default/buttons/yellow.png" position="601,4" size="5,70" scale="stretch" alphatest="on" />
                <ePixmap pixmap="skin_default/buttons/green.png" position="300,5" size="5,70" scale="stretch" alphatest="on" />
                <ePixmap pixmap="skin_default/buttons/red.png" position="5,5" size="5,70" scale="stretch" alphatest="on" />
            </screen>"""
        else:
            self.skin = """<screen name="SSUUpdateScreen" position="410,170" size="1100,820" title="speedy Service Scan Updates">
                <widget name="progress" position="10,100" size="1050,50" />
                <widget name="status" position="10,160" size="1050,50" font="Regular;30" valign="center" halign="center" />
                <widget name="progresstext" position="10,220" size="1050,50" font="Regular;30" valign="center" halign="center" />
                <widget name="key_red" position="13,2" size="250,70" font="Regular;30" halign="center" valign="center" />
                <widget name="key_green" foregroundColor="green" position="277,3" size="250,70" font="Regular;30" halign="center" valign="center" />
                <widget name="key_yellow" foregroundColor="yellow" position="538,4" size="250,70" font="Regular;30" halign="center" valign="center" />
                <widget name="key_blue" position="798,5" foregroundColor="blue" size="250,70" font="Regular;30" halign="center" valign="center" />
                <widget name="version" position="364,752" size="300,50" font="Regular;30" valign="center" halign="center" />
                <eLabel text="HELP" position="930,761" size="80,35" backgroundColor="#777777" valign="center" halign="center" font="Regular;24" zPosition="5" />
                <ePixmap pixmap="skin_default/buttons/vkey_exit.png" position="841,761" size="35,25" scale="stretch" alphatest="on" zPosition="6" />
                <ePixmap pixmap="skin_default/buttons/blue.png" position="791,5" size="5,70" scale="stretch" alphatest="on" />
                <ePixmap pixmap="skin_default/buttons/yellow.png" position="529,2" size="5,70" scale="stretch" alphatest="on" />
                <ePixmap pixmap="skin_default/buttons/green.png" position="269,2" size="5,70" scale="stretch" alphatest="on" />
                <ePixmap pixmap="skin_default/buttons/red.png" position="5,5" size="5,70" scale="stretch" alphatest="on" />
            </screen>"""

        # GUI-Komponenten
        self['status'] = Label(_("Bereit"))
        self['progress'] = ProgressBar()
        self['progresstext'] = Label("")
        self['key_red'] = Button(_("Beenden"))
        self['key_green'] = Button(_("Start"))
        self['key_yellow'] = Button(_("Abbrechen"))
        self['key_blue'] = Button(_("Update prüfen"))
        self['version'] = Label(version)

        self['actions'] = ActionMap(['ColorActions', 'OkCancelActions'], {
            'red': self.exit,
            'green': self.start_update,
            'yellow': self.cancel,
            'blue': self.check_update,
            'ok': self.start_update,
            'cancel': self.exit
        }, -1)

        self.download_progress = 0
        self.timer = eTimer()
        self.timer.callback.append(self._update_gui)
        self.timer.start(100, True)

    def _update_gui(self):
        update_progress(self['progresstext'], self.download_progress)
        self['progress'].setValue(min(self.download_progress, 100))

    def exit(self):
        self.close()

    def cancel(self):
        self['status'].setText(_("Update abgebrochen"))
        self.close()

    def check_update(self):
        check_update(self['status'])

    def start_update(self):
        start_update(self['status'], self.session)

    def _finish_update(self):
        try:
            update_folder = os.path.join(EXTRACT_DIR, "speedyServiceScanUpdates-main", "speedyServiceScanUpdates")
            if not os.path.isdir(update_folder):
                self['status'].setText(_("Fehler: Ordner speedyServiceScanUpdates nicht gefunden."))
                return
            copytree(update_folder, PLUGIN_PATH)
            self['status'].setText(_("Update erfolgreich abgeschlossen."))
            self.session.openWithCallback(
                self.restartGUI,
                MessageBox,
                _("Update abgeschlossen. GUI neu starten?"),
                MessageBox.TYPE_YESNO
            )
        except Exception as e:
            print("Fehler beim Abschluss des Updates:", str(e))
            self['status'].setText(_("Update konnte nicht abgeschlossen werden."))

    def restartGUI(self, answer):
        if answer:
            self.session.open(TryQuitMainloop, 3)
        else:
            self.close()

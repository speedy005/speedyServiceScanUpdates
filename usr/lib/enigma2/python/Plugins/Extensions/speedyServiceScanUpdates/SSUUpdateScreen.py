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
from distutils.dir_util import copy_tree
from . import _

# ===== Plugin paths =====
PLUGIN_PATH = "/usr/lib/enigma2/python/Plugins/Extensions/speedyServiceScanUpdates"
UPDATE_URL = "https://github.com/speedy005/speedyServiceScanUpdates/archive/refs/heads/main.zip"
VERSION_FILE = os.path.join(PLUGIN_PATH, "version.txt")

# ===== Config =====
config.plugins.speedyservicescanupdates = ConfigSubsection()
config.plugins.speedyservicescanupdates.add_new_tv_services = ConfigYesNo(default=True)
config.plugins.speedyservicescanupdates.add_new_radio_services = ConfigYesNo(default=True)
config.plugins.speedyservicescanupdates.clear_bouquet = ConfigYesNo(default=False)

# ===== Read version =====
def read_version():
    try:
        with open(VERSION_FILE, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return "0.0.0"

version = read_version()

# ===== Helper functions =====
def _safe_msg(session, text, mtype=None, timeout=5):
    try:
        session.open(MessageBox, text, type=mtype or MessageBox.TYPE_INFO, timeout=timeout)
    except Exception:
        pass

def update_progress(gui_label, progress):
    gui_label.setText(_("{}%").format(min(progress, 100)))

# ===== Update functions =====
def finish_update(session, extract_dir):
    try:
        extracted_folder = os.path.join(extract_dir, "speedyServiceScanUpdates-main", "speedyServiceScanUpdates")
        if not os.path.isdir(extracted_folder):
            _safe_msg(session, _("Error: speedyServiceScanUpdates folder not found."))
            return

        if os.path.exists(PLUGIN_PATH):
            shutil.rmtree(PLUGIN_PATH)

        copy_tree(extracted_folder, PLUGIN_PATH)
        _safe_msg(session, _("Update successfully completed. Restart GUI?"))

    except Exception as e:
        print("Error finishing update:", str(e))
        _safe_msg(session, _("Update could not be completed."))

def check_update(gui_label):
    if not requests:
        gui_label.setText(_("Requests module missing"))
        return
    gui_label.setText(_("Checking for updates..."))
    try:
        r = requests.get("https://raw.githubusercontent.com/speedy005/speedyServiceScanUpdates/main/version.txt", timeout=10)
        if r.status_code == 200:
            remote_version = r.text.strip()
            if remote_version > version:
                gui_label.setText(_("Update available"))
            else:
                gui_label.setText(_("No update available"))
        else:
            gui_label.setText(_("No update available"))
    except Exception as e:
        print("Error checking update:", str(e))
        gui_label.setText(_("Update check failed."))

def start_update(gui_label, session=None):
    tmp_dir = None
    try:
        if not requests:
            gui_label.setText(_("Requests module missing"))
            return

        gui_label.setText(_("Downloading update..."))
        tmp_dir = tempfile.mkdtemp()
        zip_path = os.path.join(tmp_dir, "plugin_update.zip")

        r = requests.get(UPDATE_URL, stream=True, timeout=20)
        if r.status_code != 200:
            gui_label.setText(_("Download failed"))
            return

        total_size = int(r.headers.get('Content-Length', 0))
        downloaded = 0
        with open(zip_path, 'wb') as f:
            for data in r.iter_content(chunk_size=1024):
                if data:
                    f.write(data)
                    downloaded += len(data)
                    update_progress(gui_label, downloaded * 100 // max(total_size, 1))

        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(tmp_dir)

        finish_update(session, tmp_dir)

        remote_version_file = os.path.join(tmp_dir, "speedyServiceScanUpdates-main", "speedyServiceScanUpdates", "version.txt")
        if os.path.exists(remote_version_file):
            try:
                shutil.copy2(remote_version_file, VERSION_FILE)
            except Exception:
                pass

    except Exception as e:
        print("Error during update:", str(e))
        traceback.print_exc()
        try:
            session.open(MessageBox, _("Error during update:\n%s") % str(e), MessageBox.TYPE_ERROR)
        except Exception:
            pass
    finally:
        if tmp_dir and os.path.exists(tmp_dir):
            shutil.rmtree(tmp_dir, ignore_errors=True)

# ===== SSUUpdateScreen =====
class SSUUpdateScreen(Screen):
    def __init__(self, session):
        Screen.__init__(self, session)
        self.session = session
        desktop = getDesktop(0)
        width = desktop.size().width()

        # Skin based on resolution (ASCII-safe)
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

        # ===== Widgets =====
        self['status'] = Label(_("Ready"))
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
        self['status'].setText(_("Update cancelled"))
        self.close()

    def check_update(self):
        check_update(self['status'])

    def start_update(self):
        start_update(self['status'], self.session)

    def _finish_update(self):
        try:
            update_folder = os.path.join(EXTRACT_DIR, "speedyServiceScanUpdates-main", "speedyServiceScanUpdates")
            if not os.path.isdir(update_folder):
                self['status'].setText(_("Error: speedyServiceScanUpdates folder not found."))
                return
            copytree(update_folder, PLUGIN_PATH)
            self['status'].setText(_("Update successfully completed."))
            self.session.openWithCallback(
                self.restartGUI,
                MessageBox,
                _("Update completed. Restart GUI?"),
                MessageBox.TYPE_YESNO
            )
        except Exception as e:
            print("Error finishing update:", str(e))
            self['status'].setText(_("Update could not be completed."))

    def restartGUI(self, answer):
        if answer:
            self.session.open(TryQuitMainloop, 3)
        else:
            self.close()

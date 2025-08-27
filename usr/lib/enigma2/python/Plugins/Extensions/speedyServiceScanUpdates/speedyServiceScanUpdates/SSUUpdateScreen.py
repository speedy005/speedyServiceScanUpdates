# -*- coding: utf-8 -*-
import os
import shutil
import zipfile

try:
    import requests
except ImportError:
    requests = None

# --- Plugin-Pfad dynamisch ermitteln ---
plugin_path = None
for base in (
    "/usr/lib/enigma2/python/Plugins/Extensions",
    "/usr/lib/enigma2/python/Plugins/SystemPlugins"
):
    possible = os.path.join(base, "speedyServiceScanUpdates")
    if os.path.isdir(possible):
        plugin_path = possible
        break

# --- Enigma2 imports ---
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

# ===== Constants / Paths =====
UPDATE_URL = "https://github.com/speedy005/speedyServiceScanUpdates/archive/refs/heads/main.zip"
DOWNLOAD_PATH = "/tmp/ServiceScanUpdates-main.zip"
EXTRACT_DIR = "/tmp/ServiceScanUpdates"
TARGET_DIR = "/usr/lib/enigma2/python/Plugins/Extensions/speedyServiceScanUpdates"

# ===== Config =====
config.plugins.speedyservicescanupdates = ConfigSubsection()
config.plugins.speedyservicescanupdates.add_new_tv_services = ConfigYesNo(default=True)
config.plugins.speedyservicescanupdates.add_new_radio_services = ConfigYesNo(default=True)
config.plugins.speedyservicescanupdates.clear_bouquet = ConfigYesNo(default=False)

# ===== Version =====
def read_version():
    if not plugin_path:
        return "Unknown version"
    vf = os.path.join(plugin_path, "version.txt")
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

# ===== ServiceScan Import =====
ServiceScan = None
try:
    from Screens.ServiceScan import ServiceScan
except ImportError:
    try:
        from Plugins.SystemPlugins.ServiceScan.plugin import ServiceScan
    except ImportError:
        pass

# ===== SSUUpdateScreen =====
class SSUUpdateScreen(Screen):
    def __init__(self, session):
        Screen.__init__(self, session)
        self.session = session
        desktop = getDesktop(0)
        width = desktop.size().width()

        if width >= 1920:
            self.skin = """<screen name="SSUUpdateScreen" position="center,170" size="1200,820" title="speedy Service Scan Updates">
                <widget name="progress" position="10,100" size="1180,50" />
                <widget name="status" position="12,160" size="1180,50" font="Regular;30" valign="center" halign="center" />
                <widget name="progresstext" position="10,220" size="1180,50" font="Regular;30" valign="center" halign="center" />
                <widget name="key_red" position="3,4" size="295,70" font="Regular;30" halign="center" valign="center" />
                <widget name="key_green" foregroundColor="green" position="305,3" size="300,70" font="Regular;30" halign="center" valign="center" />
                <widget name="key_yellow" foregroundColor="yellow" position="604,5" size="300,70" font="Regular;30" halign="center" valign="center" />
                <widget name="key_blue" foregroundColor="blue" position="916,6" size="295,70" font="Regular;30" halign="center" valign="center" />
                <widget name="version" position="488,769" size="200,30" font="Regular;30" valign="center" halign="center" />
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
            </screen>"""

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
        self['progress'].setValue(min(self.download_progress, 100))
        self['progresstext'].setText(f"{min(self.download_progress, 100)}%")

    def exit(self):
        self.close()

    def _finish_update(self):
        try:
            if not os.path.isdir(EXTRACT_DIR):
                self['status'].setText(_("Error: Extracted directory not found."))
                return
            if not os.path.isdir(TARGET_DIR):
                os.makedirs(TARGET_DIR)

            update_folder = os.path.join(EXTRACT_DIR, "speedyServiceScanUpdates-main")
            for root, dirs, files in os.walk(update_folder):
                for d in dirs:
                    s = os.path.join(root, d)
                    rel = os.path.relpath(s, update_folder)
                    d_target = os.path.join(TARGET_DIR, rel)
                    if os.path.exists(d_target):
                        shutil.rmtree(d_target)
                    shutil.copytree(s, d_target)
                for f in files:
                    s = os.path.join(root, f)
                    rel = os.path.relpath(s, update_folder)
                    d_target = os.path.join(TARGET_DIR, rel)
                    shutil.copy2(s, d_target)

            self['status'].setText(_("Update completed successfully."))
            self.session.openWithCallback(self.restartGUI, MessageBox, _("Update complete. Do you want to restart the GUI?"), MessageBox.TYPE_YESNO)
        except Exception as e:
            print("Finish update error:", str(e))
            self['status'].setText(_("Failed to complete update."))

    def check_update(self):
        if not requests:
            self['status'].setText(_("Requests module missing"))
            return
        self['status'].setText(_("Checking for updates..."))
        try:
            r = requests.head(UPDATE_URL, timeout=10)
            if r.status_code == 200:
                self['status'].setText(_("Update available"))
            else:
                self['status'].setText(_("No update available"))
        except Exception as e:
            print("Check update error:", str(e))
            self['status'].setText(_("Update check failed."))

    def start_update(self):
        if not requests:
            self['status'].setText(_("Requests module missing"))
            return
        self['status'].setText(_("Downloading update..."))
        try:
            r = requests.get(UPDATE_URL, stream=True, timeout=20)
            if r.status_code == 200:
                total_size = int(r.headers.get('Content-Length', 0))
                self.download_progress = 0
                with open(DOWNLOAD_PATH, 'wb') as f:
                    for data in r.iter_content(chunk_size=1024):
                        if data:
                            f.write(data)
                            self.download_progress += len(data) * 100 // max(total_size, 1)
                            self._update_gui()
                with zipfile.ZipFile(DOWNLOAD_PATH, 'r') as zip_ref:
                    zip_ref.extractall(EXTRACT_DIR)
                self._finish_update()
            else:
                self['status'].setText(_("Download failed"))
        except Exception as e:
            print("Download error:", str(e))
            self['status'].setText(_("Download failed"))

    def cancel(self):
        self['status'].setText(_("Update canceled"))
        self.close()

    def restartGUI(self, answer):
        if answer:
            self.session.open(TryQuitMainloop, 3)
        else:
            self.close()
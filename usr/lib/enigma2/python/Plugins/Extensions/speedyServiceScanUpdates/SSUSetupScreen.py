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


# ===== SSUSetupScreen =====
class SSUSetupScreen(ConfigListScreen, Screen):
    def __init__(self, session):
        Screen.__init__(self, session)
        ConfigListScreen.__init__(self, [], session=session)
        self.session = session
        w = getDesktop(0).size().width()

        if w >= 1920:
            self.skin = """<screen name="SSUSetupScreen" position="center,170" size="1200,820" title="speedy Service Scan Setup" backgroundColor="black">
                <ePixmap pixmap="skin_default/buttons/red.png" position="10,5" size="5,70" scale="stretch" alphatest="on" />
                <ePixmap pixmap="skin_default/buttons/green.png" position="314,5" size="5,70" scale="stretch" alphatest="on" />
                <eLabel text="HELP" position="1110,753" size="80,35" backgroundColor="#777777" valign="center" halign="center" font="Regular;24" zPosition="5" />
                <widget name="key_red" position="19,8" zPosition="1" size="295,70" font="Regular;30" halign="center" valign="center" backgroundColor="#9f1313" transparent="1" shadowColor="black" shadowOffset="-2,-2" />
                <widget name="key_green" position="324,5" zPosition="1" size="300,70" font="Regular;30" halign="center" valign="center" foregroundColor="green" backgroundColor="#1f771f" transparent="1" shadowColor="black" shadowOffset="-2,-2" />
                <widget name="config" position="10,90" itemHeight="35" size="1180,500" enableWrapAround="1" scrollbarMode="showOnDemand" />
                <ePixmap pixmap="skin_default/div-h.png" position="10,650" zPosition="2" size="1180,2" />
                <ePixmap pixmap="skin_default/buttons/yellow.png" position="630,7" size="5,70" scale="stretch" alphatest="on" />
                <widget name="key_yellow" position="638,6" size="300,70" font="Regular;30" halign="center" valign="center" foregroundColor="yellow" />
                <widget name="version" position="444,593" size="150,50" font="Regular;30" valign="center" halign="left" />
                <ePixmap pixmap="skin_default/buttons/blue.png" position="945,7" size="5,70" scale="stretch" alphatest="on" />
                <widget name="key_blue" position="954,8" size="250,70" font="Regular;30" halign="center" valign="center" foregroundColor="blue" />
                <widget name="help" position="10,655" size="1180,140" font="Regular;32" />
                <ePixmap pixmap="skin_default/buttons/vkey_exit.png" position="1041,761" size="35,25" scale="stretch" alphatest="on" zPosition="6" />
            </screen>"""
        else:
            self.skin = """<screen name="SSUSetupScreen" position="center,120" size="900,530" title="speedy Service Scan Setup">
                <ePixmap pixmap="skin_default/buttons/red.png" position="0,0" size="5,40" scale="stretch" alphatest="on" />
                <ePixmap pixmap="skin_default/buttons/green.png" position="200,0" size="5,40" scale="stretch" alphatest="on" />
                <ePixmap pixmap="skin_default/buttons/yellow.png" position="405,0" size="5,40" scale="stretch" alphatest="on" />
                <ePixmap pixmap="skin_default/buttons/blue.png" position="610,0" size="5,40" scale="stretch" alphatest="on" />
                <widget name="key_red" position="7,0" zPosition="1" size="200,40" font="Regular;22" halign="center" valign="center" backgroundColor="#9f1313" transparent="1" shadowColor="black" shadowOffset="-2,-2" />
                <widget name="key_green" position="206,0" zPosition="1" size="200,40" font="Regular;22" halign="center" valign="center" foregroundColor="green" backgroundColor="#1f771f" transparent="1" shadowColor="black" shadowOffset="-2,-2" />
                <widget name="key_yellow" position="414,1" size="200,40" font="Regular;22" halign="center" valign="center" foregroundColor="yellow" />
                <widget name="key_blue" position="618,1" size="200,40" font="Regular;22" halign="center" valign="center" foregroundColor="blue" />
                <widget name="config" position="5,50" itemHeight="30" size="900,390" enableWrapAround="1" scrollbarMode="showOnDemand" />
                <ePixmap pixmap="skin_default/div-h.png" position="0,445" zPosition="2" size="900,2" />
                <widget name="version" position="5,450" size="200,30" font="Regular;22" valign="center" halign="left" />
                <widget name="help" position="210,450" size="685,65" font="Regular;22" />
            </screen>"""

        self["version"] = Label(_("v %s") % version)
        self["help"] = Label(_("Configure the update options."))

        self['actions'] = ActionMap(['ColorActions', 'OkCancelActions'], {
            'red': self.cancel,
            'green': self.save,
            'yellow': self.restore_default,
            'blue': self.openUpdate,
            'ok': self.save,
            'cancel': self.cancel
        }, -1)

        self.onLayoutFinish.append(self.populateList)

    def populateList(self):
        self.list = [
            getConfigListEntry(_("Add new TV services"), config.plugins.speedyservicescanupdates.add_new_tv_services, _("Create 'Service Scan Updates' bouquet for new TV services?")),
            getConfigListEntry(_("Add new radio services"), config.plugins.speedyservicescanupdates.add_new_radio_services, _("Create 'Service Scan Updates' bouquet for new radio services?")),
            getConfigListEntry(_("Clear bouquet at each search"), config.plugins.speedyservicescanupdates.clear_bouquet, _("Empty the 'Service Scan Updates' bouquet on every scan, otherwise the new services will be appended?"))
        ]
        for entry in self.list:
            entry[1].helpText = entry[2]
        self["config"].list = self.list
        self["config"].l.setList(self.list)

    def restore_default(self):
        self.session.open(MessageBox, _("Default settings restored!"), MessageBox.TYPE_INFO, 3)
        self.close()

    def openUpdate(self):
        try:
            self.session.open(SSUUpdateScreen)
        except Exception:
            _safe_msg(self.session, _("Unable to open update screen."), MessageBox.TYPE_ERROR, 5)

    def cancel(self):
        self.close()

    def save(self):
        self.session.open(MessageBox, _("Changes saved!"), MessageBox.TYPE_INFO, 3)
        self.close()


# ===== ServiceScan Hooks / Autostart =====
_base_execBegin = None
_base_execEnd = None
_preScanDB = None

try:
    from .SSULameDBParser import SSULameDBParser
except Exception:
    SSULameDBParser = None

def _has(d, k):
    try:
        return k in d
    except Exception:
        try:
            return d.has_key(k)
        except Exception:
            return False

def ServiceScan_execBegin_hook(self, *args, **kwargs):
    global _preScanDB
    if SSULameDBParser and not _preScanDB:
        add_tv = getattr(config.plugins.speedyservicescanupdates.add_new_tv_services, "value", False)
        add_radio = getattr(config.plugins.speedyservicescanupdates.add_new_radio_services, "value", False)
        if add_tv or add_radio:
            try:
                _preScanDB = SSULameDBParser(resolveFilename(SCOPE_CONFIG) + "/lamedb")
            except Exception:
                _preScanDB = None
    if _base_execBegin:
        _base_execBegin(self, *args, **kwargs)

def ServiceScan_execEnd_hook(self, *args, **kwargs):
    global _preScanDB
    if _base_execEnd:
        _base_execEnd(self, *args, **kwargs)
    if not SSULameDBParser:
        return
    add_tv = getattr(config.plugins.speedyservicescanupdates.add_new_tv_services, "value", False)
    add_radio = getattr(config.plugins.speedyservicescanupdates.add_new_radio_services, "value", False)
    if not (add_tv or add_radio):
        return
    if not _preScanDB:
        return
    postScanDB = SSULameDBParser(resolveFilename(SCOPE_CONFIG) + "/lamedb")
    postServices = postScanDB.getServices()
    preServices = _preScanDB.getServices()
    newTV, newRadio = [], []
    for sref in postServices.keys():
        if not _has(preServices, sref):
            if SSULameDBParser.isVideoService(sref):
                newTV.append(sref)
            elif SSULameDBParser.isRadioService(sref):
                newRadio.append(sref)
    if (not newTV) and (not newRadio):
        return
    from .SSUBouquetHandler import SSUBouquetHandler
    bh = SSUBouquetHandler()
    def _apply(side, items):
        if not items:
            return
        bh.addToIndexBouquet(side)
        if config.plugins.speedyservicescanupdates.clear_bouquet.value:
            bh.createSSUBouquet(items, side)
        else:
            if bh.doesSSUBouquetFileExists(side):
                bh.appendToSSUBouquet(items, side)
            else:
                bh.createSSUBouquet(items, side)
    if add_tv:
        _apply("tv", newTV)
    if add_radio:
        _apply("radio", newRadio)
    try:
        bh.reloadBouquets()
    except Exception:
        pass
    _preScanDB = None

def _autostart(reason, **kwargs):
    global _base_execBegin, _base_execEnd
    if reason == 0 and "session" in kwargs:
        if ServiceScan is None:
            return
        if _base_execBegin is None and hasattr(ServiceScan, "execBegin"):
            _base_execBegin = ServiceScan.execBegin
            ServiceScan.execBegin = ServiceScan_execBegin_hook
        if _base_execEnd is None and hasattr(ServiceScan, "execEnd"):
            _base_execEnd = ServiceScan.execEnd
            ServiceScan.execEnd = ServiceScan_execEnd_hook

# ===== Menu openers =====
def openUpdate(session, **kwargs):
    session.open(SSUUpdateScreen)

def openSetup(session, **kwargs):
    session.open(SSUSetupScreen)

def menuHook(menuid, **kwargs):
    if menuid == "scan":
        return [(_("ServiceScanUpdates"), openSetup, "servicescanupdates", 50)]
    return []

# ===== Plugin registration =====
def Plugins(**kwargs):
    items = [
        PluginDescriptor(where=[PluginDescriptor.WHERE_SESSIONSTART, PluginDescriptor.WHERE_AUTOSTART], fnc=_autostart),
        PluginDescriptor(name="SpeedyServiceScanUpdates",
                         description=_("Download and install Service Scan Updates"),
                         where=PluginDescriptor.WHERE_PLUGINMENU,
                         icon="plugin.png",
                         fnc=openUpdate),
        PluginDescriptor(name="SpeedyServiceScanUpdates",
                         description=_("Download and install Service Scan Updates"),
                         where=PluginDescriptor.WHERE_EXTENSIONSMENU,
                         icon="plugin.png",
                         fnc=openUpdate),
        PluginDescriptor(name="ServiceScanUpdates",
                         description=_("Configure Service Scan Updates"),
                         where=PluginDescriptor.WHERE_PLUGINMENU,
                         icon="plugin.png",
                         fnc=openSetup),
        PluginDescriptor(name="ServiceScanUpdates",
                         description=_("Configure Service Scan Updates"),
                         where=PluginDescriptor.WHERE_EXTENSIONSMENU,
                         icon="plugin.png",
                         fnc=openSetup),
        PluginDescriptor(where=PluginDescriptor.WHERE_MENU, fnc=menuHook)
    ]
    return items

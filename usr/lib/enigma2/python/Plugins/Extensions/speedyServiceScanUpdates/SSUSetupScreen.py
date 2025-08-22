# -*- coding: utf-8 -*-
import os
import sys
import zipfile
import tarfile
import shutil
import traceback

# optional dependency
try:
    import requests
except Exception:
    requests = None

# --- Enigma2 imports (try both common locations for ServiceScan) ---
from enigma import getDesktop
from Screens.Screen import Screen
from Screens.MessageBox import MessageBox
from Components.ActionMap import ActionMap
from Components.Button import Button
from Components.Label import Label
from Components.ProgressBar import ProgressBar
from Components.config import config, ConfigSubsection, ConfigYesNo, getConfigListEntry
from Screens.Setup import ConfigListScreen
from Components.ConfigList import ConfigList
from Plugins.Plugin import PluginDescriptor
from Tools.Directories import resolveFilename, SCOPE_CONFIG

# try to import ServiceScan from the usual places
ServiceScan = None
try:
    from Components.ServiceScan import ServiceScan
except Exception:
    try:
        from Screens.ServiceScan import ServiceScan
    except Exception:
        ServiceScan = None

# Local translations
from . import _

# ===== Constants / Paths =====
UPDATE_URL = "https://github.com/speedy005/speedyServiceScanUpdates/archive/refs/heads/main.zip"
DOWNLOAD_PATH = "/tmp/ServiceScanUpdates-main.zip"
EXTRACT_DIR = "/tmp/ServiceScanUpdates"
TARGET_DIR = "/usr/lib/enigma2/python/Plugins/Extensions/speedyServiceScanUpdates"

# ===== Config =====
# Ensure plugin config subsection exists and keep old alias
if not hasattr(config, "plugins"):
    config.plugins = type("obj", (), {})()

if not hasattr(config.plugins, "speedyservicescanupdates"):
    config.plugins.speedyservicescanupdates = ConfigSubsection()
cfg = config.plugins.speedyservicescanupdates

def _cfg_yes(name, default):
    if not hasattr(cfg, name):
        setattr(cfg, name, ConfigYesNo(default=default))
_cfg_yes("add_new_tv_services", True)
_cfg_yes("add_new_radio_services", True)
_cfg_yes("clear_bouquet", True)

# backward alias for older name
if not hasattr(config.plugins, "servicescanupdates"):
    config.plugins.servicescanupdates = cfg
else:
    try:
        config.plugins.servicescanupdates.add_new_tv_services = cfg.add_new_tv_services
        config.plugins.servicescanupdates.add_new_radio_services = cfg.add_new_radio_services
        config.plugins.servicescanupdates.clear_bouquet = cfg.clear_bouquet
    except Exception:
        pass

# ===== Plugin path & version =====
plugin_path = None
for base in ("/usr/lib/enigma2/python/Plugins/Extensions", "/usr/lib/enigma2/python/Plugins/SystemPlugins"):
    p = os.path.join(base, "speedyServiceScanUpdates")
    if os.path.isdir(p):
        plugin_path = p
        break
if plugin_path and plugin_path not in sys.path:
    sys.path.insert(0, plugin_path)

def read_version():
    if not plugin_path:
        return "Unknown version"
    vf = os.path.join(plugin_path, "version")
    try:
        f = open(vf, "r")
        try:
            return f.read().strip()
        finally:
            f.close()
    except Exception:
        return "Unknown version"
version = read_version()

# ===== Skin helper =====
def _screen_size():
    try:
        ds = getDesktop(0).size()
        return ds.width(), ds.height()
    except Exception:
        return 1280, 720

# --- Bildschirmgröße und Skin-Auswahl ---
try:
    desktop_size = getDesktop(0).size()
    sz_w = desktop_size.width()
    sz_h = desktop_size.height()
except:
    try:
        sz_w = int(getattr(config.av.videoresolution, "width", 1280))
        sz_h = int(getattr(config.av.videoresolution, "height", 720))
    except:
        sz_w, sz_h = 1280, 720

if sz_w == 1920 and sz_h == 1080:
    skin_update = """<screen name="SSUUpdateScreen" position="center,170" size="1200,820" title="speedy Service Scan Updates">
        <widget name="progress" position="10,100" size="1180,50" />
        <widget name="status" position="12,160" size="1180,50" font="Regular;30" valign="center" halign="center" />
        <widget name="progresstext" position="10,220" size="1180,50" font="Regular;30" valign="center" halign="center" />
        <widget name="key_red" position="3,4" size="295,70" font="Regular;30" halign="center" valign="center" />
        <widget name="key_green" foregroundColor="green" position="305,3" size="300,70" font="Regular;30" halign="center" valign="center" />
        <widget name="key_yellow" foregroundColor="yellow" position="604,5" size="300,70" font="Regular;30" halign="center" valign="center" />
        <widget name="key_blue" foregroundColor="blue" position="916,6" size="295,70" font="Regular;30" halign="center" valign="center" />
        <widget name="version" position="488,769" size="200,30" font="Regular;30" valign="center" halign="center" />
<ePixmap pixmap="skin_default/buttons/red.png" position="0,0" size="5,75" scale="stretch" alphatest="on" />
<ePixmap pixmap="skin_default/buttons/green.png" position="299,3" size="5,70" scale="stretch" alphatest="on" />
<ePixmap pixmap="skin_default/buttons/yellow.png" position="600,0" size="5,70" scale="stretch" alphatest="on" />
<ePixmap pixmap="skin_default/buttons/blue.png" position="909,7" size="5,70" scale="stretch" alphatest="on" />
    </screen>"""
else:
    skin_update = """<screen name="SSUUpdateScreen" position="410,170" size="1100,820" title="speedy Service Scan Updates">
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

# ===== Update Screen =====
class SSUUpdateScreen(Screen, ConfigListScreen):
    skin = _skin_update()

    def __init__(self, session):
        Screen.__init__(self, session)
        ConfigListScreen.__init__(self, [], session=session)
        self.session = session
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

    # --- UI actions ---
    def exit(self):
        self.close()

    def cancel(self):
        self['status'].setText(_("Update cancelled."))
        self.download_complete = False
        self.update_installed = False

    def _requests_missing(self):
        if requests is None:
            self['status'].setText(_("Python 'requests' module not available."))
            return True
        return False

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
        except Exception:
            self['status'].setText(_("Update check failed."))

    def start_update(self):
        if self._requests_missing():
            return
        self['status'].setText(_("Downloading update..."))
        try:
            r = requests.get(UPDATE_URL, stream=True, timeout=20)
            if r.status_code != 200:
                self['status'].setText(_("Failed to download update."))
                return
            f = open(DOWNLOAD_PATH, "wb")
            try:
                total = r.headers.get('content-length')
                total = int(total) if total else None
                dl = 0
                for chunk in r.iter_content(chunk_size=8192):
                    if not chunk:
                        continue
                    f.write(chunk)
                    if total:
                        dl += len(chunk)
                        try:
                            pct = int(dl * 100 / total)
                            self['progress'].setValue(pct)
                            self['progresstext'].setText("%d%%" % pct)
                        except Exception:
                            pass
            finally:
                f.close()
            self._extract_and_install(DOWNLOAD_PATH)
        except Exception:
            self['status'].setText(_("Download failed."))

    # --- extraction + install ---
    def _extract_and_install(self, file_path):
        try:
            if _exists(EXTRACT_DIR):
                shutil.rmtree(EXTRACT_DIR)
            os.makedirs(EXTRACT_DIR)
        except Exception:
            pass
        try:
            if file_path.endswith(".zip"):
                zf = zipfile.ZipFile(file_path, 'r')
                try:
                    zf.extractall(EXTRACT_DIR)
                finally:
                    zf.close()
            elif file_path.endswith(".tar.gz") or file_path.endswith(".tgz"):
                tf = tarfile.open(file_path, 'r:gz')
                try:
                    tf.extractall(EXTRACT_DIR)
                finally:
                    tf.close()
            else:
                self['status'].setText(_("Unsupported file format"))
                return
        except Exception:
            self['status'].setText(_("Extraction failed."))
        else:
            self._finish_update()

    def _finish_update(self):
        try:
            if not os.path.isdir(EXTRACT_DIR):
                self['status'].setText(_("Error: Extracted directory not found."))
                return
            if not os.path.isdir(TARGET_DIR):
                try:
                    os.makedirs(TARGET_DIR)
                except Exception:
                    pass

            # copy extracted content into TARGET_DIR (replace dirs)
            for item in os.listdir(EXTRACT_DIR):
                s = os.path.join(EXTRACT_DIR, item)
                d = os.path.join(TARGET_DIR, item)
                try:
                    if os.path.isdir(s):
                        if _exists(d):
                            shutil.rmtree(d)
                        shutil.copytree(s, d)
                    else:
                        shutil.copy2(s, d)
                except Exception:
                    # ignore copy errors but continue
                    pass

            if not _exists(TARGET_DIR):
                raise IOError("Target dir missing after extraction")

            self['status'].setText(_("Update completed successfully."))
            self.update_installed = True
            self._restart_application()
        except Exception:
            self['status'].setText(_("Failed to complete update."))

    def _restart_application(self):
        if not self.update_installed:
            _safe_msg(self.session, _("No update installed. Restart not needed."), MessageBox.TYPE_INFO, 6)
            return
        _safe_msg(self.session, _("Update complete. The application will now restart."), MessageBox.TYPE_INFO, 8)
        try:
            os.system("init 4")
        except Exception:
            pass

# ===== Setup Screen =====
class SSUSetupScreen(ConfigListScreen, Screen):
    if sz_w == 1920:
        skin = """
        <screen name="SSUSetupScreen" position="center,170" size="1200,820" title="speedy Service Scan Updates">
            <ePixmap pixmap="skin_default/buttons/red.png" position="10,5" size="5,70" scale="stretch" alphatest="on" />
            <ePixmap pixmap="skin_default/buttons/green.png" position="314,5" size="5,70" scale="stretch" alphatest="on" />
            <eLabel text="HELP" position="1110,753" size="80,35" backgroundColor="#777777" valign="center" halign="center" font="Regular;24" zPosition="5" />
            <widget name="key_red" position="19,8" zPosition="1" size="295,70" font="Regular;30" halign="center" valign="center" backgroundColor="#9f1313" transparent="1" shadowColor="black" shadowOffset="-2,-2" />
            <widget name="key_green" position="324,5" zPosition="1" size="300,70" font="Regular;30" halign="center" valign="center" foregroundColor="green" backgroundColor="#1f771f" transparent="1" shadowColor="black" shadowOffset="-2,-2" />
            <widget name="config" position="10,90" itemHeight="35" size="1180,540" enableWrapAround="1" scrollbarMode="showOnDemand" />
            <ePixmap pixmap="skin_default/div-h.png" position="10,650" zPosition="2" size="1180,2" />
            <ePixmap pixmap="skin_default/buttons/yellow.png" position="630,7" size="5,70" scale="stretch" alphatest="on" />
            <widget name="key_yellow" foregroundColor="yellow" position="638,6" size="300,70" font="Regular;30" halign="center" valign="center" />
            <widget name="version" text="v." position="440,753" size="150,50" font="Regular;30" valign="center" halign="left" zPosition="5" />
            <ePixmap pixmap="skin_default/buttons/blue.png" position="945,7" size="5,70" scale="stretch" alphatest="on" />
            <widget name="key_blue" position="954,8" foregroundColor="blue" size="250,70" font="Regular;30" halign="center" valign="center" />
            <widget name="help" position="10,655" size="1180,140" font="Regular;32" />
            <ePixmap pixmap="skin_default/buttons/vkey_exit.png" position="1041,761" size="35,25" scale="stretch" alphatest="on" zPosition="6" />
        </screen>"""
    else:
        skin = """
        <screen name="SISettingsScreen" position="center,120" size="800,530" title="speedy Service Scan Updates">
            <ePixmap pixmap="skin_default/buttons/yellow.png" position="405,0" size="5,40" scale="stretch" alphatest="on" />
            <widget name="key_yellow" foregroundColor="yellow" position="414,1" size="200,40" font="Regular;30" halign="center" valign="center" />
            <ePixmap pixmap="skin_default/buttons/red.png" position="0,0" size="5,40" scale="stretch" alphatest="on" />
            <ePixmap pixmap="skin_default/buttons/green.png" position="200,0" size="5,40" scale="stretch" alphatest="on" />
            <eLabel text="HELP" position="735,15" size="60,25" backgroundColor="#777777" valign="center" halign="center" font="Regular;18" />
            <widget name="key_red" position="9,0" zPosition="1" size="200,40" font="Regular;22" halign="center" valign="center" backgroundColor="#9f1313" transparent="1" shadowColor="black" shadowOffset="-2,-2" />
            <widget name="key_green" position="206,0" zPosition="1" size="200,40" font="Regular;22" halign="center" valign="center" foregroundColor="green" backgroundColor="#1f771f" transparent="1" shadowColor="black" shadowOffset="-2,-2" />
            <widget name="config" position="5,50" itemHeight="30" size="790,390" enableWrapAround="1" scrollbarMode="showOnDemand" />
            <ePixmap pixmap="skin_default/div-h.png" position="0,445" zPosition="2" size="800,2" />
            <widget name="version" text="v" position="621,0" size="100,40" font="Regular;30" valign="center" halign="left" zPosition="5" />
            <widget name="help" position="5,450" size="790,65" font="Regular;22" />
            <ePixmap pixmap="skin_default/buttons/vkey_exit.png" position="693,492" size="35,25" scale="stretch" alphatest="on" zPosition="6" />
        </screen>"""

    def __init__(self, session):
        Screen.__init__(self, session)
        ConfigListScreen.__init__(self, [], session=session)
        self.session = session

        # --- Define ALL widgets that external skins may reference ---
        self["version"] = Label(_("v %s") % version)
        self["key_red"] = Button(_("Cancel"))
        self["key_green"] = Button(_("Save"))
        self["key_yellow"] = Button(_("Update"))
        self["key_blue"] = Button(_("Close"))
        self["help"] = Label(_("Configure the update options."))

        # Config options
        self.list = [
            getConfigListEntry(_("Add new TV services"), cfg.add_new_tv_services),
            getConfigListEntry(_("Add new Radio services"), cfg.add_new_radio_services),
            getConfigListEntry(_("Clear Bouquet"), cfg.clear_bouquet)
        ]
        # Re-init with the list so ConfigListScreen creates self["config"]
        ConfigListScreen.__init__(self, self.list, session=self.session)

        # Actions
        self['actions'] = ActionMap(['ColorActions', 'OkCancelActions'], {
            'red': self.cancel,
            'green': self.save,
            'yellow': self.openUpdate,
            'blue': self.close,
            'ok': self.save,
            'cancel': self.cancel
        }, -1)

        self.onLayoutFinish.append(self.layoutFinished)

    def openUpdate(self):
        try:
            self.session.open(SSUUpdateScreen)
        except Exception:
            _safe_msg(self.session, _("Unable to open update screen."), MessageBox.TYPE_ERROR, 5)

    def cancel(self):
        self.close()

    def save(self):
        for x in self.list:
            try:
                x[1].save()
            except Exception:
                pass
        try:
            config.save()
            _safe_msg(self.session, _("Settings saved successfully!"), MessageBox.TYPE_INFO, 4)
        except Exception:
            _safe_msg(self.session, _("Failed to save config."), MessageBox.TYPE_ERROR, 6)
        self.close()

    def layoutFinished(self):
        help_txt = _("This plugin creates a favorites bouquet (for TV and Radio) named 'Service Scan Updates'.\n")
        help_txt += _("All new services found during scans are inserted with a marker, so you can copy them to your favorites.\n\n")
        help_txt += _("For the bouquet to be visible, enable 'Allow multiple bouquets' in system settings.")
        self["help"].setText(help_txt)

# ===== ServiceScan hook =====
_base_execBegin = None
_base_execEnd = None
_preScanDB = None

# optional parser
try:
    from .SSULameDBParser import SSULameDBParser
except Exception:
    SSULameDBParser = None

def _has(d, k):
    # Python 2/3-safe membership check helper
    try:
        return k in d
    except Exception:
        try:
            return d.has_key(k)  # Py2 fallback
        except Exception:
            return False

def ServiceScan_execBegin_hook(self, *args, **kwargs):
    global _preScanDB
    # snapshot pre-scan DB if configured
    try:
        if SSULameDBParser and not _preScanDB:
            add_tv = getattr(config.plugins.servicescanupdates.add_new_tv_services, "value", False)
            add_radio = getattr(config.plugins.servicescanupdates.add_new_radio_services, "value", False)
            if add_tv or add_radio:
                try:
                    _preScanDB = SSULameDBParser(resolveFilename(SCOPE_CONFIG) + "/lamedb")
                except Exception:
                    _preScanDB = None
    except Exception:
        pass

    # call original execBegin
    try:
        if _base_execBegin:
            try:
                _base_execBegin(self, *args, **kwargs)
            except TypeError:
                try:
                    _base_execBegin(self)
                except Exception:
                    pass
    except Exception:
        pass

def ServiceScan_execEnd_hook(self, *args, **kwargs):
    global _preScanDB
    # call original first
    try:
        if _base_execEnd:
            try:
                _base_execEnd(self, *args, **kwargs)
            except TypeError:
                try:
                    _base_execEnd(self)
                except Exception:
                    pass
    except Exception:
        pass

    # post-scan handling
    try:
        if not SSULameDBParser:
            return
        add_tv = getattr(config.plugins.servicescanupdates.add_new_tv_services, "value", False)
        add_radio = getattr(config.plugins.servicescanupdates.add_new_radio_services, "value", False)
        if not (add_tv or add_radio):
            return

        # ensure scan finished if attributes exist
        proceed = True
        try:
            Done = getattr(self, "Done", None)
            state = getattr(self, "state", None)
            if Done is not None and state is not None:
                proceed = (state == Done)
        except Exception:
            proceed = True
        if not proceed:
            return

        if not _preScanDB:
            return

        # read post-scan DB
        try:
            postScanDB = SSULameDBParser(resolveFilename(SCOPE_CONFIG) + "/lamedb")
        except Exception:
            return

        postServices = postScanDB.getServices()
        preServices = _preScanDB.getServices()

        newTV, newRadio = [], []
        for sref in postServices.keys():
            try:
                if not _has(preServices, sref):
                    if SSULameDBParser.isVideoService(sref):
                        newTV.append(sref)
                    elif SSULameDBParser.isRadioService(sref):
                        newRadio.append(sref)
            except Exception:
                pass

        if (not newTV) and (not newRadio):
            return

        try:
            from .SSUBouquetHandler import SSUBouquetHandler
            bh = SSUBouquetHandler()
        except Exception:
            return

        def _apply(side, items):
            if not items:
                return
            try:
                bh.addToIndexBouquet(side)
                if config.plugins.servicescanupdates.clear_bouquet.value:
                    bh.createSSUBouquet(items, side)
                else:
                    if bh.doesSSUBouquetFileExists(side):
                        bh.appendToSSUBouquet(items, side)
                    else:
                        bh.createSSUBouquet(items, side)
            except Exception:
                pass

        if add_tv:
            _apply("tv", newTV)
        if add_radio:
            _apply("radio", newRadio)

        try:
            bh.reloadBouquets()
        except Exception:
            pass
    except Exception:
        pass
    finally:
        _preScanDB = None

# ===== Autostart: patch ServiceScan =====
def _autostart(reason, **kwargs):
    global _base_execBegin, _base_execEnd
    try:
        if reason == 0 and "session" in kwargs:
            if ServiceScan is None:
                return
            if _base_execBegin is None and hasattr(ServiceScan, "execBegin"):
                _base_execBegin = ServiceScan.execBegin
                ServiceScan.execBegin = ServiceScan_execBegin_hook
            if _base_execEnd is None and hasattr(ServiceScan, "execEnd"):
                _base_execEnd = ServiceScan.execEnd
                ServiceScan.execEnd = ServiceScan_execEnd_hook
    except Exception:
        pass

# ===== Menu openers =====
def openUpdate(session, **kwargs):
    session.open(SSUUpdateScreen)

def openSetup(session, **kwargs):
    session.open(SSUSetupScreen)

# ===== Menu integration =====
def menuHook(menuid, **kwargs):
    if menuid == "scan":  # Service Searching
        return [(_("ServiceScanUpdates"), openSetup, "servicescanupdates", 50)]
    return []

# ===== Plugin registration =====
def Plugins(**kwargs):
    """
    Return plugin descriptors:
     - autostart/sessionstart for service scan hooks
     - SpeedyServiceScanUpdates -> updater screen (plugin menu and extensions)
     - ServiceScanUpdates -> configuration screen (plugin menu, extensions, and service searching menu)
    """
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

        # New entry in Main Menu ? Setup ? Service & Recording ? Service Searching
        PluginDescriptor(where=PluginDescriptor.WHERE_MENU, fnc=menuHook)
    ]
    return items

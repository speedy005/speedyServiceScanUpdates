# -*- coding: utf-8 -*-
import os
import sys
import zipfile
import shutil
import traceback
import time
import requests

# optional dependency
try:
    import requests
except Exception:
    requests = None

# --- Plugin-Pfad dynamisch ermitteln (Extensions oder SystemPlugins) ---
plugin_path = None
for base in (
    "/usr/lib/enigma2/python/Plugins/Extensions",
    "/usr/lib/enigma2/python/Plugins/SystemPlugins"
):
    possible = os.path.join(base, "speedyServiceScanUpdates")  # Plugin-Ordnername geändert
    if os.path.isdir(possible):
        plugin_path = possible
        break

# --- Enigma2 imports (try both common locations for ServiceScan) ---
from enigma import ePixmap, eLabel, getDesktop
from Screens.Screen import Screen
from Screens.MessageBox import MessageBox
from Screens.Standby import TryQuitMainloop
from Components.ConfigList import ConfigListScreen
from Components.ActionMap import ActionMap
from Components.Button import Button
from Components.Label import Label
from Components.ProgressBar import ProgressBar
from enigma import eTimer
from Components.config import config, ConfigSubsection, ConfigYesNo, getConfigListEntry
from Screens.Setup import ConfigListScreen
from Plugins.Plugin import PluginDescriptor
from Tools.Directories import resolveFilename, SCOPE_CONFIG, fileExists

# Local translations
from . import _

# ===== Constants / Paths =====
UPDATE_URL = "https://github.com/speedy005/speedyServiceScanUpdates/archive/refs/heads/main.zip"
DOWNLOAD_PATH = "/tmp/ServiceScanUpdates-main.zip"
EXTRACT_DIR = "/tmp/ServiceScanUpdates"
TARGET_DIR = "/usr/lib/enigma2/python/Plugins/Extensions/speedyServiceScanUpdates"

# ===== Config =====
# Initialize configuration
config.plugins.speedyservicescanupdates = ConfigSubsection()
config.plugins.speedyservicescanupdates.add_new_tv_services = ConfigYesNo(default=True)
config.plugins.speedyservicescanupdates.add_new_radio_services = ConfigYesNo(default=True)
config.plugins.speedyservicescanupdates.clear_bouquet = ConfigYesNo(default=False)

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

# ===== ServiceScan Import =====
ServiceScan = None
try:
    from Screens.ServiceScan import ServiceScan
except ImportError:
    try:
        from Plugins.SystemPlugins.ServiceScan.plugin import ServiceScan
    except ImportError:
        pass

# ===== SSUUpdateScreen Class =====

class SSUUpdateScreen(Screen):
    def __init__(self, session):
        Screen.__init__(self, session)
        self.session = session

        from enigma import getDesktop
        desktop = getDesktop(0)
        width = desktop.size().width()
        height = desktop.size().height()

        if width == 1920:  # FHD
            self.skin = """
            <screen name="SSUUpdateScreen" position="center,170" size="1200,820" title="speedy Service Scan Updates">
                <widget name="progress" position="10,100" size="1180,50" />
                <widget name="status" position="12,160" size="1180,50" font="Regular;30" valign="center" halign="center" />
                <widget name="progresstext" position="10,220" size="1180,50" font="Regular;30" valign="center" halign="center" />
                <widget name="key_red" position="3,4" size="295,70" font="Regular;30" halign="center" valign="center" />
                <widget name="key_green" foregroundColor="green" position="305,3" size="300,70" font="Regular;30" halign="center" valign="center" />
                <widget name="key_yellow" foregroundColor="yellow" position="604,5" size="300,70" font="Regular;30" halign="center" valign="center" />
                <widget name="key_blue" foregroundColor="blue" position="916,6" size="295,70" font="Regular;30" halign="center" valign="center" />
                <widget name="version" position="488,769" size="200,30" font="Regular;30" valign="center" halign="center" />
            </screen>
            """
        else:  # HD
            self.skin = """
            <screen name="SSUUpdateScreen" position="410,170" size="1100,820" title="speedy Service Scan Updates">
                <widget name="progress" position="10,100" size="1050,50" />
                <widget name="status" position="10,160" size="1050,50" font="Regular;30" valign="center" halign="center" />
                <widget name="progresstext" position="10,220" size="1050,50" font="Regular;30" valign="center" halign="center" />
                <widget name="key_red" position="13,2" size="250,70" font="Regular;30" halign="center" valign="center" />
                <widget name="key_green" foregroundColor="green" position="277,3" size="250,70" font="Regular;30" halign="center" valign="center" />
                <widget name="key_yellow" foregroundColor="yellow" position="538,4" size="250,70" font="Regular;30" halign="center" valign="center" />
                <widget name="key_blue" position="798,5" foregroundColor="blue" size="250,70" font="Regular;30" halign="center" valign="center" />
                <widget name="version" position="364,752" size="300,50" font="Regular;30" valign="center" halign="center" />
            </screen>
            """

         


        # Widgets initialisieren
        self['status'] = Label(_("Checking for updates..."))
        self['progress'] = ProgressBar()
        self['progresstext'] = Label("")
        self['key_red'] = Button(_("Exit"))
        self['key_green'] = Button(_("Start"))
        self['key_yellow'] = Button(_("Cancel"))
        self['key_blue'] = Button(_("Check Update"))
        self['version'] = Label(version)

        # Aktionen
        self['actions'] = ActionMap(['ColorActions', 'OkCancelActions'], {
            'red': self.exit,
            'green': self.start_update,
            'yellow': self.cancel,
            'blue': self.check_update,
            'ok': self.start_update,
            'cancel': self.exit
        }, -1)

        # Status-Variablen
        self.download_progress = 0
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
                            self._update_gui()
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
        return 1920, 1080  # Beispiel

    def restartGUI(self, answer):
        if answer:
            self.session.open(TryQuitMainloop, 3)
        else:
            self.close()

    def _requests_missing(self):
        try:
            import requests
            return False
        except ImportError:
            self['status'].setText(_("Requests module missing"))
            return True

    

class SSUSetupScreen(ConfigListScreen, Screen):
    def __init__(self, session):
        Screen.__init__(self, session)
        ConfigListScreen.__init__(self, [], session=session)
        self.session = session

        # Bildschirmauflösung abfragen und Skin setzen
        w, h = self._screen_size()

        # Bestimmen der Bildschirmbreite basierend auf der Auflösung
        sz_w = 1180 if w >= 1920 and h >= 1080 else 1050

        # Skin für verschiedene Auflösungen festlegen
        if w >= 1920 and h >= 1080:
            self.skin = """
            <screen name="SSUSetupScreen" position="center,170" size="1200,820" title="speedy Service Scan Setup" backgroundColor="black">
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
            self.skin = """
            <screen name="SSUSetupScreen" position="center,120" size="900,530" title="speedy Service Scan Setup">
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

        # --- Definiere alle Widgets, die von externen Skins referenziert werden können ---
        self["version"] = Label(_("v %s") % version)
        self["key_red"] = Button(_("Cancel"))
        self["key_green"] = Button(_("Save"))
        self["key_yellow"] = Button(_("Restore Default"))
        self["key_blue"] = Button(_("Update"))
        self["help"] = Label(_("Configure the update options."))
        
        # Aktionen
        self['actions'] = ActionMap(['ColorActions', 'OkCancelActions'], {
            'red': self.cancel,
            'green': self.save,
            'yellow': self.restore_default,
            'blue': self.openUpdate,
            'ok': self.save,
            'cancel': self.cancel
        }, -1)

        self.onLayoutFinish.append(self.layoutFinished)
        self["config"].onSelectionChanged.append(self.updateHelp)

    def restore_default(self):
        """Stellt die Standardeinstellungen wieder her"""
        self.session.open(MessageBox, _("Default settings restored!"), MessageBox.TYPE_INFO, 3)
        self.close()

    def openUpdate(self):
        try:
            self.session.open(SSUUpdateScreen)
        except Exception as e:
            print("Error opening update screen:", str(e))
            _safe_msg(self.session, _("Unable to open update screen."), MessageBox.TYPE_ERROR, 5)

    def _screen_size(self):
        """Ermittelt die Bildschirmgröße"""
        try:
            ds = getDesktop(0).size()
            return ds.width(), ds.height()
        except Exception:
            return 1920, 1080

    def layoutFinished(self):
        self.populateList()

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

    def updateHelp(self):
        """Aktualisiert die Hilfetextanzeige basierend auf der ausgewählten Option"""
        selected = self["config"].getCurrent()
        if selected:
            help_text = getattr(selected[1], 'helpText', _("No help available for this option."))
            self["help"].setText(help_text)
        else:
            self["help"].setText("")

    def cancel(self):
        """Bricht ab und schließt das Fenster"""
        self.close()

    def save(self):
        """Speichert die Änderungen und bestätigt"""
        self.session.open(MessageBox, _("Changes saved!"), MessageBox.TYPE_INFO, 3)
        self.close()

class SSUHelpScreen(Screen):
    def __init__(self, session):
        Screen.__init__(self, session)

        # Bildschirmauflösung abfragen und Skin setzen
        w, h = self._screen_size()

        # Setzen des Skin je nach Bildschirmgröße
        self.skin = self._get_skin(w, h)

        # Hilfe-Widget initialisieren
        self["help"] = Label(_("Help information goes here"))

    def _screen_size(self):
        """Ermittelt die Bildschirmgröße"""
        try:
            ds = getDesktop(0).size()
            return ds.width(), ds.height()
        except Exception:
            return 1280, 720

    def _get_skin(self, w, h):
        """Hilfsmethode zur Bestimmung des Skins basierend auf Bildschirmauflösung"""
        if w >= 1920 and h >= 1080:
            return """
            <screen name="SSUHelpScreen" position="center,170" size="1200,820" title="Service Scan Updates">
                <widget name="help" position="20,5" size="1100,780" font="Regular;30" />
            </screen>"""
        else:
            return """
            <screen name="SSUHelpScreen" position="center,120" size="800,530" title="Service Scan Updates">
                <widget name="help" position="10,5" size="760,500" font="Regular;21" />
            </screen>"""

    def layoutFinished(self):
        help_txt = _("This plugin creates a favorites bouquet (for TV and Radio) with the name 'Service Scan Updates'.\n")
        help_txt += _("All new services found during the scan are inserted there together with a marker.\n")
        help_txt += _("This allows you to quickly and clearly see which new services were found,\n")
        help_txt += _("and you can add individual services to your own Favorites bouquets as usual.\n\n")
        help_txt += _("In order for the 'Service Scan Updates' bouquet to be displayed,\n")
        help_txt += _("the option 'Allow multiple bouquets' must be activated in the system settings of the box.")
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
            add_tv = getattr(config.plugins.speedyservicescanupdates.add_new_tv_services, "value", False)
            add_radio = getattr(config.plugins.speedyservicescanupdates.add_new_radio_services, "value", False)
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
        add_tv = getattr(config.plugins.speedyservicescanupdates.add_new_tv_services, "value", False)
        add_radio = getattr(config.plugins.speedyservicescanupdates.add_new_radio_services, "value", False)
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
                if config.plugins.speedyservicescanupdates.clear_bouquet.value:
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
        PluginDescriptor(where=PluginDescriptor.WHERE_MENU, fnc=menuHook)
    ]
    return items
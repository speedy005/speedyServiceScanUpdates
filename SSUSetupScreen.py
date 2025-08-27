# -*- coding: utf-8 -*-
import os
import sys
import zipfile
import shutil
import traceback
import time

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
from enigma import ePixmap, eLabel, getDesktop, eTimer
from Screens.Screen import Screen
from Screens.MessageBox import MessageBox
from Components.ConfigList import ConfigListScreen
from Components.ActionMap import ActionMap
from Components.Label import Label
from Components.config import config, ConfigSubsection, ConfigYesNo, getConfigListEntry
from Plugins.Plugin import PluginDescriptor
from Tools.Directories import resolveFilename, SCOPE_CONFIG
from Components.Button import Button
# Local translations
from . import _

# ===== Version =====
def read_version():
    if not plugin_path:
        return "Unknown version"
    vf = os.path.join(plugin_path, "version.txt")
    try:
        with open(vf, "r", encoding="utf-8") as f:
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

# ===== Update Screen Import =====
try:
    from .SSUUpdateScreen import SSUUpdateScreen
except ImportError:
    SSUUpdateScreen = None

# ===== Config =====
config.plugins.speedyservicescanupdates = ConfigSubsection()
config.plugins.speedyservicescanupdates.add_new_tv_services = ConfigYesNo(default=True)
config.plugins.speedyservicescanupdates.add_new_radio_services = ConfigYesNo(default=True)
config.plugins.speedyservicescanupdates.clear_bouquet = ConfigYesNo(default=False)

# ===== SSUSetupScreen =====
class SSUSetupScreen(ConfigListScreen, Screen):
    def __init__(self, session):
        Screen.__init__(self, session)
        ConfigListScreen.__init__(self, [], session=session)
        self.session = session
        w = getDesktop(0).size().width()

        # --- Skin definieren ---
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

        # --- Widgets ---
        self["version"] = Label(_("v %s") % version)
        self["key_red"] = Button(_("Cancel"))
        self["key_green"] = Button(_("Save"))
        self["key_yellow"] = Button(_("Restore Default"))
        self["key_blue"] = Button(_("Update"))
        self["help"] = Label(_("Configure the update options."))

        # --- Aktionen (inkl. EPG/Help-Taste) ---
        self['actions'] = ActionMap(
            ['ColorActions', 'OkCancelActions', 'HelpActions', 'EPGSelectActions'],
            {
                'red': self.cancel,
                'green': self.save,
                'yellow': self.restore_default,
                'blue': self.openUpdate,
                'ok': self.save,
                'cancel': self.cancel,
                'help': self.showHelp,
                'epg': self.showHelp
            },
            -1
        )

        # ConfigList initialisieren
        self.onLayoutFinish.append(self.populateList)
        self["config"].onSelectionChanged.append(self.updateHelp)

    # ===== Methoden =====
    def populateList(self):
        self.list = [
            getConfigListEntry(
                _("Add new TV services"),
                config.plugins.speedyservicescanupdates.add_new_tv_services,
                _("Create 'Service Scan Updates' bouquet for new TV services?")
            ),
            getConfigListEntry(
                _("Add new radio services"),
                config.plugins.speedyservicescanupdates.add_new_radio_services,
                _("Create 'Service Scan Updates' bouquet for new radio services?")
            ),
            getConfigListEntry(
                _("Clear bouquet at each search"),
                config.plugins.speedyservicescanupdates.clear_bouquet,
                _("Empty the 'Service Scan Updates' bouquet on every scan, otherwise the new services will be appended?")
            )
        ]
        for entry in self.list:
            entry[1].helpText = entry[2]
        self["config"].list = self.list
        

    def restore_default(self):
        self.session.open(MessageBox, _("Default settings restored!"), MessageBox.TYPE_INFO, 3)
        self.close()

    def openUpdate(self):
        if SSUUpdateScreen:
            self.session.open(SSUUpdateScreen)
        else:
            _safe_msg(self.session, _("Update screen not available."), MessageBox.TYPE_ERROR, 5)

    def cancel(self):
        self.close()

    def save(self):
        self.session.open(MessageBox, _("Changes saved!"), MessageBox.TYPE_INFO, 3)
        self.close()

    def showHelp(self):
        self.session.open(MessageBox, _("Configure the update options."), MessageBox.TYPE_INFO, 5)

    def updateHelp(self):
        # Bei ConfigList-Auswahl die Hilfe aktualisieren
        if self["config"].getCurrent():
            self["help"].setText(self["config"].getCurrent()[1].helpText)


    def checkUpdate(self):
        if SSUUpdateScreen:
            self.session.open(SSUUpdateScreen, show_only=True)
        else:
            _safe_msg(self.session, _("Update screen not available."), MessageBox.TYPE_ERROR, 5)


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
        return False

# Hooks bleiben größtenteils gleich, nur Python 3 kompatibel
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
    if SSUUpdateScreen:
        session.open(SSUUpdateScreen)
    else:
        _safe_msg(session, _("Update screen not available."), MessageBox.TYPE_ERROR, 5)

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

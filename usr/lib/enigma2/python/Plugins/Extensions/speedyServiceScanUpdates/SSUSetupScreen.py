# -*- coding: utf-8 -*-

# --- Standardbibliothek ---
import os
import sys
import re
import zipfile
import requests
import shutil

# Ubersetzungsfunktion aus __init__.py laden
from . import _

# Enigma2 Imports
from enigma import getDesktop
from Screens.Screen import Screen
from Components.ActionMap import ActionMap
from Components.Button import Button
from Components.Label import Label
from Components.ProgressBar import ProgressBar
from Screens.MessageBox import MessageBox
from Tools.Directories import fileExists
from Components.config import config, ConfigSubsection, ConfigYesNo
from Screens.Setup import ConfigListScreen
## from Components.ConfigList import getConfigListEntry
from Components.ScrollLabel import ScrollLabel  # Added missing import
from Tools import Notifications

# --- Config-Objekte initialisieren ---
config.plugins.speedyservicescanupdates = ConfigSubsection()
config.plugins.speedyservicescanupdates.add_new_tv_services = ConfigYesNo(default=True)
config.plugins.speedyservicescanupdates.add_new_radio_services = ConfigYesNo(default=True)
config.plugins.speedyservicescanupdates.clear_bouquet = ConfigYesNo(default=True)
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
if plugin_path and plugin_path not in sys.path:
    sys.path.insert(0, plugin_path)

# --- Version & URLs ---
version = "3.7"
update_url = "https://github.com/speedy005/speedyServiceScanUpdates/archive/refs/heads/main.zip"
download_path = "/tmp/ServiceScanUpdates-main.zip"
extract_dir = "/tmp/ServiceScanUpdates"
target_dir = "/usr/lib/enigma2/python/Plugins/Extensions/speedyServiceScanUpdates"

# --- Hilfsfunktionen ---
def clean_version(ver):
    """Filtert Versionsnummer auf nur Ziffern und Punkte."""
    return re.sub(r'[^0-9\.]', '', ver)
# --- Bildschirmgr??e und Skin-Auswahl ---

# --- Enigma2-Imports ---
from Screens.Screen import Screen
from Components.ConfigList import ConfigListScreen
from Components.ActionMap import ActionMap
from Components.config import config, getConfigListEntry
from Components.Button import Button
from Components.Label import Label
from Components.ScrollLabel import ScrollLabel
from enigma import getDesktop

# --- Lokale Imports ---
from . import _  # Ubersetzungsfunktion aus __init__.py laden

# --- Version ---
version = "3.8"
sz_w = getDesktop(0).size().width()


class SSUSetupScreen(ConfigListScreen, Screen):
    if sz_w == 1920:
        skin = """
        <screen name="SSUSetupScreen" position="center,170" size="1200,820" title="speedy Service Scan Updates">
            <ePixmap pixmap="skin_default/buttons/red.png" position="10,5" size="295,70" scale="stretch" alphatest="on" />
            <ePixmap pixmap="skin_default/buttons/green.png" position="305,5" size="295,70" scale="stretch" alphatest="on" />
            <eLabel text="HELP" position="1110,30" size="80,35" backgroundColor="#777777" valign="center" halign="center" font="Regular;24"/>
            <widget name="key_red" position="10,5" zPosition="1" size="295,70" font="Regular;30" halign="center" valign="center" backgroundColor="#9f1313" transparent="1" shadowColor="black" shadowOffset="-2,-2" />
            <widget name="key_green" position="310,5" zPosition="1" size="300,70" font="Regular;30" halign="center" valign="center" backgroundColor="#1f771f" transparent="1" shadowColor="black" shadowOffset="-2,-2" />
            <widget name="config" position="10,90" itemHeight="35" size="1180,540" enableWrapAround="1" scrollbarMode="showOnDemand" />
            <ePixmap pixmap="skin_default/div-h.png" position="10,650" zPosition="2" size="1180,2" />
            <widget name="help" position="10,655" size="1180,145" font="Regular;32" />
        </screen>"""
    else:
        skin = """
        <screen name="SISettingsScreen" position="center,120" size="800,530" title="speedy Service Scan Updates">
            <ePixmap pixmap="skin_default/buttons/red.png" position="0,0" size="200,40" scale="stretch" alphatest="on" />
            <ePixmap pixmap="skin_default/buttons/green.png" position="200,0" size="200,40" scale="stretch" alphatest="on" />
            <eLabel text="HELP" position="735,15" size="60,25" backgroundColor="#777777" valign="center" halign="center" font="Regular;18"/>
            <widget name="key_red" position="0,0" zPosition="1" size="200,40" font="Regular;22" halign="center" valign="center" backgroundColor="#9f1313" transparent="1" shadowColor="black" shadowOffset="-2,-2" />
            <widget name="key_green" position="200,0" zPosition="1" size="200,40" font="Regular;22" halign="center" valign="center" backgroundColor="#1f771f" transparent="1" shadowColor="black" shadowOffset="-2,-2" />
            <widget name="config" position="5,50" itemHeight="30" size="790,390" enableWrapAround="1" scrollbarMode="showOnDemand" />
            <ePixmap pixmap="skin_default/div-h.png" position="0,445" zPosition="2" size="800,2" />
            <widget name="help" position="5,450" size="790,65" font="Regular;22" />
        </screen>"""
    skin_setup = """<screen name="SSUSetupScreen" position="center,170" size="900,820" title="speedy Service Scan Updates">
        <widget name="key_red" position="10,5" size="250,70" font="Regular;30" halign="center" valign="center" />
        <widget name="key_green" position="323,3" size="250,70" font="Regular;30" halign="center" valign="center" />
        <widget name="key_yellow" position="627,3" size="250,70" font="Regular;30" halign="center" valign="center" />
        <widget name="config" position="10,90" itemHeight="35" size="850,540" enableWrapAround="1" scrollbarMode="showOnDemand" font="NotoSans-Bold;24" />
        <widget name="help" position="10,655" size="850,145" font="Regular;32" />
    </screen>"""

    def __init__(self, session):
        Screen.__init__(self, session)
        self.session = session
        self.list = []
        ConfigListScreen.__init__(self, self.list, session=session)
        self['status'] = Label(_("Checking for updates..."))
        self['progress'] = ProgressBar()
        self['progresstext'] = Label("")
        self['key_red'] = Button(_("Exit"))
        self['key_green'] = Button(_("Start"))
        self['key_yellow'] = Button(_("Cancel"))
        self['key_blue'] = Button(_("Check Update"))

        self["key_red"] = Button(_("Cancel"))
        self["key_green"] = Button(_("Save"))
        self["help"] = Label("")

        self["setupActions"] = ActionMap(
            ["SetupActions", "ColorActions", "HelpActions"],
            {
                "red": self.keyCancel,
                "green": self.keySave,
                "save": self.keySave,
                "cancel": self.keyCancel,
                "ok": self.keySave,
                "displayHelp": self.help,
            },
            -2
        )

        self.onLayoutFinish.append(self.layoutFinished)
        self["config"].onSelectionChanged.append(self.updateHelp)
    def layoutFinished(self):
        self.populateList()

    def populateList(self):
        self.list = [
            getConfigListEntry(_("Add new TV services"), config.plugins.speedyservicescanupdates.add_new_tv_services, _("Create 'Service Scan Updates' bouquet for new TV services?")),
            getConfigListEntry(_("Add new radio services"), config.plugins.speedyservicescanupdates.add_new_radio_services, _("Create 'Service Scan Updates' bouquet for new radio services?")),
            getConfigListEntry(_("Clear bouquet at each search"), config.plugins.speedyservicescanupdates.clear_bouquet, _("Empty the 'Service Scan Updates' bouquet on every scan, otherwise the new services will be appended?")),
        ]
        self["config"].list = self.list
        self["config"].l.setList(self.list)

    def updateHelp(self):
        cur = self["config"].getCurrent()
        if cur:
            self["help"].text = cur[2]

    def help(self):
        self.session.open(SSUHelpScreen)


class SSUHelpScreen(Screen):
    if sz_w == 1920:
        skin = """
        <screen name="SSUHelpScreen" position="center,170" size="1200,820" title="speedy Service Scan Updates">
            <widget name="help" position="20,5" size="1100,780" font="Regular;30" />
        </screen>"""
    else:
        skin = """
        <screen name="SSUHelpScreen" position="center,120" size="800,530" title="speedy Service Scan Updates">
            <widget name="help" position="10,5" size="760,500" font="Regular;21" />
        </screen>"""
    def check_update(self):
        self['status'].setText(_("Latest version: %s") % version)

    def __init__(self, session):
        Screen.__init__(self, session)
        self.session = session
        self['help'] = Label(_("Configure the update options."))
        self['key_red'] = Button(_("Cancel"))
        self['key_green'] = Button(_("Save"))
        self['key_yellow'] = Button(_("Default"))


        self.list = [
            getConfigListEntry(_("Add new TV services"), config.plugins.speedyservicescanupdates.add_new_tv_services),
            getConfigListEntry(_("Add new Radio services"), config.plugins.speedyservicescanupdates.add_new_radio_services),
            getConfigListEntry(_("Clear Bouquet"), config.plugins.speedyservicescanupdates.clear_bouquet)
        ]
        ConfigListScreen.__init__(self, self.list, session=self.session)
        self.displayHelp()

    def cancel(self):
        self.close()

    def save(self):
        for x in self.list:
            x[1].save()
        try:
            config.save()
        except Exception as e:
            self.session.open(MessageBox, _("Failed to save config: %s") % e, type=MessageBox.TYPE_ERROR)
        self.close()

    def set_default(self):
        for x in self.list:
            x[1].setValue(x[1].default)
        self.updateList()

    def updateList(self):
        self['config'].setList(self.list)

    def displayHelp(self):
        help_text = _("""
- Add new TV services: Add missing TV channels to bouquets.
- Add new Radio services: Add missing radio channels to bouquets.
- Clear Bouquet: Remove empty or obsolete bouquets.
- Save: Apply changes.
- Cancel: Exit without saving.
""")
        self['help'].setText(help_text.strip())

    def layoutFinished(self):
        """Zus?tzliche Infos nach Layout-Fertigstellung anzeigen."""
        help_txt = _("This plugin creates a favorites bouquet (for TV and Radio) with the name 'Service Scan Updates'.\n")
        help_txt += _("All new services found during the scan are inserted there together with a marker.\n")
        help_txt += _("This allows you to quickly and clearly see which new services were found,\n")
        help_txt += _("and you can add individual services to your own Favorites bouquets as usual.\n\n")
        help_txt += _("In order for the 'Service Scan Updates' bouquet to be displayed,\n")
        help_txt += _("the option 'Allow multiple bouquets' must be activated in the system settings of the box.")

        self["help"].setText(help_txt)

# -*- coding: utf-8 -*-
from __future__ import print_function, unicode_literals  # Sicherstellen, dass Strings Unicode sind und print funktioniert in Python 2 und 3

# --- Standardbibliothek ---
import os
import sys
import re
import zipfile
import requests
import shutil

# Übersetzungsfunktion aus __init__.py laden
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
from Screens.Config import ConfigListScreen
from Components.ConfigList import getConfigListEntry
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

# --- Bildschirmgröße und Skin-Auswahl ---
sz_w = getDesktop(0).size().width()
sz_h = getDesktop(0).size().height()

# Bildschirmauflösungen anpassen
if sz_w == 1920 and sz_h == 1080:
    skin_update = """<screen name="SSUUpdateScreen" position="center,170" size="1200,820" title="speedy Service Scan Updates">
        <widget name="progress" position="10,100" size="1180,50" />
        <widget name="status" position="10,160" size="1180,50" font="Regular;30" valign="center" halign="center" />
        <widget name="progresstext" position="10,220" size="1180,50" font="Regular;30" valign="center" halign="center" />
        <widget name="key_red" position="3,4" size="295,70" font="Regular;30" halign="center" valign="center" />
        <widget name="key_green" position="305,3" size="300,70" font="Regular;30" halign="center" valign="center" />
        <widget name="key_yellow" position="604,5" size="300,70" font="Regular;30" halign="center" valign="center" />
        <widget name="key_blue" position="916,6" size="295,70" font="Regular;30" halign="center" valign="center" />
    </screen>"""
    skin_setup = """<screen name="SSUSetupScreen" position="center,170" size="1200,820" title="speedy Service Scan Updates">
        <widget name="key_red" position="10,5" size="295,70" font="Regular;30" halign="center" valign="center" />
        <widget name="key_green" position="323,3" size="300,70" font="Regular;30" halign="center" valign="center" />
        <widget name="key_yellow" position="627,3" size="300,70" font="Regular;30" halign="center" valign="center" />
        <widget name="config" position="10,90" itemHeight="35" size="1180,540" enableWrapAround="1" scrollbarMode="showOnDemand" font="NotoSans-Bold;24" />
        <widget name="help" position="10,655" size="1180,145" font="Regular;32" />
    </screen>"""
else:
    skin_update = """<screen name="SSUUpdateScreen" position="410,170" size="1100,820" title="speedy Service Scan Updates">
        <widget name="progress" position="10,100" size="1050,50" />
        <widget name="status" position="10,160" size="1050,50" font="Regular;30" valign="center" halign="center" />
        <widget name="progresstext" position="10,220" size="1050,50" font="Regular;30" valign="center" halign="center" />
        <widget name="key_red" position="13,2" size="250,70" font="Regular;30" halign="center" valign="center" />
        <widget name="key_green" position="277,3" size="250,70" font="Regular;30" halign="center" valign="center" />
        <widget name="key_yellow" position="538,4" size="250,70" font="Regular;30" halign="center" valign="center" />
        <widget name="key_blue" position="798,5" size="250,70" font="Regular;30" halign="center" valign="center" />
    </screen>"""
    skin_setup = """<screen name="SSUSetupScreen" position="center,170" size="900,820" title="speedy Service Scan Updates">
        <widget name="key_red" position="10,5" size="250,70" font="Regular;30" halign="center" valign="center" />
        <widget name="key_green" position="323,3" size="250,70" font="Regular;30" halign="center" valign="center" />
        <widget name="key_yellow" position="627,3" size="250,70" font="Regular;30" halign="center" valign="center" />
        <widget name="config" position="10,90" itemHeight="35" size="850,540" enableWrapAround="1" scrollbarMode="showOnDemand" font="NotoSans-Bold;24" />
        <widget name="help" position="10,655" size="850,145" font="Regular;32" />
    </screen>"""

# --- Update Screen ---
class SSUUpdateScreen(Screen):
    skin = skin_update

    def __init__(self, session):
        Screen.__init__(self, session)
        self.session = session
        self['status'] = Label(_("Checking for updates..."))
        self['progress'] = ProgressBar()
        self['progresstext'] = Label("")
        self['key_red'] = Button(_("Exit"))
        self['key_green'] = Button(_("Start"))
        self['key_yellow'] = Button(_("Cancel"))
        self['key_blue'] = Button(_("Check Update"))

        self['actions'] = ActionMap(['ColorActions', 'OkCancelActions'],
                                    {
                                        'red': self.exit,
                                        'green': self.start_update,
                                        'yellow': self.cancel,
                                        'blue': self.check_update,
                                        'ok': self.start_update,
                                        'cancel': self.exit
                                    }, -1)
        self.download_complete = False

    def exit(self):
        self.close()

    def cancel(self):
        self['status'].setText(_("Update cancelled."))
        self.download_complete = False

    def start_update(self):
        try:
            self['status'].setText(_("Downloading update..."))
            r = requests.get(update_url, stream=True, timeout=10)
            if r.status_code == 200:
                with open(download_path, "wb") as f:
                    total_length = r.headers.get('content-length')
                    dl = 0
                    total_length = int(total_length) if total_length else None
                    for data in r.iter_content(chunk_size=4096):
                        f.write(data)
                        if total_length:
                            dl += len(data)
                            percent = int(dl * 100 / total_length)
                            self['progress'].setValue(percent)
                            self['progresstext'].setText(f"{percent}%")
                self.extract_update()
            else:
                self['status'].setText(f"Download failed: {r.status_code}")
        except requests.exceptions.RequestException as e:
            self['status'].setText(f"Download error: {e}")

    def extract_update(self):
        try:
            if zipfile.is_zipfile(download_path):
                if os.path.exists(extract_dir):
                    shutil.rmtree(extract_dir)
                with zipfile.ZipFile(download_path, "r") as zip_ref:
                    zip_ref.extractall(extract_dir)
                self['status'].setText(_("Update extracted."))
                self.install_update()
            else:
                self['status'].setText(_("Downloaded file is not a valid ZIP archive."))
        except Exception as e:
            self['status'].setText(f"Extraction failed: {e}")

    def install_update(self):
        try:
            if os.path.exists(extract_dir):
                shutil.rmtree(target_dir, ignore_errors=True)
                shutil.move(extract_dir, target_dir)
                self['status'].setText(_("Update installed successfully."))
            else:
                self['status'].setText(_("Extraction folder is empty."))
        except Exception as e:
            self['status'].setText(f"Installation failed: {e}")

    def check_update(self):
        self['status'].setText(_("Checking for updates..."))
        self.start_update()

# --- Konfiguration und Setup Screen ---
class SSUSetupScreen(Screen):
    skin = skin_setup

    def __init__(self, session):
        Screen.__init__(self, session)
        self.session = session
        self.list = [
            getConfigListEntry(_("Add new TV services"), config.plugins.speedyservicescanupdates.add_new_tv_services),
            getConfigListEntry(_("Add new Radio services"), config.plugins.speedyservicescanupdates.add_new_radio_services),
            getConfigListEntry(_("Clear bouquet"), config.plugins.speedyservicescanupdates.clear_bouquet),
        ]
        self['key_red'] = Button(_("Exit"))
        self['key_green'] = Button(_("Save"))
        self['key_yellow'] = Button(_("Default"))
        self['config'] = ConfigListScreen(self.list, session)
        self['actions'] = ActionMap(['OkCancelActions', 'ColorActions'], {
            'red': self.exit,
            'green': self.save,
            'yellow': self.set_default,
            'cancel': self.exit,
        })

    def exit(self):
        self.close()

    def set_default(self):
        """Setze die Einstellungen auf Standardwerte."""
        for x in self.list:
            x[1].setValue(x[1].default)
        self.updateList()
        self.session.open(MessageBox, _("Settings have been reset to default."), MessageBox.TYPE_INFO, timeout=5)

    def save(self):
        """Speichert die Konfiguration."""
        for x in self.list:
            x[1].save()
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
        """Zusätzliche Infos nach Layout-Fertigstellung anzeigen."""
        help_txt = _("This plugin creates a favorites bouquet (for TV and Radio) with the name 'Service Scan Updates'.\n")
        help_txt += _("All new services found during the scan are inserted there together with a marker.\n")
        help_txt += _("This allows you to quickly and clearly see which new services were found,\n")
        help_txt += _("and you can add individual services to your own Favorites bouquets as usual.\n\n")
        help_txt += _("In order for the 'Service Scan Updates' bouquet to be displayed,\n")
        help_txt += _("the option 'Allow multiple bouquets' must be activated in the system settings of the box.")
        self["help"].setText(help_txt)


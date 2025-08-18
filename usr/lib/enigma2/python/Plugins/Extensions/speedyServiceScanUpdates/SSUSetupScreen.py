# -*- coding: utf-8 -*-

# --- Standardbibliothek ---
import os
import sys
import re
import zipfile
import requests
import shutil

# Übersetzungsfunktion
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
from Components.config import config
from Screens.Config import ConfigListScreen
from Components.ConfigList import getConfigListEntry

# --- Plugin-Pfad dynamisch ermitteln (Extensions oder SystemPlugins) ---
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

# --- Version ---
version = "3.7"

# GitHub ZIP-Download URL
update_url = "https://github.com/speedy005/speedyServiceScanUpdates/archive/refs/heads/main.zip"

# Speicherorte
download_path = "/tmp/ServiceScanUpdates-main.zip"
extract_dir = "/tmp/ServiceScanUpdates"
target_dir = "/usr/lib/enigma2/python/Plugins/Extensions/speedyServiceScanUpdates"

# --- Hilfsfunktionen ---
def clean_version(ver):
    """Filtert Versionsnummer auf nur Ziffern und Punkte."""
    return re.sub(r'[^0-9\.]', '', ver)


# Bildschirmgröße und Skin-Auswahl
sz_w = getDesktop(0).size().width()
if sz_w == 1920:
    skin_update = """
    <screen name="SSUUpdateScreen" position="center,170" size="1200,820" title="speedy Service Scan Updates">
        <ePixmap pixmap="skin_default/buttons/red.png" position="10,5" size="5,70" />
        <ePixmap pixmap="skin_default/buttons/green.png" position="305,5" size="5,70" />
        <ePixmap pixmap="skin_default/buttons/yellow.png" position="610,5" size="5,70" />
        <ePixmap pixmap="skin_default/buttons/blue.png" position="915,5" size="5,70" />
        <widget name="progress" position="10,100" size="1180,50" />
        <widget name="status" position="10,160" size="1180,50" font="Regular;30" valign="center" halign="center" />
        <widget name="progresstext" position="10,220" size="1180,50" font="Regular;30" valign="center" halign="center" />
        <widget name="key_red" position="3,4" size="295,70" font="Regular;30" halign="center" valign="center" />
        <widget name="key_green" position="305,3" size="300,70" font="Regular;30" halign="center" valign="center" />
        <widget name="key_yellow" position="604,5" size="300,70" font="Regular;30" halign="center" valign="center" />
        <widget name="key_blue" position="916,6" size="295,70" font="Regular;30" halign="center" valign="center" />
    </screen>"""
    skin_setup = """
    <screen name="SSUSetupScreen" position="center,170" size="1200,820" title="speedy Service Scan Updates">
        <ePixmap pixmap="skin_default/buttons/red.png" position="10,5" size="5,70" />
        <ePixmap pixmap="skin_default/buttons/green.png" position="305,5" size="5,70" />
        <ePixmap pixmap="skin_default/buttons/yellow.png" position="627,5" size="5,70" />
        <eLabel text="HELP" position="1110,30" size="80,35" backgroundColor="black" valign="center" halign="center" font="Regular;24" />
        <widget name="key_red" position="10,5" size="295,70" font="Regular;30" halign="center" valign="center" />
        <widget name="key_green" position="323,3" size="300,70" font="Regular;30" halign="center" valign="center" />
        <widget name="key_yellow" position="627,3" size="300,70" font="Regular;30" halign="center" valign="center" />
        <widget name="config" position="10,90" itemHeight="35" size="1180,540" enableWrapAround="1" scrollbarMode="showOnDemand" font="NotoSans-Bold; 24" />
        <ePixmap pixmap="skin_default/div-h.png" position="10,650" size="1180,2" />
        <widget name="help" position="10,655" size="1180,145" font="Regular;32" />
    </screen>"""
else:
    skin_update = """
    <screen name="SSUUpdateScreen" position="410,170" size="1100,820" title="speedy Service Scan Updates">
        <ePixmap pixmap="skin_default/buttons/red.png" position="10,5" size="5,70" />
        <ePixmap pixmap="skin_default/buttons/green.png" position="275,5" size="5,70" />
        <ePixmap pixmap="skin_default/buttons/yellow.png" position="537,5" size="5,70" />
        <ePixmap pixmap="skin_default/buttons/blue.png" position="795,6" size="5,70" />
        <widget name="progress" position="10,100" size="1050,50" />
        <widget name="status" position="10,160" size="1050,50" font="Regular;30" valign="center" halign="center" />
        <widget name="progresstext" position="10,220" size="1050,50" font="Regular;30" valign="center" halign="center" />
        <widget name="key_red" position="13,2" size="250,70" font="Regular;30" halign="center" valign="center" />
        <widget name="key_green" position="277,3" size="250,70" font="Regular;30" halign="center" valign="center" />
        <widget name="key_yellow" position="538,4" size="250,70" font="Regular;30" halign="center" valign="center" />
        <widget name="key_blue" position="798,5" size="250,70" font="Regular;30" halign="center" valign="center" />
    </screen>"""
    skin_setup = """
    <screen name="SSUSetupScreen" position="center,170" size="900,820" title="speedy Service Scan Updates">
        <ePixmap pixmap="skin_default/buttons/red.png" position="10,5" size="5,70" />
        <ePixmap pixmap="skin_default/buttons/green.png" position="305,5" size="5,70" />
        <ePixmap pixmap="skin_default/buttons/yellow.png" position="627,5" size="5,70" />
        <eLabel text="HELP" position="800,30" size="80,35" backgroundColor="black" valign="center" halign="center" font="Regular;24" />
        <widget name="key_red" position="10,5" size="250,70" font="Regular;30" halign="center" valign="center" />
        <widget name="key_green" position="323,3" size="250,70" font="Regular;30" halign="center" valign="center" />
        <widget name="key_yellow" position="627,3" size="250,70" font="Regular;30" halign="center" valign="center" />
        <widget name="config" position="10,90" itemHeight="35" size="850,540" enableWrapAround="1" scrollbarMode="showOnDemand" font="NotoSans-Bold; 24" />
        <ePixmap pixmap="skin_default/div-h.png" position="10,650" size="850,2" />
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
        self['progresstext'] = Label()

        self["key_red"] = Button(_("Cancel"))
        self["key_green"] = Button(_("Start"))
        self["key_yellow"] = Button(_("Check for Updates"))
        self["key_blue"] = Button(_("Exit"))

        self["actions"] = ActionMap(
            ["WizardActions", "ColorActions", "SetupActions", "OkCancelActions"],
            {
                "red": self.keyCancel,
                "green": self.startUpdate,
                "yellow": self.checkForUpdates,
                "blue": self.keyExit,
                "cancel": self.keyCancel,
                "ok": self.startUpdate,
            },
            -2
        )

    def startUpdate(self):
        self.checkForUpdates()

    def checkForUpdates(self):
        self['status'].setText(_('Checking for updates...'))
        self['progresstext'].setText(_('Please wait...'))
        self.getLatestVersion()

    def getLatestVersion(self):
        try:
            response = requests.get("https://api.github.com/repos/speedy005/speedyServiceScanUpdates/releases/latest")

            if response.status_code == 200:
                data = response.json()
                if "message" in data and "rate limit" in data["message"].lower():
                    self['status'].setText(_('GitHub rate limit reached.'))
                    self['progresstext'].setText(_('Please try again later.'))
                    return

                latest_version = clean_version(str(data.get('tag_name', '0')))
                if latest_version != version:
                    self['status'].setText(_('New update available: {}').format(latest_version))
                    self['progresstext'].setText(_('Update available!'))
                    if self.downloadChangelog():
                        self.extractUpdate(download_path)
                else:
                    self['status'].setText(_('No update available.'))
                    self['progresstext'].setText(_('You have the latest version.'))
            else:
                self['status'].setText(_('Failed to check for updates.'))
                self['progresstext'].setText(_('Error: Unable to fetch the update information.'))
        except Exception as e:
            self['status'].setText(_('Failed to check for updates.'))
            self['progresstext'].setText(f'Error: {str(e)}')

    def downloadChangelog(self):
        try:
            response = requests.get(update_url, stream=True)
            if response.status_code == 200:
                with open(download_path, 'wb') as f:
                    for data in response.iter_content(chunk_size=1024):
                        f.write(data)

                if os.path.exists(download_path):
                    self['status'].setText(_('Download completed.'))
                    self['progresstext'].setText(f'File saved to: {download_path}')
                    return True
            self['status'].setText(_('Download failed.'))
            return False
        except Exception as e:
            self['status'].setText(_('Download failed.'))
            self['progresstext'].setText(f'Error: {str(e)}')
            return False

    def extractUpdate(self, downloaded_file):
        try:
            with zipfile.ZipFile(downloaded_file, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)

            extracted_folder = os.path.join(extract_dir, os.listdir(extract_dir)[0])
            shutil.copytree(extracted_folder, target_dir, dirs_exist_ok=True)

            self['status'].setText(_('Update installed successfully.'))
            self['progresstext'].setText(_('Update installed.'))
        except Exception as e:
            self['status'].setText(_('Failed to extract update: {}'.format(str(e))))
            self['progresstext'].setText(_('Extraction error.'))

    def keyCancel(self):
        self.close()

    def keyExit(self):
        self.close()


# --- Setup Screen ---
class SSUSetupScreen(ConfigListScreen, Screen):
    skin = skin_setup

    def __init__(self, session):
        Screen.__init__(self, session)
        self.session = session
        self.list = []
        ConfigListScreen.__init__(self, self.list, session=session)

        self["key_red"] = Button(_("Cancel"))
        self["key_green"] = Button(_("Save"))
        self["key_yellow"] = Button(_("Check for Updates"))
        self["help"] = Label("")

        self["setupActions"] = ActionMap(
            ["SetupActions", "ColorActions", "HelpActions"],
            {
                "red": self.keyCancel,
                "green": self.keySave,
                "yellow": self.checkForUpdates,
                "save": self.keySave,
                "cancel": self.keyCancel,
                "ok": self.keySave,
                "displayHelp": self.help,
            },
            -2
        )

        self.onLayoutFinish.append(self.layoutFinished)
        self["config"].onSelectionChanged.append(self.updateHelp)
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
        self.session.open(MessageBox, _("Help not yet implemented."), MessageBox.TYPE_INFO)

    def checkForUpdates(self):
        self.session.open(SSUUpdateScreen)

    def keyCancel(self):
        self.close()

    def keySave(self):
        self.close()

    def layoutFinished(self):
        help_txt = _("This plugin creates a favorites bouquet (for TV and Radio) with the name 'Service Scan Updates'.\n")
        help_txt += _("All new services found during the scan are inserted there together with a marker.\n")
        help_txt += _("This allows you to quickly and clearly see which new services were found,\n")
        help_txt += _("and you can add individual services to your own Favorites bouquets as usual.\n\n")
        help_txt += _("In order for the 'Service Scan Updates' bouquet to be displayed,\n")
        help_txt += _("the option 'Allow multiple bouquets' must be activated in the system settings of the box.")
        self["help"].setText(help_txt)

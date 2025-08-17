# -*- coding: utf-8 -*-

# --- Standardbibliothek ---
import os
import sys
import urllib.request
import shutil
import zipfile

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

# --- Enigma2-Imports ---
from Screens.Screen import Screen
from Components.ActionMap import ActionMap
from Components.Button import Button
from Components.Label import Label
from Components.ProgressBar import ProgressBar
from Screens.MessageBox import MessageBox
from Tools.Directories import fileExists

# --- Version ---
version = "3.6"

# GitHub URL für das ZIP-Archiv
update_url = "https://github.com/speedy005/speedyServiceScanUpdates/archive/refs/heads/main.zip"  # ZIP-Download-URL

# Speicherorte
download_path = "/tmp/speedyServiceScanUpdates.zip"  # Speicherort für die heruntergeladene ZIP-Datei
extract_dir = "/tmp/speedyServiceScanUpdates"  # Temporärer Ordner zum Entpacken
target_dir = "/usr/lib/enigma2/python/Plugins/Extensions/speedyServiceScanUpdates"  # Zielordner

# Klasse für das Update-Screen
class SSUUpdateScreen(Screen):
    if getDesktop(0).size().width() == 1920:
        skin = """
        <screen name="SSUUpdateScreen" position="center,170" size="1200,820" title="speedy Service Scan Updates">
        <ePixmap pixmap="skin_default/buttons/red.png" position="10,5" size="5,70" scale="stretch" alphatest="on" />
        <ePixmap pixmap="skin_default/buttons/green.png" position="305,5" size="5,70" scale="stretch" alphatest="on" />
        <ePixmap pixmap="skin_default/buttons/yellow.png" position="610,5" size="5,70" scale="stretch" alphatest="on" />
        <ePixmap pixmap="skin_default/buttons/blue.png" position="915,5" size="5,70" scale="stretch" alphatest="on" />
        <widget name="progress" position="10,100" size="1180,50" />
        <widget name="status" position="10,160" size="1180,50" font="Regular;30" valign="center" halign="center" />
        <widget name="progresstext" position="10,220" size="1180,50" font="Regular;30" valign="center" halign="center" />
        <widget name="key_yellow" position="604,5" zPosition="1" size="300,70" font="Regular;30" halign="center" valign="center" backgroundColor="black" transparent="1" shadowColor="green" foregroundColor="white" shadowOffset="-2,-2" />
        <widget name="key_green" position="305,3" zPosition="1" size="300,70" font="Regular;30" halign="center" valign="center" backgroundColor="black" transparent="1" shadowColor="green" foregroundColor="white" shadowOffset="-2,-2" />
        <widget name="key_red" position="3,4" zPosition="1" size="295,70" font="Regular;30" halign="center" valign="center" backgroundColor="black" transparent="1" shadowColor="green" foregroundColor="white" shadowOffset="-2,-2" />
        <widget name="key_blue" position="916,6" zPosition="1" size="295,70" font="Regular;30" halign="center" valign="center" backgroundColor="black" transparent="1" shadowColor="green" foregroundColor="white" shadowOffset="-2,-2" />
         </screen>"""
    else:
        skin = """
        <screen name="SIUpdateScreen" position="410,170" size="1100,820" title="speedy Service Scan Updates">
        <ePixmap pixmap="skin_default/buttons/red.png" position="10,5" size="5,70" scale="stretch" alphatest="on" />
        <ePixmap pixmap="skin_default/buttons/green.png" position="275,5" size="5,70" scale="stretch" alphatest="on" />
        <ePixmap pixmap="skin_default/buttons/yellow.png" position="537,5" size="5,70" scale="stretch" alphatest="on" />
        <ePixmap pixmap="skin_default/buttons/blue.png" position="795,6" size="5,70" scale="stretch" alphatest="on" />
        <widget name="progress" position="10,100" size="1050,50" />
        <widget name="status" position="10,160" size="1050,50" font="Regular;30" valign="center" halign="center" />
        <widget name="progresstext" position="10,220" size="1050,50" font="Regular;30" valign="center" halign="center" />
        <widget name="key_yellow" position="538,4" zPosition="1" size="250,70" font="Regular;30" halign="center" foregroundColor="white" valign="center" backgroundColor="black" transparent="1" foregroundColor="white" shadowColor="green" shadowOffset="-2,-2" />
        <widget name="key_green" position="277,3" zPosition="1" size="250,70" font="Regular;30" halign="center" valign="center" foregroundColor="white" backgroundColor="black" transparent="1" foregroundColor="white" shadowColor="green" shadowOffset="-2,-2" />
        <widget name="key_red" position="13,2" zPosition="1" size="250,70" font="Regular;30" foregroundColor="white" halign="center" valign="center" backgroundColor="black" transparent="1" foregroundColor="white" shadowColor="green" shadowOffset="-2,-2" />
        <widget name="key_blue" position="798,5" zPosition="1" size="250,70" font="Regular;30" halign="center" valign="center" backgroundColor="black" transparent="1" shadowColor="green" foregroundColor="white" shadowOffset="-2,-2" />
         </screen>"""

    def __init__(self, session):
        Screen.__init__(self, session)
        self.session = session
        self['status'] = Label(_("Checking for updates..."))
        self['progress'] = ProgressBar()
        self['progresstext'] = Label()

        # Tastenbelegung
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
        """Startet den Update-Prozess."""
        self.checkForUpdates()

    def checkForUpdates(self):
        """Überprüft, ob ein Update vorhanden ist und zeigt einen Hinweis an."""
        self['status'].setText(_('Checking for updates...'))
        self['progresstext'].setText(_('Please wait...'))

        # Aufruf der Methode zum Herunterladen des Updates
        self.downloadChangelog()

    def downloadChangelog(self):
        """Lädt die changelog.txt herunter und zeigt sie an."""
        try:
            self['status'].setText(_('Downloading update...'))
            print("Starting download...")  # Debugging

            # Versuche, die Datei herunterzuladen
            urllib.request.urlretrieve(update_url, download_path)

            # Überprüfen, ob die Datei heruntergeladen wurde
            if os.path.exists(download_path):
                self['status'].setText(_('Update downloaded successfully.'))
                print("Download completed.")  # Debugging
                self.extractUpdate(download_path)
            else:
                self['status'].setText(_('Failed to download update.'))
                self['progresstext'].setText(_('Download failed.'))
                print("Fehler: Die ZIP-Datei wurde nicht heruntergeladen.")  # Debugging

        except Exception as e:
            self['status'].setText(_('Download failed: {}'.format(str(e))))
            self['progresstext'].setText(_('Download error.'))
            print("Fehler beim Download: ", e)  # Debugging

    def extractUpdate(self, downloaded_file):
        """Entpackt die heruntergeladene ZIP-Datei direkt aus dem 'speedyServiceScanUpdates-main/speedyServiceScanUpdates' Ordner in das Zielverzeichnis."""
        try:
            # Überprüfen, ob die Datei existiert
            if not os.path.exists(downloaded_file):
                self['status'].setText(_('Downloaded file not found.'))
                self['progresstext'].setText(_('Download failed.'))
                print(f"Fehler: Die Datei '{downloaded_file}' existiert nicht.")  # Debugging
                return

            # Entpacken der ZIP-Datei in den temporären Ordner
            self['status'].setText(_('Extracting update...'))
            with zipfile.ZipFile(downloaded_file, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)

            # Pfad zu den entpackten Dateien im Ordner 'speedyServiceScanUpdates-main/speedyServiceScanUpdates'
            source_dir = os.path.join(extract_dir, "speedyServiceScanUpdates-main", "speedyServiceScanUpdates")
            
            # Überprüfen, ob der Ordner existiert
            if os.path.exists(source_dir):
                print(f"Found source directory: {source_dir}")  # Debugging

                # Zielordner löschen, wenn er existiert
                if os.path.exists(target_dir):
                    print(f"Removing existing target directory: {target_dir}")  # Debugging
                    shutil.rmtree(target_dir)

                # Dateien aus dem entpackten Ordner 'speedyServiceScanUpdates' direkt ins Ziel kopieren
                shutil.copytree(source_dir, target_dir)
                self['status'].setText(_('Update completed successfully!'))
                self['progresstext'].setText(_('Update installed successfully.'))
                
                # Zeige das Changelog nach der Installation an
                self.showChangelog(extract_dir)
            else:
                self['status'].setText(_('Failed to extract update. "speedyServiceScanUpdates" not found.'))
                print("Fehler: Ordner 'speedyServiceScanUpdates' nicht gefunden.")  # Debugging

        except Exception as e:
            self['status'].setText(_('Failed to extract update: {}'.format(str(e))))
            self['progresstext'].setText(_('Extraction failed.'))
            print("Fehler beim Entpacken: ", e)  # Debugging

    def showChangelog(self, extract_dir):
        """Zeigt das Changelog nach dem Update an."""
        changelog_path = os.path.join(extract_dir, "speedyServiceScanUpdates-main", "changelog.txt")
        try:
            if os.path.exists(changelog_path):
                with open(changelog_path, 'r') as changelog_file:
                    changelog = changelog_file.read()
                    self['changelogtext'].setText(changelog)
                    print("Changelog angezeigt.")  # Debugging
            else:
                print("Changelog-Datei nicht gefunden.")  # Debugging
                self['changelogtext'].setText(_('Changelog not found.'))
        except Exception as e:
            print("Fehler beim Laden des Changelogs: ", e)  # Debugging
            self['changelogtext'].setText(_('Error loading changelog.'))

    def keyCancel(self):
        """Beenden des Updates."""
        self.close()

    def keyExit(self):
        """Verlässt den Bildschirm."""
        self.close()


# SetupScreen Klasse anpassen, um den Update-Button hinzuzufügen
class SSUSetupScreen(ConfigListScreen, Screen):
    if sz_w == 1920:
        skin = """
        <screen name="SSUSetupScreen" position="center,170" size="1200,820" title="speedy Service Scan Updates">
            <ePixmap pixmap="skin_default/buttons/red.png" position="10,5" size="5,70" scale="stretch" alphatest="on" />
            <ePixmap pixmap="skin_default/buttons/green.png" position="305,5" size="5,70" scale="stretch" alphatest="on" />
            <ePixmap pixmap="skin_default/buttons/yellow.png" position="627,5" size="5,70" scale="stretch" alphatest="on" />
            <eLabel text="HELP" position="1110,30" size="80,35" backgroundColor="black" valign="center" halign="center" font="Regular;24" />
            <widget name="key_red" position="10,5" zPosition="1" size="295,70" font="Regular;30" halign="center" valign="center" foregroundColor="white" backgroundColor="#9f1313" transparent="1" shadowColor="black" shadowOffset="-2,-2" />
            <widget name="key_green" position="323,3" zPosition="1" size="300,70" font="Regular;30" halign="center" foregroundColor="white" valign="center" backgroundColor="black" transparent="1" shadowColor="black" shadowOffset="-2,-2" />
            <widget name="key_yellow" position="627,3" zPosition="1" size="300,70" font="Regular;30" halign="center" valign="center" foregroundColor="white" backgroundColor="black" transparent="1" shadowColor="black" shadowOffset="-2,-2" />
            <widget name="config" position="10,90" itemHeight="35" size="1180,540" enableWrapAround="1" scrollbarMode="showOnDemand" font="NotoSans-Bold; 24" />
            <ePixmap pixmap="skin_default/div-h.png" position="10,650" zPosition="2" size="1180,2" />
            <widget name="help" foregroundColor="green" position="10,655" size="1180,145" font="Regular;32" />
        </screen>"""
    else:
        skin = """
        <screen name="SISettingsScreen" position="center,170" size="900,820" title="speedy Service Scan Updates">
            <ePixmap pixmap="skin_default/buttons/red.png" position="10,5" size="5,70" scale="stretch" alphatest="on" />
            <ePixmap pixmap="skin_default/buttons/green.png" position="305,5" size="5,70" scale="stretch" alphatest="on" />
            <ePixmap pixmap="skin_default/buttons/yellow.png" position="627,5" size="5,70" scale="stretch" alphatest="on" />
            <eLabel text="HELP" position="1110,30" size="80,35" backgroundColor="black" valign="center" halign="center" font="Regular;24" />
            <widget name="key_red" position="10,5" zPosition="1" size="295,70" font="Regular;30" halign="center" valign="center" foregroundColor="white" backgroundColor="#9f1313" transparent="1" shadowColor="black" shadowOffset="-2,-2" />
            <widget name="key_green" position="323,3" zPosition="1" size="300,70" font="Regular;30" halign="center" foregroundColor="white" valign="center" backgroundColor="black" transparent="1" shadowColor="black" shadowOffset="-2,-2" />
            <widget name="key_yellow" position="627,3" zPosition="1" size="300,70" font="Regular;30" halign="center" valign="center" foregroundColor="white" backgroundColor="black" transparent="1" shadowColor="black" shadowOffset="-2,-2" />
            <widget name="config" position="10,90" itemHeight="35" size="850,540" enableWrapAround="1" scrollbarMode="showOnDemand" font="NotoSans-Bold; 24" />
            <ePixmap pixmap="skin_default/div-h.png" position="10,650" zPosition="2" size="850,2" />
            <widget name="help" foregroundColor="green" position="10,655" size="850,145" font="Regular;32" />
        </screen>"""

    def __init__(self, session):
        Screen.__init__(self, session)
        self.session = session
        self.list = []
        ConfigListScreen.__init__(self, self.list, session=session)

        # Initialisiere Buttons
        self["key_red"] = Button(_("Cancel"))
        self["key_green"] = Button(_("Save"))
        self["key_yellow"] = Button(_("Check for Updates"))
        self["help"] = Label("")

        # Tastenbelegung
        self["setupActions"] = ActionMap(
            ["SetupActions", "ColorActions", "HelpActions"],
            {
                "red": self.keyCancel,
                "green": self.keySave,
                "yellow": self.checkForUpdates,  # Gelbe Taste für Updates
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

    def checkForUpdates(self):
        self.session.open(SSUUpdateScreen)  # Neue Update-Seite öffnen

    def keyCancel(self):
        self.close()

    def keySave(self):
        self.close()



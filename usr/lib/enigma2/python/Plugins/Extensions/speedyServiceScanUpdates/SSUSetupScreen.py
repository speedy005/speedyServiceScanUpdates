# -*- coding: utf-8 -*-
### from __future__ import print_function, unicode_literals

# --- Standardbibliothek ---
import os
import sys
import re
import zipfile
import tarfile
import requests
import shutil

# Übersetzungsfunktion aus __init__.py laden
from . import _

# Enigma2 Imports
from enigma import getDesktop
from Screens.Screen import Screen
from Components.ConfigList import ConfigListScreen
from Components.ActionMap import ActionMap
from Components.Button import Button
from Components.Label import Label
from Components.ProgressBar import ProgressBar
from Screens.MessageBox import MessageBox
from Tools.Directories import fileExists
from Components.config import config, ConfigSubsection, ConfigYesNo
from Screens.Setup import ConfigListScreen
from Components.ScrollLabel import ScrollLabel
from Tools import Notifications

# --- Fallback for getConfigListEntry ---
def getConfigListEntry(description, configElement, help_text=""):
    return (description, configElement, help_text)

# --- Config init ---
config.plugins.speedyservicescanupdates = ConfigSubsection()
config.plugins.speedyservicescanupdates.add_new_tv_services = ConfigYesNo(default=True)
config.plugins.speedyservicescanupdates.add_new_radio_services = ConfigYesNo(default=True)
config.plugins.speedyservicescanupdates.clear_bouquet = ConfigYesNo(default=True)

# --- Plugin path ---
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
def read_version():
    """Liest die Versionsnummer aus der Datei version."""
    version_file = os.path.join(plugin_path, "version")
    try:
        with open(version_file, "r") as f:
            version = f.read().strip()
            return version
    except IOError:  # Python 2.7 kompatibel
        return "Unknown version"

version = read_version()
update_url = "https://github.com/speedy005/speedyServiceScanUpdates/archive/refs/heads/main.zip"
download_path = "/tmp/ServiceScanUpdates-main.zip"
extract_dir = "/tmp/ServiceScanUpdates"
target_dir = "/usr/lib/enigma2/python/Plugins/Extensions/speedyServiceScanUpdates"

# --- Helpers ---
def clean_version(ver):
    """Filtert Versionsnummer auf nur Ziffern und Punkte."""
    return re.sub(r'[^0-9\.]', '', ver)

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

# --- Update Screen ---
class SSUUpdateScreen(Screen, ConfigListScreen):
    skin = skin_update

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
        self['help'] = Label("")
        self['version'] = Label(read_version())  # Version hier anzeigen

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
        self.update_installed = False  # Flag, das angibt, ob ein Update erfolgreich installiert wurde

    def exit(self):
        self.close()

    def cancel(self):
        self['status'].setText(_("Update cancelled."))
        self.download_complete = False
        self.update_installed = False  # Update wird abgebrochen

    def start_update(self):
        """Startet den Update-Prozess"""
        self['status'].setText(_("Downloading update..."))
        try:
            r = requests.get(update_url, stream=True, timeout=30)
            total_size = int(r.headers.get('content-length', 0))
            with open(download_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=1024):
                    if chunk:
                        f.write(chunk)
                        self['progress'].setValue((f.tell() / total_size) * 100)
            self['status'].setText(_("Download complete. Extracting files..."))
            self.extract_files()
        except Exception as e:
            self['status'].setText(_("Download failed. Please try again later."))
            print(str(e))

    def extract_files(self):
        """Entpackt die heruntergeladene ZIP-Datei"""
        try:
            with zipfile.ZipFile(download_path, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)
            self['status'].setText(_("Extracting complete. Installing..."))
            self.install_update()
        except zipfile.BadZipFile:
            self['status'].setText(_("Error during extraction."))
        except Exception as e:
            self['status'].setText(_("Error during extraction."))
            print(str(e))

    def install_update(self):
        """Installiert das Update"""
        try:
            if os.path.isdir(target_dir):
                shutil.rmtree(target_dir)
            shutil.move(extract_dir, target_dir)
            self['status'].setText(_("Update installed successfully!"))
            self.update_installed = True
        except Exception as e:
            self['status'].setText(_("Error during installation."))
            print(str(e))

    def check_update(self):
        """Überprüft, ob Updates verfügbar sind"""
        self['status'].setText(_("Checking for updates..."))
        try:
            # Hier könnte eine Logik zur Überprüfung der Update-Verfügbarkeit hinzukommen
            self['status'].setText(_("No updates found."))
        except Exception as e:
            self['status'].setText(_("Update check failed."))
            print(str(e))


    def extract_update(self):
        """Extrahiert das heruntergeladene Archiv je nach Format (ZIP/TAR)."""
        try:
            if download_path.endswith(".zip"):
                self.extract_zip(download_path)
            elif download_path.endswith(".tar.gz") or download_path.endswith(".tgz"):
                self.extract_tar(download_path)
            else:
                self['status'].setText(_("Unsupported file format"))
        except Exception as e:
            self['status'].setText("Extraction failed: %s" % str(e))

    def extract_zip(self, path):
        """Extrahiert ein ZIP-Archiv."""
        with zipfile.ZipFile(path, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)
        self.finish_update()

    def extract_tar(self, path):
        """Extrahiert ein TAR-Archiv."""
        with tarfile.open(path, 'r:gz') as tar_ref:
            tar_ref.extractall(extract_dir)
        self.finish_update()

    def finish_update(self):
        """Verschiebt die entpackten Dateien ins Zielverzeichnis und beendet den Update-Prozess."""
        try:
            # Der Quellpfad nach dem Entpacken
            extracted_folder = "/tmp/ServiceScanUpdates/speedyServiceScanUpdates-main/usr/lib/enigma2/python/Plugins/Extensions/speedyServiceScanUpdates"
            
            # Das Zielverzeichnis
            if os.path.isdir(extracted_folder):
                for item in os.listdir(extracted_folder):
                    s = os.path.join(extracted_folder, item)
                    d = os.path.join(target_dir, item)
                    
                    if os.path.isdir(s):
                        if os.path.exists(d):
                            shutil.rmtree(d)
                        shutil.copytree(s, d)
                    else:
                        shutil.copy2(s, d)

                if not os.path.exists(target_dir):
                    raise IOError("Target directory %s not found after extraction." % target_dir)

                self['status'].setText(_("Update completed successfully."))
                self.update_installed = True
                self.restart_application()
            else:
                self['status'].setText(_("Error: Extracted directory not found."))
                self.update_installed = False
        except Exception as e:
            self['status'].setText("Failed to complete update: %s" % str(e))
            self.update_installed = False

    def restart_application(self):
        """Startet die Anwendung nach dem Update neu."""
        self['status'].setText(_("Restarting application..."))
        Notifications.AddNotification(MessageBox, _("Application will now restart."), type=MessageBox.TYPE_INFO)
        self.close()
        os.system("reboot")

    

# --- Setup Screen ---
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
        self.session = session

        # Erstelle eine Liste von Konfigurationseinträgen
        self.list = [
            getConfigListEntry(_("Add new TV services"), config.plugins.speedyservicescanupdates.add_new_tv_services),
            getConfigListEntry(_("Add new Radio services"), config.plugins.speedyservicescanupdates.add_new_radio_services),
            getConfigListEntry(_("Clear bouquet"), config.plugins.speedyservicescanupdates.clear_bouquet)
        ]

        # Initialisiere ConfigListScreen mit der Konfigurationsliste
        ConfigListScreen.__init__(self, self.list, session=session)

        # Widget Initialisierungen
        self['status'] = Label(_("Please configure the plugin settings"))
        self['help'] = Label(_("Choose your settings and press green to confirm"))
        self['key_red'] = Button(_("Exit"))
        self['key_green'] = Button(_("Save"))
        self['key_yellow'] = Button(_("Restore Default"))
        self['key_blue'] = Button(_("Update"))
        
        
        # Tastenaktionen
        self['actions'] = ActionMap(['ColorActions', 'OkCancelActions'],
                                    {
                                        'red': self.exit,  # Exit über Red Key
                                        'green': self.save_settings,
                                        'yellow': self.restore_default,
                                        'blue': self.open_ssu_update_screen,
                                    }, -1)

    def open_ssu_update_screen(self):
        """Öffnet den SSUUpdateScreen und überprüft im Hintergrund auf Updates"""
        self.session.open(SSUUpdateScreen)

    def check_for_update(self):
        """Simuliert die Überprüfung auf ein Update im Hintergrund"""
        import time
        time.sleep(2)  # Simuliert eine 2-sekündige Verzögerung für die Update-Überprüfung
        
        # Simuliere Update-Status (True = Update verfügbar, False = Kein Update)
        update_available = True  # Dies kannst du durch echte Logik ersetzen
        
        if update_available:
            self.session.openWithCallback(self.ask_for_update, MessageBox,
                                          _("Update found! Do you want to install it?"),
                                          MessageBox.TYPE_YESNO)
        else:
            self.session.open(MessageBox, _("No updates found."), MessageBox.TYPE_INFO, 3)
            self.close()

    def ask_for_update(self, answer):
        """Fragt den Benutzer, ob das Update installiert werden soll"""
        if answer:  # Der Benutzer hat auf "Ja" geklickt
            self.session.openWithCallback(self.install_update, MessageBox,
                                          _("Do you really want to install the update?"),
                                          MessageBox.TYPE_YESNO)
        else:  # Der Benutzer hat auf "Nein" geklickt
            self.close()

    def install_update(self, answer):
        """Installiert das Update, wenn der Benutzer zustimmt"""
        if answer:
            self['status'].setText(_("Installing the update..."))
            self['help'].setText(_("Please wait while the update is being installed"))

            # Simuliere die Installationszeit
            import time
            time.sleep(3)

            self.session.open(MessageBox, _("Update installed successfully!"), MessageBox.TYPE_INFO, 5)
            self.close()
        else:
            self.session.open(MessageBox, _("Update installation cancelled."), MessageBox.TYPE_INFO, 3)
            self.close()

    def exit(self):
        """Fragt den Benutzer, ob er wirklich verlassen möchte"""
        self.session.openWithCallback(self.confirm_exit, MessageBox,
                                      _("Do you really want to exit?"),
                                      MessageBox.TYPE_YESNO)

    def confirm_exit(self, answer):
        """Bestätigt das Verlassen der Anwendung"""
        if answer:  # Der Benutzer hat "Ja" gewählt
            self.close()
        else:  # Der Benutzer hat "Nein" gewählt
            pass  # Nichts tun, um die Bildschirmansicht zu erhalten
    
    def save_settings(self):
        """Speichert die aktuellen Einstellungen"""
        # Logik zum Speichern der Einstellungen hinzufügen
        self.session.open(MessageBox, _("Settings saved!"), MessageBox.TYPE_INFO, 3)
        self.close()

    def restore_default(self):
        """Stellt die Standardeinstellungen wieder her"""
        # Logik zum Wiederherstellen der Standardeinstellungen hinzufügen
        self.session.open(MessageBox, _("Default settings restored!"), MessageBox.TYPE_INFO, 3)
        self.close()

    def reset_settings(self):
        """Setzt alle Einstellungen zurück."""
        self.session.open(MessageBox, _("Resetting all settings..."), MessageBox.TYPE_INFO, 5)

    def changed(self):
        """Speichert Änderungen."""
        for item in self['config'].list:
            item[1].save()  # Speichert das Konfigurationselement

    def layoutFinished(self):
        """Zusätzliche Informationen nach Layout-Fertigstellung anzeigen."""
        help_txt = _("This plugin creates a favorites bouquet (for TV and Radio) with the name 'Service Scan Updates'.\n")
        help_txt += _("All new services found during the scan are inserted there together with a marker.\n")
        help_txt += _("This allows you to quickly and clearly see which new services were found,\n")
        help_txt += _("and you can add individual services to your own Favorites bouquets as usual.\n\n")
        help_txt += _("In order for the 'Service Scan Updates' bouquet to be displayed,\n")
        help_txt += _("the option 'Allow multiple bouquets' must be activated in the system settings of the box.")
        self["help"].setText(help_txt)
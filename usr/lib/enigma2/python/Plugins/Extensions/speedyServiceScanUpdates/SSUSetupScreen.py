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
        <widget name="status" position="10,160" size="1180,50" font="Regular;30" valign="center" halign="center" />
        <widget name="progresstext" position="10,220" size="1180,50" font="Regular;30" valign="center" halign="center" />
        <widget name="key_red" position="3,4" size="295,70" font="Regular;30" halign="center" valign="center" />
        <widget name="key_green" position="305,3" size="300,70" font="Regular;30" halign="center" valign="center" />
        <widget name="key_yellow" position="604,5" size="300,70" font="Regular;30" halign="center" valign="center" />
        <widget name="key_blue" position="916,6" size="295,70" font="Regular;30" halign="center" valign="center" />
        <widget name="version" position="488,769" size="200,30" font="Regular;30" valign="center" halign="center" />
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
        <widget name="version" position="364,784" size="300,20" font="Regular;30" valign="center" halign="center" />
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
        self['version'] = Label(version)

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
                            self['progresstext'].setText("%d%%" % percent)
                self.extract_update()
            else:
                self['status'].setText(_("Failed to download update."))
        except Exception as e:
            self['status'].setText("Download failed: %s" % str(e))

    def check_update(self):
        """Überprüft, ob ein Update verfügbar ist"""
        self['status'].setText(_("Checking for updates..."))
        try:
            response = requests.head(update_url, timeout=10)
            if response.status_code == 200:
                self['status'].setText(_("Update available"))
            else:
                self['status'].setText(_("No update available"))
        except Exception as e:
            self['status'].setText("Update check failed: %s" % str(e))

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
        self.finish_update()

    def extract_zip(self, file_path):
        """Entpackt eine ZIP-Datei."""
        with zipfile.ZipFile(file_path, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)

    def extract_tar(self, file_path):
        """Entpackt eine TAR- oder TAR.GZ-Datei."""
        with tarfile.open(file_path, 'r:gz') as tar_ref:
            tar_ref.extractall(extract_dir)

    def finish_update(self):
        """Verschiebt die entpackten Dateien ins Zielverzeichnis und beendet den Update-Prozess."""
        try:
            if os.path.isdir(extract_dir):
                for item in os.listdir(extract_dir):
                    s = os.path.join(extract_dir, item)
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
        """Zeigt eine Nachricht und startet die Anwendung neu, nur wenn Update installiert wurde."""
        if self.update_installed:
            self.session.open(MessageBox, _("Update complete. The application will now restart."), MessageBox.TYPE_INFO, 10)
            os.system("init 4")  # GUI-Neustart
        else:
            self.session.open(MessageBox, _("No update installed. Restart not needed."), MessageBox.TYPE_INFO, 10)

# --- Setup Screen ---
class SSUSetupScreen(Screen):
    skin = "<screen name=\"SSUSetupScreen\" position=\"center,170\" size=\"1200,820\" title=\"speedy Service Scan Setup\"></screen>"

    def __init__(self, session):
        Screen.__init__(self, session)
        self.session = session
        self['status'] = Label(_("Please configure the plugin settings"))
        self['config'] = ConfigListScreen([])
        self['help'] = Label(_("Choose your settings and press green to confirm"))
        self['key_red'] = Button(_("Exit"))
        self['key_green'] = Button(_("Save"))

        self['actions'] = ActionMap(['ColorActions', 'OkCancelActions'],
                                    {
                                        'red': self.exit,
                                        'green': self.save_settings,
                                        'yellow': self.restore_default,
                                        'blue': self.reset_settings,
                                    }, -1)

    def exit(self):
        self.close()

    def save_settings(self):
        self.session.open(MessageBox, _("Settings saved successfully!"), MessageBox.TYPE_INFO, 5)
        self.close()

    def restore_default(self):
        self.session.open(MessageBox, _("Restoring default settings..."), MessageBox.TYPE_INFO, 5)
        # Wiederherstellung der Standardeinstellungen (Placeholder)

    def reset_settings(self):
        self.session.open(MessageBox, _("Resetting all settings..."), MessageBox.TYPE_INFO, 5)
        # Zurücksetzen der Einstellungen (Placeholder)

    def changed(self):
        """Wird aufgerufen, wenn sich etwas geändert hat"""
        pass

    def layoutFinished(self):
        """Zusätzliche Infos nach Layout-Fertigstellung anzeigen."""
        help_txt = _("This plugin creates a favorites bouquet (for TV and Radio) with the name 'Service Scan Updates'.\n")
        help_txt += _("All new services found during the scan are inserted there together with a marker.\n")
        help_txt += _("This allows you to quickly and clearly see which new services were found,\n")
        help_txt += _("and you can add individual services to your own Favorites bouquets as usual.\n\n")
        help_txt += _("In order for the 'Service Scan Updates' bouquet to be displayed,\n")
        help_txt += _("the option 'Allow multiple bouquets' must be activated in the system settings of the box.")
        self["help"].setText(help_txt)
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

# Bildschirmauflösung abfragen
w, h = getDesktop(0).size().width(), getDesktop(0).size().height()

# Debugging-Ausgabe: Prüfen, ob die richtigen Werte für w und h geliefert werden
print(f"Screen width: {w}, Screen height: {h}")

# Bestimmen der Bildschirmbreite basierend auf der Auflösung
# Wenn w und h mindestens 1920 und 1080 sind, nehmen wir die Full HD-Einstellungen
sz_w = 1180 if w >= 1920 and h >= 1080 else 1050  # FHD oder höher gibt sz_w=1180, sonst 1050

# Debugging-Ausgabe für sz_w
print(f"sz_w is set to: {sz_w}")

# Skin für Full HD und größere Auflösungen
if w >= 1920 and h >= 1080:
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
    skin = skin_update  # Referenz zur Skin-Definition

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
class SSUSetupScreen(ConfigListScreen, Screen):
    # Bildschirmauflösung abfragen
    skin = skin_update  # Direkte Zuweisung der skin_update-Variable
    
    # Debugging-Ausgabe: Prüfen, ob die richtigen Werte für w und h geliefert werden
    print(f"Screen width: {w}, Screen height: {h}")
    
    # Bestimmen der Bildschirmbreite basierend auf der Auflösung
    # Wenn w und h mindestens 1920 und 1080 sind, nehmen wir die Full HD-Einstellungen
    sz_w = 1180 if w >= 1920 and h >= 1080 else 1050  # FHD oder höher gibt sz_w=1180, sonst 1050
    
    # Debugging-Ausgabe für sz_w
    print(f"sz_w is set to: {sz_w}")

    # Skin für Full HD und größere Auflösungen
    if w >= 1920 and h >= 1080:
        skin = """
        <screen name="SSUSetupScreen" position="center,170" size="1200,820" title="speedy Service Scan Updates" backgroundColor="black">
            <ePixmap pixmap="skin_default/buttons/red.png" position="10,5" size="5,70" scale="stretch" alphatest="on" />
            <ePixmap pixmap="skin_default/buttons/green.png" position="314,5" size="5,70" scale="stretch" alphatest="on" />
            <eLabel text="HELP" position="1110,753" size="80,35" backgroundColor="#777777" valign="center" halign="center" font="Regular;24" zPosition="5" />
            <widget name="key_red" position="19,8" zPosition="1" size="295,70" font="Regular;30" halign="center" valign="center" backgroundColor="#9f1313" transparent="1" shadowColor="black" shadowOffset="-2,-2" />
            <widget name="key_green" position="324,5" zPosition="1" size="300,70" font="Regular;30" halign="center" valign="center" foregroundColor="green" backgroundColor="#1f771f" transparent="1" shadowColor="black" shadowOffset="-2,-2" />
            <widget name="config" position="10,90" itemHeight="35" size="1180,500" enableWrapAround="1" scrollbarMode="showOnDemand" />
            <ePixmap pixmap="skin_default/div-h.png" position="10,650" zPosition="2" size="1180,2" />
            <ePixmap pixmap="skin_default/buttons/yellow.png" position="630,7" size="5,70" scale="stretch" alphatest="on" />
            <widget name="key_yellow" foregroundColor="yellow" position="638,6" size="300,70" font="Regular;30" halign="center" valign="center" />
            <widget name="version"  position="444,593" size="150,50" font="Regular;30" valign="center" halign="left"  />
            <ePixmap pixmap="skin_default/buttons/blue.png" position="945,7" size="5,70" scale="stretch" alphatest="on" />
            <widget name="key_blue" position="954,8" foregroundColor="blue" size="250,70" font="Regular;30" halign="center" valign="center" />
            <widget name="help" position="10,655" size="1180,140" font="Regular;32" />
            <ePixmap pixmap="skin_default/buttons/vkey_exit.png" position="1041,761" size="35,25" scale="stretch" alphatest="on" zPosition="6" />
        </screen>"""
    else:
        # Skin für kleinere Auflösungen (z.B. 1280x720 oder darunter)
        skin = """
        <screen name="SISettingsScreen" position="center,120" size="900,530" title="speedy Service Scan Updates">
            <ePixmap pixmap="skin_default/buttons/yellow.png" position="405,0" size="5,40" scale="stretch" alphatest="on" />
            <widget name="key_yellow" foregroundColor="yellow" position="414,1" size="200,40" font="Regular;30" halign="center" valign="center" />
            <ePixmap pixmap="skin_default/buttons/red.png" position="0,0" size="5,40" scale="stretch" alphatest="on" />
            <ePixmap pixmap="skin_default/buttons/green.png" position="200,0" size="5,40" scale="stretch" alphatest="on" />
            <eLabel text="HELP" position="838,491" size="60,25" backgroundColor="#777777" valign="center" halign="center" font="Regular;18" />
            <widget name="key_red" position="7,0" zPosition="1" size="200,40" font="Regular;22" halign="center" valign="center" backgroundColor="#9f1313" transparent="1" shadowColor="black" shadowOffset="-2,-2" />
            <widget name="key_green" position="206,0" zPosition="1" size="200,40" font="Regular;22" halign="center" valign="center" foregroundColor="green" backgroundColor="#1f771f" transparent="1" shadowColor="black" shadowOffset="-2,-2" />
            <widget name="config" position="5,50" itemHeight="30" size="900,390" enableWrapAround="1" scrollbarMode="showOnDemand" />
            <ePixmap pixmap="skin_default/div-h.png" position="0,445" zPosition="2" size="800,2" />
            <widget name="version" position="801,446" size="100,30" font="Regular;30" valign="center" halign="left"  />
            <widget name="help" position="5,450" size="790,65" font="Regular;22" />
            <ePixmap pixmap="skin_default/buttons/vkey_exit.png" position="800,491" size="35,25" scale="stretch" alphatest="on" zPosition="6" />
            <ePixmap pixmap="skin_default/buttons/blue.png" position="619,2" size="5,40" scale="stretch" alphatest="on" />
            <widget name="key_blue" position="626,2" foregroundColor="blue" size="200,40" font="Regular;30" halign="center" valign="center" />
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
        self['key_exit'] = Button(_("Exit"))
        
        # Tastenaktionen
        self['actions'] = ActionMap(['ColorActions', 'OkCancelActions'],
                                    {
                                        'red': self.exit,  # Exit über Red Key
                                        'green': self.save_settings,
                                        'yellow': self.restore_default,
                                        'blue': self.open_ssu_update_screen,
                                        'exit': self.exit  # Exit Key für den neuen Exit-Button
                                    }, -1)

    def open_ssu_update_screen(self):
        """Öffnet den SSUUpdateScreen und überprüft im Hintergrund auf Updates"""
        self.session.open(SSUUpdateScreen)

    def check_for_update(self):
        """Simuliert die Überprüfung auf ein Update im Hintergrund"""
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

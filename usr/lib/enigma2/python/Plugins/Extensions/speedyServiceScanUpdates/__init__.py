# -*- coding: utf-8 -*-
from Components.config import config, ConfigSubsection, ConfigYesNo
from Components.Language import language
from Tools.Directories import resolveFilename, SCOPE_PLUGINS, SCOPE_LANGUAGE
import os
import gettext

PluginLanguageDomain = "speedyServiceScanUpdates"

# Dynamisch den Pfad ermitteln (funktioniert für Extensions und SystemPlugins)
plugin_path = resolveFilename(SCOPE_PLUGINS, "Extensions/" + PluginLanguageDomain + "/locale/")
if not os.path.exists(plugin_path):
    plugin_path = resolveFilename(SCOPE_PLUGINS, "SystemPlugins/" + PluginLanguageDomain + "/locale/")

PluginLanguagePath = plugin_path


def isDreamOS():
    try:
        from enigma import eMediaDatabase
    except ImportError:
        return False
    else:
        return True


def localeInit():
    lang = language.getLanguage()[:2]
    os.environ["LANGUAGE"] = lang
    gettext.bindtextdomain("enigma2", resolveFilename(SCOPE_LANGUAGE))
    gettext.textdomain("enigma2")
    gettext.bindtextdomain(PluginLanguageDomain, PluginLanguagePath)


def _(txt):
    t = gettext.dgettext(PluginLanguageDomain, txt)
    if t == txt:
        t = gettext.gettext(txt)
    return t


# Direkt bei Pluginstart die Übersetzung initialisieren
localeInit()

# Callback nur registrieren, wenn es kein DreamOS ist
if not isDreamOS():
    language.addCallback(localeInit)


#######################################################
# Konfiguration initialisieren
config.plugins.speedyservicescanupdates = ConfigSubsection()
config.plugins.speedyservicescanupdates.add_new_tv_services = ConfigYesNo(default=True)
config.plugins.speedyservicescanupdates.add_new_radio_services = ConfigYesNo(default=True)
config.plugins.speedyservicescanupdates.clear_bouquet = ConfigYesNo(default=False)

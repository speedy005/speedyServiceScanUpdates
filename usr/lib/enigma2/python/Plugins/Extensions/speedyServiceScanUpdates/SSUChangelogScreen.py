from Screens.Screen import Screen
from Components.ScrollLabel import ScrollLabel
from Components.ActionMap import ActionMap
from Components.Label import Label
from Components.ProgressBar import ProgressBar

class SSUChangelogScreen(Screen):
    skin = """
    <screen name="SSUChangelogScreen" position="center,center" size="800,600" title="Changelog">
        <!-- Scrollbarer Text -->
        <widget name="text" position="10,10" size="780,540" font="Regular;20"/>

        <!-- Grafische Scroll-Leiste -->
        <widget name="progressbar" position="10,555" size="780,20" foregroundColor="#00FF00" backgroundColor="#444444"/>

        <!-- Hinweis unten -->
        <widget name="hint" position="10,580" size="780,20" font="Regular;16" halign="center" valign="center"/>
    </screen>
    """

    def __init__(self, session, changelog_text):
        Screen.__init__(self, session)

        # Scrollbarer Text
        self["text"] = ScrollLabel(changelog_text, wrap=True)

        # Grafische Scroll-Leiste
        self["progressbar"] = ProgressBar()
        self["progressbar"].setValue(0)  # Startwert 0%

        # Hinweis unten
        self["hint"] = Label("OK / EXIT zum Schließen")

        # Tastenbelegung
        self["actions"] = ActionMap(
            ["OkCancelActions", "DirectionActions"],
            {
                "ok": self.close,          # OK → schließen
                "cancel": self.close,      # EXIT / Cancel → schließen
                "exit": self.close,        # manche Fernbedienungen senden exit
                "up": self.pageUp,
                "down": self.pageDown,
                "pageUp": self.pageUp,
                "pageDown": self.pageDown
            }, -1
        )

        # Fortschritt bei Scroll ändern
        self["text"].onContentChanged.append(self.updateProgress)

    # Scroll-Funktionen
    def pageUp(self):
        self["text"].pageUp()
        self.updateProgress()

    def pageDown(self):
        self["text"].pageDown()
        self.updateProgress()

    # Fortschrittsanzeige aktualisieren
    def updateProgress(self):
        total_lines = self["text"].getTextHeight()
        current_line = self["text"].getCurrentLine()
        if total_lines > 0:
            percent = int((current_line / total_lines) * 100)
        else:
            percent = 100
        self["progressbar"].setValue(percent)

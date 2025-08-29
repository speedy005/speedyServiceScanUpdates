from Screens.Screen import Screen
from Components.ScrollLabel import ScrollLabel
from Components.ActionMap import ActionMap
from Components.Label import Label
from Components.ProgressBar import ProgressBar

class SSUChangelogScreen(Screen):
    skin = """
    <screen name="SSUChangelogScreen" position="center,center" size="800,600" title="Changelog">
        <!-- Scrollable text -->
        <widget name="text" position="10,10" size="780,540" font="Regular;20"/>

        <!-- Graphical scroll bar -->
        <widget name="progressbar" position="10,555" size="780,20" foregroundColor="#00FF00" backgroundColor="#444444"/>

        <!-- Hint at the bottom -->
        <widget name="hint" position="10,580" size="780,20" font="Regular;16" halign="center" valign="center"/>
    </screen>
    """

    def __init__(self, session, changelog_text):
        Screen.__init__(self, session)

        # Scrollable text
        self["text"] = ScrollLabel(changelog_text, wrap=True)

        # Graphical scroll bar
        self["progressbar"] = ProgressBar()
        self["progressbar"].setValue(0)  # Start value 0%

        # Hint at the bottom
        self["hint"] = Label("OK / EXIT to close")

        # Key mapping
        self["actions"] = ActionMap(
            ["OkCancelActions", "DirectionActions"],
            {
                "ok": self.close,          # OK → close
                "cancel": self.close,      # EXIT / Cancel → close
                "exit": self.close,        # some remotes send exit
                "up": self.pageUp,
                "down": self.pageDown,
                "pageUp": self.pageUp,
                "pageDown": self.pageDown
            }, -1
        )

        # Update progress when content changes
        self["text"].onContentChanged.append(self.updateProgress)

    # Scroll functions
    def pageUp(self):
        self["text"].pageUp()
        self.updateProgress()

    def pageDown(self):
        self["text"].pageDown()
        self.updateProgress()

    # Update progress bar
    def updateProgress(self):
        total_lines = self["text"].getTextHeight()
        current_line = self["text"].getCurrentLine()
        if total_lines > 0:
            percent = int((current_line / total_lines) * 100)
        else:
            percent = 100
        self["progressbar"].setValue(percent)

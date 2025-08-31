# -*- coding: utf-8 -*-
from __future__ import division, print_function, unicode_literals
from Screens.Screen import Screen
from Components.ScrollLabel import ScrollLabel
from Components.ActionMap import ActionMap
from Components.Label import Label
from Components.ProgressBar import ProgressBar
from . import _  # Übersetzungen

class SSUChangelogScreen(Screen):
    skin = """
    <screen name="SSUChangelogScreen" position="center,center" size="800,600" title="Changelog">
        <widget name="text" position="10,10" size="780,540" font="Regular;20"/>
        <widget name="progressbar" position="10,555" size="780,20" foregroundColor="#00FF00" backgroundColor="#444444"/>
        <widget name="hint" position="10,580" size="780,20" font="Regular;16" halign="center" valign="center"/>
    </screen>
    """

    def __init__(self, session, changelog_text):
        Screen.__init__(self, session)

        self["text"] = ScrollLabel(changelog_text, wrap=True)
        self["progressbar"] = ProgressBar()
        self["progressbar"].setValue(0)
        self["hint"] = Label(_("OK / EXIT to close"))

        self["actions"] = ActionMap(
            ["OkCancelActions", "DirectionActions"],
            {
                "ok": self.close,
                "cancel": self.close,
                "exit": self.close,
                "up": self.pageUp,
                "down": self.pageDown,
                "pageUp": self.pageUp,
                "pageDown": self.pageDown
            }, -1
        )

        self["text"].onContentChanged.append(self.updateProgress)

    def pageUp(self):
        self["text"].pageUp()
        self.updateProgress()

    def pageDown(self):
        self["text"].pageDown()
        self.updateProgress()

    def updateProgress(self):
        total_lines = self["text"].getTextHeight()
        current_line = self["text"].getCurrentLine()
        if total_lines > 0:
            percent = int((current_line / float(total_lines)) * 100)
        else:
            percent = 100
        self["progressbar"].setValue(percent)

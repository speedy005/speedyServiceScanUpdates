from Screens.Screen import Screen
from Components.ScrollLabel import ScrollLabel
from Components.ActionMap import ActionMap

class SSUChangelogScreen(Screen):
    skin = """
        <screen name="SSUChangelogScreen" position="center,center" size="800,600" title="Changelog">
            <widget name="text" position="10,10" size="780,580" font="Regular;20"/>
        </screen>
    """

    def __init__(self, session, changelog_text):
        Screen.__init__(self, session)
        self["text"] = ScrollLabel(changelog_text, wrap=True)
        self["actions"] = ActionMap(
            ["OkCancelActions", "DirectionActions"],
            {
                "ok": self.close,
                "cancel": self.close,
                "up": self["text"].pageUp,
                "down": self["text"].pageDown,
                "pageUp": self["text"].pageUp,
                "pageDown": self["text"].pageDown
            }, -1
        )

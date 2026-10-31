"""Transparent Tk overlay with macOS Spaces/full-screen auxiliary behavior."""


def transparent_color():
    return "systemTransparent"


def configure_window(root):
    root.configure(bg=transparent_color())
    root.attributes("-transparent", True)


def mapped(root):
    from AppKit import NSApplication, NSWindowCollectionBehaviorCanJoinAllSpaces, NSWindowCollectionBehaviorFullScreenAuxiliary
    for window in NSApplication.sharedApplication().windows():
        if window.title() == root.title():
            window.setCollectionBehavior_(window.collectionBehavior()
                | NSWindowCollectionBehaviorCanJoinAllSpaces | NSWindowCollectionBehaviorFullScreenAuxiliary)
            window.setOpaque_(False)
            window.setHasShadow_(False)

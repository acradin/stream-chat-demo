"""Transparent Tk overlay with macOS Spaces/full-screen auxiliary behavior."""


def transparent_color():
    # Tk's transparent Canvas backing on macOS drops canvas content while
    # embedded native controls remain visible. Use an opaque backing surface;
    # the native content view supplies the rounded outer silhouette instead.
    return "#151719"


def configure_window(root):
    root.configure(bg=transparent_color())
    root.attributes("-transparent", False)


def mapped(root):
    from AppKit import NSApplication, NSColor, NSWindowCollectionBehaviorCanJoinAllSpaces, NSWindowCollectionBehaviorFullScreenAuxiliary
    for window in NSApplication.sharedApplication().windows():
        if window.title() == root.title():
            window.setCollectionBehavior_(window.collectionBehavior()
                | NSWindowCollectionBehaviorCanJoinAllSpaces | NSWindowCollectionBehaviorFullScreenAuxiliary)
            window.setOpaque_(False)
            # Clipping only contentView leaves NSWindow's default white
            # backing visible in the four cut-out corners.
            window.setBackgroundColor_(NSColor.clearColor())
            window.setHasShadow_(False)
            view = window.contentView()
            view.setWantsLayer_(True)
            layer = view.layer()
            scale = window.backingScaleFactor()
            layer.setBackgroundColor_(NSColor.clearColor().CGColor())
            layer.setContentsScale_(scale)
            layer.setRasterizationScale_(scale)
            layer.setShouldRasterize_(False)
            view.layer().setCornerRadius_(26)
            view.layer().setMasksToBounds_(True)

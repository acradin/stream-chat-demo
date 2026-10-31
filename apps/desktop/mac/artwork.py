"""Retina artwork drawn by AppKit, avoiding Tk 8.6's 1x PhotoImage buffer."""
from AppKit import NSApplication, NSImage, NSImageView, NSImageScaleAxesIndependently


class TikiArtworkView(NSImageView):
    def hitTest_(self, point):
        # The underlying Tk Canvas retains mouse/keyboard handling.
        return None


def mount(canvas, path, x, y, width, height, tag=None):
    image = NSImage.alloc().initWithContentsOfFile_(str(path))
    if image is None:
        raise ValueError(f"Cannot load artwork: {path}")
    view = TikiArtworkView.alloc().initWithFrame_(((0,0),(width,height)))
    view.setImage_(image)
    view.setImageScaling_(NSImageScaleAxesIndependently)
    view.setEditable_(False)
    top = canvas.winfo_toplevel()

    def refresh(event=None):
        if not canvas.winfo_exists() or not canvas.winfo_ismapped() or (tag and canvas.itemcget(tag,"state") == "hidden"):
            view.setHidden_(True)
            return
        window = next((w for w in NSApplication.sharedApplication().windows() if w.title() == top.title()), None)
        if window is None:
            return
        content = window.contentView()
        if view.superview() != content:
            view.removeFromSuperview()
            content.addSubview_(view)
        left = canvas.winfo_rootx()-top.winfo_rootx()+x
        bottom = content.bounds().size.height-(canvas.winfo_rooty()-top.winfo_rooty()+y+height)
        view.setFrame_(((left,bottom),(width,height)))
        view.setHidden_(False)

    def hide(event=None):
        view.setHidden_(True)

    def destroy(event):
        if event.widget is canvas:
            view.removeFromSuperview()

    canvas.bind("<Map>", lambda _: canvas.after_idle(refresh), add="+")
    canvas.bind("<Configure>", refresh, add="+")
    canvas.bind("<Unmap>", hide, add="+")
    canvas.bind("<Destroy>", destroy, add="+")
    canvas.after_idle(refresh)
    # Keep native objects alive for exactly the Canvas lifetime.
    if not hasattr(canvas, "_native_artwork"):
        canvas._native_artwork = []
    canvas._native_artwork.append((view,image))
    return refresh

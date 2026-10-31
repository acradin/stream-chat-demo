"""Figma component surfaces with native editable controls and pixel typography."""
import tkinter as tk
from PIL import Image, ImageDraw, ImageTk

from apps.desktop.panel import BG, INK, MINT, panel_color


def surface(parent, x, y, width, height, *, opacity=.1, gradient=False, key=False):
    """Preserve the 0.5 px inside gradient stroke at 4x sampling."""
    scale = 4
    size = width * scale, height * scale
    if hasattr(parent, "surface"):
        backdrop = parent.surface.crop((x, y, x+width, y+height)).convert("RGB")
    else:
        backdrop = Image.new("RGB", (width, height), BG)
    backdrop = backdrop.resize(size)
    fill = Image.new("RGBA", size)
    stroke = Image.new("RGBA", size)
    fd, sd = ImageDraw.Draw(fill), ImageDraw.Draw(stroke)
    for px in range(size[0]):
        t = px / max(1, size[0]-1)
        color = tuple(round(a+(b-a)*t) for a,b in zip((3,255,213), (45,255,143))) if gradient else (255,255,255)
        fd.line((px,0,px,size[1]), fill=(*color, round((.8 if gradient else opacity)*255)))
        start = 255 if key or gradient else 186
        value, alpha = round(start+(237-start)*t), round(255*(1-.64*t))
        sd.line((px,0,px,size[1]), fill=(value,value,value,alpha))
    mask, edge = Image.new("L",size), Image.new("L",size)
    ImageDraw.Draw(mask).rounded_rectangle((0,0,size[0]-1,size[1]-1), radius=32, fill=255)
    ImageDraw.Draw(edge).rounded_rectangle((0,0,size[0]-1,size[1]-1), radius=32, outline=255, width=2)
    background = backdrop.convert("RGBA")
    painted = Image.alpha_composite(background, fill)
    background.paste(painted, mask=mask)
    painted = Image.alpha_composite(background, stroke)
    background.paste(painted, mask=edge)
    return background.resize((width,height), Image.Resampling.LANCZOS)


class DesignButton(tk.Canvas):
    def __init__(self, parent, view, text, command, x, y, width=78, height=31,
                 *, component="Shortcut/ChangeButton", gradient=False, opacity=.1, arrow=False):
        super().__init__(parent, width=width, height=height, highlightthickness=0,
                         bd=0, takefocus=1, cursor="hand2", bg=BG)
        self.design_component = component
        self.command, self.disabled = command, False
        self.photo = ImageTk.PhotoImage(surface(parent,x,y,width,height,opacity=opacity,gradient=gradient), master=self)
        self.create_image(0,0,anchor="nw",image=self.photo)
        self.label = self.create_text(width/2-(8 if arrow else 0),height/2,text=text,
                                      font=(view.family,-14),fill=INK)
        if arrow:
            self.create_image(width/2+33,height/2,image=view.photos["arrow"])
        self.focus_outline = self.create_rectangle(2,2,width-3,height-3,outline=MINT,state="hidden")
        self.bind("<Button-1>", self.invoke)
        self.bind("<Return>", self.invoke)
        self.bind("<space>", self.invoke)
        self.bind("<FocusIn>",lambda _: self.itemconfigure(self.focus_outline,state="normal"))
        self.bind("<FocusOut>",lambda _: self.itemconfigure(self.focus_outline,state="hidden"))
        self.place(x=x,y=y,width=width,height=height)

    def invoke(self, event=None):
        if not self.disabled:
            self.command()
        return "break"

    def configure(self, cnf=None, **kwargs):
        text = kwargs.pop("text",None)
        if text is not None:
            self.itemconfigure(self.label,text=text)
        state = kwargs.pop("state",None)
        if state is not None:
            self.disabled = state == "disabled"
            self.itemconfigure(self.label,fill="#888888" if self.disabled else INK)
        if cnf or kwargs:
            super().configure(cnf,**kwargs)


def field(parent, view, x, y, width, height, *, variable=None, multiline=False,
          placeholder="", opacity=.1, component="Settings/Link"):
    canvas = tk.Canvas(parent, width=width,height=height,bd=0,highlightthickness=0,bg=BG)
    canvas.design_component = component
    image = surface(parent,x,y,width,height,opacity=opacity,key=opacity==.3)
    canvas.photo = ImageTk.PhotoImage(image,master=canvas)
    canvas.create_image(0,0,anchor="nw",image=canvas.photo)
    bg = "#%02x%02x%02x" % image.getpixel((width//2,height//2))[:3]
    common = dict(bg=bg,fg=INK,insertbackground=INK,relief="flat",bd=0,
                  highlightthickness=0,font=(view.family,-12))
    if multiline:
        widget = tk.Text(canvas,wrap="word",undo=True,padx=0,pady=0,**common)
        widget.place(x=17,y=14,width=width-49,height=height-36)
    else:
        widget = tk.Entry(canvas,textvariable=variable,**common)
        widget.place(x=12,y=7,width=width-24,height=17)
        if placeholder:
            hint = tk.Label(canvas,text=placeholder,bg=bg,fg="#eaeaea",font=(view.family,-12),bd=0,padx=0)
            def refresh(*_):
                if variable.get() or widget.focus_get() is widget:
                    hint.place_forget()
                else:
                    hint.place(x=12,y=6)
            hint.bind("<Button-1>",lambda _: widget.focus_set())
            variable.trace_add("write",refresh)
            widget.bind("<FocusIn>",refresh,add="+")
            widget.bind("<FocusOut>",refresh,add="+")
            refresh()
    canvas.place(x=x,y=y,width=width,height=height)
    widget.design_surface = canvas
    return widget

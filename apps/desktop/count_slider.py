"""Interactive Main/ChatbotCountSlider using the original Figma vector paths."""
import tkinter as tk
from apps.desktop.panel import BG
from apps.desktop.vector import draw, visible

STOPS = (9,45,89,132,169)


class CountSlider(tk.Canvas):
    def __init__(self,parent,on_change):
        super().__init__(parent,width=178,height=32,bg=BG,highlightthickness=0,
                         bd=0,takefocus=1,cursor="hand2")
        self.value = 1
        self.variants = [draw(self,f"count-slider-{i}",0,0) for i in range(1,6)]
        # Invisible interaction geometry is also available to layout checks.
        self.knob = self.create_oval(3,0,15,12,state="hidden")
        self.active = self.create_line(0,6,9,6,state="hidden")
        def choose(event):
            scale = getattr(self,"_tiki_display_scale",1)
            value = min(range(5),key=lambda i:abs(STOPS[i]-event.x/scale))+1
            self.focus_set()
            on_change(value)
        self.bind("<Button-1>",choose)
        self.bind("<B1-Motion>",choose)
        self.bind("<Left>",lambda _:on_change(max(1,self.value-1)))
        self.bind("<Right>",lambda _:on_change(min(5,self.value+1)))
        self.set_value(1)

    def set_value(self,value):
        self.value = value
        scale = getattr(self,"_tiki_display_scale",1)
        x = STOPS[value-1]
        self.coords(self.knob,*(v*scale for v in (x-6,0,x+6,12)))
        self.coords(self.active,*(v*scale for v in (0,6,x,6)))
        for i,tag in enumerate(self.variants,1):
            visible(self,tag,i==value)

"""The five Figma start screens, sharing the live settings and persona controls."""
import tkinter as tk
from tkinter import messagebox

from apps.desktop.design_widgets import DesignButton, field
from backend.personas import PERSONAS
from backend.chzzk_target import parse_channel_id


class Onboarding:
    def __init__(self, view):
        from apps.desktop.figma_ui import PERSONA_ASSETS
        self.view, self.app = view, view.app
        self.personas = tuple(PERSONA_ASSETS)
        self.selected = list(dict.fromkeys(self.app.settings["personas"][:self.app.settings["count"]]))
        self.editing = False
        self.start_page = view._page("start",277,347,variant="welcome",header=False)
        self.description_page = view._page("start1",339,430,variant="setup",header=False)
        self.persona_page = view._page("start2",339,775,variant="setup",header=False)
        self.link_page = view._page("start3",339,286,variant="setup",header=False)
        self.end_page = view._page("start_end",277,347,variant="welcome",header=False)
        self._welcome(self.start_page,False)
        self._welcome(self.end_page,True)
        self._heading(self.description_page,51,1,"어떤 방송을 하시나요?",
                      "AI가 더 자연스러운 채팅을 만들 수 있게\n당신의 방송을 소개해주세요.")
        self.description = field(self.description_page,view,26,175,286,145,
                                 multiline=True,component="Start/Description")
        self.description.insert("1.0",self.app.settings["context"])
        self.description_counter = self.description.design_surface.create_text(
            269,132,anchor="e",fill="white",font=(view.family,-8))
        self.description.bind("<<Modified>>",self._description_changed)
        self._description_changed()
        self._navigation(self.description_page,38,348,lambda:view.show("start"),self.to_personas)
        self.persona_caption = self._heading(self.persona_page,81,2,"채팅 페르소나 선택",
                      "어떤 AI에게 댓글을 받고 싶으세요?\n여러 개를 선택할 수도 있어요.")
        self.cards = []
        for index,key in enumerate(self.personas):
            card = DesignButton(self.persona_page,view,"",lambda p=key:self.toggle(p),31,205+73*index,278,65)
            card.design_component = None
            card.design_node = "Shortcut/ChangeButton"
            card.create_image(12,8,anchor="nw",image=view.photos[PERSONA_ASSETS[key]])
            card.create_text(73,8,anchor="nw",text=PERSONAS[key]["name"],fill="white",font=(view.family,-14))
            card.create_text(73,28,anchor="nw",text=PERSONAS[key]["description"],fill="#eaeaea",font=(view.family,-11),width=193)
            self.cards.append(card)
        self.back, self.next = self._navigation(self.persona_page,38,663,self.persona_back,self.to_link)
        self._heading(self.link_page,43,3,"이제 마지막 단계에요","방송 링크를 첨부해주세요.")
        self.link = field(self.link_page,view,34,153,272,31,variable=self.app.channel_var,
                          placeholder="https://chzzk.naver.com/")
        self._navigation(self.link_page,34,212,lambda:view.show("start2"),self.finish)

    def _welcome(self,page,done):
        view = self.view
        # The exported 99x118 asset includes the shadow around the 69x85 logo.
        page.create_image(89,34 if done else 45,anchor="nw",image=view.photos["welcome-logo"])
        view.text(page,138.5,172 if done else 183,"설정 완료!" if done else "어서오세요!",24,
                  anchor="center",weight=True)
        copy = ("이제 방송에서 언제든\ntiki를 사용할 수 있어요.\n설정에서 언제든 변경할 수 있어요." if done else
                "tiki가 당신의 방송에\n딱 맞는 채팅을 입력해드릴게요.")
        view.text(page,138.5,216 if done else 219,copy,14,anchor="center")
        DesignButton(page,view,"시작하기",lambda:view.show("main" if done else "start1"),
                     39 if done else 40,268 if done else 263,199 if done else 198,
                     component="Start/Start",opacity=.2,arrow=True)

    def _heading(self,page,y,step,title,copy):
        view = self.view
        page.create_line(128.5,y+6,210.5,y+6,fill="#d9d9d9",width=2)
        if step > 1:
            page.create_line(128.5,y+6,128.5+(step-1)*40,y+6,fill="#2dff8f",width=2)
        for i in range(3):
            x = 123.5+i*40
            page.create_oval(x,y,x+12,y+12,fill="#2dff8f" if i<step else "#d9d9d9",outline="")
        view.text(page,169.5,y+48,title,16,anchor="center",weight=True)
        return view.text(page,169.5,y+68,copy,12,anchor="n",fill="#eaeaea")

    def _navigation(self,page,x,y,previous,next_action):
        return (DesignButton(page,self.view,"이전",previous,x,y),
                DesignButton(page,self.view,"다음",next_action,x+90,y,174,
                             component="Start/Next",gradient=True,arrow=True))

    def _description_changed(self,event=None):
        if self.description.edit_modified():
            length = len(self.description.get("1.0","end-1c"))
            self.description.design_surface.itemconfigure(self.description_counter,text=f"{length:,} / 1,000자")
            self.description.edit_modified(False)

    def start(self):
        self.editing = False
        self.description.delete("1.0","end")
        self.description.insert("1.0",self.app.context.get("1.0","end-1c"))
        self.view.show("start")

    def select_personas(self):
        self.editing = True
        by_name = {value["name"]:key for key,value in PERSONAS.items()}
        self.selected = list(dict.fromkeys(by_name[v.get()] for v in self.app.persona_vars[:self.app.settings["count"]]))
        self._selection_feedback()
        self.view.show("start2")

    def _selection_feedback(self):
        names = [PERSONAS[key]["name"] for key in self.selected]
        caption = "선택: " + ", ".join(names[:3]) + ("\n" + ", ".join(names[3:]) if len(names)>3 else "\n최대 5명 · 다시 누르면 선택 해제")
        self.persona_page.itemconfigure(self.persona_caption,text=caption)

    def toggle(self,key):
        if key in self.selected:
            self.selected.remove(key)
        elif len(self.selected) < 5:
            self.selected.append(key)
        else:
            messagebox.showinfo("페르소나 선택","채팅 멤버는 최대 5명입니다. 기존 선택을 해제한 뒤 골라주세요.",parent=self.app.root)
        self._selection_feedback()

    def to_personas(self):
        if len(self.description.get("1.0","end-1c")) > 1000:
            messagebox.showerror("방송 설명","방송 설명은 1,000자까지 입력할 수 있습니다.",parent=self.app.root)
            return
        self.view.show("start2")

    def persona_back(self):
        self.view.show("settings" if self.editing else "start1")

    def apply_personas(self):
        if not self.selected:
            messagebox.showinfo("페르소나 선택","한 명 이상의 페르소나를 선택해주세요.",parent=self.app.root)
            return False
        for i,variable in enumerate(self.app.persona_vars):
            variable.set(PERSONAS[self.selected[i % len(self.selected)]]["name"])
        self.view._count_changed(len(self.selected))
        return True

    def to_link(self):
        if not self.apply_personas():
            return
        if self.editing:
            if self.app.save_settings():
                self.view.show("settings")
        else:
            self.view.show("start3")

    def finish(self):
        link = self.app.channel_var.get().strip()
        try:
            if link:
                parse_channel_id(link)
        except ValueError as exc:
            messagebox.showerror("방송 링크",str(exc),parent=self.app.root)
            return
        # An empty link is valid for local demos; this does not authorize CHZZK.
        text = self.description.get("1.0","end-1c")
        if len(text) > 1000:
            self.view.show("start1")
            return
        self.app.context.delete("1.0","end")
        self.app.context.insert("1.0",text)
        previous = self.app.settings["onboarding_complete"]
        self.app.settings["onboarding_complete"] = True
        if self.app.save_settings():
            self.view.show("start_end")
        else:
            self.app.settings["onboarding_complete"] = previous
            messagebox.showerror("설정 저장",self.app.status.get(),parent=self.app.root)

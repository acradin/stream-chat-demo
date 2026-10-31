"""First-run service connection. No AI-provider credentials are accepted."""

import os
from pathlib import Path
import tempfile
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

from apps.desktop.service_client import ServiceClient
from backend.env import DESKTOP_KEYS, read_env_file


def save_connection(path: Path, base_url: str, token: str) -> dict:
    base_url, token = base_url.strip(), token.strip()
    if not base_url or not token:
        raise ValueError("서비스 주소와 연결 코드를 모두 입력해주세요.")
    # Reuse the same HTTPS/loopback and credential rules as actual requests.
    client = ServiceClient(base_url=base_url, token=token)
    values = {"CHAT_SERVICE_URL": client.base_url, "CHAT_SERVICE_TOKEN": token}
    lines = []
    for key, value in values.items():
        quote = "'" if "'" not in value else '"'
        if quote in value or any(char in value for char in "\r\n\0"):
            raise ValueError("연결 설정에 지원하지 않는 문자가 있습니다.")
        lines.append(f"{key}={quote}{value}{quote}\n")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=".connection-", delete=False) as stream:
            temporary = Path(stream.name)
            stream.writelines(lines)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return {"base_url": client.base_url, "token": token}


class ConnectionDialog(simpledialog.Dialog):
    def __init__(self, parent, path, base_url="http://127.0.0.1:8766"):
        self.path, self.base_url = path, base_url
        super().__init__(parent, title="서비스 연결")

    def body(self, frame):
        ttk.Label(frame, text="서비스 주소와 발급받은 연결 코드를 입력해주세요.", wraplength=380).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 12))
        self.url = tk.StringVar(value=self.base_url)
        self.token = tk.StringVar()
        ttk.Label(frame, text="서비스 주소").grid(row=1, column=0, sticky="w", padx=(0, 8))
        entry = ttk.Entry(frame, textvariable=self.url, width=42)
        entry.grid(row=1, column=1, pady=4)
        ttk.Label(frame, text="연결 코드").grid(row=2, column=0, sticky="w")
        ttk.Entry(frame, textvariable=self.token, show="•", width=42).grid(row=2, column=1, pady=4)
        ttk.Button(frame, text="연결 설정 파일 불러오기", command=self.import_file).grid(
            row=3, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        return entry

    def buttonbox(self):
        frame = ttk.Frame(self)
        ttk.Button(frame, text="연결", command=self.ok).pack(side="left", padx=5, pady=8)
        ttk.Button(frame, text="취소", command=self.cancel).pack(side="left", padx=5, pady=8)
        self.bind("<Return>", self.ok)
        self.bind("<Escape>", self.cancel)
        frame.pack()

    def import_file(self):
        filename = filedialog.askopenfilename(parent=self, title="서비스 연결 설정 선택",
                                              filetypes=[("연결 설정", "*.env .env"), ("모든 파일", "*.*")])
        if not filename:
            return
        try:
            values = read_env_file(Path(filename), DESKTOP_KEYS)
            if not all(values.get(key) for key in DESKTOP_KEYS):
                raise ValueError("서비스 주소와 연결 코드가 있는 설정 파일을 선택해주세요.")
            self.url.set(values["CHAT_SERVICE_URL"])
            self.token.set(values["CHAT_SERVICE_TOKEN"])
        except (ValueError, OSError) as exc:
            messagebox.showerror("연결 설정을 읽을 수 없습니다", str(exc), parent=self)

    def validate(self):
        try:
            self.result = save_connection(self.path, self.url.get(), self.token.get())
            return True
        except (ValueError, OSError):
            messagebox.showerror("연결 설정을 저장할 수 없습니다",
                                 "서비스 주소, 연결 코드와 저장 폴더 권한을 확인해주세요.", parent=self)
            return False

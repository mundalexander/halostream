#!/usr/bin/env python3
"""
HaloStream Chat GUI
~~~~~~~~~~~~~~~~~~~
Tkinter GUI für OpenAI-kompatible APIs (Halogen, GLM-5.3, Ollama …).
Streaming, Multi-Threading, Dark Theme, Server-Management.

Start: python3 halostream_gui.py
"""

from __future__ import annotations
import json, queue, subprocess, sys, threading, time
from dataclasses import dataclass
from datetime import datetime
from tkinter import (
    END, LEFT, RIGHT, StringVar, Text, Tk, WORD,
    Button, Entry, Frame, Label, Scrollbar, ttk,
)
from tkinter import messagebox

try:
    import requests
except ImportError:
    messagebox.showerror("Import error", "pip install requests")
    sys.exit(1)

# ── Defaults ───────────────────────────────────────────────────────────────
SYS_PROMPT  = "Du bist ein hilfreicher, präziser Assistent."
TEMPERATURE = 0.7
MAX_TOKENS  = 2048

# ── Farben (Dark Theme) ──────────────────────────────────────────────────
BG       = "#1e1e2e"
SURFACE  = "#252536"
SURFACE2 = "#2d2d44"
ACCENT   = "#7c6aef"
ACCENT_H = "#9580ff"
FG       = "#cdd6f4"
FG_DIM   = "#6c7086"
USER_BG  = "#3b3d5c"
BOT_BG   = "#2a2a40"
LOG_BG   = "#181825"
OK_C     = "#a6e3a1"
ERR_C    = "#f38ba8"
WARN_C   = "#fab387"
GLM_C    = "#89dceb"


# ── Modell-Presets ────────────────────────────────────────────────────────
@dataclass
class Preset:
    label:       str
    endpoint:    str   # base URL without /v1
    model:       str
    color:       str
    serve_cmd:   str | None = None   # shell command to start server
    serve_port:  int | None = None

    def api_url(self) -> str:
        return f"{self.endpoint}/v1"


PRESETS: list[Preset] = [
    Preset(
        label      = "Halogen (Qwen3.8)",
        endpoint   = "http://127.0.0.1:8731",
        model      = "halogen-qwen3.8-flash-next",
        color      = ACCENT,
        serve_cmd  = None,
        serve_port = 8731,
    ),
    Preset(
        label      = "GLM-5.3 (Coli)",
        endpoint   = "http://127.0.0.1:18790",
        model      = "glm-5.3-flash-colibri",
        color      = GLM_C,
        serve_cmd  = None,   # filled in dynamically
        serve_port = 18790,
    ),
]

# GLM-5.3 serve command — built at runtime
GLM_SERVE_CMD = (
    "/home/sascha/.venvs/colibri/bin/coli serve "
    "--model /home/sascha/models/colibri_store/glm53_i4 "
    "--port 18790 "
    "--ngen 1 "
    "--policy balanced "
    "--ram 0 "
    "--auto-tier "
    "2>&1"
)
PRESETS[1] = Preset(
    label      = "GLM-5.3 (Coli)",
    endpoint   = "http://127.0.0.1:18790",
    model      = "glm-5.3-flash-colibri",
    color      = GLM_C,
    serve_cmd  = GLM_SERVE_CMD,
    serve_port = 18790,
)


# ── API-Client ───────────────────────────────────────────────────────────
class APIClient:
    def __init__(self, url: str, model: str, temperature: float, max_tokens: int):
        self.url    = url.rstrip("/")
        self.model  = model
        self.temp   = temperature
        self.maxtok = max_tokens
        self._abort = False

    def abort(self):
        self._abort = True

    @staticmethod
    def health(url: str, q: queue.Queue):
        t0 = time.perf_counter()
        try:
            r = requests.get(f"{url.rstrip('/')}/health", timeout=5)
            q.put(("ok" if r.status_code == 200 else "err",
                   (time.perf_counter() - t0) * 1000))
        except Exception as e:
            q.put(("err", (time.perf_counter() - t0) * 1000, str(e)))

    def stream(self, messages: list, tok_q: queue.Queue, done_q: queue.Queue):
        self._abort = False
        t0 = time.perf_counter()
        payload = {
            "model":       self.model,
            "messages":    messages,
            "temperature": self.temp,
            "max_tokens":  self.maxtok,
            "stream":      True,
        }
        pt = ct = 0
        try:
            with requests.post(
                f"{self.url}/chat/completions",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=(10, 300),
                stream=True,
            ) as resp:
                if resp.status_code != 200:
                    done_q.put({"type": "error",
                                "msg":  f"HTTP {resp.status_code}"})
                    return
                for raw in resp.iter_lines(decode_unicode=True):
                    if self._abort:
                        done_q.put({"type": "abort",
                                    "ms":   (time.perf_counter() - t0) * 1000})
                        return
                    if not raw or not raw.startswith("data: "):
                        continue
                    d = raw.removeprefix("data: ").strip()
                    if d == "[DONE]":
                        break
                    try:
                        obj = json.loads(d)
                    except json.JSONDecodeError:
                        continue
                    if "usage" in obj:
                        u = obj["usage"]
                        pt = u.get("prompt_tokens", 0)
                        ct = u.get("completion_tokens", 0)
                    for ch in obj.get("choices", []):
                        dx = ch.get("delta", {})
                        txt = (dx.get("content") or
                               dx.get("reasoning_content") or "")
                        if txt:
                            ct += 1
                            tok_q.put(txt)
            ms = (time.perf_counter() - t0) * 1000
            done_q.put({"type": "done", "ms": ms, "pt": pt, "ct": ct})
        except Exception as e:
            done_q.put({"type": "error", "msg": str(e)})


# ── Server manager ────────────────────────────────────────────────────────
class ServerManager:
    """Start/stop/check a local server process."""

    def __init__(self, preset: Preset, log_fn):
        self.preset    = preset
        self._log      = log_fn
        self._proc:    subprocess.Popen | None = None
        self._stop_evt = threading.Event()

    @property
    def running(self) -> bool:
        if self._proc is None:
            return False
        return self._proc.poll() is None

    def start(self) -> bool:
        if self.running:
            self._log(f"[{tm()}] Server {self.preset.label} läuft bereits")
            return True
        if not self.preset.serve_cmd:
            self._log(f"[{tm()}] Kein serve_cmd für {self.preset.label}")
            return False
        self._log(f"[{tm()}] Starte {self.preset.label} auf Port "
                  f"{self.preset.serve_port} …")
        try:
            self._proc = subprocess.Popen(
                self.preset.serve_cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                preexec_fn=lambda: None,
            )
            threading.Thread(target=self._waiter, daemon=True).start()
            return True
        except Exception as e:
            self._log(f"[{tm()}] Start-Fehler: {e}")
            return False

    def stop(self):
        if not self.running:
            return
        self._log(f"[{tm()}] Stoppe {self.preset.label} …")
        self._proc.terminate()
        try:
            self._proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self._proc.kill()
            self._proc.wait()
        self._proc = None

    def _waiter(self):
        """Log server output until stopped."""
        while self.running and not self._stop_evt.wait(0.5):
            pass


# ── GUI ───────────────────────────────────────────────────────────────────
class GUI:
    def __init__(self, root: Tk):
        self.root   = root
        self.client: APIClient | None = None
        self.gen    = False

        # Conversation history (survives clears)
        self.history: list = []

        # Queue references
        self.tok_q:  queue.Queue | None = None
        self.done_q: queue.Queue | None = None
        self.hq      = queue.Queue()

        # Line counter for log
        self._lcnt      = 0

        # Tkinter mark for bot reply start
        self._bot_mark: str | None = None

        # Active preset index
        self._active_preset = 0

        # Server manager for GLM
        self._glm_server: ServerManager | None = None

        # ── Window ────────────────────────────────────────────────────────
        self.root.configure(bg=BG)
        self.root.geometry("960x720")
        self.root.title("HaloStream Chat GUI")
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        self._build()
        self._update_btns()
        self._apply_preset(0)
        self._health()

    # ── Preset switching ─────────────────────────────────────────────────
    def _apply_preset(self, idx: int):
        p = PRESETS[idx]
        self._active_preset = idx
        self.url_var.set(p.api_url())
        self.model_var.set(p.model)
        # Colour the preset buttons
        for i, btn in enumerate(self._preset_btns):
            colour = PRESETS[i].color if i == idx else SURFACE2
            fg     = "white"        if i == idx else FG_DIM
            btn.configure(bg=colour, fg=fg, activebackground=colour,
                          activeforeground=fg)
        self._health()

    # ── UI construction ────────────────────────────────────────────────────
    def _build(self):

        # ── Top bar ────────────────────────────────────────────────────────
        top = Frame(self.root, bg=SURFACE, pady=6, padx=8)
        top.pack(fill="x")
        top.columnconfigure(1, weight=1)
        top.columnconfigure(3, weight=1)

        # Preset buttons row
        preset_frame = Frame(top, bg=SURFACE)
        preset_frame.grid(row=0, column=0, columnspan=6, sticky="w", pady=(0, 6))
        self._preset_btns: list[Button] = []
        for i, p in enumerate(PRESETS):
            def make_loader(j):
                return lambda *_: self._apply_preset(j)
            btn = Button(
                preset_frame, text=p.label,
                command=make_loader(i),
                bg=SURFACE2, fg=FG_DIM, relief="flat",
                font=("Helvetica Neue", 9, "bold"),
                padx=10, pady=3,
            )
            btn.pack(side=LEFT, padx=(0, 6))
            self._preset_btns.append(btn)

        # GLM server start/stop button
        self._glm_btn = Button(
            preset_frame, text="▶ Server starten",
            command=self._toggle_glm_server,
            bg=SURFACE2, fg=WARN_C, relief="flat",
            font=("Helvetica Neue", 9),
            padx=8, pady=3,
        )
        self._glm_btn.pack(side=LEFT, padx=(8, 0))

        # Endpoint row
        Label(top, text="Endpoint:", bg=SURFACE, fg=FG).grid(
            row=1, column=0, sticky="w", padx=(0, 6))
        self.url_var = StringVar(value=PRESETS[0].api_url())
        eu = Entry(top, textvariable=self.url_var, bg=SURFACE2, fg=FG,
                   insertbackground=FG, relief="flat")
        eu.grid(row=1, column=1, sticky="we", padx=(0, 8))
        eu.bind("<KeyRelease>", lambda *_: self._health_hint())

        Label(top, text="Model:", bg=SURFACE, fg=FG).grid(
            row=1, column=2, sticky="w", padx=(0, 6))
        self.model_var = StringVar(value=PRESETS[0].model)
        Entry(top, textvariable=self.model_var, bg=SURFACE2, fg=FG,
              insertbackground=FG, relief="flat").grid(
                  row=1, column=3, sticky="we", padx=(0, 8))

        self.st_label = Label(
            top, text="⏳", bg=SURFACE, fg=WARN_C,
            font=("Helvetica Neue", 13), width=3, cursor="hand1")
        self.st_label.grid(row=1, column=4)
        self.st_label.bind("<Button-1>", lambda *_: self._health())
        Button(top, text="↻", command=self._health,
               bg=SURFACE2, fg=FG, relief="flat", width=3,
               activebackground=ACCENT, activeforeground="white",
               font=("Helvetica Neue", 13)).grid(row=1, column=5, padx=(4, 0))

        # ── Main: chat (col 0) + sidebar (col 1, grid) ─────────────────────
        main = Frame(self.root, bg=BG)
        main.pack(fill="both", expand=True, padx=8, pady=(4, 0))
        main.columnconfigure(0, weight=1)
        main.rowconfigure(0, weight=1)

        # Chat history — column 0
        cf = Frame(main, bg=BG)
        cf.grid(row=0, column=0, sticky="nsew")
        cf.columnconfigure(0, weight=1)
        cf.rowconfigure(0, weight=1)

        self.chat = Text(
            cf, bg=BG, fg=FG, font=("Helvetica Neue", 10),
            insertbackground=FG, relief="flat",
            state="disabled", wrap=WORD, padx=8, pady=8)
        self.chat.tag_config("usr", background=USER_BG, foreground="#c0c8ff",
                            lmargin1=10, lmargin2=10, rmargin=10, spacing3=4)
        self.chat.tag_config("bot", background=BOT_BG, foreground=FG,
                            lmargin1=10, lmargin2=10, rmargin=10, spacing3=4)
        sb = Scrollbar(cf, command=self.chat.yview, width=8)
        self.chat.configure(yscrollcommand=sb.set)
        sb.pack(side=RIGHT, fill="y")
        self.chat.pack(side=LEFT, fill="both", expand=True)

        # Sidebar — column 1, grid (no pack!)
        sb2 = Frame(main, bg=SURFACE, width=220)
        sb2.grid(row=0, column=1, sticky="ns", padx=(6, 0), pady=0)
        sb2.grid_propagate(False)
        sb2.columnconfigure(0, weight=1)

        r = 0

        def hdr(txt):
            nonlocal r
            Label(sb2, text=txt, bg=SURFACE2, fg=FG,
                  font=("Helvetica Neue", 9, "bold"),
                  anchor="w", padx=8, pady=4
            ).grid(row=r, column=0, sticky="ew", pady=(0, 2))
            r += 1

        hdr("Parameter")

        # Temperature
        tf = Frame(sb2, bg=SURFACE)
        tf.grid(row=r, column=0, sticky="ew", padx=6, pady=2); r += 1
        Label(tf, text="Temperature", bg=SURFACE, fg=FG_DIM,
              font=("Helvetica Neue", 8)).pack(anchor="w")
        self.tmp_sc = ttk.Scale(tf, from_=0.0, to=1.0, orient="horizontal")
        self.tmp_sc.set(TEMPERATURE)
        self.tmp_sc.pack(fill="x")
        self.tmp_lb = Label(tf, text=f"{TEMPERATURE:.2f}",
                            bg=SURFACE, fg=ACCENT,
                            font=("Helvetica Neue", 9, "bold"))
        self.tmp_lb.pack(anchor="e")
        self.tmp_sc.bind("<Motion>",
                        lambda *_: self.tmp_lb.config(
                            text=f"{float(self.tmp_sc.get()):.2f}"))

        # Max Tokens
        mf = Frame(sb2, bg=SURFACE)
        mf.grid(row=r, column=0, sticky="ew", padx=6, pady=2); r += 1
        Label(mf, text="Max Tokens", bg=SURFACE, fg=FG_DIM,
              font=("Helvetica Neue", 8)).pack(anchor="w")
        self.tok_sc = ttk.Scale(mf, from_=64, to=8192, orient="horizontal")
        self.tok_sc.set(MAX_TOKENS)
        self.tok_sc.pack(fill="x")
        self.tok_lb = Label(mf, text=str(MAX_TOKENS),
                             bg=SURFACE, fg=ACCENT,
                             font=("Helvetica Neue", 9, "bold"))
        self.tok_lb.pack(anchor="e")
        self.tok_sc.bind("<Motion>",
                        lambda *_: self.tok_lb.config(
                            text=str(int(self.tok_sc.get()))))

        hdr("System-Prompt")
        sf = Frame(sb2, bg=SURFACE)
        sf.grid(row=r, column=0, sticky="ew", padx=6, pady=(0, 4)); r += 1
        self.sys_tx = Text(sf, bg=SURFACE2, fg=FG,
                           font=("Helvetica Neue", 9),
                           insertbackground=FG, relief="flat",
                           wrap=WORD, height=7)
        self.sys_tx.insert("1.0", SYS_PROMPT)
        ss = Scrollbar(sf, command=self.sys_tx.yview)
        self.sys_tx.configure(yscrollcommand=ss.set)
        ss.pack(side=RIGHT, fill="y")
        self.sys_tx.pack(side=LEFT, fill="both", expand=True)

        # Spacer
        Frame(sb2, bg=SURFACE, height=8).grid(row=r, column=0); r += 1

        # Clear button
        self.bt_clear = Button(sb2, text="🗑 Verlauf löschen",
                                command=self._clear,
                                bg=SURFACE2, fg=FG, relief="flat",
                                font=("Helvetica Neue", 9),
                                activebackground=ERR_C, activeforeground="white")
        self.bt_clear.grid(row=r, column=0, sticky="ew", padx=6, pady=(0, 4)); r += 1

        # Stop button
        self.bt_stop = Button(sb2, text="⏹ Stoppen",
                              command=self._stop,
                              bg=SURFACE2, fg=FG, relief="flat",
                              font=("Helvetica Neue", 9),
                              activebackground=ERR_C, activeforeground="white",
                              state="disabled")
        self.bt_stop.grid(row=r, column=0, sticky="ew", padx=6); r += 1

        # ── Input bar ──────────────────────────────────────────────────────
        ib = Frame(self.root, bg=SURFACE, padx=8, pady=6)
        ib.pack(fill="x")
        self.inp_sv = StringVar()
        ie = Entry(ib, textvariable=self.inp_sv, bg=SURFACE2, fg=FG,
                   insertbackground=FG, relief="flat",
                   font=("Helvetica Neue", 10))
        ie.pack(side=LEFT, fill="x", expand=True, ipady=6)
        ie.bind("<Return>", lambda *_: self._send())
        self.bt_send = Button(ib, text="▶ Senden", command=self._send,
                              bg=ACCENT, fg="white", relief="flat",
                              font=("Helvetica Neue", 10, "bold"),
                              activebackground=ACCENT_H, padx=12)
        self.bt_send.pack(side=RIGHT, padx=(6, 0), ipady=4)

        # ── Log pane ───────────────────────────────────────────────────────
        lg = Frame(self.root, bg=SURFACE2)
        lg.pack(fill="x")
        self.bt_log = Button(lg, text="▼ Log", command=self._tog_log,
                             bg=SURFACE2, fg=FG_DIM, relief="flat",
                             font=("Helvetica Neue", 8), anchor="w", padx=8)
        self.bt_log.pack(side=LEFT)

        self.log_fr = Frame(self.root, bg=LOG_BG, height=120)
        self.log_fr.pack(fill="x")
        self.log_fr.pack_propagate(False)
        li = Frame(self.log_fr, bg=LOG_BG)
        li.pack(fill="both", expand=True, padx=6, pady=4)
        self.log_tx = Text(li, bg=LOG_BG, fg=FG,
                           font=("Courier New", 9),
                           insertbackground=FG, relief="flat",
                           state="disabled", wrap=WORD, height=5)
        ls = Scrollbar(li, command=self.log_tx.yview)
        self.log_tx.configure(yscrollcommand=ls.set)
        ls.pack(side=RIGHT, fill="y")
        self.log_tx.pack(side=LEFT, fill="both", expand=True)

    # ── GLM server toggle ───────────────────────────────────────────────
    def _toggle_glm_server(self):
        if self._glm_server is None or not self._glm_server.running:
            self._glm_server = ServerManager(PRESETS[1], self._log)
            self._glm_server.start()
            self._glm_btn.config(text="⏹ Server stoppen",
                                 bg=ERR_C, fg="white",
                                 activebackground=ERR_C, activeforeground="white")
            # Poll until server is up, then health-check
            threading.Thread(target=self._wait_glm_up, daemon=True).start()
        else:
            self._glm_server.stop()
            self._glm_btn.config(text="▶ Server starten",
                                 bg=SURFACE2, fg=WARN_C,
                                 activebackground=SURFACE2,
                                 activeforeground=WARN_C)
            self._health()

    def _wait_glm_up(self):
        """Poll health until GLM server is ready (up to 60s)."""
        url = PRESETS[1].endpoint
        for _ in range(60):
            if not self._glm_server or not self._glm_server.running:
                return
            try:
                r = requests.get(f"{url}/health", timeout=2)
                if r.status_code == 200:
                    self.root.after(0, self._on_glm_up)
                    return
            except requests.RequestException:
                pass
            time.sleep(1)
        self._log(f"[{tm()}] GLM-Server: Start-Time-out (60s)")

    def _on_glm_up(self):
        self._log(f"[{tm()}] GLM-Server läuft auf Port 18789 ✓")
        self._health()

    # ── Health ───────────────────────────────────────────────────────────
    def _health_hint(self):
        self.st_label.config(text="⏳", fg=WARN_C)

    def _health(self):
        self._health_hint()
        # Extract base URL from full endpoint
        url = self.url_var.get().rstrip("/")
        self._log(f"[{tm()}] Prüfe {url} …")
        threading.Thread(
            target=APIClient.health,
            args=(url, self.hq),
            daemon=True
        ).start()
        self.root.after(100, self._poll_h)

    def _poll_h(self):
        try:
            r = self.hq.get_nowait()
        except queue.Empty:
            self.root.after(100, self._poll_h)
            return
        ok, ms = r[0], r[1]
        msg = r[2] if len(r) > 2 else ""
        if ok == "ok":
            self.st_label.config(text="✓", fg=OK_C)
            self._log(f"[{tm()}] Verbunden · {ms:.0f} ms")
        else:
            self.st_label.config(text="✗", fg=ERR_C)
            self._log(f"[{tm()}] Fehler: {msg} ({ms:.0f} ms)")

    # ── Chat: send ───────────────────────────────────────────────────────
    def _send(self):
        if self.gen:
            return
        txt = self.inp_sv.get().strip()
        if not txt:
            return

        user_text = txt
        self.inp_sv.set("")

        self._append_usr(user_text)

        msgs = [
            {"role": "system",
             "content": self.sys_tx.get("1.0", "end").strip()},
        ]
        for m in self.history:
            msgs.append(m)
        msgs.append({"role": "user", "content": user_text})

        # Build URL from endpoint field (strip /v1 if user put it there)
        raw_url = self.url_var.get().strip().rstrip("/")
        base_url = raw_url.replace("/v1", "")

        self.client = APIClient(
            base_url,
            self.model_var.get(),
            float(self.tmp_sc.get()),
            int(self.tok_sc.get()),
        )
        self.gen = True
        self._update_btns()
        self._open_bot()
        self.st_label.config(text="◎", fg=WARN_C)
        self._log(f"[{tm()}] Start · {self.model_var.get()}")

        self.tok_q  = queue.Queue()
        self.done_q = queue.Queue()
        threading.Thread(
            target=self.client.stream,
            args=(msgs, self.tok_q, self.done_q),
            daemon=True
        ).start()
        self.root.after(100, self._pump)

    # ── Chat: pump tokens from queue ─────────────────────────────────────
    def _pump(self):
        try:
            while True:
                token = self.tok_q.get_nowait()
                self._inj(token)
        except queue.Empty:
            pass
        try:
            d = self.done_q.get_nowait()
            self._finish(d, user_text)
            return
        except queue.Empty:
            pass
        self.root.after(50, self._pump)

    def _inj(self, token: str):
        self.chat.configure(state="normal")
        self.chat.insert("end", token)
        self.chat.configure(state="disabled")
        self.chat.see("end")
        self.root.update_idletasks()

    def _finish(self, d: dict, user_text: str):
        self.gen = False
        self._update_btns()

        if d["type"] == "done":
            ms, pt, ct = d["ms"], d["pt"], d["ct"]
            spd = ct / ms * 1000 if ms > 0 and ct > 0 else 0
            self.st_label.config(text="✓", fg=OK_C)
            self._log(f"[{tm()}] Fertig · {ct} Tok / {ms/1000:.1f}s "
                      f"· ≈{spd:.1f} tok/s · P:{pt} C:{ct}")
            bot_text = self.chat.get(self._bot_mark, "end-1c").strip()
            self.history += [{"role": "user",      "content": user_text},
                           {"role": "assistant", "content": bot_text}]
        else:
            err = d.get("msg", "?")
            self.st_label.config(text="✗", fg=ERR_C)
            self._log(f"[{tm()}] Fehler: {err}")
            self.chat.configure(state="normal")
            self.chat.insert("end", f"\n⚠ {err}\n")
            self.chat.configure(state="disabled")

        # Tag the assistant block
        self.chat.configure(state="normal")
        self.chat.insert("end", "\n")
        self.chat.tag_add("bot", self._bot_mark, "end-1c")
        self.chat.configure(state="disabled")
        self.chat.see("end")
        self._bot_mark = None

    def _append_usr(self, txt: str):
        self.chat.configure(state="normal")
        ts = datetime.now().strftime("%H:%M")
        self.chat.insert("end", f"\n[{ts}] Du: {txt}\n")
        self.chat.tag_add("usr", "end-2l linestart", "end-1c")
        self.chat.configure(state="disabled")
        self.chat.see("end")

    def _open_bot(self):
        self.chat.configure(state="normal")
        ts = datetime.now().strftime("%H:%M")
        self.chat.insert("end", f"\n[{ts}] Assistent:\n")
        self._bot_mark = self.chat.index("end-1l linestart")
        self.chat.configure(state="disabled")

    def _stop(self):
        if self.client and self.gen:
            self.client.abort()
            self._log(f"[{tm()}] Stop …")

    def _clear(self):
        self.history.clear()
        self.chat.configure(state="normal")
        self.chat.delete("1.0", "end")
        self.chat.configure(state="disabled")
        self._log(f"[{tm()}] Verlauf gelöscht")
        self._bot_mark = None

    # ── Helpers ─────────────────────────────────────────────────────────
    def _update_btns(self):
        s = "normal" if not self.gen else "disabled"
        h = "normal" if self.gen else "disabled"
        self.bt_send.config(state=s)
        self.bt_stop.config(state=h)

    def _tog_log(self):
        if self.log_fr.winfo_manager == "":
            self.log_fr.pack(fill="x")
            self.bt_log.config(text="▼ Log")
        else:
            self.log_fr.pack_forget()
            self.bt_log.config(text="▲ Log")

    def _log(self, msg: str):
        self._lcnt += 1
        self.log_tx.configure(state="normal")
        self.log_tx.insert("end", f"{msg}\n")
        self.log_tx.see("end")
        self.log_tx.configure(state="disabled")
        if self._lcnt > 500:
            self.log_tx.configure(state="normal")
            self.log_tx.delete("1.0", "3.0")
            self.log_tx.configure(state="disabled")
            self._lcnt -= 3


def tm():
    return datetime.now().strftime("%H:%M:%S")


# ── Entry point ────────────────────────────────────────────────────────────
def main():
    root = Tk()
    try:
        ttk.Style(root).theme_use("clam")
    except Exception:
        pass
    GUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()

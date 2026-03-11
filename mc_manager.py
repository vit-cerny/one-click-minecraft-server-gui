"""
╔══════════════════════════════════════════════════════════════╗
║           MINECRAFT SERVER MANAGER  v2.0                     ║
║   Fabric • Paper • Vanilla • Mods • Plugins • playit.gg      ║
╠══════════════════════════════════════════════════════════════╣
║  Requirements: Python 3.8+                                   ║
║  Install deps: pip install requests                          ║
║  Run:          python mc_manager.py                          ║
╚══════════════════════════════════════════════════════════════╝
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import subprocess, threading, os, json, time, socket, queue
import platform, re, webbrowser, shutil, sys
from pathlib import Path
from datetime import datetime
import urllib.request, urllib.error, urllib.parse

try:
    import requests as _req
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

# ─────────────────────────────────────────────────────────────────────────────
#  PALETTE  ·  "terminal jade"
# ─────────────────────────────────────────────────────────────────────────────
P = dict(
    bg0     = "#07090d",
    bg1     = "#0d1117",
    bg2     = "#13191f",
    bg3     = "#1a2230",
    bg4     = "#212d3d",
    bg5     = "#2a3a50",
    green   = "#4ade80",
    green2  = "#166534",
    teal    = "#22d3ee",
    blue    = "#60a5fa",
    blue2   = "#1d4ed8",
    purple  = "#a78bfa",
    amber   = "#fbbf24",
    red     = "#f87171",
    red2    = "#7f1d1d",
    text    = "#f1f5f9",
    text2   = "#94a3b8",
    text3   = "#475569",
    border  = "#1e2d40",
    cons    = "#050709",
    white   = "#ffffff",
)

FM  = ("Consolas", 10)
FMS = ("Consolas", 9)
FMB = ("Consolas", 10, "bold")
FMT = ("Consolas", 13, "bold")
FMH = ("Consolas", 11, "bold")

CFG_PATH = os.path.join(os.path.expanduser("~"), ".mcmgr2_config.json")

PLAYIT_URLS = {
    "Windows": "https://github.com/playit-cloud/playit-agent/releases/latest/download/playit-windows-x86_64-signed.exe",
    "Darwin":  "https://github.com/playit-cloud/playit-agent/releases/latest/download/playit-darwin-x86_64",
    "Linux":   "https://github.com/playit-cloud/playit-agent/releases/latest/download/playit-linux-x86_64",
}

# ─────────────────────────────────────────────────────────────────────────────
#  NET HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def api_get(url, timeout=12):
    try:
        if HAS_REQUESTS:
            r = _req.get(url, timeout=timeout, headers={"User-Agent": "MCManager/2.0"})
            r.raise_for_status()
            return r.json()
        with urllib.request.urlopen(
            urllib.request.Request(url, headers={"User-Agent": "MCManager/2.0"}),
            timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        return None

def dl_file(url, dest, on_progress=None):
    try:
        if HAS_REQUESTS:
            r = _req.get(url, stream=True, timeout=90,
                         headers={"User-Agent": "MCManager/2.0"})
            r.raise_for_status()
            total = int(r.headers.get("content-length", 0))
            done  = 0
            with open(dest, "wb") as f:
                for chunk in r.iter_content(16384):
                    f.write(chunk); done += len(chunk)
                    if on_progress and total:
                        on_progress(done / total)
        else:
            def hook(n, bs, tot):
                if on_progress and tot > 0:
                    on_progress(min(n * bs / tot, 1.0))
            urllib.request.urlretrieve(url, dest, hook)
        if on_progress: on_progress(1.0)
        return True
    except Exception as e:
        return str(e)

# ─────────────────────────────────────────────────────────────────────────────
#  REMOTE DATA
# ─────────────────────────────────────────────────────────────────────────────

def paper_versions():
    d = api_get("https://api.papermc.io/v2/projects/paper")
    return list(reversed(d["versions"])) if d else ["1.21.1","1.21","1.20.6","1.20.4","1.20.1","1.19.4"]

def paper_latest_build(ver):
    d = api_get(f"https://api.papermc.io/v2/projects/paper/versions/{ver}")
    return d["builds"][-1] if d and "builds" in d else None

def paper_url(ver, build):
    jar = f"paper-{ver}-{build}.jar"
    return f"https://api.papermc.io/v2/projects/paper/versions/{ver}/builds/{build}/downloads/{jar}", jar

def fabric_mc_versions():
    d = api_get("https://meta.fabricmc.net/v2/versions/game")
    return [v["version"] for v in d if v.get("stable")] if d else ["1.21.1","1.21","1.20.6","1.20.4"]

def fabric_loader_ver():
    d = api_get("https://meta.fabricmc.net/v2/versions/loader")
    return d[0]["version"] if d else "0.16.0"

def fabric_installer_ver():
    d = api_get("https://meta.fabricmc.net/v2/versions/installer")
    return d[0]["version"] if d else "1.0.1"

def fabric_url(mc, loader, installer):
    u = f"https://meta.fabricmc.net/v2/versions/loader/{mc}/{loader}/{installer}/server/jar"
    return u, f"fabric-server-mc{mc}-loader{loader}.jar"

def vanilla_versions():
    d = api_get("https://launchermeta.mojang.com/mc/game/version_manifest.json")
    if d:
        return [v["id"] for v in d["versions"] if v["type"] == "release"][:20]
    return ["1.21.1","1.21","1.20.6","1.20.4"]

def vanilla_url(ver):
    d = api_get("https://launchermeta.mojang.com/mc/game/version_manifest.json")
    if not d: return None, None
    for v in d["versions"]:
        if v["id"] == ver:
            vd = api_get(v["url"])
            if vd:
                return vd["downloads"]["server"]["url"], f"minecraft_server.{ver}.jar"
    return None, None

def modrinth_search(q, loader="fabric", game_ver="1.21.1", limit=25):
    facets = json.dumps([["project_type:mod"],
                         [f"categories:{loader}"],
                         [f"versions:{game_ver}"]])
    url = (f"https://api.modrinth.com/v2/search"
           f"?query={urllib.parse.quote(q)}"
           f"&facets={urllib.parse.quote(facets)}"
           f"&limit={limit}")
    d = api_get(url)
    return d.get("hits", []) if d else []

def modrinth_mod_versions(pid, loader, game_ver):
    url = (f"https://api.modrinth.com/v2/project/{pid}/version"
           f"?loaders=[\"{loader}\"]&game_versions=[\"{game_ver}\"]")
    return api_get(url) or []

CURATED_PLUGINS = [
    ("EssentialsX",    "Utility",    "Homes, warps, economy, chat",            "https://essentialsx.net/downloads.html"),
    ("LuckPerms",      "Admin",      "Permissions & rank management",           "https://luckperms.net/download"),
    ("WorldEdit",      "Building",   "Fast in-game map editor",                 "https://dev.bukkit.org/projects/worldedit/files"),
    ("WorldGuard",     "Protection", "Protect regions from griefing",           "https://dev.bukkit.org/projects/worldguard/files"),
    ("McMMO",          "RPG",        "Skill leveling: mining, combat, fishing", "https://www.spigotmc.org/resources/64348/"),
    ("Vault",          "API",        "Economy & permissions API layer",         "https://www.spigotmc.org/resources/34315/"),
    ("Dynmap",         "Utility",    "Live browser map of your world",          "https://www.spigotmc.org/resources/274/"),
    ("Spark",          "Perf",       "TPS monitor & performance profiler",      "https://hangar.papermc.io/lucko/Spark"),
    ("ClearLag",       "Perf",       "Auto-remove lag-causing entities",        "https://www.spigotmc.org/resources/68271/"),
    ("Citizens",       "NPCs",       "Fully featured NPC system",               "https://www.spigotmc.org/resources/13811/"),
    ("Jobs Reborn",    "Economy",    "Players earn money from in-game jobs",    "https://www.spigotmc.org/resources/4216/"),
    ("CoreProtect",    "Admin",      "Block logging & rollback",                "https://www.spigotmc.org/resources/8631/"),
    ("PlaceholderAPI", "API",        "Variable placeholders for plugins",       "https://www.spigotmc.org/resources/6245/"),
    ("Multiverse",     "Worlds",     "Multiple world management",               "https://dev.bukkit.org/projects/multiverse-core"),
    ("GriefPrevention","Protection", "Anti-grief land claiming",                "https://www.spigotmc.org/resources/1884/"),
    ("ProtocolLib",    "API",        "Protocol manipulation library",           "https://www.spigotmc.org/resources/1997/"),
]

# ─────────────────────────────────────────────────────────────────────────────
#  CONFIG
# ─────────────────────────────────────────────────────────────────────────────

def cfg_load():
    cfg = {"servers": [], "java_path": "java",
           "ram_min": "1", "ram_max": "2", "playit_path": ""}
    try:
        with open(CFG_PATH) as f:
            cfg = json.load(f)
    except: pass
    # Auto-detect playit path written by START.bat
    if not cfg.get("playit_path"):
        hint = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".playit_path")
        if os.path.isfile(hint):
            try:
                p = open(hint).read().strip()
                if os.path.isfile(p):
                    cfg["playit_path"] = p
            except: pass
        # Also check for playit.exe in same folder as the script
        local = os.path.join(os.path.dirname(os.path.abspath(__file__)), "playit.exe")
        if os.path.isfile(local):
            cfg["playit_path"] = local
    return cfg

def cfg_save(c):
    try:
        with open(CFG_PATH, "w") as f: json.dump(c, f, indent=2)
    except: pass

def java_detect():
    cands = ["java"]
    if platform.system() == "Windows":
        for base in [r"C:\Program Files\Eclipse Adoptium",
                     r"C:\Program Files\Java",
                     r"C:\Program Files\Microsoft"]:
            try:
                for d in os.listdir(base):
                    cands.append(os.path.join(base, d, "bin", "java.exe"))
            except: pass
    for c in cands:
        try:
            r = subprocess.run([c, "-version"], capture_output=True, text=True, timeout=3)
            if "version" in (r.stdout + r.stderr).lower(): return c
        except: pass
    return "java"

def java_ver(path):
    try:
        r = subprocess.run([path, "-version"], capture_output=True, text=True, timeout=3)
        m = re.search(r'version "([^"]+)"', r.stderr + r.stdout)
        return m.group(1) if m else "unknown"
    except: return "not found"

def find_jar(path):
    preferred = ["server.jar","paper.jar","fabric.jar","spigot.jar","vanilla.jar"]
    for p in preferred:
        fp = os.path.join(path, p)
        if os.path.isfile(fp): return fp
    for f in os.listdir(path):
        if f.endswith(".jar") and "installer" not in f.lower(): return os.path.join(path, f)
    return None

def open_folder(path):
    sys_ = platform.system()
    if sys_ == "Windows":   os.startfile(path)
    elif sys_ == "Darwin":  subprocess.Popen(["open", path])
    else:                   subprocess.Popen(["xdg-open", path])

# ─────────────────────────────────────────────────────────────────────────────
#  WIDGETS
# ─────────────────────────────────────────────────────────────────────────────

def btn(parent, text, cmd, style="normal", **kw):
    STYLES = {
        "normal":  (P["bg4"],    P["text"],  P["bg5"]),
        "primary": (P["green2"], P["green"], "#1a7a40"),
        "blue":    (P["blue2"],  P["white"], "#2563eb"),
        "danger":  (P["red2"],   P["red"],   "#991b1b"),
        "amber":   ("#78350f",   P["amber"], "#92400e"),
        "ghost":   (P["bg2"],    P["text2"], P["bg3"]),
        "teal":    ("#134e4a",   P["teal"],  "#0f766e"),
    }
    bg, fg, abg = STYLES.get(style, STYLES["normal"])
    return tk.Button(parent, text=text, command=cmd, bg=bg, fg=fg,
                     activebackground=abg, activeforeground=fg,
                     relief="flat", bd=0, cursor="hand2",
                     font=FMB, padx=12, pady=6, **kw)

def sep(parent, vertical=False):
    return tk.Frame(parent, bg=P["border"],
                    width=1 if vertical else 0,
                    height=0 if vertical else 1)

def lbl(parent, text, color=None, size=10, bold=False, **kw):
    font = ("Consolas", size, "bold" if bold else "")
    return tk.Label(parent, text=text, bg=parent["bg"],
                    fg=color or P["text2"], font=font, **kw)

def section(parent, text):
    f = tk.Frame(parent, bg=parent["bg"])
    tk.Label(f, text=text, bg=parent["bg"], fg=P["text3"],
             font=("Consolas", 8, "bold")).pack(side="left")
    tk.Frame(f, bg=P["border"], height=1).pack(
        side="left", fill="x", expand=True, padx=(8,0), pady=1)
    return f

def entry_labeled(parent, label, var, width=None):
    f = tk.Frame(parent, bg=parent["bg"])
    tk.Label(f, text=label, bg=parent["bg"], fg=P["text2"],
             font=FM, width=20, anchor="w").pack(side="left")
    kw = {"width": width} if width else {}
    e = tk.Entry(f, textvariable=var, bg=P["bg3"], fg=P["text"],
                 insertbackground=P["text"], relief="flat", font=FM, **kw)
    e.pack(side="left", fill="x", expand=True, ipady=6, padx=(6,0))
    return f, e

def combo(parent, var, values, width=18):
    cb = ttk.Combobox(parent, textvariable=var, values=values,
                      state="readonly", font=FM, width=width)
    return cb

# ─────────────────────────────────────────────────────────────────────────────
#  MAIN APPLICATION
# ─────────────────────────────────────────────────────────────────────────────

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.cfg          = cfg_load()
        self.server_proc  = None
        self.playit_proc  = None
        self.running      = False
        self.playit_on    = False
        self.log_q        = queue.Queue()
        self.current      = None   # active server dict
        self.mod_results  = []

        self.title("⛏  Minecraft Server Manager  v2.0")
        self.geometry("1260x800")
        self.minsize(1050, 660)
        self.configure(bg=P["bg0"])
        self._styles()
        self._build()
        self._poll()
        self._tick()
        if not HAS_REQUESTS:
            self.after(600, lambda: self._toast(
                "pip install requests  →  for faster downloads", warn=True))

    # ── ttk styles ────────────────────────────────────────────────────────────
    def _styles(self):
        s = ttk.Style(self)
        try:
            s.theme_use("clam")
        except Exception:
            pass
        style_calls = [
            lambda: s.configure("Dark.TCombobox",
                fieldbackground=P["bg3"], background=P["bg3"],
                foreground=P["text"], selectbackground=P["bg4"],
                selectforeground=P["text"], borderwidth=0, arrowcolor=P["text2"]),
            lambda: s.configure("G.Horizontal.TProgressbar",
                troughcolor=P["bg3"], background=P["green"],
                borderwidth=0, thickness=7),
            lambda: s.configure("T.Horizontal.TProgressbar",
                troughcolor=P["bg3"], background=P["teal"],
                borderwidth=0, thickness=7),
            lambda: s.configure("TV.Treeview",
                background=P["bg2"], foreground=P["text"],
                fieldbackground=P["bg2"], borderwidth=0,
                rowheight=26, font=FM),
            lambda: s.configure("TV.Treeview.Heading",
                background=P["bg3"], foreground=P["text2"],
                font=("Consolas", 9, "bold"), relief="flat"),
            lambda: s.map("TV.Treeview",
                background=[("selected", P["bg4"])],
                foreground=[("selected", P["teal"])]),
        ]
        for call in style_calls:
            try:
                call()
            except Exception:
                pass


    def _build(self):
        self._topbar()
        body = tk.Frame(self, bg=P["bg0"])
        body.pack(fill="both", expand=True)
        self._sidebar(body)
        sep(body, vertical=True).pack(side="left", fill="y")
        self.content = tk.Frame(body, bg=P["bg1"])
        self.content.pack(fill="both", expand=True)
        self.panels = {}
        for build_fn in [
            self._p_home, self._p_create, self._p_console,
            self._p_mods, self._p_plugins, self._p_properties,
            self._p_playit, self._p_settings,
        ]:
            build_fn()
        self._nav("home")

    # ── topbar ────────────────────────────────────────────────────────────────
    def _topbar(self):
        bar = tk.Frame(self, bg=P["bg2"], height=52)
        bar.pack(fill="x")
        bar.pack_propagate(False)
        sep(bar, vertical=True).pack(side="left", fill="y")
        tk.Label(bar, text="⛏  MC SERVER MANAGER", bg=P["bg2"],
                 fg=P["green"], font=("Consolas", 14, "bold")).pack(side="left", padx=20)
        sep(bar, vertical=True).pack(side="left", fill="y", padx=(0,8))

        self.top_srv = tk.Label(bar, text="No server loaded",
                                bg=P["bg2"], fg=P["text2"], font=FM)
        self.top_srv.pack(side="left", padx=8)

        self.top_status = tk.Label(bar, text="● OFFLINE",
                                   bg=P["bg2"], fg=P["red"], font=FMB)
        self.top_status.pack(side="right", padx=20)

        self.top_playit = tk.Label(bar, text="playit: OFF",
                                   bg=P["bg2"], fg=P["text3"], font=FMS)
        self.top_playit.pack(side="right", padx=12)

        self.top_java = tk.Label(bar, text="Java …",
                                 bg=P["bg2"], fg=P["text3"], font=FMS)
        self.top_java.pack(side="right", padx=12)
        threading.Thread(
            target=lambda: self.after(100, lambda: self.top_java.config(
                text=f"Java {java_ver(self.cfg.get('java_path','java'))}")),
            daemon=True).start()

    # ── sidebar ───────────────────────────────────────────────────────────────
    def _sidebar(self, parent):
        sb = tk.Frame(parent, bg=P["bg2"], width=210)
        sb.pack(fill="y", side="left")
        sb.pack_propagate(False)
        self.nav_btns = {}

        ITEMS = [
            ("home",       "🏠  Home"),
            ("create",     "✦   Create Server"),
            ("console",    "📟  Console"),
            ("mods",       "🧪  Mods  (Fabric)"),
            ("plugins",    "🧩  Plugins  (Paper)"),
            ("properties", "⚙  server.properties"),
            ("playit",     "🌐  playit.gg  Tunnel"),
            ("settings",   "🔧  Settings"),
        ]
        tk.Frame(sb, bg=P["bg2"], height=10).pack()
        for pid, label in ITEMS:
            b = tk.Button(sb, text=label, anchor="w",
                          bg=P["bg2"], fg=P["text2"],
                          activebackground=P["bg3"], activeforeground=P["text"],
                          relief="flat", bd=0, padx=18, pady=11,
                          font=FM, cursor="hand2",
                          command=lambda p=pid: self._nav(p))
            b.pack(fill="x")
            self.nav_btns[pid] = b

        sep(sb).pack(fill="x", pady=12)
        tk.Label(sb, text="SERVER CONTROL", bg=P["bg2"], fg=P["text3"],
                 font=("Consolas", 8, "bold")).pack(padx=18, anchor="w")

        self.b_start   = btn(sb, "▶  START",   self.srv_start,   "primary")
        self.b_stop    = btn(sb, "■  STOP",    self.srv_stop,    "danger", state="disabled")
        self.b_restart = btn(sb, "↺  RESTART", self.srv_restart, "amber",  state="disabled")
        for b in (self.b_start, self.b_stop, self.b_restart):
            b.pack(fill="x", padx=12, pady=3)

        sep(sb).pack(fill="x", pady=10)
        tk.Label(sb, text="RECENT", bg=P["bg2"], fg=P["text3"],
                 font=("Consolas", 8, "bold")).pack(padx=18, anchor="w")
        self.recent_sb = tk.Frame(sb, bg=P["bg2"])
        self.recent_sb.pack(fill="x")
        self._recent_sb_refresh()

    def _recent_sb_refresh(self):
        for w in self.recent_sb.winfo_children(): w.destroy()
        for srv in list(reversed(self.cfg.get("servers", [])))[:6]:
            name = os.path.basename(srv["path"]) or "Server"
            b = tk.Button(self.recent_sb,
                          text=f"  ›  {name[:22]}",
                          anchor="w", bg=P["bg2"], fg=P["text3"],
                          activebackground=P["bg3"], activeforeground=P["text2"],
                          relief="flat", bd=0, padx=16, pady=4,
                          font=FMS, cursor="hand2",
                          command=lambda s=srv: self._load(s))
            b.pack(fill="x")

    # ── panel helper ──────────────────────────────────────────────────────────
    def _panel(self, pid, title, sub=""):
        f = tk.Frame(self.content, bg=P["bg1"])
        self.panels[pid] = f
        hdr = tk.Frame(f, bg=P["bg1"])
        hdr.pack(fill="x", padx=28, pady=(22,0))
        tk.Label(hdr, text=title, bg=P["bg1"], fg=P["text"],
                 font=FMT).pack(anchor="w")
        if sub:
            tk.Label(hdr, text=sub, bg=P["bg1"], fg=P["text3"],
                     font=FMS).pack(anchor="w", pady=(1,0))
        sep(f).pack(fill="x", padx=28, pady=(8,0))
        return f

    def _nav(self, pid):
        for p in self.panels.values(): p.pack_forget()
        for bid, b in self.nav_btns.items():
            b.config(bg=P["bg2"], fg=P["text2"])
        self.panels[pid].pack(fill="both", expand=True)
        if pid in self.nav_btns:
            self.nav_btns[pid].config(bg=P["bg3"], fg=P["green"])

    # ══════════════════════════════════════════════════════════════════════════
    #  HOME
    # ══════════════════════════════════════════════════════════════════════════
    def _p_home(self):
        f = self._panel("home", "Home", "Load an existing server or create a new one")

        # ── load row
        lf = tk.Frame(f, bg=P["bg2"], padx=18, pady=16)
        lf.pack(fill="x", padx=28, pady=16)
        tk.Label(lf, text="SERVER FOLDER", bg=P["bg2"], fg=P["text3"],
                 font=("Consolas", 8, "bold")).pack(anchor="w", pady=(0,6))
        row = tk.Frame(lf, bg=P["bg2"])
        row.pack(fill="x")
        self.h_path = tk.StringVar(value=self.cfg.get("last_path",""))
        tk.Entry(row, textvariable=self.h_path, bg=P["bg3"], fg=P["text"],
                 insertbackground=P["text"], relief="flat", font=FM
                 ).pack(side="left", fill="x", expand=True, ipady=7, padx=(0,8))
        btn(row, "Browse",      self._h_browse).pack(side="left", ipady=7)
        btn(row, "Load Server", self._h_load, "blue").pack(side="left", padx=(6,0), ipady=7)

        # ── stat cards
        cards = tk.Frame(f, bg=P["bg1"])
        cards.pack(fill="x", padx=28, pady=(0,14))
        cards.columnconfigure((0,1,2,3), weight=1)

        def card(col, title, val, color):
            cf = tk.Frame(cards, bg=P["bg2"], padx=16, pady=14)
            cf.grid(row=0, column=col, padx=(0,8), sticky="ew")
            tk.Label(cf, text=title, bg=P["bg2"], fg=P["text3"],
                     font=("Consolas", 8, "bold")).pack(anchor="w")
            v = tk.Label(cf, text=val, bg=P["bg2"], fg=color,
                         font=("Consolas", 14, "bold"))
            v.pack(anchor="w", pady=(4,0))
            return v

        self.c_status  = card(0, "STATUS",  "OFFLINE", P["red"])
        self.c_type    = card(1, "TYPE",    "—",       P["text2"])
        self.c_ver     = card(2, "VERSION", "—",       P["blue"])
        self.c_path    = card(3, "FOLDER",  "—",       P["text2"])

        # ── recent servers table
        section(f, "RECENT SERVERS").pack(fill="x", padx=28, pady=(4,6))
        tv_wrap = tk.Frame(f, bg=P["bg1"])
        tv_wrap.pack(fill="both", expand=True, padx=28)

        cols = ("Name","Type","Version","Path")
        self.h_tv = ttk.Treeview(tv_wrap, columns=cols, show="headings",
                                  height=8, style="TV.Treeview")
        for c, w in [("Name",160),("Type",80),("Version",90),("Path",500)]:
            self.h_tv.heading(c, text=c); self.h_tv.column(c, width=w)
        vsb = tk.Scrollbar(tv_wrap, orient="vertical", command=self.h_tv.yview, bg="#1a2230", troughcolor="#0d1117", activebackground="#22d3ee", relief="flat")
        self.h_tv.configure(yscrollcommand=vsb.set)
        self.h_tv.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self.h_tv.bind("<Double-1>", self._h_dbl)
        self._h_tv_refresh()

        br = tk.Frame(f, bg=P["bg1"])
        br.pack(fill="x", padx=28, pady=8)
        btn(br, "✦  Create New Server", lambda: self._nav("create"), "primary").pack(side="left", ipady=6)
        btn(br, "🗑  Remove Selected",  self._h_remove,              "danger" ).pack(side="left", padx=8, ipady=6)
        btn(br, "📂  Open Folder",      self._h_open,                "ghost"  ).pack(side="left", ipady=6)

    def _h_tv_refresh(self):
        self.h_tv.delete(*self.h_tv.get_children())
        for s in reversed(self.cfg.get("servers",[])):
            self.h_tv.insert("","end", values=(
                os.path.basename(s["path"]), s.get("type","?"),
                s.get("version","?"), s["path"]))

    def _h_dbl(self, _):
        sel = self.h_tv.selection()
        if sel:
            path = self.h_tv.item(sel[0])["values"][3]
            s = next((x for x in self.cfg["servers"] if x["path"]==path), None)
            if s: self._load(s)

    def _h_browse(self):
        p = filedialog.askdirectory(title="Select Server Folder")
        if p: self.h_path.set(p)

    def _h_load(self):
        p = self.h_path.get().strip()
        if not p or not os.path.isdir(p):
            self._toast("Invalid folder", warn=True); return
        stype, ver = "Unknown", "?"
        for fn in os.listdir(p):
            if not fn.endswith(".jar"): continue
            fl = fn.lower()
            if "fabric" in fl:   stype = "Fabric"
            elif "paper" in fl:  stype = "Paper"
            elif "spigot" in fl: stype = "Spigot"
            elif "minecraft_server" in fl: stype = "Vanilla"
            m = re.search(r"(\d+\.\d+[\.\d]*)", fn)
            if m: ver = m.group(1)
        self._load({"path": p, "type": stype, "version": ver})

    def _h_remove(self):
        sel = self.h_tv.selection()
        if not sel: return
        path = self.h_tv.item(sel[0])["values"][3]
        self.cfg["servers"] = [s for s in self.cfg.get("servers",[]) if s["path"]!=path]
        cfg_save(self.cfg); self._h_tv_refresh(); self._recent_sb_refresh()

    def _h_open(self):
        sel = self.h_tv.selection()
        if sel:
            path = self.h_tv.item(sel[0])["values"][3]
            if os.path.isdir(path): open_folder(path)

    def _load(self, srv):
        self.current = srv
        self.cfg["last_path"] = srv["path"]
        if not any(s["path"]==srv["path"] for s in self.cfg.get("servers",[])):
            self.cfg.setdefault("servers",[]).append(srv)
        cfg_save(self.cfg)
        self._h_tv_refresh(); self._recent_sb_refresh()
        name = os.path.basename(srv["path"]) or "Server"
        self.top_srv.config(text=name)
        self.c_type.config(text=srv.get("type","?"))
        self.c_ver.config(text=srv.get("version","?"))
        short = name[:28]
        self.c_path.config(text=short)
        self.h_path.set(srv["path"])
        self._scan_mods(); self._scan_plugins()
        self._props_load_silent()
        self._toast(f"Loaded: {name}")

    # ══════════════════════════════════════════════════════════════════════════
    #  CREATE SERVER
    # ══════════════════════════════════════════════════════════════════════════
    def _p_create(self):
        f = self._panel("create", "Create Server",
                        "Download and configure a new server — Paper, Fabric, or Vanilla")

        nb = ttk.Notebook(f)
        nb.pack(fill="both", expand=True, padx=28, pady=14)

        self._create_paper_tab(nb)
        self._create_fabric_tab(nb)
        self._create_vanilla_tab(nb)

    def _create_paper_tab(self, nb):
        f = tk.Frame(nb, bg=P["bg1"]); nb.add(f, text="  📄 Paper  ")

        info = tk.Frame(f, bg=P["bg3"], padx=16, pady=10)
        info.pack(fill="x", pady=(10,0))
        tk.Label(info,
                 text="Paper  ·  High-performance Bukkit fork. Best for plugins (EssentialsX, WorldEdit, McMMO…). Recommended.",
                 bg=P["bg3"], fg=P["text2"], font=FMS).pack(anchor="w")

        fm = tk.Frame(f, bg=P["bg1"]); fm.pack(fill="x", padx=18, pady=16)

        self.pap_folder = tk.StringVar(value=os.path.join(
            os.path.expanduser("~"), "Desktop", "paper-server"))
        self.pap_ver    = tk.StringVar(value="1.21.1")
        self.pap_rmin   = tk.StringVar(value=self.cfg.get("ram_min","1"))
        self.pap_rmax   = tk.StringVar(value=self.cfg.get("ram_max","2"))
        self.pap_eula   = tk.BooleanVar(value=True)

        self._form_folder(fm, 0, "Server Folder:", self.pap_folder)
        tk.Label(fm, text="MC Version:", bg=P["bg1"], fg=P["text2"],
                 font=FM).grid(row=1, column=0, sticky="w", pady=6)
        self.pap_ver_cb = combo(fm, self.pap_ver, ["Loading…"])
        self.pap_ver_cb.grid(row=1, column=1, sticky="w", padx=8, ipady=4)
        self._form_ram(fm, 2, self.pap_rmin, self.pap_rmax)
        tk.Checkbutton(fm, text="I agree to the Minecraft EULA  (minecraft.net/eula)",
                       variable=self.pap_eula, bg=P["bg1"], fg=P["text2"],
                       selectcolor=P["bg3"], activebackground=P["bg1"],
                       font=FM).grid(row=3, column=1, sticky="w", padx=8, pady=6)

        self.pap_prog = ttk.Progressbar(fm, style="G.Horizontal.TProgressbar",
                                         mode="determinate", length=440)
        self.pap_prog.grid(row=4, column=1, padx=8, pady=(8,2), sticky="w")
        self.pap_lbl = tk.Label(fm, text="", bg=P["bg1"], fg=P["text2"], font=FMS)
        self.pap_lbl.grid(row=5, column=1, padx=8, sticky="w")

        btn(fm, "⬇  Download & Create Server", self._create_paper, "primary"
            ).grid(row=6, column=1, padx=8, pady=14, sticky="w", ipady=9)

        threading.Thread(target=lambda: (
            (lambda vs: (
                self.after(0, lambda: self.pap_ver_cb.config(values=vs)),
                self.after(0, lambda: self.pap_ver.set(vs[0]) if vs else None)
            ))(paper_versions())
        ), daemon=True).start()

    def _create_fabric_tab(self, nb):
        f = tk.Frame(nb, bg=P["bg1"]); nb.add(f, text="  🧵 Fabric  ")

        info = tk.Frame(f, bg=P["bg3"], padx=16, pady=10)
        info.pack(fill="x", pady=(10,0))
        tk.Label(info,
                 text="Fabric  ·  Lightweight mod loader. Use with Fabric mods from Modrinth. Players need Fabric client too.",
                 bg=P["bg3"], fg=P["text2"], font=FMS).pack(anchor="w")

        fm = tk.Frame(f, bg=P["bg1"]); fm.pack(fill="x", padx=18, pady=16)

        self.fab_folder = tk.StringVar(value=os.path.join(
            os.path.expanduser("~"), "Desktop", "fabric-server"))
        self.fab_ver    = tk.StringVar(value="1.21.1")
        self.fab_rmin   = tk.StringVar(value=self.cfg.get("ram_min","1"))
        self.fab_rmax   = tk.StringVar(value=self.cfg.get("ram_max","2"))
        self.fab_eula   = tk.BooleanVar(value=True)

        self._form_folder(fm, 0, "Server Folder:", self.fab_folder)
        tk.Label(fm, text="MC Version:", bg=P["bg1"], fg=P["text2"],
                 font=FM).grid(row=1, column=0, sticky="w", pady=6)
        self.fab_ver_cb = combo(fm, self.fab_ver, ["Loading…"])
        self.fab_ver_cb.grid(row=1, column=1, sticky="w", padx=8, ipady=4)
        self._form_ram(fm, 2, self.fab_rmin, self.fab_rmax)
        tk.Checkbutton(fm, text="I agree to the Minecraft EULA",
                       variable=self.fab_eula, bg=P["bg1"], fg=P["text2"],
                       selectcolor=P["bg3"], activebackground=P["bg1"],
                       font=FM).grid(row=3, column=1, sticky="w", padx=8, pady=6)

        self.fab_prog = ttk.Progressbar(fm, style="G.Horizontal.TProgressbar",
                                         mode="determinate", length=440)
        self.fab_prog.grid(row=4, column=1, padx=8, pady=(8,2), sticky="w")
        self.fab_lbl = tk.Label(fm, text="", bg=P["bg1"], fg=P["text2"], font=FMS)
        self.fab_lbl.grid(row=5, column=1, padx=8, sticky="w")

        btn(fm, "⬇  Download & Create Server", self._create_fabric, "primary"
            ).grid(row=6, column=1, padx=8, pady=14, sticky="w", ipady=9)

        threading.Thread(target=lambda: (
            (lambda vs: (
                self.after(0, lambda: self.fab_ver_cb.config(values=vs)),
                self.after(0, lambda: self.fab_ver.set(vs[0]) if vs else None)
            ))(fabric_mc_versions())
        ), daemon=True).start()

    def _create_vanilla_tab(self, nb):
        f = tk.Frame(nb, bg=P["bg1"]); nb.add(f, text="  🍦 Vanilla  ")

        info = tk.Frame(f, bg=P["bg3"], padx=16, pady=10)
        info.pack(fill="x", pady=(10,0))
        tk.Label(info,
                 text="Vanilla  ·  Official Mojang server. No mods or plugins. Pure survival experience.",
                 bg=P["bg3"], fg=P["text2"], font=FMS).pack(anchor="w")

        fm = tk.Frame(f, bg=P["bg1"]); fm.pack(fill="x", padx=18, pady=16)

        self.van_folder = tk.StringVar(value=os.path.join(
            os.path.expanduser("~"), "Desktop", "vanilla-server"))
        self.van_ver    = tk.StringVar(value="1.21.1")
        self.van_rmin   = tk.StringVar(value=self.cfg.get("ram_min","1"))
        self.van_rmax   = tk.StringVar(value=self.cfg.get("ram_max","2"))
        self.van_eula   = tk.BooleanVar(value=True)

        self._form_folder(fm, 0, "Server Folder:", self.van_folder)
        tk.Label(fm, text="MC Version:", bg=P["bg1"], fg=P["text2"],
                 font=FM).grid(row=1, column=0, sticky="w", pady=6)
        self.van_ver_cb = combo(fm, self.van_ver, ["Loading…"])
        self.van_ver_cb.grid(row=1, column=1, sticky="w", padx=8, ipady=4)
        self._form_ram(fm, 2, self.van_rmin, self.van_rmax)
        tk.Checkbutton(fm, text="I agree to the Minecraft EULA",
                       variable=self.van_eula, bg=P["bg1"], fg=P["text2"],
                       selectcolor=P["bg3"], activebackground=P["bg1"],
                       font=FM).grid(row=3, column=1, sticky="w", padx=8, pady=6)

        self.van_prog = ttk.Progressbar(fm, style="G.Horizontal.TProgressbar",
                                         mode="determinate", length=440)
        self.van_prog.grid(row=4, column=1, padx=8, pady=(8,2), sticky="w")
        self.van_lbl = tk.Label(fm, text="", bg=P["bg1"], fg=P["text2"], font=FMS)
        self.van_lbl.grid(row=5, column=1, padx=8, sticky="w")

        btn(fm, "⬇  Download & Create Server", self._create_vanilla, "primary"
            ).grid(row=6, column=1, padx=8, pady=14, sticky="w", ipady=9)

        threading.Thread(target=lambda: (
            (lambda vs: (
                self.after(0, lambda: self.van_ver_cb.config(values=vs)),
                self.after(0, lambda: self.van_ver.set(vs[0]) if vs else None)
            ))(vanilla_versions())
        ), daemon=True).start()

    def _form_folder(self, fm, row, label, var):
        tk.Label(fm, text=label, bg=P["bg1"], fg=P["text2"],
                 font=FM).grid(row=row, column=0, sticky="w", pady=6)
        fr = tk.Frame(fm, bg=P["bg1"])
        fr.grid(row=row, column=1, sticky="ew", padx=8)
        tk.Entry(fr, textvariable=var, bg=P["bg3"], fg=P["text"],
                 insertbackground=P["text"], relief="flat",
                 font=FM, width=42).pack(side="left", ipady=6)
        btn(fr, "Browse",
            lambda v=var: v.set(filedialog.askdirectory() or v.get())
            ).pack(side="left", padx=(6,0), ipady=6)

    def _form_ram(self, fm, row, rmin, rmax):
        tk.Label(fm, text="RAM (GB):", bg=P["bg1"], fg=P["text2"],
                 font=FM).grid(row=row, column=0, sticky="w", pady=6)
        rf = tk.Frame(fm, bg=P["bg1"])
        rf.grid(row=row, column=1, sticky="w", padx=8)
        for ltext, var in [("Min:", rmin), ("Max:", rmax)]:
            tk.Label(rf, text=ltext, bg=P["bg1"], fg=P["text2"],
                     font=FM).pack(side="left")
            tk.Entry(rf, textvariable=var, bg=P["bg3"], fg=P["text"],
                     insertbackground=P["text"], relief="flat",
                     font=FM, width=4).pack(side="left", padx=(3,14), ipady=6)

    def _create_paper(self):
        if not self.pap_eula.get():
            self._toast("Must agree to EULA", warn=True); return
        folder = self.pap_folder.get().strip()
        ver    = self.pap_ver.get()
        if not folder or not ver: return

        def run():
            self.pap_lbl.config(text="Fetching latest build…")
            build = paper_latest_build(ver)
            if not build:
                self.after(0, lambda: self._toast("Could not fetch build info", warn=True)); return
            url, jar_name = paper_url(ver, build)
            os.makedirs(folder, exist_ok=True)
            dest = os.path.join(folder, "server.jar")
            def prog(p):
                self.pap_prog["value"] = p*100
                self.pap_lbl.config(text=f"Downloading Paper {ver} build {build}… {int(p*100)}%")
            result = dl_file(url, dest, prog)
            if result is not True:
                self.after(0, lambda: self._toast(f"Download failed: {result}", warn=True)); return
            self._write_server_files(folder, self.pap_rmin.get(), self.pap_rmax.get(), is_fabric=False)
            srv = {"path": folder, "type": "Paper", "version": ver,
                   "ram_min": self.pap_rmin.get(), "ram_max": self.pap_rmax.get()}
            self.pap_lbl.config(text=f"✓  Done! Paper {ver}")
            self.after(0, lambda: self._on_created(srv))
        threading.Thread(target=run, daemon=True).start()

    def _create_fabric(self):
        if not self.fab_eula.get():
            self._toast("Must agree to EULA", warn=True); return
        folder = self.fab_folder.get().strip()
        ver    = self.fab_ver.get()
        if not folder or not ver: return

        def run():
            self.fab_lbl.config(text="Fetching Fabric meta…")
            loader    = fabric_loader_ver()
            installer = fabric_installer_ver()
            url, jar_name = fabric_url(ver, loader, installer)
            os.makedirs(folder, exist_ok=True)
            os.makedirs(os.path.join(folder, "mods"), exist_ok=True)
            dest = os.path.join(folder, "server.jar")
            def prog(p):
                self.fab_prog["value"] = p*100
                self.fab_lbl.config(text=f"Downloading Fabric {ver}… {int(p*100)}%")
            result = dl_file(url, dest, prog)
            if result is not True:
                self.after(0, lambda: self._toast(f"Download failed: {result}", warn=True)); return
            self._write_server_files(folder, self.fab_rmin.get(), self.fab_rmax.get(), is_fabric=True)
            srv = {"path": folder, "type": "Fabric", "version": ver,
                   "ram_min": self.fab_rmin.get(), "ram_max": self.fab_rmax.get()}
            self.fab_lbl.config(text=f"✓  Done! Fabric {ver}")
            self.after(0, lambda: self._on_created(srv))
        threading.Thread(target=run, daemon=True).start()

    def _create_vanilla(self):
        if not self.van_eula.get():
            self._toast("Must agree to EULA", warn=True); return
        folder = self.van_folder.get().strip()
        ver    = self.van_ver.get()
        if not folder or not ver: return

        def run():
            self.van_lbl.config(text="Fetching version manifest…")
            url, _ = vanilla_url(ver)
            if not url:
                self.after(0, lambda: self._toast("Could not find download URL", warn=True)); return
            os.makedirs(folder, exist_ok=True)
            dest = os.path.join(folder, "server.jar")
            def prog(p):
                self.van_prog["value"] = p*100
                self.van_lbl.config(text=f"Downloading Vanilla {ver}… {int(p*100)}%")
            result = dl_file(url, dest, prog)
            if result is not True:
                self.after(0, lambda: self._toast(f"Download failed: {result}", warn=True)); return
            self._write_server_files(folder, self.van_rmin.get(), self.van_rmax.get(), is_fabric=False)
            srv = {"path": folder, "type": "Vanilla", "version": ver,
                   "ram_min": self.van_rmin.get(), "ram_max": self.van_rmax.get()}
            self.van_lbl.config(text=f"✓  Done! Vanilla {ver}")
            self.after(0, lambda: self._on_created(srv))
        threading.Thread(target=run, daemon=True).start()

    def _write_server_files(self, folder, rmin, rmax, is_fabric=False):
        with open(os.path.join(folder, "eula.txt"), "w") as f:
            f.write("eula=true\n")
        java = self.cfg.get("java_path","java")
        flags = "-XX:+UseG1GC -XX:+ParallelRefProcEnabled -XX:MaxGCPauseMillis=200"
        bat = (f'@echo off\ntitle Minecraft Server\n'
               f'"{java}" {flags} -Xms{rmin}G -Xmx{rmax}G -jar server.jar nogui\npause\n')
        sh  = (f'#!/bin/bash\n'
               f'"{java}" {flags} -Xms{rmin}G -Xmx{rmax}G -jar server.jar nogui\n')
        with open(os.path.join(folder, "start.bat"), "w") as f: f.write(bat)
        with open(os.path.join(folder, "start.sh"),  "w") as f: f.write(sh)
        if platform.system() != "Windows":
            os.chmod(os.path.join(folder, "start.sh"), 0o755)

    def _on_created(self, srv):
        self.cfg.setdefault("servers",[]).append(srv)
        cfg_save(self.cfg)
        self._load(srv)
        self._h_tv_refresh(); self._recent_sb_refresh()
        self._toast(f"✓  Created {srv['type']} {srv['version']}")
        self._nav("home")

    # ══════════════════════════════════════════════════════════════════════════
    #  CONSOLE
    # ══════════════════════════════════════════════════════════════════════════
    def _p_console(self):
        f = self._panel("console", "Console", "Live server output and command input")

        self.con = scrolledtext.ScrolledText(
            f, bg=P["cons"], fg=P["green"], insertbackground=P["text"],
            font=("Consolas", 9), relief="flat", wrap="word", state="disabled")
        self.con.pack(fill="both", expand=True, padx=28, pady=(12,0))
        for tag, col in [("info",P["green"]),("warn",P["amber"]),
                          ("err",P["red"]),("dim",P["text3"]),("cmd",P["teal"])]:
            self.con.tag_config(tag, foreground=col)

        bar = tk.Frame(f, bg=P["bg2"], pady=10)
        bar.pack(fill="x", padx=28, pady=8)
        tk.Label(bar, text=" ❯ ", bg=P["bg2"], fg=P["green"],
                 font=("Consolas", 14, "bold")).pack(side="left")
        self.cmd_v = tk.StringVar()
        ce = tk.Entry(bar, textvariable=self.cmd_v, bg=P["bg3"], fg=P["text"],
                      insertbackground=P["text"], relief="flat",
                      font=("Consolas", 11))
        ce.pack(side="left", fill="x", expand=True, ipady=9)
        ce.bind("<Return>", self._send)
        btn(bar, "Send",  self._send,          "primary").pack(side="left", padx=(8,0), ipady=9)
        btn(bar, "Clear", self._console_clear, "ghost"  ).pack(side="left", padx=(4,0), ipady=9)

    def _console_clear(self):
        self.con.config(state="normal")
        self.con.delete("1.0","end")
        self.con.config(state="disabled")

    # ══════════════════════════════════════════════════════════════════════════
    #  MODS  (Fabric / Modrinth)
    # ══════════════════════════════════════════════════════════════════════════
    def _p_mods(self):
        f = self._panel("mods", "Mods", "Search Modrinth and manage your /mods folder")

        pw = tk.PanedWindow(f, orient="horizontal", bg=P["bg1"],
                            sashwidth=5, sashrelief="flat", sashpad=0)
        pw.pack(fill="both", expand=True, padx=28, pady=12)

        # ── LEFT: installed
        L = tk.Frame(pw, bg=P["bg1"]); pw.add(L, width=320)
        section(L, "INSTALLED MODS").pack(fill="x", pady=(0,6))
        self.mods_lb = tk.Listbox(L, bg=P["bg2"], fg=P["text"],
                                   selectbackground=P["bg4"], selectforeground=P["teal"],
                                   font=FM, relief="flat", activestyle="none", height=18)
        sb_m = tk.Scrollbar(L, orient="vertical", command=self.mods_lb.yview, bg="#1a2230", troughcolor="#0d1117", activebackground="#22d3ee", relief="flat")
        self.mods_lb.configure(yscrollcommand=sb_m.set)
        self.mods_lb.pack(side="left", fill="both", expand=True)
        sb_m.pack(side="right", fill="y")

        br = tk.Frame(L, bg=P["bg1"]); br.pack(fill="x", pady=6)
        btn(br, "⟳ Scan",      self._scan_mods                ).pack(side="left", ipady=5)
        btn(br, "📂 Folder",   self._open_mods_folder,  "ghost").pack(side="left", padx=4, ipady=5)
        btn(br, "🗑 Remove",   self._remove_mod,         "danger").pack(side="left", ipady=5)

        # ── RIGHT: search
        R = tk.Frame(pw, bg=P["bg1"]); pw.add(R)
        section(R, "BROWSE MODRINTH").pack(fill="x", pady=(0,6))

        sr = tk.Frame(R, bg=P["bg1"]); sr.pack(fill="x", pady=(0,8))
        self.mod_q  = tk.StringVar()
        self.mod_loader = tk.StringVar(value="fabric")
        self.mod_gver   = tk.StringVar(value="1.21.1")
        qe = tk.Entry(sr, textvariable=self.mod_q, bg=P["bg3"], fg=P["text"],
                      insertbackground=P["text"], relief="flat", font=FM)
        qe.pack(side="left", fill="x", expand=True, ipady=7)
        qe.bind("<Return>", lambda _: self._search_mods())
        combo(sr, self.mod_loader, ["fabric","quilt","forge","neoforge"], width=10
              ).pack(side="left", padx=4, ipady=4)
        combo(sr, self.mod_gver,
              ["1.21.1","1.21","1.20.6","1.20.4","1.20.1","1.19.4","1.18.2"],
              width=8).pack(side="left", padx=4, ipady=4)
        btn(sr, "Search", self._search_mods, "blue").pack(side="left", padx=(4,0), ipady=7)

        cols = ("Mod","Downloads","Description")
        self.mod_tv = ttk.Treeview(R, columns=cols, show="headings",
                                    height=16, style="TV.Treeview")
        self.mod_tv.heading("Mod",         text="Mod Name")
        self.mod_tv.heading("Downloads",   text="Downloads")
        self.mod_tv.heading("Description", text="Description")
        self.mod_tv.column("Mod",         width=170)
        self.mod_tv.column("Downloads",   width=90)
        self.mod_tv.column("Description", width=360)
        sb2 = tk.Scrollbar(R, orient="vertical", command=self.mod_tv.yview, bg="#1a2230", troughcolor="#0d1117", activebackground="#22d3ee", relief="flat")
        self.mod_tv.configure(yscrollcommand=sb2.set)
        self.mod_tv.pack(side="left", fill="both", expand=True)
        sb2.pack(side="right", fill="y")

        dr = tk.Frame(R, bg=P["bg1"]); dr.pack(fill="x", pady=6, side="bottom")
        self.mod_dl_p = ttk.Progressbar(dr, style="T.Horizontal.TProgressbar",
                                         mode="determinate", length=200)
        self.mod_dl_p.pack(side="left")
        self.mod_dl_lbl = tk.Label(dr, text="", bg=P["bg1"], fg=P["text2"], font=FMS)
        self.mod_dl_lbl.pack(side="left", padx=8)
        btn(dr, "⬇  Install Selected", self._install_mod,  "primary").pack(side="right", ipady=6)
        btn(dr, "↗ Open Page",         self._open_mod_page,"ghost"  ).pack(side="right", padx=6, ipady=6)

    def _scan_mods(self):
        self.mods_lb.delete(0,"end")
        if not self.current: return
        d = os.path.join(self.current["path"], "mods")
        if os.path.isdir(d):
            jars = sorted(f for f in os.listdir(d) if f.endswith(".jar"))
            for j in jars: self.mods_lb.insert("end", f"  ✓  {j}")
            if not jars: self.mods_lb.insert("end","  (no mods installed)")
        else:
            self.mods_lb.insert("end","  /mods folder not found — Fabric only")

    def _open_mods_folder(self):
        if not self.current: self._toast("No server loaded",warn=True); return
        d = os.path.join(self.current["path"],"mods"); os.makedirs(d,exist_ok=True)
        open_folder(d)

    def _remove_mod(self):
        sel = self.mods_lb.curselection()
        if not sel or not self.current: return
        name = self.mods_lb.get(sel[0]).replace("  ✓  ","").strip()
        path = os.path.join(self.current["path"],"mods",name)
        if os.path.isfile(path) and messagebox.askyesno("Remove",f"Delete {name}?"):
            os.remove(path); self._scan_mods(); self._toast(f"Removed {name}")

    def _search_mods(self):
        q = self.mod_q.get().strip()
        if not q: return
        self.mod_tv.delete(*self.mod_tv.get_children())
        self.mod_tv.insert("","end",values=("Searching…","",""))
        def run():
            results = modrinth_search(q, self.mod_loader.get(), self.mod_gver.get())
            self.mod_results = results
            self.after(0, lambda: self._fill_mod_tv(results))
        threading.Thread(target=run,daemon=True).start()

    def _fill_mod_tv(self, results):
        self.mod_tv.delete(*self.mod_tv.get_children())
        if not results:
            self.mod_tv.insert("","end",values=("No results","","")); return
        for r in results:
            self.mod_tv.insert("","end", values=(
                r.get("title","?"),
                f"{r.get('downloads',0):,}",
                r.get("description","")[:80]))

    def _install_mod(self):
        sel = self.mod_tv.selection()
        if not sel: self._toast("Select a mod",warn=True); return
        if not self.current: self._toast("Load a server first",warn=True); return
        idx = self.mod_tv.index(sel[0])
        if not hasattr(self,"mod_results") or idx >= len(self.mod_results): return
        mod = self.mod_results[idx]
        loader  = self.mod_loader.get()
        gver    = self.mod_gver.get()
        mdir    = os.path.join(self.current["path"],"mods")
        os.makedirs(mdir, exist_ok=True)

        def run():
            self.mod_dl_lbl.config(text="Fetching versions…")
            versions = modrinth_mod_versions(mod["project_id"], loader, gver)
            if not versions:
                self.after(0, lambda: self._toast(
                    f"No {loader} version for MC {gver}", warn=True)); return
            files = versions[0].get("files",[])
            pri   = next((fi for fi in files if fi.get("primary")), files[0] if files else None)
            if not pri:
                self.after(0, lambda: self._toast("No file found",warn=True)); return
            url   = pri["url"]
            fname = pri["filename"]
            dest  = os.path.join(mdir, fname)
            def prog(p):
                self.mod_dl_p["value"] = p*100
                self.mod_dl_lbl.config(text=f"{fname[:30]}… {int(p*100)}%")
            result = dl_file(url, dest, prog)
            if result is True:
                self.after(0, lambda: (self._scan_mods(),
                    self._toast(f"✓  Installed {fname}")))
                self.mod_dl_lbl.config(text=f"✓  {fname}")
            else:
                self.after(0, lambda: self._toast(f"Failed: {result}",warn=True))
        threading.Thread(target=run,daemon=True).start()

    def _open_mod_page(self):
        sel = self.mod_tv.selection()
        if sel:
            idx = self.mod_tv.index(sel[0])
            if hasattr(self,"mod_results") and idx < len(self.mod_results):
                slug = self.mod_results[idx].get("slug","")
                webbrowser.open(f"https://modrinth.com/mod/{slug}")

    # ══════════════════════════════════════════════════════════════════════════
    #  PLUGINS  (Paper / Spigot)
    # ══════════════════════════════════════════════════════════════════════════
    def _p_plugins(self):
        f = self._panel("plugins","Plugins","Manage Paper/Spigot plugins")

        pw = tk.PanedWindow(f, orient="horizontal", bg=P["bg1"],
                            sashwidth=5, sashrelief="flat")
        pw.pack(fill="both", expand=True, padx=28, pady=12)

        L = tk.Frame(pw, bg=P["bg1"]); pw.add(L, width=300)
        section(L, "INSTALLED PLUGINS").pack(fill="x", pady=(0,6))
        self.plug_lb = tk.Listbox(L, bg=P["bg2"], fg=P["text"],
                                   selectbackground=P["bg4"], selectforeground=P["teal"],
                                   font=FM, relief="flat", activestyle="none", height=18)
        sb3 = tk.Scrollbar(L, orient="vertical", command=self.plug_lb.yview, bg="#1a2230", troughcolor="#0d1117", activebackground="#22d3ee", relief="flat")
        self.plug_lb.configure(yscrollcommand=sb3.set)
        self.plug_lb.pack(side="left",fill="both",expand=True)
        sb3.pack(side="right",fill="y")
        br = tk.Frame(L, bg=P["bg1"]); br.pack(fill="x",pady=6)
        btn(br,"⟳ Scan",     self._scan_plugins          ).pack(side="left",ipady=5)
        btn(br,"📂 Folder",  self._open_plugins_folder,"ghost").pack(side="left",padx=4,ipady=5)
        btn(br,"🗑 Remove",  self._remove_plugin,"danger"  ).pack(side="left",ipady=5)

        R = tk.Frame(pw, bg=P["bg1"]); pw.add(R)
        section(R,"RECOMMENDED PLUGINS  ·  double-click to open download page"
                ).pack(fill="x",pady=(0,6))
        cols2 = ("Plugin","Category","Description")
        self.plug_tv = ttk.Treeview(R, columns=cols2, show="headings",
                                     height=18, style="TV.Treeview")
        self.plug_tv.heading("Plugin",      text="Plugin")
        self.plug_tv.heading("Category",    text="Category")
        self.plug_tv.heading("Description", text="Description")
        self.plug_tv.column("Plugin",       width=140)
        self.plug_tv.column("Category",     width=90)
        self.plug_tv.column("Description",  width=400)
        sb4 = tk.Scrollbar(R, orient="vertical", command=self.plug_tv.yview, bg="#1a2230", troughcolor="#0d1117", activebackground="#22d3ee", relief="flat")
        self.plug_tv.configure(yscrollcommand=sb4.set)
        self.plug_tv.pack(side="left",fill="both",expand=True)
        sb4.pack(side="right",fill="y")
        for name,cat,desc,_ in CURATED_PLUGINS:
            self.plug_tv.insert("","end",values=(name,cat,desc))
        self.plug_tv.bind("<Double-1>", self._open_plugin_page)

        dr2 = tk.Frame(R, bg=P["bg1"]); dr2.pack(fill="x",pady=6,side="bottom")
        btn(dr2,"↗ Open Download Page", self._open_plugin_page,"blue"
            ).pack(side="left",ipady=6)
        tk.Label(dr2,text="  download .jar → drop into /plugins → restart",
                 bg=P["bg1"],fg=P["text3"],font=FMS).pack(side="left")

    def _scan_plugins(self):
        self.plug_lb.delete(0,"end")
        if not self.current: return
        d = os.path.join(self.current["path"],"plugins")
        if os.path.isdir(d):
            jars = sorted(f for f in os.listdir(d) if f.endswith(".jar"))
            for j in jars: self.plug_lb.insert("end",f"  ✓  {j}")
            if not jars: self.plug_lb.insert("end","  (no plugins installed)")
        else:
            self.plug_lb.insert("end","  /plugins folder not found")

    def _open_plugins_folder(self):
        if not self.current: self._toast("No server loaded",warn=True); return
        d = os.path.join(self.current["path"],"plugins"); os.makedirs(d,exist_ok=True)
        open_folder(d)

    def _remove_plugin(self):
        sel = self.plug_lb.curselection()
        if not sel or not self.current: return
        name = self.plug_lb.get(sel[0]).replace("  ✓  ","").strip()
        path = os.path.join(self.current["path"],"plugins",name)
        if os.path.isfile(path) and messagebox.askyesno("Remove",f"Delete {name}?"):
            os.remove(path); self._scan_plugins(); self._toast(f"Removed {name}")

    def _open_plugin_page(self, _=None):
        sel = self.plug_tv.selection()
        if sel:
            idx = self.plug_tv.index(sel[0])
            if idx < len(CURATED_PLUGINS):
                webbrowser.open(CURATED_PLUGINS[idx][3])

    # ══════════════════════════════════════════════════════════════════════════
    #  SERVER.PROPERTIES
    # ══════════════════════════════════════════════════════════════════════════
    def _p_properties(self):
        f = self._panel("properties","server.properties","Edit server configuration")

        # quick settings
        qs = tk.Frame(f, bg=P["bg2"], padx=18, pady=14)
        qs.pack(fill="x", padx=28, pady=14)
        tk.Label(qs, text="QUICK SETTINGS", bg=P["bg2"], fg=P["text3"],
                 font=("Consolas",8,"bold")).grid(row=0,column=0,columnspan=6,sticky="w",pady=(0,8))

        self.qs = {}
        QS = [
            ("gamemode",   "Gamemode",    ["survival","creative","adventure","spectator"]),
            ("difficulty", "Difficulty",  ["easy","normal","hard","peaceful"]),
            ("max-players","Max Players", None),
            ("online-mode","Online Mode", ["true","false"]),
            ("pvp",        "PVP",         ["true","false"]),
            ("level-name", "World Name",  None),
            ("motd",       "MOTD",        None),
            ("server-port","Port",        None),
            ("enforce-secure-profile","Secure Profile",["false","true"]),
        ]
        for i,(key,label,opts) in enumerate(QS):
            col = (i%3)*2; row = i//3+1
            tk.Label(qs,text=label+":",bg=P["bg2"],fg=P["text2"],
                     font=FMS).grid(row=row,column=col,sticky="w",padx=(0,4),pady=3)
            var = tk.StringVar(); self.qs[key] = var
            if opts:
                w = ttk.Combobox(qs,textvariable=var,values=opts,
                                 font=FMS,style="Dark.TCombobox",state="readonly",width=13)
            else:
                w = tk.Entry(qs,textvariable=var,bg=P["bg3"],fg=P["text"],
                             insertbackground=P["text"],relief="flat",font=FMS,width=15)
            w.grid(row=row,column=col+1,sticky="w",padx=(0,18),ipady=4)

        br2 = tk.Frame(qs, bg=P["bg2"])
        br2.grid(row=5, column=0, columnspan=6, sticky="w", pady=(10,0))
        btn(br2,"📂 Load",          self._props_load,  "ghost"  ).pack(side="left",ipady=6)
        btn(br2,"⚡ Apply & Save",   self._props_apply, "primary").pack(side="left",padx=6,ipady=6)
        btn(br2,"📂 Open Folder",   lambda: self.current and open_folder(self.current["path"]),
            "ghost").pack(side="right",ipady=6)

        section(f,"RAW EDITOR").pack(fill="x",padx=28,pady=(0,4))
        self.props_ed = scrolledtext.ScrolledText(
            f, bg=P["cons"], fg=P["text"], insertbackground=P["text"],
            font=FMS, relief="flat")
        self.props_ed.pack(fill="both",expand=True,padx=28,pady=(0,16))

    def _props_load(self):
        if not self.current: self._toast("No server loaded",warn=True); return
        pf = os.path.join(self.current["path"],"server.properties")
        if os.path.isfile(pf):
            with open(pf) as f: content = f.read()
            self.props_ed.delete("1.0","end")
            self.props_ed.insert("1.0",content)
            for key,var in self.qs.items():
                m = re.search(rf"^{re.escape(key)}=(.*)$",content,re.MULTILINE)
                if m: var.set(m.group(1).strip())
            self._toast("Loaded server.properties")
        else:
            self._toast("server.properties not found — start server once",warn=True)

    def _props_load_silent(self):
        if not self.current: return
        pf = os.path.join(self.current["path"],"server.properties")
        if os.path.isfile(pf):
            with open(pf) as f: content = f.read()
            self.props_ed.delete("1.0","end")
            self.props_ed.insert("1.0",content)
            for key,var in self.qs.items():
                m = re.search(rf"^{re.escape(key)}=(.*)$",content,re.MULTILINE)
                if m: var.set(m.group(1).strip())

    def _props_apply(self):
        if not self.current: self._toast("No server loaded",warn=True); return
        content = self.props_ed.get("1.0","end-1c")
        for key,var in self.qs.items():
            val = var.get().strip()
            if not val: continue
            if re.search(rf"^{re.escape(key)}=",content,re.MULTILINE):
                content = re.sub(rf"^{re.escape(key)}=.*$",f"{key}={val}",
                                 content,flags=re.MULTILINE)
            else:
                content += f"\n{key}={val}"
        pf = os.path.join(self.current["path"],"server.properties")
        try:
            with open(pf,"w") as f: f.write(content)
            self.props_ed.delete("1.0","end")
            self.props_ed.insert("1.0",content)
            self._toast("✓  server.properties saved (restart to apply)")
        except Exception as e:
            self._toast(f"Save failed: {e}",warn=True)

    # ══════════════════════════════════════════════════════════════════════════
    #  PLAYIT.GG TUNNEL
    # ══════════════════════════════════════════════════════════════════════════
    def _p_playit(self):
        f = self._panel("playit","playit.gg  Tunnel",
                        "Expose your server to the internet without port forwarding — free!")

        # How it works box
        how = tk.Frame(f, bg=P["bg3"], padx=18, pady=14)
        how.pack(fill="x", padx=28, pady=(12,0))
        tk.Label(how, text="How it works", bg=P["bg3"], fg=P["teal"],
                 font=FMH).pack(anchor="w")
        steps = (
            "1.  Download the playit.gg agent below.\n"
            "2.  Run it once — it opens a browser link for a free account.\n"
            "3.  Click 'Start Tunnel' here after your server is running.\n"
            "4.  Your public address appears in the tunnel output below.\n"
            "5.  Share that address with friends  (e.g. funny-word.joinmc.link)"
        )
        tk.Label(how, text=steps, bg=P["bg3"], fg=P["text2"],
                 font=FMS, justify="left").pack(anchor="w", pady=(4,0))

        # Path row
        pr = tk.Frame(f, bg=P["bg1"]); pr.pack(fill="x", padx=28, pady=14)
        tk.Label(pr, text="playit.exe Path:", bg=P["bg1"], fg=P["text2"],
                 font=FM).pack(side="left")
        self.playit_path_v = tk.StringVar(value=self.cfg.get("playit_path",""))
        tk.Entry(pr, textvariable=self.playit_path_v, bg=P["bg3"], fg=P["text"],
                 insertbackground=P["text"], relief="flat", font=FM, width=48
                 ).pack(side="left", fill="x", expand=True, ipady=6, padx=8)
        btn(pr, "Browse", self._playit_browse).pack(side="left", ipady=6)

        # buttons
        cr = tk.Frame(f, bg=P["bg1"]); cr.pack(fill="x", padx=28, pady=(0,8))
        btn(cr, "⬇  Download playit",     self._playit_download,     "blue"   ).pack(side="left", ipady=7)
        btn(cr, "▶  Start Tunnel",         self._playit_start,        "primary").pack(side="left", padx=8, ipady=7)
        btn(cr, "■  Stop Tunnel",          self._playit_stop,         "danger" ).pack(side="left", ipady=7)
        btn(cr, "↗ playit.gg Dashboard",
            lambda: webbrowser.open("https://playit.gg"), "ghost").pack(side="right", ipady=7)

        self.playit_prog = ttk.Progressbar(f, style="T.Horizontal.TProgressbar",
                                            mode="determinate", length=400)
        self.playit_prog.pack(anchor="w", padx=28, pady=(0,4))
        self.playit_dl_lbl = tk.Label(f, text="", bg=P["bg1"], fg=P["text2"], font=FMS)
        self.playit_dl_lbl.pack(anchor="w", padx=28)

        section(f,"TUNNEL OUTPUT").pack(fill="x", padx=28, pady=(10,4))
        self.playit_con = scrolledtext.ScrolledText(
            f, bg=P["cons"], fg=P["teal"], font=FMS,
            relief="flat", state="disabled", height=14)
        self.playit_con.pack(fill="both", expand=True, padx=28, pady=(0,16))
        self.playit_con.tag_config("warn", foreground=P["amber"])
        self.playit_con.tag_config("addr", foreground=P["green"])
        self.playit_con.tag_config("err",  foreground=P["red"])

    def _playit_browse(self):
        f = filedialog.askopenfilename(
            title="Select playit executable",
            filetypes=[("Executable","*.exe *.bin *"),("All","*")])
        if f:
            self.playit_path_v.set(f)
            self.cfg["playit_path"] = f
            cfg_save(self.cfg)

    def _playit_download(self):
        sys_ = platform.system()
        url  = PLAYIT_URLS.get(sys_, PLAYIT_URLS["Linux"])
        ext  = ".exe" if sys_ == "Windows" else ""
        dest = os.path.join(os.path.expanduser("~"), f"playit{ext}")

        def run():
            self.playit_dl_lbl.config(text="Downloading playit agent…")
            def prog(p):
                self.playit_prog["value"] = p*100
                self.playit_dl_lbl.config(text=f"Downloading playit… {int(p*100)}%")
            result = dl_file(url, dest, prog)
            if result is True:
                if sys_ != "Windows":
                    os.chmod(dest, 0o755)
                self.playit_path_v.set(dest)
                self.cfg["playit_path"] = dest
                cfg_save(self.cfg)
                self.playit_dl_lbl.config(text=f"✓  Saved to {dest}")
                self.after(0, lambda: self._toast("✓  playit downloaded!"))
            else:
                self.after(0, lambda: self._toast(f"Download failed: {result}", warn=True))
        threading.Thread(target=run, daemon=True).start()

    def _playit_start(self):
        exe = self.playit_path_v.get().strip()
        if not exe or not os.path.isfile(exe):
            self._toast("Set playit path first (or download it)", warn=True); return
        if self.playit_proc:
            self._toast("Tunnel already running", warn=True); return
        try:
            self.playit_proc = subprocess.Popen(
                [exe], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1)
            self.playit_on = True
            self._playit_log("[Manager] playit tunnel started…\n")
            threading.Thread(target=self._playit_read, daemon=True).start()
        except Exception as e:
            self._toast(f"Failed: {e}", warn=True)

    def _playit_stop(self):
        if self.playit_proc:
            try: self.playit_proc.terminate()
            except: pass
            self.playit_proc = None
            self.playit_on   = False
            self._playit_log("[Manager] Tunnel stopped.\n", "warn")

    def _playit_read(self):
        for line in self.playit_proc.stdout:
            tag = "addr" if ".joinmc.link" in line or ".ply.gg" in line else None
            if "WARN" in line.upper(): tag = "warn"
            if "ERROR" in line.upper(): tag = "err"
            self.after(0, lambda l=line, t=tag: self._playit_log(l, t))
        self.playit_on = False
        self.playit_proc = None

    def _playit_log(self, text, tag=None):
        self.playit_con.config(state="normal")
        self.playit_con.insert("end", text, tag or "")
        self.playit_con.see("end")
        self.playit_con.config(state="disabled")

    # ══════════════════════════════════════════════════════════════════════════
    #  SETTINGS
    # ══════════════════════════════════════════════════════════════════════════
    def _p_settings(self):
        f = self._panel("settings","Settings","Java path, RAM, and app preferences")

        fm = tk.Frame(f, bg=P["bg1"]); fm.pack(fill="x", padx=28, pady=16)

        section(fm,"JAVA").pack(fill="x",pady=(0,8))

        jr = tk.Frame(fm, bg=P["bg1"]); jr.pack(fill="x",pady=4)
        tk.Label(jr,text="Java Path:",bg=P["bg1"],fg=P["text2"],
                 font=FM,width=18,anchor="w").pack(side="left")
        self.java_v = tk.StringVar(value=self.cfg.get("java_path",java_detect()))
        je = tk.Entry(jr,textvariable=self.java_v,bg=P["bg3"],fg=P["text"],
                      insertbackground=P["text"],relief="flat",font=FM)
        je.pack(side="left",fill="x",expand=True,ipady=6,padx=(6,8))
        btn(jr,"Auto-Detect",self._java_detect).pack(side="left",ipady=6)
        btn(jr,"Browse",     self._java_browse).pack(side="left",padx=4,ipady=6)

        self.java_lbl = tk.Label(fm,text="",bg=P["bg1"],fg=P["text2"],font=FMS)
        self.java_lbl.pack(anchor="w",pady=(0,10))
        self._java_check()

        section(fm,"DEFAULT RAM").pack(fill="x",pady=(8,8))
        rr = tk.Frame(fm,bg=P["bg1"]); rr.pack(fill="x",pady=4)
        self.def_rmin = tk.StringVar(value=self.cfg.get("ram_min","1"))
        self.def_rmax = tk.StringVar(value=self.cfg.get("ram_max","2"))
        for ltext,var in [("Min (GB):",self.def_rmin),("Max (GB):",self.def_rmax)]:
            tk.Label(rr,text=ltext,bg=P["bg1"],fg=P["text2"],font=FM).pack(side="left")
            tk.Entry(rr,textvariable=var,bg=P["bg3"],fg=P["text"],
                     insertbackground=P["text"],relief="flat",font=FM,width=5
                     ).pack(side="left",padx=(3,18),ipady=6)

        sep(fm).pack(fill="x",pady=14)

        btn(fm,"💾  Save Settings",self._settings_save,"primary").pack(anchor="w",ipady=8)

        sep(fm).pack(fill="x",pady=14)

        # Java download info
        info = tk.Frame(fm,bg=P["bg2"],padx=16,pady=12); info.pack(fill="x")
        tk.Label(info,text="Need Java 21?",bg=P["bg2"],fg=P["teal"],font=FMB).pack(anchor="w")
        tk.Label(info,
                 text="Download Eclipse Temurin 21 (free, recommended for Minecraft 1.17+):",
                 bg=P["bg2"],fg=P["text2"],font=FMS).pack(anchor="w")
        btn(info,"Open adoptium.net",
            lambda: webbrowser.open("https://adoptium.net/temurin/releases/?version=21"),
            "ghost").pack(anchor="w",pady=(6,0),ipady=5)

    def _java_detect(self):
        self.java_v.set(java_detect()); self._java_check()

    def _java_browse(self):
        f = filedialog.askopenfilename(title="Select java executable",
                                       filetypes=[("All","*"),("EXE","*.exe")])
        if f: self.java_v.set(f); self._java_check()

    def _java_check(self):
        def run():
            ver = java_ver(self.java_v.get())
            ok  = ver not in ("not found","unknown")
            self.after(0, lambda: self.java_lbl.config(
                text=f"  Detected: Java {ver}",
                fg=P["green"] if ok else P["red"]))
        threading.Thread(target=run,daemon=True).start()

    def _settings_save(self):
        self.cfg["java_path"] = self.java_v.get()
        self.cfg["ram_min"]   = self.def_rmin.get()
        self.cfg["ram_max"]   = self.def_rmax.get()
        cfg_save(self.cfg)
        self._toast("✓  Settings saved")

    # ══════════════════════════════════════════════════════════════════════════
    #  SERVER CONTROL
    # ══════════════════════════════════════════════════════════════════════════
    def srv_start(self):
        if not self.current:
            self._toast("Load or create a server first",warn=True)
            self._nav("home"); return
        jar = find_jar(self.current["path"])
        if not jar: self._toast("No server .jar found",warn=True); return
        java    = self.cfg.get("java_path","java")
        ram_min = self.current.get("ram_min", self.cfg.get("ram_min","1"))
        ram_max = self.current.get("ram_max", self.cfg.get("ram_max","2"))
        flags   = ["-XX:+UseG1GC","-XX:+ParallelRefProcEnabled",
                   "-XX:MaxGCPauseMillis=200","-XX:+DisableExplicitGC"]
        cmd     = [java, f"-Xms{ram_min}G", f"-Xmx{ram_max}G"] + flags + ["-jar", jar, "nogui"]
        try:
            self.server_proc = subprocess.Popen(
                cmd, cwd=self.current["path"],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, text=True, bufsize=1)
            self.running = True
            self._ctrl(True)
            self._clog(f"[Manager] ▶ Started: {' '.join(cmd)}\n","info")
            self._nav("console")
            threading.Thread(target=self._read_proc, daemon=True).start()
        except FileNotFoundError:
            self._toast("Java not found! Check Settings",warn=True)
        except Exception as e:
            self._toast(f"Failed: {e}",warn=True)

    def srv_stop(self):
        if self.server_proc:
            self._raw("stop")
            threading.Thread(target=self._wait_stop, daemon=True).start()

    def srv_restart(self):
        self.srv_stop()
        self.after(5000, self.srv_start)

    def _wait_stop(self):
        try: self.server_proc.wait(timeout=20)
        except: self.server_proc.kill()
        self.running = False; self.server_proc = None
        self.after(100, lambda: self._ctrl(False))
        self._clog("[Manager] ■ Server stopped.\n","warn")

    def _read_proc(self):
        for line in self.server_proc.stdout:
            self.log_q.put(line)
        self.running = False
        self.log_q.put("[Manager] Process ended.\n")

    def _poll(self):
        try:
            while True:
                line = self.log_q.get_nowait()
                self._clog(line)
        except queue.Empty: pass
        self.after(80, self._poll)

    def _clog(self, text, tag=None):
        if not tag:
            up = text.upper()
            if   "ERROR" in up or "EXCEPTION" in up: tag = "err"
            elif "WARN"  in up:                       tag = "warn"
            elif "[MANAGER]" in up:                   tag = "info"
            else:                                     tag = "dim"
        self.con.config(state="normal")
        self.con.insert("end", text, tag)
        self.con.see("end")
        self.con.config(state="disabled")

    def _send(self, _=None):
        c = self.cmd_v.get().strip()
        if not c: return
        self._raw(c)
        self._clog(f"❯ {c}\n","cmd")
        self.cmd_v.set("")

    def _raw(self, cmd):
        if self.server_proc and self.server_proc.stdin:
            try:
                self.server_proc.stdin.write(cmd+"\n")
                self.server_proc.stdin.flush()
            except: pass

    def _ctrl(self, on):
        self.b_start.config(  state="disabled" if on  else "normal")
        self.b_stop.config(   state="normal"   if on  else "disabled")
        self.b_restart.config(state="normal"   if on  else "disabled")

    def _tick(self):
        if self.running:
            self.top_status.config(text="● ONLINE",  fg=P["green"])
            self.c_status.config(  text="ONLINE",    fg=P["green"])
        else:
            self.top_status.config(text="● OFFLINE", fg=P["red"])
            self.c_status.config(  text="OFFLINE",   fg=P["red"])
        if self.playit_on:
            self.top_playit.config(text="playit: ON",  fg=P["teal"])
        else:
            self.top_playit.config(text="playit: OFF", fg=P["text3"])
        self.after(1500, self._tick)

    # ── toast notification ────────────────────────────────────────────────────
    def _toast(self, msg, warn=False):
        t = tk.Toplevel(self)
        t.overrideredirect(True)
        t.attributes("-topmost", True)
        bg = P["bg3"] if not warn else "#3d1e00"
        fg = P["green"] if not warn else P["amber"]
        tk.Label(t, text=f"  {msg}  ", bg=bg, fg=fg,
                 font=FMB, padx=12, pady=10).pack()
        t.update_idletasks()
        x = self.winfo_x() + self.winfo_width()//2  - t.winfo_width()//2
        y = self.winfo_y() + self.winfo_height() - 80
        t.geometry(f"+{x}+{y}")
        t.after(2800, t.destroy)

    def on_close(self):
        if self.running:
            if messagebox.askyesno("Exit","Server is running. Stop it before closing?"):
                self.srv_stop()
                self.after(4000, self.destroy)
                return
        if self.playit_proc:
            try: self.playit_proc.terminate()
            except: pass
        self.destroy()

# ─────────────────────────────────────────────────────────────────────────────
#  ENTRY
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = App()
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    app.mainloop()

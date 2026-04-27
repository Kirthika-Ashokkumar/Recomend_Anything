"""
app.py  —  Tkinter UI for Recommend Anything.
Requires: DB_interface.py  model.py  (same directory)

Pages
─────
  LoginPage     sign in
  RegisterPage  create account
  HomePage      feed from followed users + direct sends; sidebar tag filter
  DiscoverPage  search users by username, follow them
  PostPage      create recommendation, optionally target specific followers
  AdminPage     admin-only: browse all posts (filter by tag), delete posts

NOTE ON BUTTONS
  tk.Button ignores bg/fg on macOS (native renderer takes over).
  We use tk.Label with mouse bindings instead — colours always respected.
"""

import tkinter as tk
from tkinter import messagebox
import time
import webbrowser
import urllib.request
import threading
from io import BytesIO

try:
    from PIL import Image, ImageTk
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

# ── Palette ──────────────────────────────────────────────────────────────────
BG       = "#0b0b0f"
SURFACE  = "#13131a"
CARD     = "#1e1e2e"
BORDER   = "#3a3a5c"
ACCENT   = "#7c6af7"   # purple  — primary action
ACCENT2  = "#f06292"   # pink    — register stripe / errors
TEXT     = "#d0ceea"   # light lavender body text
MUTED    = "#7a789a"   # dimmed labels
SUCCESS  = "#3ecf8e"   # green confirmation
DANGER   = "#f05c5c"   # red delete
WARNING  = "#f0a05a"   # amber — partial success
STAR_ON  = "#f5c842"
STAR_OFF = "#3a3a5c"

# Button colour sets  (bg, fg, hover_bg)
_C_ACCENT  = (ACCENT,   "#ffffff", "#9d8fff")
_C_DANGER  = (DANGER,   "#ffffff", "#ff7c7c")
_C_NEUTRAL = ("#2a2a45", TEXT,     "#3c3c60")

FH   = ("Georgia",    24, "bold")
FS   = ("Georgia",    13, "italic")
FL   = ("Courier New", 11)
FB   = ("Courier New", 12)
FM   = ("Courier New", 10)
FBIG = ("Georgia",    32, "bold")
FN   = ("Courier New", 11, "bold")


# ── Helpers ───────────────────────────────────────────────────────────────────

def btn(parent, text, cmd, accent=False, danger=False, small=False):
    """
    Label-based button — always respects bg/fg on every platform.
    """
    bg, fg, hov = _C_ACCENT if accent else (_C_DANGER if danger else _C_NEUTRAL)
    pad_x = 12 if small else 20
    pad_y = 5  if small else 10
    font  = ("Courier New", 10) if small else FB

    lbl = tk.Label(
        parent, text=text, bg=bg, fg=fg,
        font=font, cursor="hand2",
        padx=pad_x, pady=pad_y,
        relief="flat"
    )
    lbl.bind("<Enter>",       lambda _: lbl.config(bg=hov, fg="#ffffff"))
    lbl.bind("<Leave>",       lambda _: lbl.config(bg=bg,  fg=fg))
    lbl.bind("<ButtonPress-1>",   lambda _: lbl.config(bg=hov))
    lbl.bind("<ButtonRelease-1>", lambda e: (lbl.config(bg=bg, fg=fg), cmd()))
    return lbl


def entry(parent, show=None, width=32):
    return tk.Entry(
        parent, bg=CARD, fg=TEXT, insertbackground=ACCENT,
        relief="flat", font=FB, bd=0,
        highlightthickness=1, highlightbackground=BORDER,
        highlightcolor=ACCENT, width=width, show=show or ""
    )


def sep(parent):
    tk.Frame(parent, bg=BORDER, height=1).pack(fill="x", pady=6)


def chip(parent, text, bg_col=None):
    c = bg_col or ACCENT
    f = tk.Frame(parent, bg=c, padx=6, pady=2)
    tk.Label(f, text=f"#{text}", bg=c, fg="#ffffff", font=FM).pack()
    return f


def stars(parent, rating, bg_col=None):
    bg_col = bg_col or CARD
    f = tk.Frame(parent, bg=bg_col)
    for i in range(1, 6):
        tk.Label(f, text="★", bg=bg_col,
                 fg=STAR_ON if i <= rating else STAR_OFF,
                 font=("Georgia", 13)).pack(side="left")
    return f


def _is_image_url(url: str) -> bool:
    """Guess if a URL points to an image by its extension."""
    low = url.lower().split("?")[0]  # strip query params
    return any(low.endswith(ext) for ext in (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"))


def _widget_alive(w) -> bool:
    """Return True if a tkinter widget still exists and hasn't been destroyed."""
    try:
        return bool(w.winfo_exists())
    except Exception:
        return False


def _media_widget(parent, url: str):
    """
    Render a media URL in a card:
    - If it looks like an image AND Pillow is installed: fetch and display inline,
      with a fallback link if the fetch fails.
    - Otherwise: show a clickable link label that opens in the browser.
    """
    if PIL_AVAILABLE and _is_image_url(url):
        frame = tk.Frame(parent, bg=CARD)
        frame.pack(anchor="w", pady=(2, 4))
        loading = tk.Label(frame, text="⏳ loading image…", bg=CARD, fg=MUTED, font=FM)
        loading.pack(anchor="w")

        def fetch():
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=8) as resp:
                    data = resp.read()
                img = Image.open(BytesIO(data))
                img.thumbnail((480, 320), Image.LANCZOS)
                photo = ImageTk.PhotoImage(img)
                # Guard: only schedule UI update if the widget still exists
                if _widget_alive(loading):
                    loading.after(0, lambda: _show_image(frame, loading, photo, url))
            except Exception:
                if _widget_alive(loading):
                    loading.after(0, lambda: _fallback_link(frame, loading, url))

        threading.Thread(target=fetch, daemon=True).start()
    else:
        _link_label(parent, url)


def _show_image(frame, placeholder, photo, url):
    # Guard: the card may have been destroyed while the image was fetching
    if not _widget_alive(placeholder):
        return
    placeholder.destroy()
    if not _widget_alive(frame):
        return
    lbl = tk.Label(frame, image=photo, bg=CARD, cursor="hand2")
    lbl.image = photo  # keep reference so GC doesn't collect it
    lbl.pack(anchor="w")
    lbl.bind("<ButtonRelease-1>", lambda _: webbrowser.open(url))
    cap = tk.Label(frame, text=url, bg=CARD, fg=ACCENT, font=FM,
                   cursor="hand2", wraplength=480)
    cap.pack(anchor="w")
    cap.bind("<ButtonRelease-1>", lambda _: webbrowser.open(url))


def _fallback_link(frame, placeholder, url):
    if not _widget_alive(placeholder):
        return
    placeholder.destroy()
    if not _widget_alive(frame):
        return
    _link_label(frame, url)


def _link_label(parent, url: str):
    """A purple underline-style label that opens the URL in the browser on click."""
    lbl = tk.Label(parent, text=url, bg=CARD, fg=ACCENT, font=FM,
                   cursor="hand2", wraplength=540, justify="left")
    lbl.pack(anchor="w", pady=1)
    lbl.bind("<Enter>",           lambda _: lbl.config(fg="#b0a0ff"))
    lbl.bind("<Leave>",           lambda _: lbl.config(fg=ACCENT))
    lbl.bind("<ButtonRelease-1>", lambda _: webbrowser.open(url))


# ── Scrollable frame ──────────────────────────────────────────────────────────

class ScrollFrame(tk.Frame):
    def __init__(self, parent, bg=None, **kw):
        bg = bg or BG
        super().__init__(parent, bg=bg, **kw)
        c  = tk.Canvas(self, bg=bg, bd=0, highlightthickness=0)
        sb = tk.Scrollbar(self, orient="vertical", command=c.yview)
        self.inner = tk.Frame(c, bg=bg)
        self.inner.bind("<Configure>", lambda _: c.configure(scrollregion=c.bbox("all")))
        c.create_window((0, 0), window=self.inner, anchor="nw")
        c.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        c.pack(side="left", fill="both", expand=True)
        c.bind("<Enter>",  lambda _: c.bind_all("<MouseWheel>",
               lambda e: c.yview_scroll(int(-1*(e.delta/120)), "units")))
        c.bind("<Leave>",  lambda _: c.unbind_all("<MouseWheel>"))


# ── Nav bar ───────────────────────────────────────────────────────────────────

class NavBar(tk.Frame):
    def __init__(self, parent, app, active=""):
        super().__init__(parent, bg=SURFACE)
        self.pack(fill="x", side="top")

        tk.Label(self, text="Recommend Anything.", bg=SURFACE, fg=ACCENT,
                 font=("Georgia", 15, "bold"), padx=20, pady=12).pack(side="left")

        r = tk.Frame(self, bg=SURFACE)
        r.pack(side="right", padx=16, pady=8)

        pages = [("Home", "HomePage"), ("Discover", "DiscoverPage"), ("Post", "PostPage")]
        _, _, role = app.current_user or (None, None, 0)
        if role == 1:
            pages.append(("Admin", "AdminPage"))

        for label, name in pages:
            is_active = name.lower().startswith(active.lower())
            # Nav links are Labels too — same reason
            lnk = tk.Label(
                r, text=label, bg=SURFACE,
                fg=ACCENT if is_active else MUTED,
                font=FN, cursor="hand2", padx=10, pady=6
            )
            lnk.bind("<Enter>", lambda e, l=lnk: l.config(fg=ACCENT))
            lnk.bind("<Leave>", lambda e, l=lnk, n=name: l.config(
                fg=ACCENT if n.lower().startswith(active.lower()) else MUTED))
            lnk.bind("<ButtonRelease-1>", lambda e, n=name: app.show(n))
            lnk.pack(side="left")

        tk.Frame(r, bg=BORDER, width=1).pack(side="left", fill="y", padx=8)

        if app.current_user:
            _, uname, _ = app.current_user
            tk.Label(r, text=uname, bg=SURFACE, fg=TEXT, font=FM, padx=6).pack(side="left")

        so = tk.Label(r, text="sign out", bg=SURFACE, fg=MUTED, font=FN,
                      cursor="hand2", padx=6)
        so.bind("<Enter>", lambda _: so.config(fg=ACCENT2))
        so.bind("<Leave>", lambda _: so.config(fg=MUTED))
        so.bind("<ButtonRelease-1>", lambda _: app.logout())
        so.pack(side="left")


# ═════════════════════════════════════════════════════════════════════════════
#  APP SHELL
# ═════════════════════════════════════════════════════════════════════════════

class App(tk.Tk):
    def __init__(self, db):
        super().__init__()
        self.db           = db
        self.current_user = None   # (user_id, username, role)

        self.title("Recommend Anything.")
        self.geometry("1020x700")
        self.minsize(800, 560)
        self.configure(bg=BG)

        self._container = tk.Frame(self, bg=BG)
        self._container.pack(fill="both", expand=True)
        self._container.grid_rowconfigure(0, weight=1)
        self._container.grid_columnconfigure(0, weight=1)

        self._frames = {}
        for Cls in (LoginPage, RegisterPage, HomePage,
                    DiscoverPage, PostPage, AdminPage):
            f = Cls(self._container, self)
            self._frames[Cls.__name__] = f
            f.grid(row=0, column=0, sticky="nsew")

        self.show("LoginPage")

    def show(self, name, **kw):
        f = self._frames[name]
        if hasattr(f, "on_show"):
            f.on_show(**kw)
        f.tkraise()

    def login(self, uid, username, role):
        self.current_user = (uid, username, role)
        self.show("HomePage")

    def logout(self):
        self.current_user = None
        self.show("LoginPage")


# ═════════════════════════════════════════════════════════════════════════════
#  LOGIN
# ═════════════════════════════════════════════════════════════════════════════

class LoginPage(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=BG)
        self.app = app
        self._build()

    def _build(self):
        tk.Frame(self, bg=ACCENT, width=4).pack(side="left", fill="y")

        c = tk.Frame(self, bg=BG)
        c.pack(expand=True)

        tk.Label(c, text="Recommend Anything.", bg=BG, fg=ACCENT, font=FBIG).pack(pady=(0, 4))
        tk.Label(c, text="share what's worth sharing.", bg=BG, fg=MUTED, font=FS).pack(pady=(0, 36))

        box = tk.Frame(c, bg=SURFACE, padx=44, pady=40,
                       highlightthickness=1, highlightbackground=BORDER)
        box.pack(ipadx=8)

        self._u = self._field(box, "USERNAME")
        self._p = self._field(box, "PASSWORD", show="•")
        self._p.bind("<Return>", lambda _: self._go())

        btn(box, "Sign In",        self._go,                    accent=True).pack(fill="x", pady=(8, 6))
        tk.Label(box, text="— or —", bg=SURFACE, fg=MUTED, font=FM).pack()
        btn(box, "Create Account", lambda: self.app.show("RegisterPage")).pack(fill="x", pady=(6, 0))

        self._err = tk.Label(c, text="", bg=BG, fg=ACCENT2, font=FL)
        self._err.pack(pady=6)

    def _field(self, parent, label, show=None):
        tk.Label(parent, text=label, bg=SURFACE, fg=MUTED, font=FL).pack(anchor="w")
        e = entry(parent, show=show)
        e.pack(fill="x", ipady=7, pady=(3, 14))
        return e

    def _go(self):
        u, p = self._u.get().strip(), self._p.get().strip()
        if not u or not p:
            self._err.config(text="Please fill in all fields.")
            return
        uid = self.app.db.verify_login(u, p)
        if uid is None:
            self._err.config(text="Invalid username or password.")
            return
        row = self.app.db.get_user_by_username(u)
        self.app.login(uid, row[1], row[2])

    def on_show(self, **_):
        self._err.config(text="")
        self._u.delete(0, "end")
        self._p.delete(0, "end")


# ═════════════════════════════════════════════════════════════════════════════
#  REGISTER
# ═════════════════════════════════════════════════════════════════════════════

class RegisterPage(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=BG)
        self.app = app
        self._build()

    def _build(self):
        tk.Frame(self, bg=ACCENT2, width=4).pack(side="left", fill="y")

        c = tk.Frame(self, bg=BG)
        c.pack(expand=True)

        tk.Label(c, text="Join Recommend Anything.", bg=BG, fg=TEXT, font=FH).pack(pady=(0, 4))
        tk.Label(c, text="Start recommending things you love.", bg=BG, fg=MUTED, font=FS).pack(pady=(0, 28))

        box = tk.Frame(c, bg=SURFACE, padx=44, pady=40,
                       highlightthickness=1, highlightbackground=BORDER)
        box.pack(ipadx=8)

        self._u  = self._field(box, "USERNAME")
        self._p  = self._field(box, "PASSWORD",         show="•")
        self._p2 = self._field(box, "CONFIRM PASSWORD", show="•")

        btn(box, "Create Account",    self._go,                    accent=True).pack(fill="x", pady=(8, 6))
        btn(box, "← Back to Sign In", lambda: self.app.show("LoginPage")).pack(fill="x")

        self._err = tk.Label(c, text="", bg=BG, fg=ACCENT2, font=FL)
        self._err.pack(pady=6)

    def _field(self, parent, label, show=None):
        tk.Label(parent, text=label, bg=SURFACE, fg=MUTED, font=FL).pack(anchor="w")
        e = entry(parent, show=show)
        e.pack(fill="x", ipady=7, pady=(3, 14))
        return e

    def _go(self):
        u  = self._u.get().strip()
        p  = self._p.get().strip()
        p2 = self._p2.get().strip()
        if not u or not p or not p2:
            self._err.config(text="Please fill in all fields.")
            return
        if p != p2:
            self._err.config(text="Passwords do not match.")
            return
        ok = self.app.db.create_user(u, p)
        if ok:
            messagebox.showinfo("Account Created", f"Welcome, {u}!\nPlease sign in.")
            self.app.show("LoginPage")
        else:
            # Username already taken — clear the field and ask them to pick another
            self._err.config(
                text=f'"{u}" is already taken — please choose a different username.'
            )
            self._u.delete(0, "end")
            self._u.focus_set()

    def on_show(self, **_):
        self._err.config(text="")
        for e in (self._u, self._p, self._p2):
            e.delete(0, "end")


# ═════════════════════════════════════════════════════════════════════════════
#  HOME
# ═════════════════════════════════════════════════════════════════════════════

class HomePage(tk.Frame):
    """
    req 4.2.2 — _load_base  → get_recommendations_for_user (followed + direct)
    req 4.2.3 — _fetch_by_tag → get_recommendations_by_tag  (DB-side filter)
                Falls back to client-side filter if the DB method raises.
    """

    def __init__(self, parent, app):
        super().__init__(parent, bg=BG)
        self.app         = app
        self._base_recs  = []
        self._shown_recs = []
        self._tag_vars   = {}
        self._active_tag = ""

    def on_show(self, **_):
        for w in self.winfo_children():
            w.destroy()
        NavBar(self, self.app, active="home")
        self._load_base()

    def _load_base(self):
        uid = self.app.current_user[0]
        try:
            self._base_recs = self.app.db.get_recommendations_for_user(uid, limit=60)
        except Exception:
            self._base_recs = []

        self._active_tag = ""
        self._shown_recs = list(self._base_recs)
        all_tags = sorted({t for r in self._base_recs for t in r.tags})
        self._build_layout(all_tags)

    def _fetch_by_tag(self, tag: str):
        uid = self.app.current_user[0]
        try:
            recs = self.app.db.get_recommendations_by_tag(tag, uid, limit=60)
            self._shown_recs = recs if recs is not None else []
        except Exception:
            self._shown_recs = [r for r in self._base_recs if tag in r.tags]
        self._active_tag = tag
        self._render()

    def _build_layout(self, all_tags):
        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True)

        side = tk.Frame(body, bg=SURFACE, width=190, padx=14, pady=18)
        side.pack(side="left", fill="y")
        side.pack_propagate(False)

        tk.Label(side, text="FILTER BY TAG", bg=SURFACE, fg=MUTED,
                 font=FL).pack(anchor="w", pady=(0, 8))

        self._tag_vars = {}
        for tag in all_tags:
            v = tk.BooleanVar()
            self._tag_vars[tag] = v
            tk.Checkbutton(
                side, text=f"#{tag}", variable=v,
                bg=SURFACE, fg=TEXT, selectcolor=CARD,
                activebackground=SURFACE, activeforeground=ACCENT,
                font=FM, cursor="hand2",
                command=lambda t=tag, bv=v: self._on_toggle(t, bv)
            ).pack(anchor="w", pady=1)

        if not all_tags:
            tk.Label(side, text="No tags yet", bg=SURFACE,
                     fg=MUTED, font=FM).pack(anchor="w")

        sep(side)
        btn(side, "Clear", self._clear, small=True).pack(anchor="w")

        self._sf   = ScrollFrame(body)
        self._sf.pack(side="left", fill="both", expand=True)
        self._feed = self._sf.inner
        self._render()

    def _on_toggle(self, tag: str, var: tk.BooleanVar):
        if var.get():
            for t, v in self._tag_vars.items():
                if t != tag:
                    v.set(False)
            self._fetch_by_tag(tag)
        else:
            self._shown_recs = list(self._base_recs)
            self._active_tag = ""
            self._render()

    def _clear(self):
        for v in self._tag_vars.values():
            v.set(False)
        self._shown_recs = list(self._base_recs)
        self._active_tag = ""
        self._render()

    def _render(self):
        for w in self._feed.winfo_children():
            w.destroy()

        hdr = tk.Frame(self._feed, bg=BG)
        hdr.pack(fill="x", padx=22, pady=(18, 8))
        tk.Label(hdr, text="Your Feed", bg=BG, fg=TEXT, font=FH).pack(side="left")
        tag_note = f"  · #{self._active_tag}" if self._active_tag else ""
        tk.Label(hdr, text=f"  {len(self._shown_recs)} posts{tag_note}",
                 bg=BG, fg=MUTED, font=FM).pack(side="left", pady=(6, 0))

        if not self._shown_recs:
            e = tk.Frame(self._feed, bg=BG)
            e.pack(pady=60)
            tk.Label(e, text="✦", bg=BG, fg=MUTED, font=("Georgia", 28)).pack()
            tk.Label(e, text="Nothing here yet.", bg=BG, fg=MUTED, font=FS).pack()
            tk.Label(e, text="Follow people on Discover to populate your feed.",
                     bg=BG, fg=MUTED, font=FM).pack(pady=4)
            return

        for r in self._shown_recs:
            self._card(r)

    def _card(self, r):
        c = tk.Frame(self._feed, bg=CARD, padx=18, pady=14,
                     highlightthickness=1, highlightbackground=BORDER)
        c.pack(fill="x", padx=22, pady=6)

        top = tk.Frame(c, bg=CARD)
        top.pack(fill="x")
        tk.Label(top, text=r.title, bg=CARD, fg=TEXT,
                 font=("Georgia", 14, "bold")).pack(side="left")
        stars(top, r.rating).pack(side="right")

        tk.Label(c, text=r.description, bg=CARD, fg=TEXT, font=FB,
                 wraplength=580, justify="left").pack(anchor="w", pady=(5, 7))

        if r.tags:
            row = tk.Frame(c, bg=CARD)
            row.pack(anchor="w", pady=(0, 5))
            for t in r.tags:
                chip(row, t).pack(side="left", padx=(0, 4))

        if r.multimedia_urls:
            tk.Label(c, text="MEDIA", bg=CARD, fg=MUTED, font=FL).pack(anchor="w", pady=(4, 2))
            for url in r.multimedia_urls:
                _media_widget(c, url)

        ts = time.strftime("%b %d, %Y", time.localtime(r.date))
        tk.Label(c, text=ts, bg=CARD, fg=MUTED, font=FM).pack(anchor="e")


# ═════════════════════════════════════════════════════════════════════════════
#  DISCOVER
# ═════════════════════════════════════════════════════════════════════════════

class DiscoverPage(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=BG)
        self.app = app

    def on_show(self, **_):
        for w in self.winfo_children():
            w.destroy()
        NavBar(self, self.app, active="discover")
        self._build()

    def _build(self):
        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True, padx=44, pady=24)

        tk.Label(body, text="Discover People", bg=BG, fg=TEXT, font=FH).pack(anchor="w")
        tk.Label(body, text="Search for users and follow them to see their recommendations.",
                 bg=BG, fg=MUTED, font=FS).pack(anchor="w", pady=(0, 18))

        row = tk.Frame(body, bg=BG)
        row.pack(fill="x", pady=(0, 16))
        self._sq = entry(row, width=42)
        self._sq.pack(side="left", ipady=8, padx=(0, 8))
        self._sq.bind("<Return>", lambda _: self._search())
        btn(row, "Search", self._search, accent=True).pack(side="left")

        sep(body)

        self._res = ScrollFrame(body)
        self._res.pack(fill="both", expand=True)

    def _search(self):
        q = self._sq.get().strip().lower()
        for w in self._res.inner.winfo_children():
            w.destroy()

        if not q:
            tk.Label(self._res.inner, text="Enter a username to search.",
                     bg=BG, fg=MUTED, font=FM).pack(pady=20)
            return

        try:
            row = self.app.db.get_user_by_username(q)
            results = [row] if row else []
        except Exception:
            results = []

        if not results:
            tk.Label(self._res.inner, text=f'No user found for "{q}".',
                     bg=BG, fg=MUTED, font=FM).pack(pady=20)
            return

        for u in results:
            self._user_card(u)

    def _user_card(self, user):
        uid, uname, role = user
        my_uid = self.app.current_user[0]
        if uid == my_uid:
            tk.Label(self._res.inner, text="(That's you!)",
                     bg=BG, fg=MUTED, font=FM).pack(pady=20)
            return

        c = tk.Frame(self._res.inner, bg=CARD, padx=20, pady=14,
                     highlightthickness=1, highlightbackground=BORDER)
        c.pack(fill="x", pady=5)

        left = tk.Frame(c, bg=CARD)
        left.pack(side="left", fill="x", expand=True)
        tk.Label(left, text=uname, bg=CARD, fg=TEXT,
                 font=("Georgia", 14, "bold")).pack(anchor="w")
        tk.Label(left, text="Admin" if role == 1 else "Member",
                 bg=CARD, fg=MUTED, font=FM).pack(anchor="w")

        def do_follow(tid=uid, tn=uname):
            try:
                self.app.db.add_follower(tid, my_uid)
                messagebox.showinfo("Following", f"Now following {tn}!")
            except Exception:
                messagebox.showwarning("Already Following",
                                       f"You are already following {tn}.")

        btn(c, "Follow", do_follow, accent=True, small=True).pack(side="right", padx=6)


# ═════════════════════════════════════════════════════════════════════════════
#  POST
# ═════════════════════════════════════════════════════════════════════════════

class PostPage(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=BG)
        self.app     = app
        self._rating = 5

    def on_show(self, **_):
        for w in self.winfo_children():
            w.destroy()
        NavBar(self, self.app, active="post")
        self._build()

    def _build(self):
        sf = ScrollFrame(self)
        sf.pack(fill="both", expand=True)
        w = tk.Frame(sf.inner, bg=BG)
        w.pack(padx=60, pady=24, fill="x")

        tk.Label(w, text="New Recommendation", bg=BG, fg=TEXT, font=FH).pack(anchor="w")
        tk.Label(w, text="Share something worth recommending.",
                 bg=BG, fg=MUTED, font=FS).pack(anchor="w", pady=(0, 22))

        self._lbl(w, "TITLE")
        self._title = entry(w, width=62)
        self._title.pack(fill="x", ipady=8, pady=(3, 14))

        self._lbl(w, "DESCRIPTION")
        self._desc = tk.Text(
            w, bg=CARD, fg=TEXT, insertbackground=ACCENT,
            relief="flat", font=FB, height=5, bd=0,
            highlightthickness=1, highlightbackground=BORDER, wrap="word"
        )
        self._desc.pack(fill="x", pady=(3, 14))

        self._lbl(w, "RATING")
        sf2 = tk.Frame(w, bg=BG)
        sf2.pack(anchor="w", pady=(3, 14))
        self._star_btns = []
        for i in range(1, 6):
            # Star buttons use tk.Label too for colour consistency
            b = tk.Label(sf2, text="★", bg=BG, fg=STAR_ON,
                         font=("Georgia", 22), cursor="hand2")
            b.bind("<ButtonRelease-1>", lambda e, v=i: self._set_stars(v))
            b.pack(side="left", padx=2)
            self._star_btns.append(b)
        self._set_stars(5)

        self._lbl(w, "TAGS  (comma separated)")
        self._tags = entry(w, width=62)
        self._tags.pack(fill="x", ipady=8, pady=(3, 14))

        self._lbl(w, "MEDIA URLS  (comma separated, optional)")
        self._urls = entry(w, width=62)
        self._urls.pack(fill="x", ipady=8, pady=(3, 14))

        sep(w)

        self._lbl(w, "SEND TO SPECIFIC FOLLOWERS  "
                     "(usernames, comma separated — blank = visible to all followers)")
        self._send = entry(w, width=62)
        self._send.pack(fill="x", ipady=8, pady=(3, 22))

        row = tk.Frame(w, bg=BG)
        row.pack(anchor="w")
        btn(row, "Post Recommendation", self._post, accent=True).pack(side="left", padx=(0, 10))
        btn(row, "Clear",               self._clear).pack(side="left")

        self._status = tk.Label(w, text="", bg=BG, fg=SUCCESS, font=FL)
        self._status.pack(anchor="w", pady=6)

    def _lbl(self, parent, text):
        tk.Label(parent, text=text, bg=BG, fg=MUTED, font=FL).pack(anchor="w")

    def _set_stars(self, v):
        self._rating = v
        for i, b in enumerate(self._star_btns, 1):
            b.config(fg=STAR_ON if i <= v else STAR_OFF)

    def _post(self):
        uid   = self.app.current_user[0]
        title = self._title.get().strip()
        desc  = self._desc.get("1.0", "end").strip()
        tags  = [t.strip() for t in self._tags.get().split(",") if t.strip()]
        urls  = [u.strip() for u in self._urls.get().split(",") if u.strip()]

        if not title:
            self._status.config(text="Title cannot be empty.", fg=ACCENT2); return
        if not desc:
            self._status.config(text="Description cannot be empty.", fg=ACCENT2); return

        try:
            rec = self.app.db.create_recommendation(uid, title, desc, self._rating, tags, urls)
        except ValueError as e:
            self._status.config(text=str(e), fg=ACCENT2); return
        except Exception as e:
            self._status.config(text=f"Error: {e}", fg=ACCENT2); return

        sent       = 0
        not_found  = []
        not_follow = []

        for uname in [s.strip() for s in self._send.get().split(",") if s.strip()]:
            row = self.app.db.get_user_by_username(uname)
            if not row:
                not_found.append(uname)
                continue

            target_id = row[0]

            # Verify the target is actually a follower of the poster
            try:
                is_follower = self.app.db.is_follower(uid, target_id)
            except AttributeError:
                # is_follower not yet added to DB — skip check, send anyway
                is_follower = True

            if not is_follower:
                not_follow.append(uname)
                continue

            try:
                self.app.db.send_reqs(rec.recommendation_id, target_id)
                sent += 1
            except Exception:
                pass

        # Build status message
        parts = [f"✓  Posted!  (ID {rec.recommendation_id})"]
        if sent:
            parts.append(f"Sent to {sent} follower(s).")
        if not_follow:
            parts.append(f"Skipped (not your follower): {', '.join(not_follow)}.")
        if not_found:
            parts.append(f"Not found: {', '.join(not_found)}.")

        self._status.config(text="  ".join(parts), fg=SUCCESS if not (not_follow or not_found) else WARNING)
        self._clear(keep_status=True)

    def _clear(self, keep_status=False):
        self._title.delete(0, "end")
        self._desc.delete("1.0", "end")
        self._tags.delete(0, "end")
        self._urls.delete(0, "end")
        self._send.delete(0, "end")
        self._set_stars(5)
        if not keep_status:
            self._status.config(text="")


# ═════════════════════════════════════════════════════════════════════════════
#  ADMIN
# ═════════════════════════════════════════════════════════════════════════════

class AdminPage(tk.Frame):
    """Visible in nav only when role == 1 (ROLE_ADMIN)."""

    def __init__(self, parent, app):
        super().__init__(parent, bg=BG)
        self.app   = app
        self._recs = []

    def on_show(self, **_):
        for w in self.winfo_children():
            w.destroy()
        NavBar(self, self.app, active="admin")
        self._build()

    def _build(self):
        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True, padx=44, pady=20)

        hdr = tk.Frame(body, bg=BG)
        hdr.pack(fill="x", pady=(0, 4))
        tk.Label(hdr, text="Admin Panel", bg=BG, fg=TEXT, font=FH).pack(side="left")
        badge = tk.Frame(hdr, bg=DANGER, padx=8, pady=2)
        badge.pack(side="left", padx=12, pady=(6, 0))
        tk.Label(badge, text="ADMIN", bg=DANGER, fg="#ffffff", font=FM).pack()

        tk.Label(body, text="Manage all platform recommendations.",
                 bg=BG, fg=MUTED, font=FS).pack(anchor="w", pady=(0, 14))

        frow = tk.Frame(body, bg=BG)
        frow.pack(fill="x", pady=(0, 10))
        tk.Label(frow, text="FILTER BY TAG", bg=BG, fg=MUTED, font=FL).pack(side="left", padx=(0, 8))
        self._tag_entry = entry(frow, width=22)
        self._tag_entry.pack(side="left", ipady=6, padx=(0, 6))
        self._tag_entry.bind("<Return>", lambda _: self._load(self._tag_entry.get().strip()))
        btn(frow, "Apply",     lambda: self._load(self._tag_entry.get().strip()), small=True).pack(side="left", padx=(0, 4))
        btn(frow, "All Posts", lambda: self._load(),                              small=True).pack(side="left")

        self._count_lbl = tk.Label(body, text="", bg=BG, fg=MUTED, font=FM)
        self._count_lbl.pack(anchor="w", pady=(0, 4))

        sep(body)

        self._sf   = ScrollFrame(body)
        self._sf.pack(fill="both", expand=True)
        self._feed = self._sf.inner
        self._load()

    def _load(self, tag_filter=""):
        uid, _, role = self.app.current_user
        try:
            if tag_filter:
                recs = self.app.db.list_recommendations_tags(role, uid, tag_filter.lower())
            else:
                recs = self.app.db.list_recommendations(role, uid)
        except Exception:
            recs = None

        for w in self._feed.winfo_children():
            w.destroy()

        if recs is None:
            tk.Label(self._feed, text="Access denied or an error occurred.",
                     bg=BG, fg=DANGER, font=FB).pack(pady=30)
            self._count_lbl.config(text="")
            return

        self._recs = recs
        suffix = f'  tagged "#{tag_filter}"' if tag_filter else ""
        self._count_lbl.config(text=f"{len(recs)} post(s){suffix}")

        if not recs:
            tk.Label(self._feed, text="No recommendations found.",
                     bg=BG, fg=MUTED, font=FS).pack(pady=40)
            return

        for r in recs:
            self._admin_card(r)

    def _admin_card(self, r):
        outer = tk.Frame(self._feed, bg=CARD, padx=18, pady=14,
                         highlightthickness=1, highlightbackground=BORDER)
        outer.pack(fill="x", pady=5)

        top = tk.Frame(outer, bg=CARD)
        top.pack(fill="x")
        tk.Label(top, text=r.title, bg=CARD, fg=TEXT,
                 font=("Georgia", 14, "bold")).pack(side="left")
        stars(top, r.rating).pack(side="right")

        meta = tk.Frame(outer, bg=CARD)
        meta.pack(anchor="w", pady=(2, 6))
        for txt in (f"ID {r.recommendation_id}", f"poster_id {r.poster_id}",
                    time.strftime("%b %d, %Y", time.localtime(r.date))):
            tk.Label(meta, text=txt, bg=CARD, fg=MUTED, font=FM).pack(side="left", padx=(0, 14))

        tk.Label(outer, text=r.description, bg=CARD, fg=TEXT, font=FB,
                 wraplength=600, justify="left").pack(anchor="w", pady=(0, 8))

        foot = tk.Frame(outer, bg=CARD)
        foot.pack(fill="x")

        if r.tags:
            trow = tk.Frame(foot, bg=CARD)
            trow.pack(side="left")
            for t in r.tags:
                chip(trow, t).pack(side="left", padx=(0, 4))

        if r.multimedia_urls:
            tk.Label(outer, text="MEDIA", bg=CARD, fg=MUTED, font=FL).pack(anchor="w", pady=(4, 2))
            for url in r.multimedia_urls:
                _media_widget(outer, url)

        def do_delete(rid=r.recommendation_id, rtitle=r.title):
            if not messagebox.askyesno("Confirm Delete",
                                       f'Permanently delete "{rtitle}"?\nThis cannot be undone.'):
                return
            uid2, _, role2 = self.app.current_user
            try:
                ok = self.app.db.delete_recommendation(role2, uid2, rid)
                if ok:
                    self._load(self._tag_entry.get().strip())
                else:
                    messagebox.showerror("Error", "Could not delete that recommendation.")
            except Exception as ex:
                messagebox.showerror("Error", str(ex))

        btn(foot, "Delete", do_delete, danger=True, small=True).pack(side="right")


# ═════════════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ═════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    from DB_interface import DatabaseInterface
    db  = DatabaseInterface("./Recommend_Anything.db")
    app = App(db)
    app.mainloop()
#!/usr/bin/env python3
"""
Fifa Progress — janela flutuante (PySide6/Qt) do watcher da Copa 2026.

Espelha o padrão do PKM Progress (versão Qt, moderna e clara): uma janelinha sem
bordas, sempre no topo, arrastável pelo titlebar, redimensionável pelo grip no
canto. Mostra a fila de jogos pendentes e o progresso. O estado vive em
/tmp/fifa-copa.json e é atualizado por um socket Unix — o daemon (watch-fifa.py)
escreve, a janela lê e desenha.

Modos:
  --window            abre só a janela Qt (lê /tmp/fifa-copa.json)
  --daemon            servidor de socket sem janela
  --windows           servidor de socket + janela (uso normal pelo systemd)
  <pct> [msg]         cliente CLI: pct = 0-100 ou "done"/"idle"
  --pending a,b,c     cliente CLI: define a fila exibida
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HTML_PATH = ROOT / "reports" / "tournament" / "ranking_race.html"

STATE_FILE = "/tmp/fifa-copa.json"
SOCK_PATH = "/tmp/fifa-copa.sock"
CMD_FILE = "/tmp/fifa-copa-cmd.json"   # janela → daemon (pedido de processar)
STOP_FILE = "/tmp/fifa-copa-stop"      # janela → daemon (pedido de encerrar)
LOCK_FILE = "/tmp/fifa-copa.lock"      # garante instância única da janela
GEOM_FILE = ROOT / "watcher" / ".window-geometry.json"


# ── helpers ───────────────────────────────────────────────────────────────────

def _shorten(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max(1, max_chars - 1)] + "…"


def _open_html():
    """Abre o ranking no navegador. Evita xdg-open porque .html pode estar
    associado a outro app (ex.: Calibre)."""
    if not HTML_PATH.exists():
        return
    url = str(HTML_PATH)
    # tenta navegadores conhecidos primeiro; xdg-open por último
    # (xdg-open pode abrir o .html no Calibre, dependendo da associação MIME)
    for launcher in (
        ["google-chrome", url],
        ["google-chrome-stable", url],
        ["chromium", url],
        ["firefox", url],
        ["x-www-browser", url],
        ["xdg-open", url],
    ):
        try:
            subprocess.Popen(launcher, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return
        except FileNotFoundError:
            continue


# ── estado em disco ───────────────────────────────────────────────────────────

def _write_state(pct, msg="", done=False, idle=False, pending=None,
                 ready=None, scheduled=None, live=None, update_ts=True):
    tmp = STATE_FILE + ".tmp"
    try:
        try:
            existing = json.loads(Path(STATE_FILE).read_text())
        except Exception:
            existing = {}
        state = {
            "pct": pct,
            "msg": msg,
            "done": done,
            "idle": idle,
            "ts": time.time() if update_ts else existing.get("ts", time.time()),
            # pending: compat antiga (lista simples)
            "pending": pending if pending is not None else existing.get("pending", []),
            # ready: jogos prontos a processar [{"n": int, "label": str}]
            "ready": ready if ready is not None else existing.get("ready", []),
            # scheduled: próximos jogos (labels) [str]
            "scheduled": scheduled if scheduled is not None else existing.get("scheduled", []),
            # live: jogos acontecendo agora (labels com placar) [str]
            "live": live if live is not None else existing.get("live", []),
        }
        with open(tmp, "w") as f:
            json.dump(state, f)
        os.replace(tmp, STATE_FILE)
    except Exception:
        pass


def _read_state() -> dict:
    try:
        return json.loads(Path(STATE_FILE).read_text())
    except Exception:
        return {"pct": None, "msg": "", "done": False, "idle": True,
                "pending": [], "ready": [], "scheduled": [], "live": [], "ts": time.time()}


# ── comando janela → daemon ───────────────────────────────────────────────────

def request_process(ns=None):
    """Janela pede ao daemon para processar. ns=None → todos os prontos."""
    try:
        with open(CMD_FILE, "w") as f:
            json.dump({"action": "process", "ns": ns, "ts": time.time()}, f)
    except Exception:
        pass


def request_refresh():
    """Janela pede ao daemon para coletar as fontes e atualizar a lista."""
    try:
        with open(CMD_FILE, "w") as f:
            json.dump({"action": "refresh", "ts": time.time()}, f)
    except Exception:
        pass


def read_command() -> dict | None:
    """Daemon lê e consome o pedido pendente (apaga após ler)."""
    try:
        cmd = json.loads(Path(CMD_FILE).read_text())
        os.unlink(CMD_FILE)
        return cmd
    except Exception:
        return None


def _read_geom() -> dict:
    try:
        return json.loads(GEOM_FILE.read_text())
    except Exception:
        return {}


def _save_geom(win):
    try:
        g = win.geometry()
        GEOM_FILE.write_text(json.dumps({"x": g.x(), "y": g.y(), "w": g.width(), "h": g.height()}))
    except Exception:
        pass


# ── servidor de socket ────────────────────────────────────────────────────────

def _handle_command(payload: dict):
    keys = set(payload.keys())
    # comandos que só atualizam listas, preservando o progresso atual
    list_only = keys <= {"pending", "ready", "scheduled", "live"}
    if list_only:
        cur = _read_state()
        _write_state(cur.get("pct"), cur.get("msg", ""), cur.get("done", False),
                     cur.get("idle", True),
                     pending=payload.get("pending"),
                     ready=payload.get("ready"),
                     scheduled=payload.get("scheduled"),
                     live=payload.get("live"),
                     update_ts=False)
        return
    _write_state(
        payload.get("pct"),
        payload.get("msg", ""),
        payload.get("done", False),
        payload.get("idle", False),
        pending=payload.get("pending"),
        ready=payload.get("ready"),
        scheduled=payload.get("scheduled"),
        live=payload.get("live"),
    )


def _serve_socket():
    try:
        os.unlink(SOCK_PATH)
    except FileNotFoundError:
        pass
    srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    srv.bind(SOCK_PATH)
    srv.listen(8)
    while True:
        try:
            conn, _ = srv.accept()
            with conn:
                data = conn.recv(65536)
                if not data:
                    continue
                try:
                    _handle_command(json.loads(data.decode("utf-8")))
                except Exception:
                    pass
        except Exception:
            time.sleep(0.2)


def _send(payload: dict) -> bool:
    try:
        c = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        c.connect(SOCK_PATH)
        c.sendall(json.dumps(payload).encode("utf-8"))
        c.close()
        return True
    except Exception:
        _handle_command(payload)
        return False


# ── API pública (importável pelo daemon) ──────────────────────────────────────

def progress_update(pct, msg=""):
    _send({"pct": max(0, min(100, pct)) if pct is not None else None, "msg": msg, "idle": False})


def progress_done(msg="Concluído"):
    _send({"pct": 100, "msg": msg, "done": True, "idle": False})


def progress_idle(msg="Aguardando jogos…"):
    _send({"pct": None, "msg": msg, "idle": True})


def set_pending(items):
    _send({"pending": list(items)})


def set_ready(items):
    """items: [{"n": int, "label": str}] — jogos prontos a processar."""
    _send({"ready": list(items)})


def set_scheduled(items):
    """items: [str] — próximos jogos agendados (só exibição)."""
    _send({"scheduled": list(items)})


def set_live(items):
    """items: [str] — jogos acontecendo agora (com placar parcial)."""
    _send({"live": list(items)})


# ── estilo (QSS) — espelha a versão moderna/clara do pkm_progress ─────────────

QSS = """
QWidget {
    background: #f5f7fa;
    color: #18202a;
    font-family: Inter, "SF Pro Display", "Segoe UI", Sans;
    font-size: 13px;
}
QLabel { background: transparent; }
#shell {
    background: #ffffff;
    border: 1px solid #d8dee8;
    border-radius: 12px;
}
#titlebar {
    background: #eef2f7;
    border-top-left-radius: 12px;
    border-top-right-radius: 12px;
}
QLabel#title { font-weight: 700; font-size: 12px; color: #202936; }
QLabel#kicker { color: #637084; font-size: 10px; font-weight: 800; }
QLabel#queue, QLabel#meta { color: #718096; font-size: 11px; }
QLabel#active { font-size: 15px; font-weight: 700; color: #151b24; }
QLabel#status { font-size: 12px; font-weight: 700; }
QLabel#dot {
    min-width: 9px; max-width: 9px; min-height: 9px; max-height: 9px;
    border-radius: 4px; background: #8c96a6;
}
QPushButton {
    background: #f1f4f8; border: 1px solid #d5dce7; border-radius: 6px;
    padding: 6px 9px; color: #263241; font-weight: 650;
}
QPushButton:hover { background: #e7edf5; border-color: #bac6d6; }
QPushButton#blue { background: #e9f1ff; border-color: #bed3fb; color: #2457a7; }
QPushButton#blue:hover { background: #dbe8ff; }
QPushButton#green { background: #e7f8ed; border-color: #a8dfba; color: #176b3a; }
QPushButton#green:hover { background: #d6f1e0; }
QPushButton#processBtn {
    background: #1f9d55; border: 1px solid #1a8a4a; border-radius: 6px;
    color: #ffffff; font-weight: 700; padding: 2px 12px;
}
QPushButton#processBtn:hover { background: #1a8a4a; }
QFrame#rowReady { background: #eafaf0; border: 1px solid #b6e3c6; border-radius: 10px; }
QFrame#rowReady:hover { background: #def5e8; border-color: #98d8b0; }
QFrame#rowLive { background: #fdeced; border: 1px solid #f3b8bf; border-radius: 10px; }
QFrame#rowLive:hover { background: #fbe0e3; border-color: #ec9aa4; }
QToolButton#close {
    background: transparent; border: 0; border-radius: 8px;
    color: #657386; font-size: 15px; padding: 2px 6px;
}
QToolButton#close:hover { background: #ffe8ea; color: #b42335; }
QToolButton#refresh {
    background: transparent; border: 0; border-radius: 8px;
    color: #2457a7; font-size: 14px; font-weight: 700; padding: 2px 7px;
}
QToolButton#refresh:hover { background: #e9f1ff; }
QToolButton#refresh:disabled { color: #b8c0cc; }
QProgressBar {
    background: #e6ebf2; border: 0; border-radius: 6px; height: 10px;
    text-align: center; color: transparent;
}
QProgressBar::chunk { border-radius: 6px; background: #3d7fe0; }
QFrame#row { background: #f8fafc; border: 1px solid #dde4ee; border-radius: 10px; }
QFrame#row:hover { background: #f1f6fd; border-color: #c7d6ea; }
QFrame#summary { background: #f7f9fc; border: 1px solid #e1e7f0; border-radius: 10px; }
QLabel#resizeHandle { background: transparent; color: #8a96a8; font-size: 13px; font-weight: 800; }
QScrollArea { border: 0; background: transparent; }
QScrollArea QWidget { background: transparent; }
QToolButton#move {
    background: #eef3fa; border: 1px solid #d3dded; border-radius: 6px;
    color: #3a526f; font-weight: 800; padding: 0;
}
QToolButton#move:hover { background: #dde9fb; }
QToolButton#move:disabled { background: #f3f5f8; color: #c2c9d4; border-color: #e3e8ef; }
"""


def _acquire_lock() -> "object | None":
    """Garante uma única janela. Retorna o handle do lock, ou None se já há outra."""
    import fcntl
    try:
        f = open(LOCK_FILE, "w")
        fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        f.write(str(os.getpid()))
        f.flush()
        return f  # mantém aberto enquanto o processo viver
    except (OSError, BlockingIOError):
        return None


def _run_window():
    # instância única: se já há uma janela aberta, não abre outra
    lock = _acquire_lock()
    if lock is None:
        print("[fifa-progress] janela já está aberta — ignorando segunda instância.",
              file=sys.stderr, flush=True)
        return

    from PySide6.QtCore import QEvent, QPoint, Qt, QTimer
    from PySide6.QtWidgets import (
        QApplication, QFrame, QHBoxLayout, QLabel, QProgressBar, QPushButton,
        QScrollArea, QToolButton, QVBoxLayout, QWidget,
    )

    DOT_COLORS = {"idle": "#8c96a6", "run": "#3d7fe0", "done": "#1f9d55", "err": "#d23a4b"}

    class Panel(QWidget):
        def __init__(self):
            super().__init__()
            self.drag_pos: QPoint | None = None
            self.dragging = False
            self.resizing = False
            self.rsz_start = None
            self.rsz_size = None
            self.ready: list[dict] = []      # jogos prontos a processar
            self.scheduled: list[str] = []   # próximos jogos agendados
            self.live: list[str] = []        # jogos acontecendo agora
            self._processing = False         # True entre o clique e o "concluído"
            self._item_buttons: list = []    # botões "Processar" de cada item

            self.setWindowTitle("Copa 2026 · Watcher")
            self.setWindowFlags(
                Qt.WindowType.FramelessWindowHint
                | Qt.WindowType.WindowStaysOnTopHint
                | Qt.WindowType.Tool
            )
            self.setMinimumSize(320, 280)
            self.resize(380, 360)
            self._place_initial()
            self._build()
            self.setStyleSheet(QSS)

            self.timer = QTimer(self)
            self.timer.timeout.connect(self.poll)
            self.timer.start(400)
            self.poll()

        def _place_initial(self):
            saved = _read_geom()
            screen = QApplication.primaryScreen().availableGeometry()
            w = int(saved.get("w") or self.width())
            h = int(saved.get("h") or self.height())
            x = int(saved["x"]) if saved.get("x") is not None else screen.right() - w - 24
            y = int(saved["y"]) if saved.get("y") is not None else screen.y() + 80
            x = max(screen.x(), min(x, screen.right() - w))
            y = max(screen.y(), min(y, screen.bottom() - h))
            self.setGeometry(x, y, max(320, w), max(280, h))

        def _build(self):
            root = QVBoxLayout(self)
            root.setContentsMargins(0, 0, 0, 0)
            self.shell = QFrame(objectName="shell")
            root.addWidget(self.shell)

            layout = QVBoxLayout(self.shell)
            layout.setContentsMargins(0, 0, 0, 6)
            layout.setSpacing(0)

            # titlebar (arrastável)
            self.titlebar = QFrame(objectName="titlebar")
            tl = QHBoxLayout(self.titlebar)
            tl.setContentsMargins(14, 9, 10, 9)
            tl.setSpacing(10)
            self.dot = QLabel(objectName="dot")
            self.title = QLabel("Copa 2026 · Watcher", objectName="title")
            self.queue = QLabel("fila vazia", objectName="queue")
            tl.addWidget(self.dot)
            tl.addWidget(self.title)
            tl.addStretch(1)
            tl.addWidget(self.queue)
            self.refresh_btn = QToolButton(objectName="refresh")
            self.refresh_btn.setText("↻")
            self.refresh_btn.setToolTip("Buscar dados novos das fontes")
            self.refresh_btn.clicked.connect(self._refresh)
            tl.addWidget(self.refresh_btn)
            self.close_btn = QToolButton(objectName="close")
            self.close_btn.setText("✕")
            self.close_btn.clicked.connect(self._quit)
            tl.addWidget(self.close_btn)
            layout.addWidget(self.titlebar)
            for wdg in (self.titlebar, self.dot, self.title, self.queue):
                wdg.installEventFilter(self)
                wdg.setCursor(Qt.CursorShape.SizeAllCursor)

            body = QVBoxLayout()
            body.setContentsMargins(16, 12, 16, 0)
            body.setSpacing(8)
            layout.addLayout(body)

            self.kicker = QLabel("ESTADO", objectName="kicker")
            body.addWidget(self.kicker)
            self.active = QLabel("Sem job ativo", objectName="active")
            self.active.setWordWrap(True)
            body.addWidget(self.active)

            self.summary = QFrame(objectName="summary")
            sl = QHBoxLayout(self.summary)
            sl.setContentsMargins(10, 7, 10, 7)
            sl.setSpacing(8)
            self.status = QLabel("Aguardando", objectName="status")
            self.meta = QLabel("sem atividade", objectName="meta")
            self.meta.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            sl.addWidget(self.status)
            sl.addWidget(self.meta, 1)
            body.addWidget(self.summary)

            self.progress = QProgressBar()
            self.progress.setRange(0, 100)
            self.progress.setValue(0)
            body.addWidget(self.progress)

            # lista de jogos (scroll) — os títulos de seção são criados em _render_jobs
            self.scroll = QScrollArea()
            self.scroll.setWidgetResizable(True)
            self.scroll_host = QWidget()
            self.jobs_layout = QVBoxLayout(self.scroll_host)
            self.jobs_layout.setContentsMargins(0, 0, 0, 0)
            self.jobs_layout.setSpacing(7)
            self.jobs_layout.addStretch(1)
            self.scroll.setWidget(self.scroll_host)
            body.addWidget(self.scroll, 1)

            # botão de processar (verde) — só aparece quando há jogos prontos
            self.process_all_btn = QPushButton("Processar jogos", objectName="green")
            self.process_all_btn.setMinimumHeight(30)
            self.process_all_btn.clicked.connect(lambda: self._request(None))
            self.process_all_btn.setVisible(False)
            body.addWidget(self.process_all_btn)

            # botão de abrir ranking — embaixo de tudo
            self.html_btn = QPushButton("Abrir Ranking Race", objectName="blue")
            self.html_btn.setMinimumHeight(30)
            self.html_btn.clicked.connect(_open_html)
            body.addWidget(self.html_btn)

            # footer com grip de resize
            footer = QHBoxLayout()
            footer.setContentsMargins(0, -3, 0, 0)
            footer.addStretch(1)
            self.resize_handle = QLabel("⟋", objectName="resizeHandle")
            self.resize_handle.setFixedSize(24, 20)
            self.resize_handle.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom)
            self.resize_handle.setCursor(Qt.CursorShape.SizeFDiagCursor)
            self.resize_handle.installEventFilter(self)
            footer.addWidget(self.resize_handle)
            body.addLayout(footer)

        # ── drag (titlebar) e resize (handle) ──
        def eventFilter(self, obj, event):
            if obj is getattr(self, "resize_handle", None):
                if event.type() == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
                    self.resizing = True
                    self.rsz_start = event.globalPosition().toPoint()
                    self.rsz_size = self.size()
                    return True
                if event.type() == QEvent.Type.MouseMove and self.resizing and self.rsz_start is not None:
                    d = event.globalPosition().toPoint() - self.rsz_start
                    mn = self.minimumSize()
                    st = self.rsz_size or self.size()
                    self.resize(max(mn.width(), st.width() + d.x()),
                                max(mn.height(), st.height() + d.y()))
                    return True
                if event.type() == QEvent.Type.MouseButtonRelease and self.resizing:
                    self.resizing = False
                    _save_geom(self)
                    return True
            if obj in (self.titlebar, self.dot, self.title, self.queue):
                if event.type() == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
                    h = self.windowHandle()
                    if h is not None and h.startSystemMove():
                        return True
                    self.dragging = True
                    self.drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                    return True
                if event.type() == QEvent.Type.MouseMove and self.dragging and self.drag_pos is not None:
                    self.move(event.globalPosition().toPoint() - self.drag_pos)
                    return True
                if event.type() == QEvent.Type.MouseButtonRelease and self.dragging:
                    self.dragging = False
                    _save_geom(self)
                    return True
            return super().eventFilter(obj, event)

        def _request(self, ns):
            # feedback visual imediato: desabilita botões e marca "enviando"
            self._processing = True
            self._disable_process_buttons("Enviando…")
            request_process(ns)

        def _refresh(self):
            # pede ao daemon para coletar as fontes e atualizar a lista
            self._processing = True
            self.refresh_btn.setEnabled(False)
            self.active.setText("Atualizando dados das fontes…")
            request_refresh()

        def _process_one(self, n):
            self._request([n])

        def _disable_process_buttons(self, label="Processando…"):
            self.process_all_btn.setEnabled(False)
            self.process_all_btn.setText(label)
            for b in getattr(self, "_item_buttons", []):
                try:
                    b.setEnabled(False)
                    b.setText("…")
                except Exception:
                    pass

        def _quit(self):
            from PySide6.QtWidgets import QApplication
            # avisa o daemon para encerrar também (run-window.sh observa este sinal)
            try:
                Path(STOP_FILE).write_text("1")
            except Exception:
                pass
            QApplication.quit()

        def _render_jobs(self):
            from PySide6.QtCore import Qt
            from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton
            # limpa
            while self.jobs_layout.count() > 1:
                item = self.jobs_layout.takeAt(0)
                w = item.widget()
                if w:
                    w.deleteLater()
            self._item_buttons = []

            live = self.live            # [str]
            ready = self.ready          # [{"n", "label"}]
            scheduled = self.scheduled  # [str]

            def _section(title, color):
                hdr = QLabel(title, objectName="kicker")
                hdr.setStyleSheet(f"color:{color}; font-size:10px; font-weight:800; padding-top:4px;")
                self.jobs_layout.insertWidget(self.jobs_layout.count() - 1, hdr)

            # ── ao vivo (vermelho) ──
            if live:
                _section("● AO VIVO", "#d23a4b")
                for label in live:
                    row = QFrame(objectName="rowLive")
                    rl = QHBoxLayout(row)
                    rl.setContentsMargins(10, 6, 8, 6)
                    rl.setSpacing(6)
                    num = QLabel("🔴")
                    lbl = QLabel(label)
                    lbl.setWordWrap(True)
                    lbl.setStyleSheet("color:#3a1216; font-weight:800;")
                    rl.addWidget(num)
                    rl.addWidget(lbl, 1)
                    self.jobs_layout.insertWidget(self.jobs_layout.count() - 1, row)

            # ── prontos a processar (verde) ──
            if ready:
                _section("PRONTOS PARA PROCESSAR", "#1f9d55")
                for job in ready:
                    row = QFrame(objectName="rowReady")
                    rl = QHBoxLayout(row)
                    rl.setContentsMargins(10, 6, 8, 6)
                    rl.setSpacing(6)
                    num = QLabel("●")
                    num.setStyleSheet("color:#1f9d55; font-weight:800;")
                    lbl = QLabel(job.get("label", ""))
                    lbl.setWordWrap(True)
                    lbl.setStyleSheet("color:#17331f; font-weight:700;")
                    btn = QPushButton("Processar", objectName="processBtn")
                    btn.setFixedHeight(24)
                    btn.clicked.connect(lambda _=False, n=job.get("n"): self._process_one(n))
                    if self._processing:
                        btn.setEnabled(False)
                        btn.setText("…")
                    self._item_buttons.append(btn)
                    rl.addWidget(num)
                    rl.addWidget(lbl, 1)
                    rl.addWidget(btn)
                    self.jobs_layout.insertWidget(self.jobs_layout.count() - 1, row)

            # ── próximos jogos agendados (cinza) ──
            if scheduled:
                _section("PRÓXIMOS JOGOS", "#637084")
                for label in scheduled:
                    row = QFrame(objectName="row")
                    rl = QHBoxLayout(row)
                    rl.setContentsMargins(10, 6, 8, 6)
                    rl.setSpacing(6)
                    num = QLabel("◷")
                    num.setStyleSheet("color:#6b8bbf; font-weight:800;")
                    lbl = QLabel(label)
                    lbl.setWordWrap(True)
                    lbl.setStyleSheet("color:#48515e; font-weight:600;")
                    rl.addWidget(num)
                    rl.addWidget(lbl, 1)
                    self.jobs_layout.insertWidget(self.jobs_layout.count() - 1, row)

            if not live and not ready and not scheduled:
                empty = QLabel("Sem jogos")
                empty.setStyleSheet("color:#9aa4b2; padding:14px 4px;")
                empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
                self.jobs_layout.insertWidget(self.jobs_layout.count() - 1, empty)

        # ── poll de estado ──
        def poll(self):
            st = _read_state()
            idle = st.get("idle", True)
            done = st.get("done", False)
            pct = st.get("pct")
            msg = st.get("msg", "")
            ready = st.get("ready", [])
            scheduled = st.get("scheduled", [])
            live = st.get("live", [])
            ts = st.get("ts", 0)

            # guarda contra estado preso: se diz "processando" mas o estado está
            # velho (>STALE_SECS sem atualização), o daemon parou no meio — trata como
            # ocioso. O daemon manda heartbeat a cada ~5s durante etapas longas (coleta,
            # narrativa), então só dispara quando ele realmente morre.
            STALE_SECS = 30
            if not idle and (time.time() - ts) > STALE_SECS:
                idle = True
                pct = None
                done = False

            if not self.isVisible():
                self.show()

            processing = not idle and not done and pct != 100

            # sincroniza o flag de processamento com o estado real do daemon:
            # quando o daemon começa a trabalhar (pct definido) ou conclui, atualiza.
            if processing:
                self._processing = True
            elif done or idle:
                self._processing = False

            # reconstrói a lista quando ao vivo/prontos/agendados/processando mudam
            if (live != self.live or ready != self.ready or scheduled != self.scheduled):
                self.live = list(live)
                self.ready = list(ready)
                self.scheduled = list(scheduled)
                self._render_jobs()

            n_ready = len(ready)
            # botão "Processar" só quando há prontos, ocioso E não processando
            self.process_all_btn.setVisible(bool(ready) and idle and not self._processing)
            if not self._processing:
                self.process_all_btn.setEnabled(True)
                self.process_all_btn.setText(f"Processar {n_ready} jogo(s)")
                self.refresh_btn.setEnabled(True)

            # resumo do canto da titlebar
            if live:
                self.queue.setText(f"{len(live)} ao vivo")
            elif n_ready:
                self.queue.setText(f"{n_ready} pronto(s)")
            elif scheduled:
                self.queue.setText(f"{len(scheduled)} agendados")
            else:
                self.queue.setText("sem jogos")

            if processing:
                # realmente processando (clicou em Processar)
                self.active.setText(msg or "Processando…")
                if pct is None:
                    self.status.setText("Processando")
                    self.progress.setRange(0, 0)  # indeterminado
                    self.meta.setText("em andamento")
                else:
                    self.status.setText(f"Processando · {int(pct)}%")
                    self.progress.setRange(0, 100)
                    self.progress.setValue(int(pct))
                    self.meta.setText(f"{int(pct)}%")
                self.status.setStyleSheet("color:#2457a7;")
                self.dot.setStyleSheet(f"background:{DOT_COLORS['run']};")
                return

            # garante barra determinada fora do modo "processando"
            if self.progress.maximum() == 0:
                self.progress.setRange(0, 100)

            if done or pct == 100:
                self.active.setText(msg or "Concluído")
                self.status.setText("Concluído")
                self.status.setStyleSheet("color:#1f9d55;")
                self.dot.setStyleSheet(f"background:{DOT_COLORS['done']};")
                self.progress.setValue(100)
                self.meta.setText("pronto")
                return

            # ── ocioso: o foco é mostrar o que está rolando, não "processando" ──
            self.progress.setValue(0)
            if live:
                self.active.setText("Jogo ao vivo agora")
                self.status.setText("AO VIVO")
                self.status.setStyleSheet("color:#d23a4b; font-weight:800;")
                self.dot.setStyleSheet(f"background:{DOT_COLORS['err']};")
                self.meta.setText(f"{len(scheduled)} agendados" if scheduled else "")
            elif n_ready:
                self.active.setText(f"{n_ready} jogo(s) pronto(s) para processar")
                self.status.setText("Pronto")
                self.status.setStyleSheet("color:#1f9d55;")
                self.dot.setStyleSheet(f"background:{DOT_COLORS['done']};")
                self.meta.setText(f"{len(scheduled)} agendados" if scheduled else "")
            else:
                self.active.setText("Aguardando próximos jogos")
                self.status.setText("Aguardando")
                self.status.setStyleSheet("color:#718096;")
                self.dot.setStyleSheet(f"background:{DOT_COLORS['idle']};")
                self.meta.setText(f"{len(scheduled)} agendados" if scheduled else "sem atividade")

    app = QApplication.instance() or QApplication(sys.argv[:1])
    panel = Panel()
    panel.show()
    app.exec()


# ── entrada ───────────────────────────────────────────────────────────────────

def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return

    mode = args[0]

    if mode == "--window":
        _run_window()
    elif mode == "--daemon":
        _serve_socket()
    elif mode == "--windows":
        threading.Thread(target=_serve_socket, daemon=True).start()
        _run_window()
    elif mode == "--pending":
        items = args[1].split(",") if len(args) > 1 and args[1] else []
        set_pending([i for i in items if i])
    else:
        raw = args[0]
        msg = " ".join(args[1:])
        if raw == "done":
            progress_done(msg or "Concluído")
        elif raw == "idle":
            progress_idle(msg or "Aguardando jogos…")
        else:
            try:
                progress_update(int(raw), msg)
            except ValueError:
                print(f"Argumento inválido: {raw}", file=sys.stderr)


if __name__ == "__main__":
    main()

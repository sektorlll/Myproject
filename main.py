import math
import socket
import threading
import requests

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, Ellipse, RoundedRectangle, Triangle
from kivy.metrics import dp
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.widget import Widget

TV_PORT = 1925
TV_IP = None

# Preencha uma vez (assim o botão ligar funciona com a TV desligada):
# IP e MAC da TV (Configurações > Rede > ver configurações de rede)
TV_IP_FIXO = ""                     # ex.: "192.168.0.50"
TV_MAC = ""                         # ex.: "AA:BB:CC:DD:EE:FF"
if TV_IP_FIXO:
    TV_IP = TV_IP_FIXO

# ---------- Cores (estilo controle Philips: grafite escuro) ----------
FUNDO = (0.07, 0.07, 0.08, 1)
CORPO = (0.12, 0.12, 0.14, 1)
BTN = (0.20, 0.20, 0.23, 1)
ANEL = (0.17, 0.17, 0.19, 1)
OK_COR = (0.10, 0.10, 0.12, 1)
BRANCO = (0.93, 0.93, 0.95, 1)
CINZA = (0.60, 0.60, 0.65, 1)
VERMELHO = (0.85, 0.15, 0.15, 1)
VERDE = (0.15, 0.65, 0.25, 1)
AMARELO = (0.95, 0.75, 0.10, 1)
AZUL = (0.15, 0.40, 0.85, 1)
AMBI = (0.10, 0.45, 0.80, 1)

Window.clearcolor = FUNDO


# ============================================================
# TV
# ============================================================

def descobrir_tv():
    global TV_IP
    msg = (
        'M-SEARCH * HTTP/1.1\r\n'
        'HOST: 239.255.255.250:1900\r\n'
        'MAN: "ssdp:discover"\r\n'
        'MX: 2\r\n'
        'ST: urn:schemas-upnp-org:device:MediaRenderer:1\r\n'
        '\r\n'
    ).encode()
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(3)
        s.sendto(msg, ("239.255.255.250", 1900))
        while True:
            try:
                data, addr = s.recvfrom(8192)
                if "MediaRenderer" in data.decode(errors="ignore"):
                    TV_IP = addr[0]
                    break
            except socket.timeout:
                break
        s.close()
    except Exception as e:
        print("SSDP:", e)
    return TV_IP


def enviar_tecla(tecla):
    if not TV_IP:
        print("TV não encontrada")
        return
    try:
        r = requests.post(
            f"http://{TV_IP}:{TV_PORT}/6/input/key",
            json={"key": tecla},
            timeout=2,
        )
        print(tecla, r.status_code)
    except Exception as e:
        print("Erro:", e)


def wake_on_lan(mac):
    """Envia o pacote mágico (Wake-on-LAN) para ligar a TV."""
    mac = mac.replace(":", "").replace("-", "")
    if len(mac) != 12:
        print("MAC inválido")
        return
    pacote = b"\xff" * 6 + bytes.fromhex(mac) * 16
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    for porta in (9, 7):
        s.sendto(pacote, ("255.255.255.255", porta))
    s.close()


def tv_ligada():
    if not TV_IP:
        return False
    try:
        r = requests.get(f"http://{TV_IP}:{TV_PORT}/6/powerstate", timeout=1.5)
        return r.json().get("powerstate") == "On"
    except Exception:
        return False


def energia():
    """Liga se estiver desligada, desliga se estiver ligada."""
    if tv_ligada():
        enviar_tecla("Standby")
        return
    if TV_MAC:
        wake_on_lan(TV_MAC)
    if TV_IP:
        try:
            requests.post(f"http://{TV_IP}:{TV_PORT}/6/powerstate",
                          json={"powerstate": "On"}, timeout=2)
        except Exception as e:
            print("powerstate:", e)


def mandar(tecla):
    alvo = energia if tecla == "Standby" else enviar_tecla
    args = () if tecla == "Standby" else (tecla,)
    threading.Thread(target=alvo, args=args, daemon=True).start()


# ============================================================
# WIDGETS
# ============================================================

class Tecla(ButtonBehavior, Label):
    """Botão arredondado (ou pílula) que envia uma tecla."""

    def __init__(self, texto, tecla=None, bg=BTN, cor=BRANCO,
                 font=14, pill=True, **kw):
        super().__init__(text=texto, font_size=dp(font), color=cor,
                         bold=True, **kw)
        self.tecla = tecla
        self.bg = bg
        self.pill = pill
        with self.canvas.before:
            self._cor = Color(*bg)
            self._ret = RoundedRectangle(pos=self.pos, size=self.size,
                                         radius=[dp(12)])
        self.bind(pos=self._atualizar, size=self._atualizar,
                  state=self._estado)

    def _atualizar(self, *a):
        self._ret.pos = self.pos
        self._ret.size = self.size
        r = self.height / 2 if self.pill else dp(12)
        self._ret.radius = [r]

    def _estado(self, *a):
        if self.state == "down":
            if self.bg[3] == 0:
                self._cor.rgba = (1, 1, 1, 0.15)
            else:
                self._cor.rgba = tuple(min(1, c + 0.18) for c in self.bg[:3]) + (1,)
        else:
            self._cor.rgba = self.bg

    def on_press(self):
        if self.tecla:
            mandar(self.tecla)


class Circulo(Tecla):
    """Botão redondo (power, mute, etc.)."""

    def _atualizar(self, *a):
        self._ret.pos = self.pos
        self._ret.size = self.size
        self._ret.radius = [min(self.size) / 2]


class DPad(Widget):
    """Direcional circular com OK no centro."""

    def __init__(self, **kw):
        super().__init__(**kw)
        self.lbl = Label(text="OK", bold=True, font_size=dp(18),
                         color=BRANCO, size_hint=(None, None))
        self.add_widget(self.lbl)
        self.bind(pos=self.desenhar, size=self.desenhar)

    def desenhar(self, *a):
        self.canvas.before.clear()
        cx, cy = self.center_x, self.center_y
        R = min(self.size) / 2
        r = R * 0.38
        m = R * 0.69
        t = R * 0.09
        with self.canvas.before:
            Color(*ANEL)
            Ellipse(pos=(cx - R, cy - R), size=(2 * R, 2 * R))
            Color(*OK_COR)
            Ellipse(pos=(cx - r, cy - r), size=(2 * r, 2 * r))
            Color(*BRANCO)
            Triangle(points=[cx - t, cy + m - t, cx + t, cy + m - t, cx, cy + m + t])
            Triangle(points=[cx - t, cy - m + t, cx + t, cy - m + t, cx, cy - m - t])
            Triangle(points=[cx - m + t, cy - t, cx - m + t, cy + t, cx - m - t, cy])
            Triangle(points=[cx + m - t, cy - t, cx + m - t, cy + t, cx + m + t, cy])
        self.lbl.size = (2 * r, 2 * r)
        self.lbl.center = (cx, cy)

    def on_touch_down(self, touch):
        if not self.collide_point(*touch.pos):
            return False
        dx = touch.x - self.center_x
        dy = touch.y - self.center_y
        R = min(self.size) / 2
        d = math.hypot(dx, dy)
        if d > R:
            return False
        if d < R * 0.38:
            mandar("Confirm")
        elif abs(dx) > abs(dy):
            mandar("CursorRight" if dx > 0 else "CursorLeft")
        else:
            mandar("CursorUp" if dy > 0 else "CursorDown")
        return True


class Rocker(BoxLayout):
    """Gangorra vertical (+ / rótulo / −), como VOL e CH da Philips."""

    def __init__(self, rotulo, tecla_mais, tecla_menos, **kw):
        super().__init__(orientation="vertical", **kw)
        with self.canvas.before:
            Color(*BTN)
            self._ret = RoundedRectangle(pos=self.pos, size=self.size,
                                         radius=[dp(30)])
        self.bind(pos=self._atualizar, size=self._atualizar)
        transp = (0, 0, 0, 0)
        self.add_widget(Tecla("+", tecla_mais, bg=transp, font=22, pill=False))
        self.add_widget(Label(text=rotulo, font_size=dp(11), color=CINZA,
                              size_hint_y=0.5))
        self.add_widget(Tecla("-", tecla_menos, bg=transp, font=24, pill=False))

    def _atualizar(self, *a):
        self._ret.pos = self.pos
        self._ret.size = self.size


# ============================================================
# TELA ÚNICA (tudo cabe na tela; alturas proporcionais)
# ============================================================

def linha(peso, spacing=6, **kw):
    return BoxLayout(size_hint_y=peso, spacing=dp(spacing), **kw)


class Remoto(BoxLayout):

    def __init__(self, **kw):
        super().__init__(orientation="vertical", padding=dp(8),
                         spacing=dp(6), **kw)

        self.status = Label(text="Procurando TV...", size_hint_y=0.35,
                            font_size=dp(11), color=CINZA)
        self.add_widget(self.status)

        # Power | Source | Mute | Ambilight
        l = linha(1)
        l.add_widget(Circulo("ON/OFF", "Standby", bg=VERMELHO, font=10))
        l.add_widget(Tecla("SOURCE", "Source", font=11))
        l.add_widget(Tecla("MUTE", "Mute", font=11))
        l.add_widget(Tecla("AMBI", "AmbilightOnOff", bg=AMBI, font=11))
        self.add_widget(l)

        # Home | Back | Info | Options
        l = linha(1)
        for t, k in [("HOME", "Home"), ("BACK", "Back"),
                     ("INFO", "Info"), ("OPTIONS", "Options")]:
            l.add_widget(Tecla(t, k, font=11))
        self.add_widget(l)

        # VOL | D-PAD | CH
        l = linha(4.2, spacing=4)
        l.add_widget(Rocker("VOL", "VolumeUp", "VolumeDown", size_hint_x=0.22))
        l.add_widget(DPad(size_hint_x=0.56))
        l.add_widget(Rocker("CH", "ChannelStepUp", "ChannelStepDown",
                            size_hint_x=0.22))
        self.add_widget(l)

        # Números (2 linhas de 5)
        for faixa in (range(1, 6), [6, 7, 8, 9, 0]):
            l = linha(0.85, spacing=5)
            for n in faixa:
                l.add_widget(Circulo(str(n), f"Digit{n}", font=16))
            self.add_widget(l)

        # Cores
        l = linha(0.45, spacing=8)
        for tecla, cor in [("RedColour", VERMELHO), ("GreenColour", VERDE),
                           ("YellowColour", AMARELO), ("BlueColour", AZUL)]:
            l.add_widget(Tecla("", tecla, bg=cor))
        self.add_widget(l)

        # Playback
        l = linha(0.8)
        for t, k in [("<<", "Rewind"), ("PLAY", "PlayPause"),
                     (">>", "FastForward"), ("STOP", "Stop")]:
            l.add_widget(Tecla(t, k, font=11))
        self.add_widget(l)

        # Funções extras (2 linhas de 3)
        extras = [("FIND", "Find"), ("ADJUST", "Adjust"), ("FORMAT", "Viewmode"),
                  ("SUBTITLE", "Subtitle"), ("TEXT", "Teletext"),
                  ("WATCH TV", "WatchTV")]
        for i in (0, 3):
            l = linha(0.75, spacing=5)
            for t, k in extras[i:i + 3]:
                l.add_widget(Tecla(t, k, font=10))
            self.add_widget(l)

        threading.Thread(target=self.buscar, daemon=True).start()

    def buscar(self):
        ip = descobrir_tv()
        Clock.schedule_once(
            lambda dt: setattr(
                self.status, "text",
                ("TV conectada: " + ip) if ip else "TV não encontrada"),
            0)


class PhilipsRemote(App):

    def build(self):
        self.title = "Philips Remote"
        return Remoto()


if __name__ == "__main__":
    PhilipsRemote().run()

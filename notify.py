"""Notificacao nativa do desktop no fim de fase.

Motivo: a troca de fase e manual, entao o fim do tempo precisa chegar a voce
mesmo com o app minimizado ou atras de outra janela. O bipe avisa que *algo*
aconteceu; a notificacao diz o que, aparece por cima de tudo e fica guardada
na central de notificacoes se voce nao vir na hora.

Backends, escolhidos na inicializacao:
    Linux  -> notify-send (libnotify; presente em praticamente todo desktop)
    macOS  -> osascript
    outros -> nenhum, e o Notifier fica em silencio

Nao ha dependencia nova: e um processo externo, disparado numa thread daemon
para nao segurar o loop de 60 FPS se o barramento estiver lento.
"""

import shutil
import subprocess
import threading

APP_NAME = "Pomodoro Pet"
ICON = "appointment-soon"     # icone do tema do sistema, sem asset proprio
TIMEOUT = 5.0                 # segundos ate desistir do processo externo

# Faz a notificacao nova substituir a anterior em vez de empilhar.
# Ignorado por servidores que nao conhecem a dica.
SYNCHRONOUS_HINT = "string:x-canonical-private-synchronous:pomodoro-pet"


def _linux_command(title, body):
    return ["notify-send", "-a", APP_NAME, "-i", ICON,
            "-h", SYNCHRONOUS_HINT, title, body]


def _macos_command(title, body):
    script = (f'display notification "{body}" '
              f'with title "{APP_NAME}" subtitle "{title}"')
    return ["osascript", "-e", script]


BACKENDS = (
    ("notify-send", _linux_command),
    ("osascript", _macos_command),
)


def _run(command):
    try:
        subprocess.run(command, timeout=TIMEOUT, check=False,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass          # notificacao e conveniencia: nunca derruba o app


class Notifier:
    """Envia notificacoes do sistema, se houver como.

    `backend` fica com o nome do binario escolhido (ou None), para o app e os
    testes distinguirem "desligado por opcao" de "nao ha backend aqui".
    """

    def __init__(self, enabled=True, which=None, runner=None):
        self.enabled = bool(enabled)
        self.backend = None
        self._build = None
        self._runner = runner or self._spawn
        which = which or shutil.which
        if not self.enabled:
            return
        for binary, build in BACKENDS:
            if which(binary):
                self.backend = binary
                self._build = build
                break

    @property
    def ok(self):
        return self.enabled and self.backend is not None

    @staticmethod
    def _spawn(command):
        # daemon: se o app fechar antes, a thread nao segura o processo
        threading.Thread(target=_run, args=(command,), daemon=True).start()

    def notify(self, title, body):
        """Dispara a notificacao. Retorna se havia como enviar."""
        if not self.ok:
            return False
        try:
            self._runner(self._build(title, body))
            return True
        except Exception:
            return False

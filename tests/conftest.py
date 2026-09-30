import sys
import os

# Add project root to Python path so 'import pomodoro' works
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Drivers falsos antes de qualquer import de pygame: a suite roda sem abrir
# janela e sem emitir som, inclusive em CI e por ssh.
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pytest

import notify
import storage


@pytest.fixture(autouse=True)
def isolated_state(tmp_path, monkeypatch):
    """Cada teste comeca com o estado em disco vazio, num diretorio proprio.

    Sem isso a suite leria e sobrescreveria o estado real do usuario, e os
    testes passariam a depender de quanto o bichinho tinha de energia.
    """
    path = tmp_path / "state.json"
    monkeypatch.setattr(storage, "state_path", lambda: str(path))
    return path


@pytest.fixture(autouse=True)
def no_desktop_notifications(monkeypatch):
    """Nenhum teste dispara notificacao de verdade.

    Sem isso, rodar a suite numa maquina com notify-send encheria a central
    de notificacoes do desenvolvedor a cada `pytest`.
    """
    monkeypatch.setattr(notify.Notifier, "_spawn",
                        staticmethod(lambda command: None))

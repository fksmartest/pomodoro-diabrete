"""Persistencia do bichinho entre sessoes.

Sem isso o acumulo de cansaco — a ideia central do Tamagotchi — nao sobrevive
a fechar o app. Aqui ficam o arquivo de estado e a regra de retomada.

A regra, em uma frase: reabrir logo depois continua de onde parou; reabrir no
dia seguinte comeca descansado.

    fechou e reabriu em ate RESUME_WINDOW (2h), no mesmo dia
        -> retoma energia, ciclos, fase e tempo restante (sempre pausado,
           porque o tempo passou enquanto o app estava fechado)
    fora disso
        -> sessao nova com a energia inicial; os ciclos do dia continuam
           contados no historico

O historico guarda quantos focos foram concluidos em cada dia, que e o dado
que sobrevive a tudo e responde "como foi minha semana" (ver --stats).
"""

import json
import os
import sys
import tempfile
import time

APP_DIR = "pomodoro-pet"
STATE_FILE = "state.json"
VERSION = 1

RESUME_WINDOW = 2 * 60 * 60     # segundos: reabrir dentro disso retoma
HISTORY_DAYS = 60               # dias mantidos no historico


def state_dir():
    """Diretorio de estado do usuario, conforme a convencao de cada sistema."""
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
    elif sys.platform == "darwin":
        base = os.path.expanduser("~/Library/Application Support")
    else:
        base = (os.environ.get("XDG_STATE_HOME")
                or os.path.expanduser("~/.local/state"))
    return os.path.join(base, APP_DIR)


def state_path():
    return os.path.join(state_dir(), STATE_FILE)


def today(now=None):
    return time.strftime("%Y-%m-%d", time.localtime(now or time.time()))


def should_resume(saved_at, now, window=RESUME_WINDOW):
    """Retoma so se foi ha pouco e no mesmo dia."""
    if saved_at is None or now < saved_at:
        return False            # relogio andou para tras: nao confia
    if now - saved_at > window:
        return False
    return today(saved_at) == today(now)


def trim_history(history, keep=HISTORY_DAYS):
    """Mantem apenas os dias mais recentes, para o arquivo nao crescer."""
    days = sorted(history)[-keep:]
    return {day: history[day] for day in days}


def snapshot(pet, history, now=None):
    """Estado serializavel do bichinho + historico."""
    return {
        "version": VERSION,
        "saved_at": now or time.time(),
        "phase": pet.phase,
        "remaining": pet.remaining,
        "awaiting": pet.awaiting,
        "energy": pet.energy,
        "cycles": pet.cycles,
        "history": trim_history(dict(history)),
    }


def restore(pet, state, now=None):
    """Aplica o estado salvo ao bichinho. Devolve se houve retomada."""
    now = now or time.time()
    if not state or state.get("version") != VERSION:
        return False
    if not should_resume(state.get("saved_at"), now):
        return False
    pet.phase = state["phase"]
    # clamp: o estado pode ter sido gravado com duracoes maiores (--demo usa
    # ciclos de segundos), e restaurar 1400s numa fase de 6s travaria o app
    pet.remaining = max(0.0, min(float(state["remaining"]), pet.duration))
    pet.awaiting = bool(state["awaiting"])
    pet.energy = float(state["energy"])
    pet.cycles = int(state["cycles"])
    # Sempre pausado: o tempo correu com o app fechado e nao deve ser contado.
    pet.running = False
    return True


class StateStore:
    """Le e escreve o arquivo de estado. Falhas de disco nunca sobem."""

    def __init__(self, path=None, enabled=True):
        self.enabled = bool(enabled)
        self.path = path or state_path()

    def load(self):
        """Estado salvo, ou {} se nao houver, estiver corrompido ou ilegivel."""
        if not self.enabled:
            return {}
        try:
            with open(self.path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def save(self, state):
        """Grava de forma atomica: escreve ao lado e troca o arquivo."""
        if not self.enabled:
            return False
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            handle = tempfile.NamedTemporaryFile(
                "w", encoding="utf-8", delete=False,
                dir=os.path.dirname(self.path), prefix=".state-", suffix=".tmp")
            try:
                with handle:
                    json.dump(state, handle, indent=2)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(handle.name, self.path)
            except BaseException:
                # nao deixa lixo se a troca falhar no meio
                try:
                    os.unlink(handle.name)
                except OSError:
                    pass
                raise
            return True
        except (OSError, ValueError, TypeError):
            return False


def format_stats(history, days=14):
    """Resumo em texto dos focos concluidos por dia (usado por --stats)."""
    if not history:
        return "Nenhum ciclo registrado ainda."
    recent = sorted(history.items())[-days:]
    width = max(len(str(count)) for _, count in recent)
    lines = [f"Focos concluidos (ultimos {len(recent)} dias com registro):", ""]
    for day, count in recent:
        lines.append(f"  {day}  {count:>{width}}  {'#' * count}")
    total = sum(count for _, count in recent)
    lines += ["", f"  total {total} | media {total / len(recent):.1f} por dia"]
    return "\n".join(lines)

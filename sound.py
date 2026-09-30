"""Bipes do fim de fase, sintetizados em codigo.

Mesma filosofia do sprite: nada de assets externos. As ondas sao geradas com
a stdlib (`array`) e entregues ao mixer do pygame como buffer cru, entao o
projeto continua com uma unica dependencia.

Se o mixer nao abrir — maquina sem placa de som, container, driver `dummy`,
PulseAudio ausente — a classe simplesmente fica muda em vez de derrubar o app.
"""

import array
import math

SAMPLE_RATE = 44100
AMPLITUDE = 0.28        # bem abaixo do teto: e um lembrete, nao um susto
FADE = 0.012            # rampa (s) para nao estalar no inicio/fim da nota

# (frequencia Hz, duracao s) — alerta sobe dois tons; alegria e um arpejo
ALERT_NOTES = ((660.0, 0.13), (880.0, 0.20))
JOY_NOTES = ((659.3, 0.09), (830.6, 0.09), (987.8, 0.09), (1318.5, 0.18))


def _envelope(i, total, fade_samples):
    """Rampa linear de entrada e saida, para evitar o clique do corte seco."""
    if i < fade_samples:
        return i / fade_samples
    if i > total - fade_samples:
        return max(0.0, (total - i) / fade_samples)
    return 1.0


def render_notes(notes, sample_rate=SAMPLE_RATE, amplitude=AMPLITUDE):
    """Devolve um array('h') mono 16-bit com as notas tocadas em sequencia."""
    samples = array.array("h")
    peak = int(32767 * amplitude)
    for freq, duration in notes:
        total = max(1, int(sample_rate * duration))
        fade_samples = max(1, int(sample_rate * FADE))
        step = 2.0 * math.pi * freq / sample_rate
        for i in range(total):
            value = math.sin(step * i) * _envelope(i, total, fade_samples)
            samples.append(int(peak * value))
    return samples


class Chime:
    """Toca os bipes do app. Silencioso e inofensivo quando nao ha audio.

    `ok` diz se o mixer abriu de verdade — util para o app (e para os testes)
    distinguirem "mudo por opcao" de "mudo por falta de dispositivo".
    """

    def __init__(self, enabled=True, mixer=None):
        self.enabled = bool(enabled)
        self.ok = False
        self._alert = None
        self._joy = None
        if not self.enabled:
            return
        try:
            if mixer is None:
                import pygame.mixer as mixer
            mixer.init(frequency=SAMPLE_RATE, size=-16, channels=1,
                       buffer=512)
            self._alert = mixer.Sound(buffer=render_notes(ALERT_NOTES))
            self._joy = mixer.Sound(buffer=render_notes(JOY_NOTES))
            self.ok = True
        except Exception:
            # Sem audio o app continua util; o "!" na tela ainda avisa.
            self.ok = False
            self._alert = None
            self._joy = None

    def _play(self, sound):
        if not self.ok or sound is None:
            return False
        try:
            sound.play()
            return True
        except Exception:
            return False

    def alert(self):
        """Fim de fase: o bichinho esta esperando voce."""
        return self._play(self._alert)

    def joy(self):
        """Comecou a pausa: comemoracao."""
        return self._play(self._joy)

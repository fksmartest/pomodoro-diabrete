#!/usr/bin/env python3
"""Gera os icones do app a partir do proprio sprite do bichinho.

Mesma filosofia do resto do projeto: nada de asset externo. O icone e o
personagem desenhado pelo codigo que roda na tela, so que renderizado
headless e ampliado com nearest-neighbor para cada tamanho que o tema de
icones espera.

    python desktop/make_icons.py [destino]
"""

import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame

from pomodoro import PetWindow, SPRITE
from storage import StateStore

# Energia do bichinho no icone: alta o bastante para ele estar sorrindo,
# baixa o bastante para os chifres e a cauda ja aparecerem — e isso que da
# identidade ao personagem. Com energia cheia ele fica verde e sem chifres,
# e o icone perde a graca.
ICON_ENERGY = 52.0
ICON_EXPRESSION = "happy"
ICON_TIME = 1.0        # nao use 0.0: cai no frame em que ele pisca
SIZES = (16, 24, 32, 48, 64, 128, 256)
NAME = "pomodoro-pet"


def build_sprite():
    window = PetWindow(focus_duration=1500, break_duration=300, mute=True,
                       notify=False, scale=1,
                       store=StateStore(enabled=False))
    window.pet.energy = ICON_ENERGY
    window.look = (0.0, 0.0)                   # olhando para a frente
    sprite = window._sprite(ICON_EXPRESSION, ICON_TIME)
    window.running = False
    return sprite


def resize(sprite, size):
    """Amplia com nearest (mantem a pixel art) e reduz com suavizacao."""
    if size >= sprite.get_width():
        return pygame.transform.scale(sprite, (size, size))
    return pygame.transform.smoothscale(sprite, (size, size))


def trim(surface):
    """Recorta a margem transparente, para o bichinho ocupar o quadro todo."""
    rect = surface.get_bounding_rect()
    side = max(rect.width, rect.height)
    square = pygame.Surface((side, side), pygame.SRCALPHA)
    square.blit(surface, ((side - rect.width) // 2 - rect.x,
                          (side - rect.height) // 2 - rect.y))
    return square


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    out_dir = argv[0] if argv else os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "icons")

    sprite = trim(build_sprite())
    written = []
    for size in SIZES:
        target = os.path.join(out_dir, f"{size}x{size}")
        os.makedirs(target, exist_ok=True)
        scaled = resize(sprite, size)
        path = os.path.join(target, f"{NAME}.png")
        pygame.image.save(scaled, path)
        written.append(path)

    print(f"{len(written)} icones gerados a partir de um sprite de "
          f"{SPRITE}x{SPRITE}:")
    for path in written:
        print(f"  {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

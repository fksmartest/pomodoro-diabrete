"""Regressoes de portabilidade: o app precisa se comportar fora do Windows.

Cada teste aqui cobre um bug real observado ao rodar no Linux (Fedora 44,
KDE Plasma em Wayland) com a versao anterior do codigo.
"""

import os

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import pygame
import pytest

import pomodoro
from pomodoro import (
    PetWindow, _WindowDrag, main,
    BG, MAGIC, BUTTON_PADDING,
    BTN_MAIN, BTN_SKIP, BTN_RESET, BTN_EXIT,
)


@pytest.fixture
def window():
    w = PetWindow(focus_duration=2, break_duration=1, mute=True)
    yield w
    w.running = False


class _SpyChime:
    def __init__(self):
        self.alerts = 0
        self.joys = 0

    def alert(self):
        self.alerts += 1
        return True

    def joy(self):
        self.joys += 1
        return True


class TestWindowDragWithoutNativeApi:
    """Sem a API do Windows, os metodos devolvem valores neutros em vez de
    estourar AttributeError no primeiro clique."""

    @pytest.fixture
    def drag(self):
        d = _WindowDrag.__new__(_WindowDrag)
        d.ok = False
        d.transparent = False
        return d

    def test_cursor_pos_is_safe(self, drag):
        assert drag.cursor_pos() == (0, 0)

    def test_top_left_is_safe(self, drag):
        assert drag.top_left() == (0, 0)

    def test_move_to_is_a_noop(self, drag):
        assert drag.move_to(10, 10) is None

    def test_set_topmost_is_a_noop(self, drag):
        assert drag.set_topmost() is None

    def test_set_alpha_is_a_noop(self, drag):
        assert drag.set_alpha(120) is None


class TestMouseDownDoesNotCrash:
    def test_left_click_without_native_drag(self, window):
        window.drag.ok = False
        event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1,
                                   pos=(120, 120))
        window._on_mouse_down(event)          # nao pode levantar excecao
        assert window.pressed is True

    def test_motion_without_native_drag(self, window):
        window.drag.ok = False
        window.pressed = True
        window._on_motion()
        assert window.drag_moved is False

    def test_right_click_resets(self, window):
        window.pet.cycles = 3
        event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=3,
                                   pos=(120, 120))
        window._on_mouse_down(event)
        assert window.pet.cycles == 0


class TestBackgroundColor:
    def test_solid_background_when_transparency_is_unavailable(self, window):
        """A cor-chave so pode ser usada quando a layered window existe."""
        if window.drag.transparent:
            assert window.base == MAGIC
        else:
            assert window.base == BG

    def test_opaque_flag_forces_solid_background(self):
        w = PetWindow(focus_duration=2, break_duration=1, opaque=True,
                      mute=True)
        assert w.base == BG
        assert w.drag.transparent is False
        w.running = False


class TestButtonLabelsFit:
    """Fora do Windows a Consolas nao existe e o fallback e mais largo."""

    LABELS = [
        (BTN_MAIN, "comecar pausa"),
        (BTN_MAIN, "iniciar foco"),
        (BTN_MAIN, "iniciar pausa"),
        (BTN_MAIN, "pausar"),
        (BTN_MAIN, "retomar"),
        (BTN_SKIP, "pular"),
        (BTN_RESET, "reset"),
        (BTN_EXIT, "sair"),
    ]

    @pytest.mark.parametrize("rect,label", LABELS)
    def test_label_fits_inside_button(self, window, rect, label):
        font = window._button_font(label, rect.width - BUTTON_PADDING)
        assert font.size(label)[0] <= rect.width - BUTTON_PADDING

    def test_picks_the_largest_font_that_fits(self, window):
        wide = window._button_font("ok", 999)
        assert wide is window.font_buttons[0]

    def test_falls_back_to_smallest_when_nothing_fits(self, window):
        tiny = window._button_font("rotulo bem comprido", 1)
        assert tiny is window.font_buttons[-1]

    def test_every_action_label_is_covered(self, window):
        """Se _action_label() ganhar um rotulo novo, ele entra na lista acima."""
        seen = set()
        for awaiting, running, progress, phase in [
            (True, False, 1.0, "focus"), (True, False, 1.0, "break"),
            (False, True, 0.5, "focus"), (False, False, 0.5, "focus"),
            (False, False, 0.0, "focus"), (False, False, 0.0, "break"),
        ]:
            window.pet.awaiting = awaiting
            window.pet.running = running
            window.pet.phase = phase
            window.pet.remaining = window.pet.duration * (1 - progress)
            seen.add(window._action_label())
        assert seen <= {label for _, label in self.LABELS}


class TestChimeIsTriggered:
    def test_alert_on_phase_end_from_tick(self, window):
        window.chime = _SpyChime()
        window.pet.start()
        window._update(10)
        assert window.pet.awaiting is True
        assert window.chime.alerts == 1

    def test_alert_on_skip(self, window):
        window.chime = _SpyChime()
        window._skip()
        assert window.chime.alerts == 1

    def test_joy_when_break_starts(self, window):
        window.chime = _SpyChime()
        window.pet.skip()
        window._primary_action()
        assert window.chime.joys == 1
        assert window.joy > 0

    def test_no_joy_when_focus_starts(self, window):
        window.pet.skip()
        window._primary_action()      # -> pausa
        window.pet.skip()
        window.chime = _SpyChime()
        window._primary_action()      # -> foco
        assert window.chime.joys == 0

    def test_mute_creates_a_silent_chime(self, window):
        assert window.chime.enabled is False
        assert window.chime.ok is False


class TestCli:
    def test_help_returns_zero_without_opening_a_window(self, capsys):
        assert main(["--help"]) == 0
        assert "--mute" in capsys.readouterr().out

    def test_unknown_argument_is_rejected(self, capsys):
        assert main(["--turbo"]) == 2
        assert "desconhecido" in capsys.readouterr().out

    def test_mono_list_has_a_generic_fallback(self):
        assert pomodoro.MONO.strip().endswith("monospace")

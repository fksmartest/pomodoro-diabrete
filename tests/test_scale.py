"""Escala da interface: a janela cresce, o layout logico continua 240x168."""

import os

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import pygame
import pytest

from pomodoro import (
    PetWindow, auto_ui_scale, parse_args,
    WIDTH, HEIGHT, MAX_UI_SCALE, BTN_EXIT, BTN_SKIP,
)


def make(scale):
    return PetWindow(focus_duration=2, break_duration=1, mute=True,
                     scale=scale)


class TestAutoScale:
    @pytest.mark.parametrize("height,expected", [
        (768, 1),
        (1080, 1),
        (1399, 1),
        (1400, 2),
        (1800, 2),
        (1999, 2),
        (2000, 3),
        (2160, 3),
    ])
    def test_scale_grows_with_screen_height(self, height, expected):
        assert auto_ui_scale(height) == expected

    def test_never_returns_zero(self):
        assert auto_ui_scale(0) == 1
        assert auto_ui_scale(-100) == 1


class TestWindowSize:
    @pytest.mark.parametrize("scale", [1, 2, 3, 4])
    def test_window_is_the_logical_size_times_scale(self, scale):
        w = make(scale)
        assert w.window.get_size() == (WIDTH * scale, HEIGHT * scale)
        w.running = False

    @pytest.mark.parametrize("scale", [1, 2, 3])
    def test_logical_surface_never_changes(self, scale):
        w = make(scale)
        assert w.screen.get_size() == (WIDTH, HEIGHT)
        w.running = False

    def test_scale_one_draws_straight_to_the_window(self):
        w = make(1)
        assert w.screen is w.window
        w.running = False

    def test_higher_scale_uses_a_separate_surface(self):
        w = make(3)
        assert w.screen is not w.window
        w.running = False

    def test_scale_is_clamped(self):
        low = make(0)
        high = make(MAX_UI_SCALE + 5)
        assert low.scale == 1
        assert high.scale == MAX_UI_SCALE
        low.running = high.running = False

    def test_drag_knows_the_real_window_size(self):
        w = make(3)
        assert w.drag.size == (WIDTH * 3, HEIGHT * 3)
        w.running = False


class TestMouseMapping:
    """O bug que esta classe existe para impedir: com a janela ampliada, um
    clique visual sobre um botao chegava em coordenada de janela e errava o
    alvo, porque os retangulos do layout estao em pixels logicos."""

    @pytest.mark.parametrize("scale", [1, 2, 3])
    def test_click_on_exit_button_hits_at_any_scale(self, scale):
        w = make(scale)
        target = BTN_EXIT.center
        event = pygame.event.Event(
            pygame.MOUSEBUTTONUP, button=1,
            pos=(target[0] * scale, target[1] * scale))
        w.reveal = 1.0
        w._on_mouse_up(event)
        assert w.running is False

    @pytest.mark.parametrize("scale", [1, 2, 3])
    def test_click_on_skip_button_hits_at_any_scale(self, scale):
        w = make(scale)
        w.reveal = 1.0
        target = BTN_SKIP.center
        event = pygame.event.Event(
            pygame.MOUSEBUTTONUP, button=1,
            pos=(target[0] * scale, target[1] * scale))
        w._on_mouse_up(event)
        assert w.pet.awaiting is True
        w.running = False

    def test_to_logical_divides_by_scale(self):
        w = make(3)
        assert w._to_logical((300, 150)) == (100, 50)
        w.running = False

    def test_to_logical_is_identity_at_scale_one(self):
        w = make(1)
        assert w._to_logical((77, 55)) == (77, 55)
        w.running = False

    @pytest.mark.parametrize("scale", [1, 2, 3])
    def test_draw_produces_a_full_window_at_any_scale(self, scale):
        w = make(scale)
        w.reveal = 1.0
        w._draw()
        assert w.window.get_size() == (WIDTH * scale, HEIGHT * scale)
        w.running = False


class TestScaleCli:
    def test_scale_flag_is_parsed(self):
        options, code = parse_args(["--scale", "3"])
        assert code is None
        assert options["scale"] == 3

    def test_absent_flag_means_auto(self):
        options, code = parse_args([])
        assert code is None
        assert options["scale"] is None

    def test_scale_combines_with_other_flags(self):
        options, _ = parse_args(["--demo", "--scale", "2", "--mute"])
        assert options["scale"] == 2
        assert options["demo"] is True
        assert options["mute"] is True

    @pytest.mark.parametrize("bad", [
        ["--scale"],
        ["--scale", "0"],
        ["--scale", "99"],
        ["--scale", "grande"],
        ["--scale", "-2"],
    ])
    def test_invalid_scale_is_rejected(self, bad, capsys):
        options, code = parse_args(bad)
        assert code == 2
        assert options is None
        capsys.readouterr()

    def test_help_mentions_scale(self, capsys):
        parse_args(["--help"])
        assert "--scale" in capsys.readouterr().out

"""Integracao com o desktop: icone gerado do sprite e entrada de menu."""

import os
import sys

import pygame
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DESKTOP = os.path.join(ROOT, "desktop")
sys.path.insert(0, DESKTOP)

import make_icons
from make_icons import build_sprite, trim, resize, SIZES, NAME


TEMPLATE = os.path.join(DESKTOP, f"{NAME}.desktop.in")
INSTALLER = os.path.join(DESKTOP, "install.sh")


class TestWmClass:
    """Sem WM_CLASS a barra de tarefas nao liga a janela ao lancador."""

    def test_app_declares_a_window_class(self):
        import pomodoro
        assert pomodoro.WM_CLASS == NAME

    def test_both_backends_are_set(self):
        import pomodoro                      # noqa: F401  (define no import)
        assert os.environ["SDL_VIDEO_X11_WMCLASS"] == NAME
        assert os.environ["SDL_VIDEO_WAYLAND_WMCLASS"] == NAME

    def test_desktop_entry_matches_the_app(self):
        with open(TEMPLATE, encoding="utf-8") as handle:
            content = handle.read()
        import pomodoro
        assert f"StartupWMClass={pomodoro.WM_CLASS}" in content


class TestSprite:
    def test_icon_time_avoids_the_blink_frame(self):
        """t=0 cai justamente no frame em que o bichinho pisca."""
        blink_at = lambda t: (t % 3.6) < 0.11
        assert blink_at(0.0) is True
        assert blink_at(make_icons.ICON_TIME) is False

    def test_sprite_is_not_empty(self):
        sprite = build_sprite()
        assert sprite.get_bounding_rect().width > 0

    def test_energy_keeps_the_horns_visible(self):
        """Com energia cheia o bichinho perde chifres e cauda."""
        from pomodoro import clamp
        menace = clamp((0.7 - make_icons.ICON_ENERGY / 100.0) / 0.7, 0.0, 1.0)
        assert menace > 0.2      # limiar em que a cauda nasce


class TestTrim:
    def test_result_is_square(self):
        square = trim(build_sprite())
        assert square.get_width() == square.get_height()

    def test_no_transparent_border_is_wasted(self):
        square = trim(build_sprite())
        bounds = square.get_bounding_rect()
        assert max(bounds.width, bounds.height) == square.get_width()


class TestResize:
    @pytest.fixture
    def sprite(self):
        return trim(build_sprite())

    @pytest.mark.parametrize("size", SIZES)
    def test_every_size_is_produced(self, sprite, size):
        assert resize(sprite, size).get_size() == (size, size)

    def test_enlarging_keeps_hard_pixels(self, sprite):
        """Ampliar com suavizacao borraria a pixel art."""
        big = resize(sprite, 256)
        colors = {big.get_at((x, 128))[:3] for x in range(100, 160)}
        assert len(colors) < 20      # blocos de cor, nao um degrade

    def test_writes_every_size(self, sprite, tmp_path):
        make_icons.main([str(tmp_path)])
        for size in SIZES:
            assert (tmp_path / f"{size}x{size}" / f"{NAME}.png").exists()


class TestDesktopEntry:
    @pytest.fixture
    def template(self):
        with open(TEMPLATE, encoding="utf-8") as handle:
            return handle.read()

    def test_is_an_application_entry(self, template):
        assert template.startswith("[Desktop Entry]")
        assert "Type=Application" in template

    @pytest.mark.parametrize("marker", ["@PYTHON@", "@APPDIR@", "@ARGS@",
                                        "@TERMINAL@"])
    def test_installer_replaces_every_marker(self, template, marker):
        """Um marcador esquecido viraria um lancador quebrado."""
        assert marker in template
        with open(INSTALLER, encoding="utf-8") as handle:
            assert marker in handle.read()

    def test_runs_without_a_terminal(self, template):
        assert "Terminal=false" in template

    def test_offers_the_stats_action(self, template):
        assert "Actions=Stats;" in template
        assert "[Desktop Action Stats]" in template
        assert "--stats" in template

    def test_installer_is_executable(self):
        assert os.access(INSTALLER, os.X_OK)

    def test_installer_supports_uninstall(self):
        with open(INSTALLER, encoding="utf-8") as handle:
            assert "--uninstall" in handle.read()

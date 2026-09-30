"""Testes do sintetizador de bipes — sem tocar audio de verdade."""

import array

import pytest

from sound import Chime, render_notes, SAMPLE_RATE


class _FakeSound:
    def __init__(self, buffer=None):
        self.buffer = buffer
        self.plays = 0

    def play(self):
        self.plays += 1


class _FakeMixer:
    """Dublê do pygame.mixer, para testar sem dispositivo de audio."""

    Sound = _FakeSound

    def __init__(self, fail=False):
        self.fail = fail
        self.init_kwargs = None

    def init(self, **kwargs):
        if self.fail:
            raise RuntimeError("sem dispositivo de audio")
        self.init_kwargs = kwargs


class TestRenderNotes:
    def test_returns_signed_16bit_array(self):
        samples = render_notes(((440.0, 0.01),))
        assert isinstance(samples, array.array)
        assert samples.typecode == "h"

    def test_length_matches_duration(self):
        samples = render_notes(((440.0, 0.1),), sample_rate=1000)
        assert len(samples) == 100

    def test_sequences_are_concatenated(self):
        samples = render_notes(((440.0, 0.1), (880.0, 0.2)), sample_rate=1000)
        assert len(samples) == 300

    def test_stays_inside_16bit_range(self):
        samples = render_notes(((440.0, 0.05),))
        assert max(samples) <= 32767
        assert min(samples) >= -32768

    def test_amplitude_is_respected(self):
        quiet = render_notes(((440.0, 0.05),), amplitude=0.1)
        loud = render_notes(((440.0, 0.05),), amplitude=0.5)
        assert max(loud) > max(quiet)

    def test_fade_starts_and_ends_near_silence(self):
        samples = render_notes(((440.0, 0.2),))
        assert abs(samples[0]) < 50
        assert abs(samples[-1]) < 50


class TestChime:
    def test_disabled_never_plays(self):
        chime = Chime(enabled=False, mixer=_FakeMixer())
        assert chime.ok is False
        assert chime.alert() is False
        assert chime.joy() is False

    def test_enabled_plays_both_sounds(self):
        chime = Chime(enabled=True, mixer=_FakeMixer())
        assert chime.ok is True
        assert chime.alert() is True
        assert chime.joy() is True
        assert chime._alert.plays == 1
        assert chime._joy.plays == 1

    def test_mixer_failure_degrades_to_silence(self):
        chime = Chime(enabled=True, mixer=_FakeMixer(fail=True))
        assert chime.ok is False
        assert chime.enabled is True     # queria som, mas nao ha dispositivo
        assert chime.alert() is False    # e nao levanta excecao

    def test_mixer_is_configured_as_mono_16bit(self):
        mixer = _FakeMixer()
        Chime(enabled=True, mixer=mixer)
        assert mixer.init_kwargs["frequency"] == SAMPLE_RATE
        assert mixer.init_kwargs["size"] == -16
        assert mixer.init_kwargs["channels"] == 1

    def test_play_survives_a_failing_sound(self):
        chime = Chime(enabled=True, mixer=_FakeMixer())

        def boom():
            raise RuntimeError("canal ocupado")

        chime._alert.play = boom
        assert chime.alert() is False

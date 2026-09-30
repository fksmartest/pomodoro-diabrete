"""Notificacao do sistema — testada com dublês, sem disparar processo algum."""

import pytest

import notify
from notify import Notifier, APP_NAME


class _Runner:
    """Captura o comando em vez de executa-lo."""

    def __init__(self, fail=False):
        self.commands = []
        self.fail = fail

    def __call__(self, command):
        if self.fail:
            raise OSError("nao foi possivel iniciar o processo")
        self.commands.append(command)


def which_only(*available):
    return lambda binary: f"/usr/bin/{binary}" if binary in available else None


class TestBackendChoice:
    def test_prefers_notify_send(self):
        n = Notifier(which=which_only("notify-send", "osascript"))
        assert n.backend == "notify-send"

    def test_falls_back_to_osascript(self):
        n = Notifier(which=which_only("osascript"))
        assert n.backend == "osascript"

    def test_no_backend_available(self):
        n = Notifier(which=which_only())
        assert n.backend is None
        assert n.ok is False

    def test_disabled_skips_detection(self):
        n = Notifier(enabled=False, which=which_only("notify-send"))
        assert n.backend is None
        assert n.ok is False

    def test_ok_requires_both_enabled_and_backend(self):
        assert Notifier(which=which_only("notify-send")).ok is True


class TestSending:
    def test_sends_through_the_runner(self):
        runner = _Runner()
        n = Notifier(which=which_only("notify-send"), runner=runner)
        assert n.notify("Foco concluido", "Hora da pausa") is True
        assert len(runner.commands) == 1

    def test_linux_command_shape(self):
        runner = _Runner()
        n = Notifier(which=which_only("notify-send"), runner=runner)
        n.notify("Titulo", "Corpo")
        command = runner.commands[0]
        assert command[0] == "notify-send"
        assert APP_NAME in command
        assert command[-2:] == ["Titulo", "Corpo"]

    def test_linux_replaces_previous_notification(self):
        runner = _Runner()
        n = Notifier(which=which_only("notify-send"), runner=runner)
        n.notify("a", "b")
        assert notify.SYNCHRONOUS_HINT in runner.commands[0]

    def test_macos_command_shape(self):
        runner = _Runner()
        n = Notifier(which=which_only("osascript"), runner=runner)
        n.notify("Titulo", "Corpo")
        command = runner.commands[0]
        assert command[0] == "osascript"
        assert "display notification" in command[-1]
        assert "Corpo" in command[-1]

    def test_no_backend_sends_nothing(self):
        runner = _Runner()
        n = Notifier(which=which_only(), runner=runner)
        assert n.notify("a", "b") is False
        assert runner.commands == []

    def test_disabled_sends_nothing(self):
        runner = _Runner()
        n = Notifier(enabled=False, which=which_only("notify-send"),
                     runner=runner)
        assert n.notify("a", "b") is False
        assert runner.commands == []

    def test_runner_failure_is_swallowed(self):
        n = Notifier(which=which_only("notify-send"), runner=_Runner(fail=True))
        assert n.notify("a", "b") is False      # e nao levanta excecao


class TestIntegrationWithTheApp:
    """A notificacao precisa sair no fim de fase, com o texto da fase certa."""

    @pytest.fixture
    def window(self):
        from pomodoro import PetWindow
        w = PetWindow(focus_duration=2, break_duration=1, mute=True,
                      scale=1)
        w.notifier = Notifier(which=which_only("notify-send"),
                              runner=_Runner())
        yield w
        w.running = False

    def test_focus_end_announces_the_break(self, window):
        window._skip()
        title, body = window.notifier._runner.commands[0][-2:]
        assert "Foco" in title
        assert "pausa" in body.lower()

    def test_break_end_announces_the_focus(self, window):
        window.pet.skip()
        window.pet.advance()          # entra na pausa
        window._skip()
        title, body = window.notifier._runner.commands[-1][-2:]
        assert "Pausa" in title
        assert "foco" in body.lower()

    def test_tick_reaching_zero_also_notifies(self, window):
        window.pet.start()
        window._update(10)
        assert len(window.notifier._runner.commands) == 1

    def test_no_notify_flag_disables_it(self):
        from pomodoro import PetWindow
        w = PetWindow(focus_duration=2, break_duration=1, mute=True,
                      scale=1, notify=False)
        assert w.notifier.ok is False
        w._skip()                     # nao pode levantar excecao
        w.running = False

    def test_every_phase_has_a_notice(self):
        from pomodoro import PHASE_NOTICE
        from pet import FOCUS, BREAK
        assert set(PHASE_NOTICE) == {FOCUS, BREAK}
        for title, body in PHASE_NOTICE.values():
            assert title and body


class TestNotifyCli:
    def test_flag_is_parsed(self):
        from pomodoro import parse_args
        options, code = parse_args(["--no-notify"])
        assert code is None
        assert options["notify"] is False

    def test_notifications_are_on_by_default(self):
        from pomodoro import parse_args
        options, _ = parse_args([])
        assert options["notify"] is True

    def test_help_mentions_the_flag(self, capsys):
        from pomodoro import parse_args
        parse_args(["--help"])
        assert "--no-notify" in capsys.readouterr().out


class TestRunHelper:
    def test_run_never_raises(self):
        """O helper engole qualquer falha do processo externo."""
        notify._run(["binario-que-nao-existe-em-lugar-nenhum"])

    def test_run_survives_a_timeout(self, monkeypatch):
        import subprocess

        def boom(*args, **kwargs):
            raise subprocess.TimeoutExpired(cmd="x", timeout=1)

        monkeypatch.setattr(subprocess, "run", boom)
        notify._run(["qualquer-coisa"])

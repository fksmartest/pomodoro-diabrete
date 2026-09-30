"""Persistencia entre sessoes: arquivo de estado e regra de retomada."""

import json
import os
import time

import pytest

import storage
from storage import (
    StateStore, should_resume, trim_history, snapshot, restore,
    format_stats, state_dir, today, RESUME_WINDOW, VERSION,
)
from pet import PomodoroPet, FOCUS, BREAK


HOUR = 60 * 60


@pytest.fixture
def pet():
    return PomodoroPet(focus_duration=100, break_duration=40)


@pytest.fixture
def store(tmp_path):
    return StateStore(path=str(tmp_path / "sub" / "state.json"))


class TestStateDir:
    def test_linux_uses_xdg_state_home(self, monkeypatch):
        monkeypatch.setattr(storage.sys, "platform", "linux")
        monkeypatch.setenv("XDG_STATE_HOME", "/tmp/xdg")
        assert state_dir() == os.path.join("/tmp/xdg", storage.APP_DIR)

    def test_linux_falls_back_to_local_state(self, monkeypatch):
        monkeypatch.setattr(storage.sys, "platform", "linux")
        monkeypatch.delenv("XDG_STATE_HOME", raising=False)
        assert state_dir().endswith(os.path.join(".local", "state",
                                                 storage.APP_DIR))

    def test_windows_uses_appdata(self, monkeypatch):
        monkeypatch.setattr(storage.sys, "platform", "win32")
        monkeypatch.setenv("APPDATA", r"C:\Users\x\AppData\Roaming")
        assert storage.APP_DIR in state_dir()

    def test_macos_uses_application_support(self, monkeypatch):
        monkeypatch.setattr(storage.sys, "platform", "darwin")
        assert "Application Support" in state_dir()


class TestShouldResume:
    def test_recent_same_day_resumes(self):
        now = time.time()
        assert should_resume(now - 60, now) is True

    def test_older_than_the_window_does_not(self):
        now = time.time()
        assert should_resume(now - RESUME_WINDOW - 1, now) is False

    def test_another_day_does_not(self):
        # meio-dia de ontem vs meio-dia de hoje, com janela larga
        now = time.time()
        yesterday = now - 24 * HOUR
        assert should_resume(yesterday, now, window=48 * HOUR) is False

    def test_missing_timestamp_does_not(self):
        assert should_resume(None, time.time()) is False

    def test_clock_going_backwards_does_not(self):
        now = time.time()
        assert should_resume(now + 500, now) is False


class TestHistory:
    def test_trim_keeps_the_most_recent(self):
        history = {f"2026-01-{day:02d}": day for day in range(1, 11)}
        trimmed = trim_history(history, keep=3)
        assert sorted(trimmed) == ["2026-01-08", "2026-01-09", "2026-01-10"]

    def test_trim_below_the_limit_keeps_everything(self):
        history = {"2026-01-01": 2}
        assert trim_history(history, keep=10) == history

    def test_today_is_iso_formatted(self):
        assert len(today()) == 10
        assert today().count("-") == 2


class TestSnapshotAndRestore:
    def test_round_trip(self, pet):
        pet.energy = 42.5
        pet.cycles = 3
        pet.remaining = 25.0
        state = snapshot(pet, {"2026-09-30": 3})

        other = PomodoroPet(focus_duration=100, break_duration=40)
        assert restore(other, state) is True
        assert other.energy == 42.5
        assert other.cycles == 3
        assert other.remaining == 25.0

    def test_restore_always_comes_back_paused(self, pet):
        pet.start()
        state = snapshot(pet, {})
        other = PomodoroPet(focus_duration=100, break_duration=40)
        other.start()
        restore(other, state)
        assert other.running is False

    def test_restore_keeps_awaiting(self, pet):
        pet.skip()
        state = snapshot(pet, {})
        other = PomodoroPet(focus_duration=100, break_duration=40)
        assert restore(other, state) is True
        assert other.awaiting is True
        assert other.cycles == 1

    def test_restore_keeps_the_break_phase(self, pet):
        pet.skip()
        pet.advance()
        state = snapshot(pet, {})
        other = PomodoroPet(focus_duration=100, break_duration=40)
        restore(other, state)
        assert other.phase == BREAK

    def test_remaining_is_clamped_to_the_phase(self, pet):
        """Estado gravado com fases longas nao pode travar uma fase curta."""
        pet.remaining = 1400.0
        state = snapshot(pet, {})
        short = PomodoroPet(focus_duration=6, break_duration=4)
        restore(short, state)
        assert short.remaining == 6

    def test_empty_state_is_ignored(self, pet):
        assert restore(pet, {}) is False
        assert restore(pet, None) is False

    def test_wrong_version_is_ignored(self, pet):
        state = snapshot(pet, {})
        state["version"] = VERSION + 99
        other = PomodoroPet()
        assert restore(other, state) is False
        assert other.energy == 85

    def test_stale_state_is_ignored(self, pet):
        pet.energy = 10
        state = snapshot(pet, {}, now=time.time() - 48 * HOUR)
        other = PomodoroPet()
        assert restore(other, state) is False
        assert other.energy == 85      # comeca descansado

    def test_snapshot_trims_history(self, pet):
        history = {f"2026-01-{d:02d}": 1 for d in range(1, 29)}
        state = snapshot(pet, history)
        assert len(state["history"]) <= storage.HISTORY_DAYS

    def test_snapshot_does_not_mutate_the_caller_history(self, pet):
        history = {"2026-09-30": 1}
        snapshot(pet, history)
        assert history == {"2026-09-30": 1}


class TestStateStore:
    def test_load_without_a_file(self, store):
        assert store.load() == {}

    def test_save_then_load(self, store, pet):
        assert store.save(snapshot(pet, {"2026-09-30": 2})) is True
        assert store.load()["history"] == {"2026-09-30": 2}

    def test_save_creates_the_directory(self, store, pet):
        store.save(snapshot(pet, {}))
        assert os.path.isdir(os.path.dirname(store.path))

    def test_corrupted_file_loads_as_empty(self, store, pet):
        store.save(snapshot(pet, {}))
        with open(store.path, "w", encoding="utf-8") as handle:
            handle.write("{isso nao e json")
        assert store.load() == {}

    def test_a_json_list_loads_as_empty(self, store):
        os.makedirs(os.path.dirname(store.path), exist_ok=True)
        with open(store.path, "w", encoding="utf-8") as handle:
            json.dump([1, 2, 3], handle)
        assert store.load() == {}

    def test_disabled_store_does_nothing(self, tmp_path, pet):
        disabled = StateStore(path=str(tmp_path / "state.json"), enabled=False)
        assert disabled.save(snapshot(pet, {})) is False
        assert disabled.load() == {}
        assert not os.path.exists(disabled.path)

    def test_save_leaves_no_temporary_file(self, store, pet):
        store.save(snapshot(pet, {}))
        leftovers = [n for n in os.listdir(os.path.dirname(store.path))
                     if n.endswith(".tmp")]
        assert leftovers == []

    def test_save_of_unserializable_data_fails_quietly(self, store):
        assert store.save({"impossivel": object()}) is False

    def test_save_on_a_read_only_path_fails_quietly(self, tmp_path, pet):
        blocked = tmp_path / "arquivo"
        blocked.write_text("sou um arquivo, nao um diretorio")
        store = StateStore(path=str(blocked / "state.json"))
        assert store.save(snapshot(pet, {})) is False


class TestIntegrationWithTheApp:
    """O acumulo de cansaco precisa sobreviver a fechar o app."""

    @pytest.fixture
    def make_window(self, tmp_path):
        from pomodoro import PetWindow
        path = str(tmp_path / "state.json")
        created = []

        def factory():
            w = PetWindow(focus_duration=100, break_duration=40, mute=True,
                          notify=False, scale=1, store=StateStore(path=path))
            created.append(w)
            return w

        yield factory
        for w in created:
            w.running = False

    def test_finishing_a_focus_writes_the_file(self, make_window):
        w = make_window()
        w._skip()
        assert os.path.exists(w.store.path)

    def test_finishing_a_focus_counts_in_the_history(self, make_window):
        w = make_window()
        w._skip()
        assert w.history[today()] == 1
        w.pet.advance()
        w._skip()                       # fim da pausa: nao conta
        assert w.history[today()] == 1

    def test_a_new_window_resumes_the_state(self, make_window):
        first = make_window()
        first.pet.start()
        first._update(50)               # gasta energia
        energy = first.pet.energy
        first.save()

        second = make_window()
        assert second.resumed is True
        assert second.pet.energy == pytest.approx(energy)
        assert second.pet.running is False

    def test_the_history_survives_a_restart(self, make_window):
        first = make_window()
        first._skip()
        second = make_window()
        assert second.history[today()] == 1

    def test_a_fresh_install_starts_rested(self, make_window):
        w = make_window()
        assert w.resumed is False
        assert w.pet.energy == 85

    def test_periodic_save_happens_after_the_interval(self, make_window):
        from pomodoro import SAVE_INTERVAL
        w = make_window()
        w.pet.start()
        w._update(SAVE_INTERVAL / 2)
        assert not os.path.exists(w.store.path)
        w._update(SAVE_INTERVAL / 2 + 0.1)
        assert os.path.exists(w.store.path)

    def test_disabled_store_writes_nothing(self, tmp_path):
        from pomodoro import PetWindow
        path = str(tmp_path / "state.json")
        w = PetWindow(focus_duration=100, break_duration=40, mute=True,
                      notify=False, scale=1,
                      store=StateStore(path=path, enabled=False))
        w._skip()
        assert not os.path.exists(path)
        w.running = False


class TestStatsCli:
    def test_stats_prints_and_does_not_open_a_window(self, tmp_path,
                                                     monkeypatch, capsys):
        from pomodoro import main
        path = tmp_path / "state.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"version": VERSION, "saved_at": 0,
                                    "history": {"2026-09-30": 7}}))
        monkeypatch.setattr(storage, "state_path", lambda: str(path))
        assert main(["--stats"]) == 0
        assert "2026-09-30" in capsys.readouterr().out

    def test_stats_without_history(self, capsys):
        from pomodoro import main
        assert main(["--stats"]) == 0
        assert "Nenhum ciclo" in capsys.readouterr().out

    def test_no_save_flag_is_parsed(self):
        from pomodoro import parse_args
        options, _ = parse_args(["--no-save"])
        assert options["save"] is False

    def test_saving_is_on_by_default(self):
        from pomodoro import parse_args
        options, _ = parse_args([])
        assert options["save"] is True
        assert options["stats"] is False

    def test_help_shows_where_the_state_lives(self, capsys):
        from pomodoro import parse_args
        parse_args(["--help"])
        out = capsys.readouterr().out
        assert "--stats" in out
        assert storage.state_path() in out      # caminho real, nao o literal
        assert "{state_path}" not in out


class TestFormatStats:
    def test_empty_history(self):
        assert "Nenhum ciclo" in format_stats({})

    def test_lists_days_and_counts(self):
        text = format_stats({"2026-09-29": 4, "2026-09-30": 6})
        assert "2026-09-29" in text
        assert "2026-09-30" in text
        assert "total 10" in text

    def test_shows_an_average(self):
        text = format_stats({"2026-09-29": 4, "2026-09-30": 6})
        assert "media 5.0" in text

    def test_limits_the_number_of_days(self):
        history = {f"2026-01-{d:02d}": 1 for d in range(1, 21)}
        text = format_stats(history, days=5)
        assert "2026-01-16" in text
        assert "2026-01-15" not in text

"""Explicit offline fixtures assert the approved bound-generation refusal contract."""

import ctypes
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
PATH = ROOT / "reports/runs/recovery_r06_activation_prep_20261016/candidate/core/windows_actor.py"
SPEC = importlib.util.spec_from_file_location("review_unknown_bound_actor", PATH)
assert SPEC is not None and SPEC.loader is not None
ACTOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ACTOR)
CREATED = "2026-10-16T00:00:00.123456+00:00"
BIRTH = ACTOR._snapshot_ticks(CREATED) + 7


class KernelFunction:
    def __init__(self, operation):
        self.operation = operation

    def __call__(self, *arguments):
        return self.operation(*arguments)


class FixtureKernel:
    """Only held birth/exit are successful; any new open, Job query or signal is recorded."""

    def __init__(self):
        self.signals = []
        self.opens = []
        self.job_queries = []
        self.closed = []
        self.GetProcessTimes = KernelFunction(self.times)
        self.WaitForSingleObject = KernelFunction(lambda *_: 0)
        self.CloseHandle = KernelFunction(lambda handle: self.closed.append(handle) or 1)
        self.TerminateProcess = KernelFunction(lambda handle, code: self.signals.append((handle, code)) or 1)
        self.OpenProcess = KernelFunction(lambda *args: self.opens.append(args) or 122)

    def times(self, handle, created, *_):
        created._obj.dwLowDateTime = BIRTH & 0xFFFFFFFF
        created._obj.dwHighDateTime = BIRTH >> 32
        return 1


def actor_fixture():
    kernel = FixtureKernel()
    actor = ACTOR.WindowsOwnedActor.__new__(ACTOR.WindowsOwnedActor)
    actor.kernel, actor.pid, actor.handle, actor.owned_job_handle = kernel, 11, 111, 80
    actor.creation_ticks = BIRTH
    actor.in_owned_job = lambda _: True
    actor.exited = lambda: True
    return actor, kernel


def test_unknown_descendant_birth_is_the_explicit_ownership_error():
    actor, kernel = actor_fixture()
    with pytest.raises(ACTOR.OwnershipError):
        actor.bind_descendant(22, {"created": None}, BIRTH)
    assert kernel.opens == kernel.signals == []


def test_unknown_initial_actor_birth_is_the_explicit_ownership_error(monkeypatch):
    actor, kernel = actor_fixture()
    monkeypatch.setattr(ACTOR, "process_tree", lambda: {11: {"parent": 7, "created": None}})
    with pytest.raises(ACTOR.OwnershipError):
        actor.kill_owned_tree()
    assert kernel.opens == kernel.signals == []


@pytest.mark.parametrize("bound_role", ["actor", "descendant"])
def test_remaining_unknown_bound_pid_refuses_even_with_live_snapshot_parent(monkeypatch, bound_role):
    actor, kernel = actor_fixture()
    initial = {11: {"parent": 7, "created": CREATED}}
    if bound_role == "descendant":
        initial[22] = {"parent": 11, "created": CREATED}
        actor.bind_descendant = lambda *_: (122, BIRTH)
    remaining = {
        0: {"parent": 0, "created": None},
        2: {"parent": 0, "created": CREATED},
        7: {"parent": 2, "created": CREATED},
        11: {"parent": 7, "created": None if bound_role == "actor" else CREATED},
    }
    if bound_role == "descendant":
        remaining[22] = {"parent": 7, "created": None}
    snapshots = iter([initial, remaining])
    monkeypatch.setattr(ACTOR, "process_tree", lambda: next(snapshots))
    with pytest.raises(ACTOR.OwnershipError):
        actor.kill_owned_tree()
    assert kernel.signals == []

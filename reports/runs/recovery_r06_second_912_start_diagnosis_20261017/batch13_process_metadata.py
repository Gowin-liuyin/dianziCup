"""Birth-aware Windows ancestry prevents a reused parent PID from claiming older processes."""

import ctypes
import importlib.util
from ctypes import wintypes
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location("author_identity", Path(__file__).with_name("process_metadata.py"))
identity_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(identity_module)
identity = identity_module.identity
current_identity = identity_module.current_identity


def control_root(root_identity):
    class ProcessEntry(ctypes.Structure):
        _fields_ = [("size", wintypes.DWORD), ("usage", wintypes.DWORD), ("pid", wintypes.DWORD), ("heap", ctypes.c_size_t), ("module", wintypes.DWORD), ("threads", wintypes.DWORD), ("parent", wintypes.DWORD), ("priority", wintypes.LONG), ("flags", wintypes.DWORD), ("executable", wintypes.WCHAR * 260)]
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    kernel.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(ProcessEntry)]
    kernel.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(ProcessEntry)]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    snapshot = kernel.CreateToolhelp32Snapshot(2, 0)
    entries = {}
    try:
        entry = ProcessEntry()
        entry.size = ctypes.sizeof(entry)
        success = kernel.Process32FirstW(snapshot, ctypes.byref(entry))
        while success:
            entries[entry.pid] = (entry.parent, entry.executable)
            success = kernel.Process32NextW(snapshot, ctypes.byref(entry))
    finally:
        kernel.CloseHandle(snapshot)
    child = root_identity
    chain = [root_identity]
    for _ in range(8):
        parent_pid = entries[child["pid"]][0]
        parent = identity(parent_pid)
        if parent["birth_utc"] > child["birth_utc"]:
            raise OSError("reused parent PID cannot establish control root")
        chain.append({**parent, "executable": entries[parent_pid][1]})
        if entries[parent_pid][1].lower() in {"powershell.exe", "pwsh.exe"}:
            return parent, chain
        child = parent
    raise OSError("actual outer PowerShell exec root not found")


def descendants(root_identity):
    class ProcessEntry(ctypes.Structure):
        _fields_ = [("size", wintypes.DWORD), ("usage", wintypes.DWORD), ("pid", wintypes.DWORD), ("heap", ctypes.c_size_t), ("module", wintypes.DWORD), ("threads", wintypes.DWORD), ("parent", wintypes.DWORD), ("priority", wintypes.LONG), ("flags", wintypes.DWORD), ("executable", wintypes.WCHAR * 260)]
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    kernel.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(ProcessEntry)]
    kernel.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(ProcessEntry)]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    snapshot = kernel.CreateToolhelp32Snapshot(2, 0)
    if snapshot == wintypes.HANDLE(-1).value:
        raise OSError("tree snapshot unavailable")
    try:
        entry = ProcessEntry()
        entry.size = ctypes.sizeof(entry)
        entries = {}
        success = kernel.Process32FirstW(snapshot, ctypes.byref(entry))
        while success:
            entries[entry.pid] = (entry.parent, entry.executable)
            success = kernel.Process32NextW(snapshot, ctypes.byref(entry))
        root_pid = root_identity["pid"]
        if identity(root_pid) != root_identity:
            return {}
        tree = {root_pid: {**root_identity, "executable": entries[root_pid][1]}}
        while True:
            added = {}
            for pid, (parent, executable) in entries.items():
                if pid in tree or parent not in tree:
                    continue
                try:
                    child = identity(pid)
                except OSError:
                    continue
                if child["birth_utc"] < tree[parent]["birth_utc"]:
                    continue
                added[pid] = {**child, "parent_pid": parent, "executable": executable}
            if not added:
                return tree
            tree.update(added)
    finally:
        kernel.CloseHandle(snapshot)


def linux_owned(run):
    proc = Path(r"\\wsl.localhost\Ubuntu-22.04\proc")
    entries = {}
    for path in proc.iterdir():
        if not path.name.isdigit():
            continue
        try:
            value = (path / "stat").read_text()
            fields = value.rsplit(")", 1)[1].split()
            entries[int(path.name)] = {"pid": int(path.name), "ppid": int(fields[1]), "birth_clock_ticks": int(fields[19]), "comm": value.split("(", 1)[1].rsplit(")", 1)[0]}
        except (OSError, ValueError):
            pass
    roots = set()
    host_file = run / "tool_active_host.stat"
    if host_file.exists():
        for row in host_file.read_text().splitlines():
            try:
                role, value = row.split(" ", 1)
                pid = int(value.split(" ", 1)[0])
                ticks = int(value.rsplit(")", 1)[1].split()[19])
                if pid in entries and entries[pid]["birth_clock_ticks"] == ticks:
                    roots.add(pid)
            except (ValueError, IndexError):
                continue
    for pid in tuple(roots):
        parent = entries[pid]["ppid"]
        if parent in entries and entries[parent]["comm"] == "SessionLeader" and entries[parent]["birth_clock_ticks"] <= entries[pid]["birth_clock_ticks"]:
            roots.add(parent)
    container_file = run / "tool_active_container.stat"
    if roots and container_file.exists():
        value = container_file.read_text().split(" ", 1)[1].strip()
        container_pid = int(value.split(" ", 1)[0])
        ticks = int(value.rsplit(")", 1)[1].split()[19])
        for pid, entry in entries.items():
            if entry["birth_clock_ticks"] != ticks or entry["comm"] not in {"pg_dump", "pg_restore", "sh"}:
                continue
            try:
                namespace = next(line for line in (proc / str(pid) / "status").read_text().splitlines() if line.startswith("NSpid:"))
                if int(namespace.split()[-1]) == container_pid:
                    roots.add(pid)
            except (OSError, StopIteration):
                continue
    owned = set(roots)
    if roots:
        minimum_birth = min(entries[pid]["birth_clock_ticks"] for pid in roots)
        for pid, entry in entries.items():
            if entry["comm"] == "runc" and entry["birth_clock_ticks"] >= minimum_birth:
                owned.add(pid)
        while True:
            added = {pid for pid, entry in entries.items() if entry["ppid"] in owned and entry["birth_clock_ticks"] >= entries[entry["ppid"]]["birth_clock_ticks"]}
            if added <= owned:
                break
            owned.update(added)
    return {pid: entries[pid] for pid in owned}

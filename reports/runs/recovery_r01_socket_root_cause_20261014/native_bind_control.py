"""Bind a new native AF_UNIX control object only inside this authorized run directory."""

import ctypes
import json
from ctypes import wintypes
from datetime import datetime
from pathlib import Path


class UnixAddress(ctypes.Structure):
    _fields_ = [("family", ctypes.c_ushort), ("path", ctypes.c_char * 108)]


class RenameInformation(ctypes.Structure):
    _fields_ = [("replace", ctypes.c_ubyte), ("root", wintypes.HANDLE),
               ("name_length", wintypes.DWORD), ("name", wintypes.WCHAR * 1)]


kernel = ctypes.WinDLL("kernel32", use_last_error=True)
kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                              wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD,
                              wintypes.HANDLE]
kernel.CreateFileW.restype = wintypes.HANDLE
kernel.CloseHandle.argtypes = [wintypes.HANDLE]
kernel.CloseHandle.restype = wintypes.BOOL
kernel.SetFileInformationByHandle.argtypes = [wintypes.HANDLE, ctypes.c_int,
                                              wintypes.LPVOID, wintypes.DWORD]
kernel.SetFileInformationByHandle.restype = wintypes.BOOL
kernel.DeleteFileW.argtypes = [wintypes.LPCWSTR]
kernel.DeleteFileW.restype = wintypes.BOOL
winsock = ctypes.WinDLL("ws2_32", use_last_error=True)
winsock.WSAStartup.argtypes = [wintypes.WORD, wintypes.LPVOID]
winsock.socket.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_int]
winsock.socket.restype = ctypes.c_size_t
winsock.bind.argtypes = [ctypes.c_size_t, wintypes.LPVOID, ctypes.c_int]
winsock.closesocket.argtypes = [ctypes.c_size_t]
directory = Path(__file__).resolve().parent
path = directory / ("control-" + datetime.now().strftime("%H%M%S") + ".sock")
assert path.parent == directory and not path.exists()
encoded_path = str(path).encode("ascii")
assert len(encoded_path) < 108
records = []
for access_flags in (0, 0x200000, 0x2200000):
    handle = kernel.CreateFileW(__file__, 0x80, 7, None, 3, access_flags, None)
    invalid = handle == ctypes.c_void_p(-1).value
    records.append({"probe": "ordinary_file_open", "flags": hex(access_flags),
                    "success": not invalid, "winerror": ctypes.get_last_error() if invalid else 0})
    if not invalid:
        assert kernel.CloseHandle(handle)
assert all(record["success"] for record in records), "Control file cannot be opened."
wsa_buffer = ctypes.create_string_buffer(512)
startup = winsock.WSAStartup(0x202, wsa_buffer)
assert startup == 0
socket_handle = winsock.socket(1, 1, 0)
assert socket_handle != ctypes.c_size_t(-1).value
try:
    address = UnixAddress(1, encoded_path)
    status = winsock.bind(socket_handle, ctypes.byref(address), ctypes.sizeof(address))
    records.append({"probe": "native_afunix_bind", "path": str(path),
                    "sockaddr_size": ctypes.sizeof(address), "success": status == 0,
                    "winsock_error": winsock.WSAGetLastError() if status else 0,
                    "recorded_at": datetime.now().astimezone().isoformat(timespec="seconds")})
finally:
    assert winsock.closesocket(socket_handle) == 0
    assert winsock.WSACleanup() == 0
if status == 0:
    records.append({"probe": "control_socket_metadata", "tag": hex(path.lstat().st_reparse_tag),
                    "size": path.lstat().st_size})
    for access_flags in (0, 0x200000, 0x2200000):
        handle = kernel.CreateFileW(str(path), 0x80, 7, None, 3, access_flags, None)
        invalid = handle == ctypes.c_void_p(-1).value
        records.append({"probe": "control_socket_open", "flags": hex(access_flags),
                        "success": not invalid, "winerror": ctypes.get_last_error() if invalid else 0})
        if not invalid:
            assert kernel.CloseHandle(handle)
    handle = kernel.CreateFileW(str(path), 0x10080, 7, None, 3, 0x200000, None)
    assert handle != ctypes.c_void_p(-1).value
    try:
        backup_path = path.with_suffix(".backup.sock")
        assert backup_path.parent == directory and not backup_path.exists()
        name = str(backup_path).encode("utf-16le")
        buffer = ctypes.create_string_buffer(RenameInformation.name.offset + len(name))
        information = ctypes.cast(buffer, ctypes.POINTER(RenameInformation)).contents
        information.replace = 0
        information.root = None
        information.name_length = len(name)
        ctypes.memmove(ctypes.addressof(buffer) + RenameInformation.name.offset, name, len(name))
        rename_success = kernel.SetFileInformationByHandle(handle, 3, buffer, len(buffer))
        records.append({"probe": "control_socket_rename", "destination": str(backup_path),
                        "success": bool(rename_success),
                        "winerror": 0 if rename_success else ctypes.get_last_error()})
    finally:
        assert kernel.CloseHandle(handle)
    controlled_path = backup_path if rename_success else path
    assert controlled_path.parent == directory
    cleanup_success = kernel.DeleteFileW(str(controlled_path))
    records.append({"probe": "control_socket_cleanup", "path": str(controlled_path),
                    "success": bool(cleanup_success),
                    "winerror": 0 if cleanup_success else ctypes.get_last_error()})
print(json.dumps(records, ensure_ascii=True, indent=2))
assert status == 0, "Native AF_UNIX control bind failed."
assert rename_success and cleanup_success, "Native control lifecycle failed."

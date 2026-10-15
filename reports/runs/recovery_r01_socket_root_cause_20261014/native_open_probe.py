"""Compare normal and explicit reparse-point opens of the exact runtime socket."""

import ctypes
import json
from ctypes import wintypes
from datetime import datetime


SOCKET_PATH = r"C:\Users\yinha\AppData\Local\Docker\run\dockerInference"
FILE_READ_ATTRIBUTES = 0x80
DELETE = 0x10000
FILE_FLAG_OPEN_REPARSE_POINT = 0x200000
INVALID_HANDLE = ctypes.c_void_p(-1).value
kernel = ctypes.WinDLL("kernel32", use_last_error=True)
native = ctypes.WinDLL("ntdll")
kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                              wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD,
                              wintypes.HANDLE]
kernel.CreateFileW.restype = wintypes.HANDLE
kernel.CloseHandle.argtypes = [wintypes.HANDLE]
kernel.CloseHandle.restype = wintypes.BOOL
kernel.DeviceIoControl.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPVOID,
                                   wintypes.DWORD, wintypes.LPVOID, wintypes.DWORD,
                                   ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID]
kernel.DeviceIoControl.restype = wintypes.BOOL
native.RtlGetLastNtStatus.restype = wintypes.LONG
records = []
for name, access, flags in [
    ("ordinary_read_attributes", FILE_READ_ATTRIBUTES, 0),
    ("reparse_read_attributes", FILE_READ_ATTRIBUTES, FILE_FLAG_OPEN_REPARSE_POINT),
    ("reparse_rename_permission", FILE_READ_ATTRIBUTES | DELETE, FILE_FLAG_OPEN_REPARSE_POINT),
    ("reparse_backup_read_attributes", FILE_READ_ATTRIBUTES, FILE_FLAG_OPEN_REPARSE_POINT | 0x2000000),
    ("reparse_zero_access", 0, FILE_FLAG_OPEN_REPARSE_POINT),
]:
    ctypes.set_last_error(0)
    handle = kernel.CreateFileW(SOCKET_PATH, access, 7, None, 3, flags, None)
    error = ctypes.get_last_error() if handle == INVALID_HANDLE else 0
    status = native.RtlGetLastNtStatus() & 0xFFFFFFFF
    record = {
        "name": name,
        "path": SOCKET_PATH,
        "access": hex(access),
        "flags": hex(flags),
        "opened": handle != INVALID_HANDLE,
        "winerror": error,
        "message": ctypes.FormatError(error) if error else None,
        "ntstatus_after_open": hex(status),
        "recorded_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    }
    if handle != INVALID_HANDLE:
        try:
            output = ctypes.create_string_buffer(16384)
            returned = wintypes.DWORD()
            success = kernel.DeviceIoControl(handle, 0x900A8, None, 0, output,
                                             len(output), ctypes.byref(returned), None)
            record["get_reparse_point"] = bool(success)
            record["get_reparse_error"] = 0 if success else ctypes.get_last_error()
            if success:
                record["reparse_tag"] = hex(int.from_bytes(output.raw[:4], "little"))
                record["reparse_data_length"] = int.from_bytes(output.raw[4:6], "little")
                record["reparse_bytes_returned"] = returned.value
        finally:
            assert kernel.CloseHandle(handle)
    records.append(record)
print(json.dumps(records, ensure_ascii=False, indent=2))
assert records[0]["winerror"] == 1920, "The expected ordinary-open failure changed."
assert all(record["winerror"] == 1920 for record in records), "The failure pattern changed."

$ErrorActionPreference = 'Stop'
$OutputEncoding = [Text.Encoding]::UTF8
[Console]::OutputEncoding = [Text.Encoding]::UTF8
Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class RuntimeSocketSupport {
    [DllImport("ws2_32.dll")] public static extern int WSAStartup(ushort version, IntPtr data);
    [DllImport("ws2_32.dll")] public static extern IntPtr socket(int family, int type, int protocol);
    [DllImport("ws2_32.dll")] public static extern int closesocket(IntPtr handle);
    [DllImport("ws2_32.dll")] public static extern int WSAGetLastError();
    [DllImport("ws2_32.dll")] public static extern int WSACleanup();
}
'@
$startupBuffer = [Runtime.InteropServices.Marshal]::AllocHGlobal(512)
try {
    $startupResult = [RuntimeSocketSupport]::WSAStartup(0x0202, $startupBuffer)
    if ($startupResult -ne 0) {
        throw "WSAStartup failed: $startupResult"
    }
    $socketHandle = [RuntimeSocketSupport]::socket(1, 1, 0)
    $socketCreated = ($socketHandle -ne [IntPtr](-1))
    $socketError = if ($socketCreated) { 0 } else { [RuntimeSocketSupport]::WSAGetLastError() }
    if ($socketCreated) {
        $null = [RuntimeSocketSupport]::closesocket($socketHandle)
    }
    $null = [RuntimeSocketSupport]::WSACleanup()
    [ordered]@{ recorded_at = [DateTimeOffset]::Now.ToString('o'); socket_api = 'Winsock socket(AF_UNIX=1, SOCK_STREAM=1, protocol=0)'; socket_created = $socketCreated; wsa_error = $socketError; bound = $false; filesystem_artifact_created = $false } | ConvertTo-Json
} finally {
    [Runtime.InteropServices.Marshal]::FreeHGlobal($startupBuffer)
}
if (-not $socketCreated) { exit 1 }

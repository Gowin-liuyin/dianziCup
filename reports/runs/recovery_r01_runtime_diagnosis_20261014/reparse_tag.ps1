$ErrorActionPreference = 'Stop'
$OutputEncoding = [Text.Encoding]::UTF8
[Console]::OutputEncoding = [Text.Encoding]::UTF8
Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class RuntimeReparseMetadata {
    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    public struct FindData {
        public uint attributes;
        public System.Runtime.InteropServices.ComTypes.FILETIME creationTime;
        public System.Runtime.InteropServices.ComTypes.FILETIME accessTime;
        public System.Runtime.InteropServices.ComTypes.FILETIME writeTime;
        public uint sizeHigh;
        public uint sizeLow;
        public uint reparseTag;
        public uint reserved;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 260)] public string fileName;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 14)] public string alternateName;
    }
    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    public static extern IntPtr FindFirstFileW(string fileName, out FindData metadata);
    [DllImport("kernel32.dll", SetLastError = true)]
    public static extern bool FindClose(IntPtr handle);
}
'@
$runtimeDirectoryPath = 'C:\Users\yinha\AppData\Local\Docker\run'
$runtimePath = Join-Path $runtimeDirectoryPath 'dockerInference'
$resolvedPath = (Resolve-Path -LiteralPath $runtimePath).ProviderPath
if ($resolvedPath -ne $runtimePath -or (Split-Path -Parent $resolvedPath) -ne $runtimeDirectoryPath) {
    throw 'The exact runtime listener path did not resolve within the authorized directory.'
}
$runtimeMetadata = Get-Item -LiteralPath $resolvedPath -Force
$directoryMetadata = Get-Item -LiteralPath $runtimeDirectoryPath -Force
if (($directoryMetadata.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
    throw 'The runtime directory is a reparse point; isolation is not authorized.'
}
$findData = New-Object RuntimeReparseMetadata+FindData
$findHandle = [RuntimeReparseMetadata]::FindFirstFileW($resolvedPath, [ref]$findData)
if ($findHandle -eq [IntPtr](-1)) {
    throw [ComponentModel.Win32Exception]::new([Runtime.InteropServices.Marshal]::GetLastWin32Error())
}
$null = [RuntimeReparseMetadata]::FindClose($findHandle)
[ordered]@{
    recorded_at = [DateTimeOffset]::Now.ToString('o')
    resolved_path = $resolvedPath
    directory_attributes = $directoryMetadata.Attributes.ToString()
    file_attributes = $runtimeMetadata.Attributes.ToString()
    length_bytes = $runtimeMetadata.Length
    link_type = $runtimeMetadata.LinkType
    link_target = $runtimeMetadata.Target
    reparse_tag = ('0x{0:X8}' -f $findData.reparseTag)
    is_name_surrogate = (($findData.reparseTag -band 0x20000000) -ne 0)
    expected_af_unix = ($findData.reparseTag -eq [uint32]::Parse('80000023', [Globalization.NumberStyles]::HexNumber))
} | ConvertTo-Json -Depth 3

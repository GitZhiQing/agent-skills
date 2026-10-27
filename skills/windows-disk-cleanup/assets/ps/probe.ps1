param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('recyclebin', 'volume')]
    [string]$Action,
    [string]$Path = $env:SystemDrive + '\'
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$OutputEncoding = [Console]::OutputEncoding

try {
    if ($Action -eq 'recyclebin') {
        $drive = [System.IO.Path]::GetPathRoot((Resolve-Path -LiteralPath $Path).Path)
        $shell = New-Object -ComObject Shell.Application
        $bin = $shell.Namespace(10)
        $items = @($bin.Items())
        $matched = @($items | Where-Object {
            $_.Path -and $_.Path.StartsWith($drive, [System.StringComparison]::OrdinalIgnoreCase)
        })
        $size = [int64]0
        foreach ($item in $matched) {
            if ($null -ne $item.Size) { $size += [int64]$item.Size }
        }
        [pscustomobject]@{
            ok    = $true
            count = [int]$matched.Count
            size  = $size
        } | ConvertTo-Json -Compress
        exit 0
    }

    if ($Action -eq 'volume') {
        $root = [System.IO.Path]::GetPathRoot((Resolve-Path -LiteralPath $Path).Path)
        $volume = Get-CimInstance -ClassName Win32_LogicalDisk -Filter "DeviceID='$($root.TrimEnd('\'))'"
        if ($null -eq $volume) {
            [pscustomobject]@{ ok = $false; error = 'volume not found' } | ConvertTo-Json -Compress
            exit 0
        }
        [pscustomobject]@{
            ok         = $true
            root       = $root
            label      = $volume.VolumeName
            filesystem = $volume.FileSystem
            total      = [int64]$volume.Size
            free       = [int64]$volume.FreeSpace
        } | ConvertTo-Json -Compress
        exit 0
    }
}
catch {
    [pscustomobject]@{ ok = $false; error = $_.Exception.Message } | ConvertTo-Json -Compress
    exit 0
}

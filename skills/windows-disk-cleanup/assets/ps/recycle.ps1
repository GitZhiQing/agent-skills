param(
    [Parameter(Mandatory = $true)]
    [string]$InputFile
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$OutputEncoding = [Console]::OutputEncoding
Add-Type -AssemblyName Microsoft.VisualBasic

$payload = Get-Content -LiteralPath $InputFile -Raw -Encoding UTF8 | ConvertFrom-Json
$results = @()

foreach ($raw in @($payload.paths)) {
    $path = [string]$raw
    try {
        if ([string]::IsNullOrWhiteSpace($path)) {
            throw 'empty path'
        }
        $path = $path.TrimEnd('\')
        if (-not (Test-Path -LiteralPath $path)) {
            $results += [pscustomobject]@{
                path  = $path
                ok    = $false
                error = 'path no longer exists'
            }
            continue
        }
        $item = Get-Item -LiteralPath $path -Force
        if (($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
            $results += [pscustomobject]@{
                path  = $path
                ok    = $false
                error = 'reparse point is not allowed'
            }
            continue
        }
        if ($item.PSIsContainer) {
            [Microsoft.VisualBasic.FileIO.FileSystem]::DeleteDirectory(
                $path,
                [Microsoft.VisualBasic.FileIO.UIOption]::OnlyErrorDialogs,
                [Microsoft.VisualBasic.FileIO.RecycleOption]::SendToRecycleBin,
                [Microsoft.VisualBasic.FileIO.UICancelOption]::DoNothing
            )
        }
        else {
            [Microsoft.VisualBasic.FileIO.FileSystem]::DeleteFile(
                $path,
                [Microsoft.VisualBasic.FileIO.UIOption]::OnlyErrorDialogs,
                [Microsoft.VisualBasic.FileIO.RecycleOption]::SendToRecycleBin,
                [Microsoft.VisualBasic.FileIO.UICancelOption]::DoNothing
            )
        }
        if (Test-Path -LiteralPath $path) {
            $results += [pscustomobject]@{
                path  = $path
                ok    = $false
                error = 'path still exists after recycle operation'
            }
        }
        else {
            $results += [pscustomobject]@{
                path  = $path
                ok    = $true
                error = $null
            }
        }
    }
    catch {
        $results += [pscustomobject]@{
            path  = $path
            ok    = $false
            error = $_.Exception.Message
        }
    }
}

[pscustomobject]@{ results = @($results) } | ConvertTo-Json -Depth 4 -Compress

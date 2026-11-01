# MAIN ORDER Nee58d0 item 5 (EW-OVERLAY-FOCUS): report the OS foreground
# window's process name and whether the game process runs, one line per
# change: fg=<name>|game=<0|1>. Read-only window-manager queries; it never
# opens, reads or sends input to the game process or any other window.
$ErrorActionPreference = 'SilentlyContinue'
Add-Type -Namespace EwFg -Name User32 -MemberDefinition @'
[DllImport("user32.dll")] public static extern System.IntPtr GetForegroundWindow();
[DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(System.IntPtr hWnd, out uint pid);
'@
$last = ''
$n = 0
$game = 0
while ($true) {
    $name = ''
    $h = [EwFg.User32]::GetForegroundWindow()
    if ($h -ne [System.IntPtr]::Zero) {
        $procId = [uint32]0
        [void][EwFg.User32]::GetWindowThreadProcessId($h, [ref]$procId)
        if ($procId -ne 0) {
            $p = Get-Process -Id $procId
            if ($p) { $name = $p.ProcessName }
        }
    }
    if (($n % 10) -eq 0) {
        if (Get-Process -Name 'BlackDesert64') { $game = 1 } else { $game = 0 }
    }
    $n++
    $line = "fg=$name|game=$game"
    if ($line -ne $last) {
        [Console]::Out.WriteLine($line)
        [Console]::Out.Flush()
        $last = $line
    }
    Start-Sleep -Milliseconds 400
}

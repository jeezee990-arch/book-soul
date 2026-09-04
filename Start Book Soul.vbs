' Book Soul launcher (double-click; hidden window).
' cd into apps/desktop (where package.json lives) and spawn pnpm tauri dev.
' Closing the Tauri window auto-kills the Python backend (Rust on_window_event).

Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

' pnpm tauri dev must be run from apps/desktop (where package.json is)
WshShell.CurrentDirectory = fso.BuildPath( _
    fso.GetParentFolderName(WScript.ScriptFullName), "apps\desktop")

' 0 = hidden window, False = don't wait
WshShell.Run "pnpm.cmd tauri dev", 0, False

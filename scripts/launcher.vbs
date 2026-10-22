' Book Soul silent launcher (zero console).
'
' Just runs scripts\launcher_hidden.ps1 with WindowStyle Hidden, then exits.
' No string interpolation in VBScript -> no escaping bugs.

Dim shell
Set shell = CreateObject("WScript.Shell")

' Project root = parent of this script's folder (this vbs lives in scripts/)
Dim fso, scriptFull, scriptsDir, rootPath
Set fso = CreateObject("Scripting.FileSystemObject")
scriptFull = WScript.ScriptFullName
scriptsDir = fso.GetParentFolderName(scriptFull)
rootPath   = fso.GetParentFolderName(scriptsDir)

Dim ps1Path
ps1Path = scriptsDir & "\launcher_hidden.ps1"

If Not fso.FileExists(ps1Path) Then
    MsgBox "Missing launcher script: " & ps1Path, 16, "Book Soul"
    WScript.Quit 1
End If

' Run PowerShell hidden. WindowStyle 0 = hidden; do NOT wait.
shell.Run "powershell.exe -NoProfile -ExecutionPolicy Bypass -File """ & ps1Path & """", 0, False

WScript.Quit 0
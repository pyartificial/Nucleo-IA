Option Explicit
Dim shell, fso, base, pythonw, command, result
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
base = fso.GetParentFolderName(WScript.ScriptFullName)
pythonw = fso.BuildPath(base, "venv\Scripts\pythonw.exe")
shell.CurrentDirectory = base
If fso.FileExists(pythonw) Then
    command = Chr(34) & pythonw & Chr(34) & " " & Chr(34) & fso.BuildPath(base, "scripts\mis_servicios.py") & Chr(34) & " --serve"
    result = shell.Run(command, 0, True)
    If result <> 0 Then MsgBox "No se pudo abrir Mis servicios. Proba mis_servicios.bat para revisar el inicio.", 48, "Nucleo IA"
Else
    shell.Run Chr(34) & fso.BuildPath(base, "mis_servicios.bat") & Chr(34), 1, False
End If

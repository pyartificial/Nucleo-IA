Option Explicit
Dim shell, fso, base
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
base = fso.GetParentFolderName(WScript.ScriptFullName)
shell.CurrentDirectory = base
shell.Run Chr(34) & fso.BuildPath(base, "centro_control.bat") & Chr(34), 0, False

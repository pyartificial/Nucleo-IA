Option Explicit

Dim shell, fso, root, pythonw, stopScript, stateDir, logFile, q
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

root = fso.GetParentFolderName(WScript.ScriptFullName)
pythonw = fso.BuildPath(root, "venv\Scripts\pythonw.exe")
stopScript = fso.BuildPath(root, "scripts\detener_granja.py")
stateDir = fso.BuildPath(root, "state")
logFile = fso.BuildPath(stateDir, "inicio_windows.log")
q = Chr(34)

If Not fso.FolderExists(stateDir) Then
    fso.CreateFolder(stateDir)
End If

If Not fso.FileExists(pythonw) Then
    Dim logMissing
    Set logMissing = fso.OpenTextFile(logFile, 8, True)
    logMissing.WriteLine Now & " ERROR: falta venv\Scripts\pythonw.exe; ejecutar instalar_nucleo_ia.bat"
    logMissing.Close
    WScript.Quit 1
End If

shell.CurrentDirectory = root
shell.Environment("PROCESS")("PYTHONPATH") = root
shell.Environment("PROCESS")("PYTHONIOENCODING") = "utf-8"
shell.Environment("PROCESS")("PYTHONUTF8") = "1"

If fso.FileExists(stopScript) Then
    shell.Run q & pythonw & q & " " & q & stopScript & q, 0, True
End If

shell.Run q & pythonw & q & " -m proxy.servidor", 0, False

Dim logOk
Set logOk = fso.OpenTextFile(logFile, 8, True)
logOk.WriteLine Now & " Inicio solicitado en segundo plano."
logOk.Close

using System;
using System.Diagnostics;
using System.IO;

namespace NucleoIALauncher
{
    class Program
    {
        static void Main(string[] args)
        {
            try
            {
                string baseDir = AppDomain.CurrentDomain.BaseDirectory;
                Directory.SetCurrentDirectory(baseDir);

                // 1. Detectar ejecutable de Python preferido (pythonw no abre ventana)
                string pythonExe = ResolvePythonExecutable(baseDir);
                if (string.IsNullOrEmpty(pythonExe))
                {
                    return; // Si no hay python, salir silenciosamente
                }

                // 2. Detener instancias previas limpiamente si existe el script
                string stopScript = Path.Combine(baseDir, @"scripts\detener_granja.py");
                if (File.Exists(stopScript))
                {
                    RunHiddenProcess(pythonExe, "\"" + stopScript + "\"", baseDir, true);
                }

                // 3. Iniciar el servidor Proxy FastAPI en segundo plano permanente
                RunHiddenProcess(pythonExe, "-m proxy.servidor", baseDir, false);
            }
            catch
            {
                // Silencioso para modo segundo plano
            }
        }

        static string ResolvePythonExecutable(string baseDir)
        {
            string[] candidates = new string[]
            {
                Path.Combine(baseDir, @"venv\Scripts\pythonw.exe"),
                Path.Combine(baseDir, @"venv\Scripts\python.exe"),
                "pythonw.exe",
                "python.exe"
            };

            foreach (var path in candidates)
            {
                if (File.Exists(path))
                {
                    return path;
                }
            }

            // Si es un nombre del PATH global
            return "pythonw.exe";
        }

        static void RunHiddenProcess(string exe, string arguments, string workingDir, bool waitForExit)
        {
            ProcessStartInfo psi = new ProcessStartInfo();
            psi.FileName = exe;
            psi.Arguments = arguments;
            psi.WorkingDirectory = workingDir;
            psi.WindowStyle = ProcessWindowStyle.Hidden;
            psi.CreateNoWindow = true;
            psi.UseShellExecute = false;

            // Variables de entorno necesarias para Nucleo IA
            psi.EnvironmentVariables["PYTHONPATH"] = workingDir;
            psi.EnvironmentVariables["PYTHONIOENCODING"] = "utf-8";
            psi.EnvironmentVariables["PYTHONUTF8"] = "1";

            Process p = Process.Start(psi);
            if (waitForExit && p != null)
            {
                p.WaitForExit(4000); // Esperar maximo 4 segundos
            }
        }
    }
}

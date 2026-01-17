import socket
import threading
import logging
import os
import time

# ================= CONFIG =================
PORT = int(os.getenv("PORT", "65530"))
BANK_IP = os.getenv("BANK_IP", None)
TIMEOUT = int(os.getenv("TIMEOUT", "5"))  # seconds

# ================= LOGGING =================
logging.basicConfig(
    filename="bank.log",
    level=logging.INFO,
    format="%(asctime)s %(message)s"
)

def log(msg):
    logging.info(msg)

# ================= STORAGE =================
# accounts = { 10001: balance }
accounts = {}
accounts_lock = threading.Lock()

# ================= HELPERS =================
def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()

if BANK_IP is None:
    BANK_IP = get_local_ip()

def error(msg):
    return f"ER {msg}"

def valid_account(n):
    return isinstance(n, int) and 10000 <= n <= 99999

def valid_amount(n):
    return isinstance(n, int) and 0 <= n <= 9223372036854775807

def parse_account(text):
    try:
        acc_str, ip = text.split("/")
        acc = int(acc_str)
        if ip != BANK_IP:
            return None
        if not valid_account(acc):
            return None
        return acc
    except Exception:
        return None

# ================= COMMAND HANDLER =================
def handle_command(line):
    parts = line.strip().split()
    if not parts:
        return None

    cmd = parts[0]

    try:
        if cmd == "BC":
            return f"BC {BANK_IP}"

        elif cmd == "AC":
            with accounts_lock:
                for acc in range(10000, 100000):
                    if acc not in accounts:
                        accounts[acc] = 0
                        return f"AC {acc}/{BANK_IP}"
            return error("Nelze vytvořit nový účet.")

        elif cmd == "AD":
            if len(parts) != 3:
                return error("Špatný formát příkazu.")
            acc = parse_account(parts[1])
            amount = int(parts[2]) if parts[2].isdigit() else -1
            if acc is None or not valid_amount(amount):
                return error("Číslo účtu nebo částka není ve správném formátu.")
            with accounts_lock:
                if acc not in accounts:
                    return error("Účet neexistuje.")
                accounts[acc] += amount
            return "AD"

        elif cmd == "AW":
            if len(parts) != 3:
                return error("Špatný formát příkazu.")
            acc = parse_account(parts[1])
            amount = int(parts[2]) if parts[2].isdigit() else -1
            if acc is None or not valid_amount(amount):
                return error("Číslo účtu nebo částka není ve správném formátu.")
            with accounts_lock:
                if acc not in accounts:
                    return error("Účet neexistuje.")
                if accounts[acc] < amount:
                    return error("Není dostatek finančních prostředků.")
                accounts[acc] -= amount
            return "AW"

        elif cmd == "AB":
            if len(parts) != 2:
                return error("Špatný formát příkazu.")
            acc = parse_account(parts[1])
            if acc is None:
                return error("Formát čísla účtu není správný.")
            with accounts_lock:
                if acc not in accounts:
                    return error("Účet neexistuje.")
                return f"AB {accounts[acc]}"

        elif cmd == "AR":
            if len(parts) != 2:
                return error("Špatný formát příkazu.")
            acc = parse_account(parts[1])
            if acc is None:
                return error("Formát čísla účtu není správný.")
            with accounts_lock:
                if acc not in accounts:
                    return error("Účet neexistuje.")
                if accounts[acc] != 0:
                    return error("Nelze smazat bankovní účet na kterém jsou finance.")
                del accounts[acc]
            return "AR"

        elif cmd == "BA":
            with accounts_lock:
                total = sum(accounts.values())
            return f"BA {total}"

        elif cmd == "BN":
            with accounts_lock:
                return f"BN {len(accounts)}"

        else:
            return error("Nepovolený příkaz.")

    except Exception as e:
        log(f"ERROR {e}")
        return error("Chyba v aplikaci, zkuste to později.")

# ================= CLIENT HANDLER =================
def handle_client(conn, addr):
    conn.settimeout(TIMEOUT)
    log(f"CLIENT CONNECTED {addr[0]}")

    try:
        buffer = ""
        while True:
            data = conn.recv(1024)
            if not data:
                break
            buffer += data.decode("utf-8")
            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                line = line.strip()
                if not line:
                    continue
                log(f"IN  {line}")
                response = handle_command(line)
                log(f"OUT {response}")
                conn.sendall((response + "\n").encode("utf-8"))
    except socket.timeout:
        log("CLIENT TIMEOUT")
    finally:
        conn.close()
        log("CLIENT DISCONNECTED")

# ================= SERVER =================
def main():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("", PORT))
    server.listen(5)

    log(f"BANK NODE STARTED {BANK_IP}:{PORT}")
    print(f"Bank node running on {BANK_IP}:{PORT}")

    while True:
        conn, addr = server.accept()
        t = threading.Thread(target=handle_client, args=(conn, addr), daemon=True)
        t.start()

if __name__ == "__main__":
    main()

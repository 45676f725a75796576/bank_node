import socket
import threading
import sqlite3
import logging
import argparse
import time
import re
from contextlib import closing

import lib.data_provider.data_provider as dp

# =========================
# CONFIG
# =========================
SOCKET_TIMEOUT = 5
CLIENT_TIMEOUT = 30
DB_FILE = "bank.db"

ACCOUNT_RE = re.compile(r"^(\d{5})/(\d{1,3}(?:\.\d{1,3}){3})$")
NUMBER_RE = re.compile(r"^\d+$")

lock = threading.Lock()

# =========================
# LOGGING
# =========================
logging.basicConfig(
    filename="bank.log",
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)

# =========================
# DATABASE
# =========================
def init_db():
    with sqlite3.connect(DB_FILE) as db:
        db.execute("""
        CREATE TABLE IF NOT EXISTS accounts (
            account INTEGER PRIMARY KEY,
            balance INTEGER NOT NULL
        )
        """)

# =========================
# BANK CORE
# =========================
class Bank:
    def __init__(self, ip):
        self.ip = ip
        init_db()

    def create_account(self):
        with lock, sqlite3.connect(DB_FILE) as db:
            for acc in range(10000, 100000):
                if not db.execute(
                    "SELECT 1 FROM accounts WHERE account=?",
                    (acc,)
                ).fetchone():
                    db.execute(
                        "INSERT INTO accounts(account,balance) VALUES (?,0)",
                        (acc,)
                    )
                    return acc
        raise RuntimeError("Nelze vytvořit účet")

    def deposit(self, acc, amount):
        with lock, sqlite3.connect(DB_FILE) as db:
            r = db.execute(
                "SELECT balance FROM accounts WHERE account=?",
                (acc,)
            ).fetchone()
            if not r:
                raise ValueError("Účet neexistuje")
            db.execute(
                "UPDATE accounts SET balance=? WHERE account=?",
                (r[0] + amount, acc)
            )

    def withdraw(self, acc, amount):
        with lock, sqlite3.connect(DB_FILE) as db:
            r = db.execute(
                "SELECT balance FROM accounts WHERE account=?",
                (acc,)
            ).fetchone()
            if not r:
                raise ValueError("Účet neexistuje")
            if r[0] < amount:
                raise ValueError("Není dostatek finančních prostředků")
            db.execute(
                "UPDATE accounts SET balance=? WHERE account=?",
                (r[0] - amount, acc)
            )

    def balance(self, acc):
        with sqlite3.connect(DB_FILE) as db:
            r = db.execute(
                "SELECT balance FROM accounts WHERE account=?",
                (acc,)
            ).fetchone()
            if not r:
                raise ValueError("Účet neexistuje")
            return r[0]

    def remove(self, acc):
        with lock, sqlite3.connect(DB_FILE) as db:
            r = db.execute(
                "SELECT balance FROM accounts WHERE account=?",
                (acc,)
            ).fetchone()
            if not r:
                raise ValueError("Účet neexistuje")
            if r[0] != 0:
                raise ValueError("Nelze smazat účet se zůstatkem")
            db.execute("DELETE FROM accounts WHERE account=?", (acc,))

    def total_amount(self):
        with sqlite3.connect(DB_FILE) as db:
            return db.execute("SELECT COALESCE(SUM(balance),0) FROM accounts").fetchone()[0]

    def client_count(self):
        with sqlite3.connect(DB_FILE) as db:
            return db.execute("SELECT COUNT(*) FROM accounts").fetchone()[0]

# =========================
# P2P COMMUNICATION
# =========================
def send_command(ip, port, cmd):
    with closing(socket.socket()) as s:
        s.settimeout(SOCKET_TIMEOUT)
        s.connect((ip, port))
        s.sendall((cmd + "\n").encode())
        return s.recv(4096).decode().strip()

# =========================
# COMMAND HANDLER
# =========================
class Handler:
    def __init__(self, bank, port):
        self.bank = bank
        self.port = port

    def handle(self, line):
        try:
            cmd = line.strip()
            if not cmd:
                return "ER Prázdný příkaz"

            code = cmd[:2].upper()

            if code == "BC":
                return f"BC {self.bank.ip}"

            if code == "AC":
                acc = self.bank.create_account()
                return f"AC {acc}/{self.bank.ip}"

            if code in ("AD", "AW", "AB", "AR"):
                parts = cmd.split()
                if len(parts) < 2:
                    return "ER Špatný formát"

                m = ACCOUNT_RE.match(parts[1])
                if not m:
                    return "ER Formát čísla účtu není správný"

                acc = int(m.group(1))
                ip = m.group(2)

                # PROXY
                if ip != self.bank.ip:
                    return send_command(ip, self.port, cmd)

                if code == "AB":
                    return f"AB {self.bank.balance(acc)}"

                if len(parts) != 3:
                    return "ER Chybí částka"

                if not NUMBER_RE.match(parts[2]):
                    return "ER Částka není číslo"

                amount = int(parts[2])

                if code == "AD":
                    self.bank.deposit(acc, amount)
                    return "AD"

                if code == "AW":
                    self.bank.withdraw(acc, amount)
                    return "AW"

                if code == "AR":
                    self.bank.remove(acc)
                    return "AR"

            if code == "BA":
                return f"BA {self.bank.total_amount()}"

            if code == "BN":
                return f"BN {self.bank.client_count()}"

            if code == "RP":
                target = int(cmd.split()[1])
                return self.robbery_plan(target)

            return "ER Neznámý příkaz"

        except Exception as e:
            logging.exception("ERROR")
            return f"ER {str(e)}"

    # =========================
    # HACKER PART
    # =========================
    def robbery_plan(self, target):
        banks = []

        for i in range(65525, 65536):
            try:
                r1 = send_command(self.bank.ip, i, "BA")
                r2 = send_command(self.bank.ip, i, "BN")
                if r1.startswith("BA") and r2.startswith("BN"):
                    amount = int(r1.split()[1])
                    clients = int(r2.split()[1])
                    banks.append((self.bank.ip, amount, clients))
            except:
                continue

        banks.sort(key=lambda x: (x[2], -x[1]))

        total = 0
        victims = 0
        chosen = []

        for ip, amt, cl in banks:
            if total >= target:
                break
            total += amt
            victims += cl
            chosen.append(ip)

        return (
            f"RP K dosažení {target} je třeba vyloupit banky "
            + ", ".join(chosen)
            + f" a bude poškozeno {victims} klientů."
        )

# =========================
# SERVER
# =========================
def client_thread(conn, handler):
    conn.settimeout(CLIENT_TIMEOUT)
    with conn:
        while True:
            try:
                data = conn.recv(1024)
                if not data:
                    return
                resp = handler.handle(data.decode())
                conn.sendall((resp + "\n").encode())
            except socket.timeout:
                return

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--ip", default=None)
    args = parser.parse_args()

    ip = args.ip or socket.gethostbyname(socket.gethostname())
    bank = Bank(ip)
    handler = Handler(bank, args.port)

    with socket.socket() as s:
        s.bind(("", args.port))
        s.listen()
        logging.info(f"Bank node running {ip}:{args.port}")

        while True:
            conn, _ = s.accept()
            threading.Thread(
                target=client_thread,
                args=(conn, handler),
                daemon=True
            ).start()

if __name__ == "__main__":
    main()

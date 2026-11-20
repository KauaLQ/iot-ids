"""Injeta flows sintéticos de PortScan no conn_live.log para testar o relatório de IA
sem o ESP32. Rode a partir de backend/:  python -m script.simular_incidente
O incidente fica visível por ~4 min (janela de histórico do classificador)."""
import argparse
import random
import time

from app import config


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--ip", default=f"{config.SUBNET_PREFIX}99", help="IP fictício do dispositivo atacante")
    p.add_argument("--fluxos", type=int, default=150)
    a = p.parse_args()

    agora = time.time()
    linhas = []
    for i in range(a.fluxos):
        ts = agora - 60 + (i / a.fluxos) * 30            # entre -60 s e -30 s: janelas já fechadas
        dst = f"10.77.0.{random.randint(2, 250)}" if i % 2 else f"{config.SUBNET_PREFIX}1"
        porta = random.choice([21, 22, 23, 80, 443, 445, 3389, 8080])
        linhas.append("\t".join([
            f"{ts:.6f}", f"CSIM{i:08x}", a.ip, str(random.randint(40000, 60000)), dst, str(porta),
            "tcp", "-", "-", "0", "0", "S0", "-", "-", "0", "S", "1", "60", "0", "0", "-", "6",
        ]))
    with open(config.CONN_LOG_PATH, "a", encoding="utf-8") as fh:
        fh.write("\n".join(linhas) + "\n")
    print(f"{len(linhas)} flows de varredura injetados em {config.CONN_LOG_PATH} (origem {a.ip}).")


if __name__ == "__main__":
    main()
"""Ponte local: repassa linhas da COM do Arduino ao servidor via WebSocket."""
import argparse
import asyncio
import os

import serial
import websockets


async def executar(url: str, token: str, porta: str, baudrate: int):
    cabecalhos = {"Authorization": f"Bearer {token}"}
    while True:
        try:
            with serial.Serial(porta, baudrate, timeout=0.2, write_timeout=2) as dispositivo:
                # O Uno reinicia quando a porta serial abre.
                await asyncio.sleep(2.2)
                dispositivo.reset_input_buffer()
                # Repassa leituras do Arduino ao servidor e comandos do servidor
                # de volta à porta serial.
                async with websockets.connect(url, additional_headers=cabecalhos, ping_interval=20) as ws:
                    async def enviar_leituras():
                        while True:
                            linha = await asyncio.to_thread(dispositivo.readline)
                            if linha:
                                await ws.send(linha.decode("ascii", errors="replace").strip())

                    async def receber_comandos():
                        async for comando in ws:
                            await asyncio.to_thread(dispositivo.write, (comando + "\n").encode("ascii"))
                            await asyncio.to_thread(dispositivo.flush)

                    tarefas = [asyncio.create_task(enviar_leituras()), asyncio.create_task(receber_comandos())]
                    _, pendentes = await asyncio.wait(tarefas, return_when=asyncio.FIRST_COMPLETED)
                    for tarefa in pendentes:
                        tarefa.cancel()
                    await asyncio.gather(*tarefas, return_exceptions=True)
        except asyncio.CancelledError:
            raise
        except Exception as erro:
            print(f"Ponte desconectada ({erro}); tentando novamente em 5 segundos.", flush=True)
            await asyncio.sleep(5)


def main():
    parser = argparse.ArgumentParser(description="Conecta o Arduino local ao Cana Mania no Render.")
    parser.add_argument("--url", default=os.getenv("ARDUINO_BRIDGE_URL"), help="Ex.: wss://seu-servico.onrender.com/ws/arduino")
    parser.add_argument("--port", default=os.getenv("ARDUINO_PORT", "COM11"))
    parser.add_argument("--baudrate", type=int, default=9600)
    args = parser.parse_args()
    token = os.getenv("ARDUINO_BRIDGE_TOKEN", "").strip()
    if not args.url or not token:
        parser.error("Configure ARDUINO_BRIDGE_URL e ARDUINO_BRIDGE_TOKEN.")
    url = args.url.replace("https://", "wss://", 1).replace("http://", "ws://", 1)
    asyncio.run(executar(url, token, args.port, args.baudrate))


if __name__ == "__main__":
    main()

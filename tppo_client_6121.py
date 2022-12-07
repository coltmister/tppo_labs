import argparse
import logging
import socket
import threading
import time

logging.basicConfig(filename='client_notifications.log',
                    filemode='a',
                    format='%(asctime)s,%(msecs)d %(name)s %(levelname)s %(message)s',
                    datefmt='%H:%M:%S',
                    level=logging.DEBUG)
logger = logging.getLogger(__name__)

STOP_THREADS = False


def threaded(fn):
    def custom_hook(args):
        # report the failure
        print(f'Thread failed: {args.exc_value}')

    def wrapper(*args, **kwargs):
        threading.excepthook = custom_hook
        t = threading.Thread(target=fn, args=args, kwargs=kwargs).start()

    return wrapper


class BedReanimationClient:
    def __init__(self, host: str, port: int, notify_port: int):

        self.COMMANDS = {
            1: {
                "command": "get_angles",
                "help": "Get angles of the bed"
            },
            2: {
                "command": "get_height",
                "help": "Get height of the bed"
            },
            3: {
                "command": "get_weight",
                "help": "Get weight of the patient"
            },
            4: {
                "command": "set_angles",
                "help": "Set angles of the bed"
            },
            5: {
                "command": "set_height",
                "help": "Set height of the bed"
            },
            6: {
                "command": "set_weight",
                "help": "Set weight of the patient"
            },
            7: {
                "command": "subscribe_angles",
                "help": "Subscribe to notifications on angles of the bed"
            },
            8: {
                "command": "subscribe_height",
                "help": "Subscribe to notifications on height of the bed"
            },
            9: {
                "command": "subscribe_weight",
                "help": "Subscribe to notifications on weight of the patient"
            },
            10: {
                "command": "unsubscribe_angles",
                "help": "Unsubscribe from notifications on angles of the bed"
            },
            11: {
                "command": "unsubscribe_height",
                "help": "Unsubscribe from notifications on height of the bed"
            },
            12: {
                "command": "unsubscribe_weight",
                "help": "Unsubscribe from notifications on weight of the patient"
            },
            13: {
                "command": "exit",
                "help": "Exit the client"
            },
            14: {
                "command": "commands",
                "help": "Show commands"
            }
        }
        self.host = host
        self.port = port
        self.notify_port = notify_port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((self.host, self.port))
        self.notify_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.notify_sock.connect((self.host, self.notify_port))

        print(f"Connected to {self.host}:{self.port}")
        self.help_commands()

    def listen_notifications(self) -> None:
        global STOP_THREADS
        while not STOP_THREADS:
            try:
                data = self.receive_notify()
                logger.info(data)
            except Exception as e:
                pass

    def start_transmitter(self) -> None:
        global STOP_THREADS
        try:
            while not STOP_THREADS:
                command = input("Enter command: ")
                if command.isdigit():
                    command = int(command)
                    if command in self.COMMANDS:
                        if command in [1, 2, 3]:
                            self.send(self.COMMANDS[command]['command'])
                            print(f"Received: {self.receive()}")
                        elif command in [4, 5, 6]:
                            self.send(f"{self.COMMANDS[command]['command']}")
                            print(f"{self.receive()}")
                            value = input()
                            self.send(value)
                            print(f"Received: {self.receive()}")
                        elif command in [7, 8, 9, 10, 11, 12]:
                            self.subscribe(self.COMMANDS[command]['command'])
                            time.sleep(1)
                        else:
                            if command == 13:
                                print("Exiting...")
                                self.sock.close()
                                self.notify_sock.close()
                                STOP_THREADS = True
                                exit(0)
                            elif command == 14:
                                self.help_commands()
                    else:
                        print("Wrong command")
                else:
                    if command == "exit":
                        print("Exiting...")
                        self.sock.close()
                        self.notify_sock.close()
                        STOP_THREADS = True
                        exit(0)
                    elif command == "commands":
                        self.help_commands()
                    print("Wrong command")
        except (KeyboardInterrupt,):
            print("Connection error")
            STOP_THREADS = True
            exit(0)

    def send(self, data: str) -> None:
        self.sock.sendall(data.encode() + b'\n')

    def subscribe(self, command: str) -> None:
        self.notify_sock.sendall(command.encode() + b'\n')

    def help_commands(self) -> None:
        for key, value in self.COMMANDS.items():
            print(f"{key} - {value['help']}")
        print('\n')

    def receive(self) -> str:
        data = self.sock.recv(1024).decode()
        return data

    def receive_notify(self) -> str:
        data = self.notify_sock.recv(1024).decode()
        if not data:
            print("Connection error")
            exit(0)
        return data

    def __delete__(self, instance):
        self.sock.close()
        self.notify_sock.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', help='Server address', default='127.0.0.1', type=str)
    parser.add_argument('-p', '--port', help='Server port', default=8000, type=int)
    parser.add_argument('-n', '--notify_port', help='Server port', default=8001, type=int)
    args = parser.parse_args()
    client = BedReanimationClient(args.host, args.port, args.notify_port)
    try:
        t2 = threading.Thread(target=client.listen_notifications)
        t2.daemon = True
        t2.start()
        client.start_transmitter()
        t2.join()
    except (KeyboardInterrupt, Exception):
        print("Connection error")
        client.sock.close()
        client.notify_sock.close()
        STOP_THREADS = True
        exit(0)

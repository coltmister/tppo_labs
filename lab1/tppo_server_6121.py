"""
Вариант работы: 6121
6 - Устройство: Кровать реанимационная
1 - Файл устройства: Plain Text
2 - Формата передачи данных: Binary
1 - Транспортный протокол: TCP
Параметры устройства:
1. Углы наклона секций:
- спинной (0 .. 50)
- тазобедренной (-15 .. 15)
- голеностопной (0 .. 30)
2. Высота ложа (0 .. 100 процентов).
3. Вес на тазобедренной секции (0 .. 300 кг).
Функции устройства:
1. Установить углы наклона секций.
2. Получить значения углов наклона и текущего веса.
3. Получить уведомление об изменении углов
наклона или текущего веса.
"""
import argparse
import logging
import socket
import threading
import time
import traceback

log_level = logging.DEBUG

logging.basicConfig(filename='logs/server_error.log',
                    filemode='a+',
                    format='%(asctime)s,%(msecs)d %(name)s %(levelname)s %(message)s',
                    datefmt='%H:%M:%S',
                    level=log_level)
logger = logging.getLogger(__name__)


def threaded(fn):
    def wrapper(*args, **kwargs):
        t1 = threading.Thread(target=fn, args=args, kwargs=kwargs)
        t1.daemon = True
        t1.start()

    return wrapper


class BedReanimation:

    @staticmethod
    def validate(back: int = None, hip: int = None, ankle: int = None, height: int = None, weight: int = None):
        if back and not (0 <= back <= 50):
            logger.error(f'bed_reanimation: back angle is not valid: {back}')
            raise ValueError('back angle is out of range')
        if hip and not (-15 <= hip <= 15):
            logger.error(f'bed_reanimation: hip angle is not valid: {hip}')
            raise ValueError('hip angle is out of range')
        if ankle and not (0 <= ankle <= 30):
            logger.error(f'bed_reanimation: ankle angle is not valid: {ankle}')
            raise ValueError('ankle angle is out of range')
        if height and not (0 <= height <= 100):
            logger.error(f'bed_reanimation: height is not valid: {height}')
            raise ValueError('height is out of range')
        if weight and not (0 <= weight <= 300):
            logger.error(f'bed_reanimation: weight is not valid: {weight}')
            raise ValueError('weight is out of range')

    def __init__(self, file, host: str = '0.0.0.0', port: int = 8000, notify_port: int = 8001):
        self.ankle = 0
        self.hip = 0
        self.back = 0
        self.height = 0
        self.weight = 0
        self.device_file = file
        self.port = port
        self.address = host
        self.notify_port = notify_port
        self.angles_clients = []
        self.weight_clients = []
        self.height_clients = []

    def listen_file(self):
        while True:
            try:
                file = open(self.device_file, 'r')
                for line in file:
                    if line:
                        back, hip, ankle, height, weight = self.parse_line(line)
                        if back != self.back or hip != self.hip or ankle != self.ankle:
                            self.set_angles(int(back), int(hip), int(ankle))
                        if height != self.height:
                            self.set_height(int(height))
                            logger.info(f'bed_reanimation: height is changed: {height}')
                        if weight != self.weight:
                            self.set_weight(int(weight))
                            logger.info(f'bed_reanimation: weight is changed: {weight}')
                    time.sleep(1)
            except FileNotFoundError:
                file.close()
                logger.error(f'bed_reanimation: file {self.device_file} not found')
            except ValueError:
                file.close()
                logger.error(f'bed_reanimation: wrong data in file: {line}')
            except Exception as e:
                logger.error(f'[listen_file] bed_reanimation: {traceback.format_exc()}')
                file.close()

    # ----------------- TCP -----------------
    def start_notify_server(self) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind((self.address, self.notify_port))
            sock.listen()
            while True:
                conn, addr = sock.accept()
                threading.Thread(target=self.accept_notification_request, args=(conn, addr)).start()

    def listen_tcp(self) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind((self.address, self.port))
            s.listen()
            while True:
                conn, addr = s.accept()
                threading.Thread(target=self.client_connection, args=(conn, addr)).start()

    def accept_notification_request(self, conn, addr: tuple) -> None:
        try:
            with conn:
                while True:
                    try:
                        data = conn.recv(1024)
                        if data:
                            if data == b'subscribe_angles\n':
                                self.angles_clients.append(conn)
                                conn.sendall(b'You are subscribed to angles changes' + b'\n')
                            elif data == b'subscribe_weight\n':
                                self.weight_clients.append(conn)
                                conn.sendall(b'You are subscribed to weight changes' + b'\n')
                            elif data == b'subscribe_height\n':
                                self.height_clients.append(conn)
                                conn.sendall(b'You are subscribed to height changes' + b'\n')
                            elif data == b'unsubscribe_angles\n':
                                self.angles_clients.remove(conn)
                                conn.sendall(b'You are unsubscribed from angles changes' + b'\n')
                            elif data == b'unsubscribe_weight\n':
                                self.weight_clients.remove(conn)
                                conn.sendall(b'You are unsubscribed from weight changes' + b'\n')
                            elif data == b'unsubscribe_height\n':
                                self.height_clients.remove(conn)
                                conn.sendall(b'You are unsubscribed from height changes' + b'\n')
                            else:
                                conn.sendall(b'Wrong command' + b'\n')
                    except ConnectionResetError:
                        logger.error(f'bed_reanimation: client {addr} disconnected')
                        break
        except Exception as e:
            logger.error(f'[accept_notification_request] bed_reanimation: {e}')
            self.angles_clients.remove(conn)
            self.weight_clients.remove(conn)
            self.height_clients.remove(conn)

    def client_connection(self, conn, address: tuple):
        try:
            with conn:
                while True:
                    try:
                        data = conn.recv(1024)
                    except ConnectionResetError:
                        logger.error(f'[client_connection] bed_reanimation: client {address} disconnected')
                        break
                    if not data:
                        break
                    if data == b'get_angles\n':
                        conn.sendall(self.get_angles() + b'\n')
                    elif data == b'get_weight\n':
                        conn.sendall(self.get_weight() + b'\n')
                    elif data == b'get_height\n':
                        conn.sendall(self.get_height() + b'\n')
                    elif data == b'set_angles\n':
                        help_text = f"------Enter angles------\n" \
                                    f"back: 0 .. 50\n" \
                                    f"hip: -15 .. 15\n" \
                                    f"ankle: 0 .. 30\n" \
                                    f"---format---\n" \
                                    f"back,hip,ankle\n" \
                                    f"---example---\n" \
                                    f"10,0,0\n" \
                                    f"------------------------\n" \
                                    f"Enter angles: "
                        conn.sendall(help_text.encode())
                        data = conn.recv(1024)
                        if data:
                            try:
                                back, hip, ankle, *_ = self.parse_tcp_angles(data.decode(encoding='latin-1'))
                                conn.sendall(self.set_angles_to_device(back, hip, ankle))
                            except ValueError as e:
                                conn.sendall(f'Angles are not set: {e}'.encode() + b'\n')
                    elif data == b'set_weight\n':
                        help_text = f"------Enter weight------\n" \
                                    f"weight: 0 .. 300\n" \
                                    f"---format---\n" \
                                    f"weight\n" \
                                    f"---example---\n" \
                                    f"150\n" \
                                    f"------------------------\n" \
                                    f"Enter weight: "
                        conn.sendall(help_text.encode())
                        data = conn.recv(1024)
                        if data:
                            try:
                                weight = int(data.decode(encoding='latin-1'))
                                conn.sendall(self.set_weight_to_device(weight))
                            except ValueError as e:
                                conn.sendall(f'Weight is not set: {e}'.encode())
                    elif data == b'set_height\n':
                        help_text = f"------Enter height------\n" \
                                    f"height: 0 .. 100\n" \
                                    f"---format---\n" \
                                    f"height\n" \
                                    f"---example---\n" \
                                    f"80\n" \
                                    f"------------------------\n" \
                                    f"Enter height: "
                        conn.sendall(help_text.encode())
                        data = conn.recv(1024)
                        if data:
                            try:
                                height = int(data.decode(encoding='latin-1'))
                                conn.sendall(self.set_height_to_device(height))
                            except ValueError as e:
                                conn.sendall(f'Height is not set: {e}'.encode() + b'\n')
                    else:
                        conn.sendall(b'unknown command: "' + data + b'"\n')
        except Exception as e:
            logger.error(f'[client_connection2] bed_reanimation: {e}')

    # ----------------- parsers -----------------

    def parse_line(self, line: str):
        back, hip, ankle, height, weight = line.split(',')
        try:
            back = int(back)
            hip = int(hip)
            ankle = int(ankle)
            height = int(height)
            weight = int(weight)
        except ValueError:
            logger.error(f'bed_reanimation: wrong data in file: {line}')
            return self.back, self.hip, self.ankle, self.height, self.weight
        return back, hip, ankle, height, weight

    def parse_tcp_angles(self, data: str):
        back, hip, ankle = data.split(',')
        try:
            back = int(back)
            hip = int(hip)
            ankle = int(ankle)
        except ValueError:
            logger.error(f'bed_reanimation: wrong data in tcp: {data}')
            return self.back, self.hip, self.ankle
        return back, hip, ankle

    # -------------------setters-------------------

    def set_angles(self, back: int, hip: int, ankle: int) -> None:
        try:
            self.validate(back, hip, ankle)
            self.back = back
            self.hip = hip
            self.ankle = ankle
            for client in self.angles_clients:
                try:
                    client.sendall(f"!Notify! New angles: back={back}, hip={hip}, ankle={ankle}".encode())
                except (ConnectionResetError, BrokenPipeError, OSError):
                    self.angles_clients.remove(client)
        except ValueError as e:
            logger.error(f'bed_reanimation: angles are not set: {e}')

    def set_angles_to_device(self, back: int, hip: int, ankle: int) -> bytes:
        try:
            self.validate(back, hip, ankle)
            with open('device.csv', 'w') as file:
                file.write(f'{back},{hip},{ankle},{self.height},{self.weight}')
            return "!Success: Angles are set \n".encode()
        except ValueError as e:
            logger.error(f'bed_reanimation: angles are not set: {e}')
            return f'!Error: Angles are not set: {e} \n'.encode()

    def set_height(self, height: int) -> None:
        try:
            self.validate(height=height)
            self.height = height
            for client in self.height_clients:
                try:
                    client.sendall(f"!Notify! New height is {height}".encode())
                except (ConnectionResetError, BrokenPipeError, OSError):
                    self.height_clients.remove(client)
        except ValueError as e:
            logger.error(f'bed_reanimation: height is not set: {e}')

    def set_height_to_device(self, height: int) -> bytes:
        try:
            self.validate(height=height)
            with open('device.csv', 'w') as file:
                file.write(f'{self.back},{self.hip},{self.ankle},{height},{self.weight}')
            return "!Success: Height is set \n".encode()
        except ValueError as e:
            logger.error(f'bed_reanimation: height is not set: {e}')
            return f'!Error: Height is not set: {e} \n'.encode()

    def set_weight(self, weight: int) -> None:
        try:
            self.validate(weight=weight)
            self.weight = weight
            for client in self.weight_clients:
                try:
                    client.sendall(f"!Notify! New weight is {weight}".encode() + b'\n')
                except (ConnectionResetError, BrokenPipeError, OSError):
                    self.weight_clients.remove(client)

        except ValueError as e:
            logger.error(f'bed_reanimation: weight is not set: {e}')

    def set_weight_to_device(self, weight: int) -> bytes:
        try:
            self.validate(weight=weight)
            with open('device.csv', 'w') as file:
                file.write(f'{self.back},{self.hip},{self.ankle},{self.height},{weight}')
            return "!Success: Weight is set \n".encode()
        except ValueError as e:
            logger.error(f'bed_reanimation: weight is not set: {e}')
            return f'!Error: Weight is not set: {e} \n'.encode()

    # -------------------getters-------------------

    def get_angles(self) -> bytes:
        bytes_angles = f"{self.back},{self.hip},{self.ankle}".encode()
        return bytes_angles

    def get_weight(self) -> bytes:
        bytes_weight = f"{self.weight}".encode()
        return bytes_weight

    def get_height(self) -> bytes:
        bytes_height = f"{self.height}".encode()
        return bytes_height

    # -------------------inner_methods-------------------

    def __str__(self) -> str:
        return f'back: {self.back}, hip: {self.hip}, ankle: {self.ankle}, height: {self.height}, weight: {self.weight}'

    def __repr__(self) -> str:
        return self.__str__()

    def __delete__(self, instance):
        logger.info('bed_reanimation: bed is deleted')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-f', '--file', help='path to file with data', default='./device.csv')
    parser.add_argument('-a', '--address', help='address to listen', default='0.0.0.0')
    parser.add_argument('-p', '--port', help='port to listen', default=8000, type=int)
    parser.add_argument('-l', '--notification-port', help='port to listen for notifications', default=8001, type=int)
    parser.add_argument('-d', '--debug', help='debug mode', default=False, type=bool)

    if parser.parse_args().debug:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)
    args = parser.parse_args()
    try:
        bed = BedReanimation(args.file, args.address, args.port, args.notification_port)
        t1 = threading.Thread(target=bed.listen_file)
        t1.daemon = True
        t1.start()
        t2 = threading.Thread(target=bed.listen_tcp)
        t2.daemon = True
        t2.start()
        t3 = threading.Thread(target=bed.start_notify_server)
        t3.daemon = True
        t3.start()
        t1.join()
        t2.join()
        t3.join()
    except KeyboardInterrupt:
        print('bed_reanimation: bed is deleted')

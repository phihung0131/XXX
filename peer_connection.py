import socket
import threading
import json

class PeerConnection(threading.Thread):
    def __init__(self, node, peer_address, is_initiator=True):
        threading.Thread.__init__(self)
        self.node = node
        self.peer_address = peer_address
        self.is_initiator = is_initiator
        self.sock = None

    def run(self):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            if self.is_initiator:
                self.sock.connect(self.peer_address)
                print(f"Leecher: Đã kết nối thành công với peer: {self.peer_address[0]}:{self.peer_address[1]}")
                self.send_message("HELLO")
            else:
                self.sock.bind((self.node.ip, self.node.port))
                self.sock.listen(1)
                print(f"Seeder: Đang lắng nghe kết nối tại {self.node.ip}:{self.node.port}")
                client_sock, address = self.sock.accept()
                self.sock = client_sock
                print(f"Seeder: Đã chấp nhận kết nối từ: {address[0]}:{address[1]}")

            self.handle_communication()
        except Exception as e:
            print(f"Lỗi kết nối với peer {self.peer_address[0]}:{self.peer_address[1]}: {str(e)}")
        finally:
            if self.sock:
                self.sock.close()

    def handle_communication(self):
        while True:
            try:
                data = self.sock.recv(1024)
                if not data:
                    break
                message = data.decode('utf-8')
                print(f"Nhận được tin nhắn từ peer: {message}")
                self.process_message(message)
            except Exception as e:
                print(f"Lỗi trong quá trình giao tiếp: {str(e)}")
                break

    def process_message(self, message):
        try:
            msg_data = json.loads(message)
            if msg_data['type'] == "HELLO":
                self.send_message(json.dumps({"type": "HELLO_ACK"}))
            elif msg_data['type'] == "HELLO_ACK":
                print("Leecher: Kết nối đã được thiết lập")
            elif msg_data['type'] == "REQUEST_PIECE":
                print(f"Seeder: Nhận yêu cầu piece {msg_data['piece_index']}")
                # Thêm logic để gửi piece ở đây
            elif msg_data['type'] == "PIECE":
                print(f"Leecher: Nhận được piece {msg_data['piece_index']}")
                # Thêm logic để xử lý piece nhận được ở đây
        except json.JSONDecodeError:
            print(f"Lỗi khi xử lý tin nhắn: {message}")

    def send_message(self, message):
        try:
            self.sock.sendall(message.encode('utf-8'))
        except Exception as e:
            print(f"Lỗi khi gửi tin nhắn: {str(e)}")

    def request_piece(self, piece_index):
        message = json.dumps({"type": "REQUEST_PIECE", "piece_index": piece_index})
        self.send_message(message)

    def send_piece(self, piece_index, piece_data):
        message = json.dumps({"type": "PIECE", "piece_index": piece_index, "data": piece_data})
        self.send_message(message)

import socket
import threading
import json
import hashlib

class PeerConnection(threading.Thread):
    def __init__(self, node, peer_address):
        threading.Thread.__init__(self)
        self.node = node
        self.peer_address = peer_address
        self.sock = None
        self.total_pieces = 0
        self.current_piece = 0

    def run(self):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            if self.is_initiator:
                print(f"Đang kết nối đến peer (server) tại: {self.peer_address[0]}:{self.peer_address[1]}...")
                self.sock.connect(self.peer_address)
                print(f"Leecher: Đã kết nối thành công với peer: {self.peer_address[0]}:{self.peer_address[1]}")
                self.send_message("HELLO")
            else:
                self.sock.bind(('0.0.0.0', self.node.port))
                self.sock.listen(5)
                print(f"Seeder: Đang lắng nghe kết nối tại 0.0.0.0:{self.node.port}")
                client_sock, address = self.sock.accept()
                self.sock = client_sock
                print(f"Seeder: Đã chấp nhận kết nối từ: {address[0]}:{address[1]}")

            self.handle_communication()
        except ConnectionRefusedError:
            print(f"Không thể kết nối đến peer {self.peer_address[0]}:{self.peer_address[1]}. Hãy kiểm tra IP và port.")
        except socket.error as e:
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
                print(f"Seeder nhận HELLO từ {self.peer_address[0]}:{self.peer_address[1]}")
                self.send_message(json.dumps({"type": "HELLO_ACK"}))
            elif msg_data['type'] == "HELLO_ACK":
                print(f"Leecher nhận HELLO_ACK từ {self.peer_address[0]}:{self.peer_address[1]}")
                # Bắt đầu yêu cầu piece 0
                print("Bắt đầu yêu cầu piece...")
                self.send_message(json.dumps({
                    "type": "REQUEST_PIECE",
                    "piece_index": 0
                }))
            elif msg_data['type'] == "REQUEST_PIECE":
                piece_index = msg_data.get('piece_index')
                print(f"Seeder nhận yêu cầu piece {piece_index} từ {self.peer_address[0]}:{self.peer_address[1]}")
                piece_data = self.node.get_piece_data(piece_index)
                if piece_data:
                    print(f"Seeder gửi piece {piece_index} cho {self.peer_address[0]}:{self.peer_address[1]}")
                    self.send_message(json.dumps({
                        "type": "PIECE_DATA",
                        "piece_index": piece_index,
                        "data": piece_data.decode('latin1')
                    }))
            elif msg_data['type'] == "PIECE_DATA":
                piece_index = msg_data.get('piece_index')
                piece_data = msg_data.get('data').encode('latin1')
                print(f"Leecher nhận piece {piece_index} từ {self.peer_address[0]}:{self.peer_address[1]}")
                self.node.save_piece(piece_index, piece_data)
                # Yêu cầu piece tiếp theo
                self.send_message(json.dumps({
                    "type": "REQUEST_PIECE",
                    "piece_index": piece_index + 1
                }))

        except json.JSONDecodeError:
            print(f"Lỗi khi xử lý tin nhắn: {message}")
        except Exception as e:
            print(f"Lỗi trong process_message: {str(e)}")

    def request_next_piece(self, retry_piece=None):
        piece_index = retry_piece if retry_piece is not None else self.current_piece
        print(f"Leecher yêu cầu piece {piece_index} từ {self.peer_address[0]}:{self.peer_address[1]}")
        self.send_message(json.dumps({
            "type": "REQUEST_PIECE",
            "piece_index": piece_index
        }))

    def verify_piece(self, piece_index, piece_data):
        expected_hash = self.node.get_piece_hash(piece_index)
        actual_hash = hashlib.sha1(piece_data).hexdigest()
        return expected_hash == actual_hash

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

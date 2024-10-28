import socket
import threading
import json
import hashlib
import traceback

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
                print(f"Đang kết nối đến {self.peer_address[0]}:{self.peer_address[1]}...")
                self.sock.connect(self.peer_address)
                print(f"Leecher: Đã kết nối thành công với peer: {self.peer_address[0]}:{self.peer_address[1]}")
                self.send_message(json.dumps({"type": "HELLO"}))
            else:
                self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                self.sock.bind(('0.0.0.0', self.node.port))
                self.sock.listen(5)
                print(f"Seeder: Đang lắng nghe kết nối tại 0.0.0.0:{self.node.port}")
                self.client_sock, address = self.sock.accept()
                print(f"Seeder: Đã chấp nhận kết nối từ: {address[0]}:{address[1]}")
                self.peer_address = address

            # Xử lý giao tiếp
            while True:
                try:
                    if self.is_initiator:
                        data = self.sock.recv(1024)
                    else:
                        data = self.client_sock.recv(1024)
                    if not data:
                        print("Kết nối đã đóng")
                        break
                    message = data.decode('utf-8')
                    print(f"Nhận được tin nhắn: {message}")
                    self.process_message(message)
                except socket.error as e:
                    print(f"Lỗi khi nhận tin nhắn: {e}")
                    break

        except ConnectionRefusedError:
            print(f"Không thể kết nối đến peer {self.peer_address[0]}:{self.peer_address[1]}")
        except socket.error as e:
            print(f"Lỗi socket: {e}")
        finally:
            if hasattr(self, 'client_sock'):
                self.client_sock.close()
            if self.sock:
                self.sock.close()
            print("Đã đóng kết nối")

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
            print(f"Bắt đầu xử lý tin nhắn: {message}")
            msg_data = json.loads(message)
            print(f"Đã giải mã JSON thành công: {msg_data}")
            
            if msg_data['type'] == "HELLO":
                print(f"Seeder nhận HELLO từ {self.peer_address[0]}:{self.peer_address[1]}")
                try:
                    response = json.dumps({"type": "HELLO_ACK"})
                    print(f"Seeder đã tạo tin nhắn HELLO_ACK: {response}")
                    if hasattr(self, 'client_sock'):
                        print("Sử dụng client_sock để gửi")
                        self.client_sock.sendall(response.encode('utf-8'))
                    else:
                        print("Sử dụng sock để gửi")
                        self.sock.sendall(response.encode('utf-8'))
                    print(f"Seeder đã gửi HELLO_ACK thành công")
                except Exception as e:
                    print(f"Lỗi khi seeder gửi HELLO_ACK: {str(e)}")
                    print(f"Chi tiết stack trace:", traceback.format_exc())
                
            elif msg_data['type'] == "HELLO_ACK":
                print(f"Leecher nhận HELLO_ACK từ {self.peer_address[0]}:{self.peer_address[1]}")
                try:
                    request = json.dumps({
                        "type": "REQUEST_PIECE",
                        "piece_index": 0
                    })
                    print(f"Leecher gửi yêu cầu piece 0")
                    self.sock.sendall(request.encode('utf-8'))
                except Exception as e:
                    print(f"Lỗi khi leecher gửi REQUEST_PIECE: {str(e)}")
                    print(f"Chi tiết stack trace:", traceback.format_exc())
                
            elif msg_data['type'] == "REQUEST_PIECE":
                piece_index = msg_data.get('piece_index')
                print(f"Seeder nhận yêu cầu piece {piece_index}")
                try:
                    piece_data = "TEST_PIECE_DATA"  # Tạm thời dùng dữ liệu test
                    response = json.dumps({
                        "type": "PIECE_DATA",
                        "piece_index": piece_index,
                        "data": piece_data
                    })
                    if hasattr(self, 'client_sock'):
                        self.client_sock.sendall(response.encode('utf-8'))
                    else:
                        self.sock.sendall(response.encode('utf-8'))
                    print(f"Seeder đã gửi piece {piece_index}")
                except Exception as e:
                    print(f"Lỗi khi seeder gửi PIECE_DATA: {str(e)}")
                    print(f"Chi tiết stack trace:", traceback.format_exc())
                
            elif msg_data['type'] == "PIECE_DATA":
                piece_index = msg_data.get('piece_index')
                print(f"Leecher nhận được piece {piece_index}")
                try:
                    # Yêu cầu piece tiếp theo
                    next_request = json.dumps({
                        "type": "REQUEST_PIECE",
                        "piece_index": piece_index + 1
                    })
                    self.sock.sendall(next_request.encode('utf-8'))
                    print(f"Leecher đã yêu cầu piece tiếp theo: {piece_index + 1}")
                except Exception as e:
                    print(f"Lỗi khi leecher yêu cầu piece tiếp theo: {str(e)}")
                    print(f"Chi tiết stack trace:", traceback.format_exc())

        except json.JSONDecodeError as e:
            print(f"Lỗi khi giải mã JSON: {str(e)}")
            print(f"Tin nhắn gốc gây lỗi: {message}")
            print(f"Chi tiết stack trace:", traceback.format_exc())
        except Exception as e:
            print(f"Lỗi không xác định trong process_message: {str(e)}")
            print(f"Tin nhắn gây lỗi: {message}")
            print(f"Chi tiết stack trace:", traceback.format_exc())

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
            print(f"Đang cố gắng gửi tin nhắn: {message}")
            if self.is_initiator:
                self.sock.sendall(message.encode('utf-8'))
            else:
                self.client_sock.sendall(message.encode('utf-8'))
            print(f"Đã gửi tin nhắn thành công: {message}")
        except Exception as e:
            print(f"Lỗi khi gửi tin nhắn: {str(e)}")
            print(f"Chi tiết tin nhắn bị lỗi: {message}")

    def request_piece(self, piece_index):
        message = json.dumps({"type": "REQUEST_PIECE", "piece_index": piece_index})
        self.send_message(message)

    def send_piece(self, piece_index, piece_data):
        message = json.dumps({"type": "PIECE", "piece_index": piece_index, "data": piece_data})
        self.send_message(message)

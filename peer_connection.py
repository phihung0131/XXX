import socket
import threading
import json
import hashlib
import traceback

class PeerConnection(threading.Thread):
    def __init__(self, node, peer_address, is_initiator=True):
        threading.Thread.__init__(self)
        self.node = node
        self.peer_address = peer_address
        self.is_initiator = is_initiator  # Thêm biến is_initiator vào constructor
        self.sock = None
        self.total_pieces = 0
        self.current_piece = 0
        self.active_socket = None  # Socket đang được sử dụng để giao tiếp

    def run(self):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            if self.is_initiator:  # Leecher
                print(f"Leecher: Đang kết nối đến {self.peer_address[0]}:{self.peer_address[1]}...")
                self.sock.connect(self.peer_address)
                print(f"Leecher: Đã kết nối thành công với peer: {self.peer_address[0]}:{self.peer_address[1]}")
                hello_msg = json.dumps({"type": "HELLO"})
                print(f"Leecher: Gửi HELLO: {hello_msg}")
                self.sock.sendall(hello_msg.encode('utf-8'))
                print("Leecher: Đã gửi HELLO, đang đợi phản hồi...")
            else:  # Seeder
                self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                self.sock.bind(('0.0.0.0', self.node.port))
                self.sock.listen(5)
                print(f"Seeder: Đang lắng nghe kết nối tại 0.0.0.0:{self.node.port}")
                self.client_sock, address = self.sock.accept()
                self.peer_address = address
                print(f"Seeder: Đã chấp nhận kết nối từ: {address[0]}:{address[1]}")

            # Xử lý giao tiếp
            while True:
                try:
                    if self.is_initiator:  # Leecher
                        print("Leecher: Đang đợi nhận dữ liệu...")
                        data = self.sock.recv(1024)
                    else:  # Seeder
                        print("Seeder: Đang đợi nhận dữ liệu...")
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

        except Exception as e:
            print(f"Lỗi: {e}")
        finally:
            if hasattr(self, 'client_sock'):
                self.client_sock.close()
            if self.sock:
                self.sock.close()
            print("Đã đóng kết nối")

    def process_message(self, message):
        try:
            msg_data = json.loads(message)
            
            if msg_data['type'] == "HELLO":
                print(f"Seeder: Nhận HELLO từ {self.peer_address[0]}:{self.peer_address[1]}")
                # Gửi HELLO_ACK
                hello_ack = json.dumps({"type": "HELLO_ACK"})
                print("Seeder: Đang gửi HELLO_ACK...")
                self.client_sock.sendall(hello_ack.encode('utf-8'))
                print("Seeder: Đã gửi HELLO_ACK")
                
            elif msg_data['type'] == "HELLO_ACK":
                print(f"Leecher: Nhận HELLO_ACK từ {self.peer_address[0]}:{self.peer_address[1]}")
                # Gửi yêu cầu piece đầu tiên
                request = json.dumps({
                    "type": "REQUEST_PIECE",
                    "piece_index": 0
                })
                print("Leecher: Đang gửi yêu cầu piece 0...")
                self.sock.sendall(request.encode('utf-8'))
                print("Leecher: Đã gửi yêu cầu piece 0")
                
            elif msg_data['type'] == "REQUEST_PIECE":
                piece_index = msg_data['piece_index']
                print(f"Seeder: Nhận yêu cầu piece {piece_index}")
                # Gửi piece data (tạm thời dùng dữ liệu test)
                piece_data = json.dumps({
                    "type": "PIECE_DATA",
                    "piece_index": piece_index,
                    "data": f"TEST_PIECE_{piece_index}"
                })
                print(f"Seeder: Đang gửi piece {piece_index}...")
                self.client_sock.sendall(piece_data.encode('utf-8'))
                print(f"Seeder: Đã gửi piece {piece_index}")
                
            elif msg_data['type'] == "PIECE_DATA":
                piece_index = msg_data['piece_index']
                print(f"Leecher: Nhận được piece {piece_index}")
                # Yêu cầu piece tiếp theo
                next_piece = piece_index + 1
                request = json.dumps({
                    "type": "REQUEST_PIECE",
                    "piece_index": next_piece
                })
                print(f"Leecher: Đang gửi yêu cầu piece {next_piece}...")
                self.sock.sendall(request.encode('utf-8'))
                print(f"Leecher: Đã gửi yêu cầu piece {next_piece}")

        except Exception as e:
            print(f"Lỗi xử lý tin nhắn: {e}")

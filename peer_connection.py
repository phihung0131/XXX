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
        self.is_initiator = is_initiator
        self.sock = None
        self.total_pieces = 0
        self.current_piece = 0
        self.connected = False

    def run(self):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            
            if self.is_initiator:  # Leecher
                print(f"Leecher: Đang kết nối đến {self.peer_address[0]}:{self.peer_address[1]}...")
                self.sock.connect(self.peer_address)
                print(f"Leecher: Đã kết nối thành công với peer: {self.peer_address[0]}:{self.peer_address[1]}")
                self.connected = True
                hello_msg = json.dumps({"type": "HELLO"})
                print(f"Leecher: Gửi HELLO: {hello_msg}")
                self.send_message(hello_msg)
                print("Leecher: Đã gửi HELLO, đang đợi phản hồi...")
            else:  # Seeder
                self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                self.sock.bind(('0.0.0.0', self.node.port))
                self.sock.listen(5)
                print(f"Seeder: Đang lắng nghe kết nối tại 0.0.0.0:{self.node.port}")
                client_sock, address = self.sock.accept()
                self.sock = client_sock  # Gán socket kết nối cho self.sock
                self.peer_address = address
                self.connected = True
                print(f"Seeder: Đã chấp nhận kết nối từ: {address[0]}:{address[1]}")

            # Xử lý giao tiếp
            while self.connected:
                try:
                    print(f"{'Leecher' if self.is_initiator else 'Seeder'}: Đang đợi nhận dữ liệu...")
                    data = self.sock.recv(1024)

                    if not data:
                        print("Kết nối đã đóng")
                        self.connected = False
                        break

                    message = data.decode('utf-8')
                    print(f"Nhận được tin nhắn: {message}")
                    self.process_message(message)

                except socket.error as e:
                    print(f"Lỗi khi nhận tin nhắn: {e}")
                    self.connected = False
                    break

        except Exception as e:
            print(f"Lỗi: {e}")
            traceback.print_exc()
        finally:
            if self.sock:
                self.sock.close()
            print("Đã đóng kết nối")

    def send_message(self, message):
        """Hàm gửi tin nhắn thống nhất cho cả seeder và leecher"""
        if self.connected and self.sock:
            try:
                self.sock.sendall(message.encode('utf-8'))
                return True
            except socket.error as e:
                print(f"Lỗi khi gửi tin nhắn: {e}")
                self.connected = False
                return False
        return False

    def process_message(self, message):
        try:
            msg_data = json.loads(message)
            
            if msg_data['type'] == "HELLO":
                print(f"Seeder: Nhận HELLO từ {self.peer_address[0]}:{self.peer_address[1]}")
                # Gửi HELLO_ACK
                hello_ack = json.dumps({"type": "HELLO_ACK"})
                print("Seeder: Đang gửi HELLO_ACK...")
                self.send_message(hello_ack)
                print("Seeder: Đã gửi HELLO_ACK")
                
            elif msg_data['type'] == "HELLO_ACK":
                print(f"Leecher: Nhận HELLO_ACK từ {self.peer_address[0]}:{self.peer_address[1]}")
                # Gửi yêu cầu piece đầu tiên
                request = json.dumps({
                    "type": "REQUEST_PIECE",
                    "piece_index": 0
                })
                print("Leecher: Đang gửi yêu cầu piece 0...")
                self.send_message(request)
                print("Leecher: Đã gửi yêu cầu piece 0")
                
            elif msg_data['type'] == "REQUEST_PIECE":
                piece_index = msg_data['piece_index']
                print(f"Seeder: Nhận yêu cầu piece {piece_index}")
                # Gửi piece data
                piece_data = json.dumps({
                    "type": "PIECE_DATA",
                    "piece_index": piece_index,
                    "data": f"TEST_PIECE_{piece_index}"
                })
                print(f"Seeder: Đang gửi piece {piece_index}...")
                self.send_message(piece_data)
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
                self.send_message(request)
                print(f"Leecher: Đã gửi yêu cầu piece {next_piece}")

        except Exception as e:
            print(f"Lỗi xử lý tin nhắn: {e}")
            traceback.print_exc()
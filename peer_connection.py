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
            
            if self.is_initiator:
                # Leecher mode
                print(f"Leecher: Đang kết nối đến {self.peer_address[0]}:{self.peer_address[1]}...")
                self.sock.connect(self.peer_address)
                self.active_socket = self.sock
                print(f"Leecher: Đã kết nối thành công với peer: {self.peer_address[0]}:{self.peer_address[1]}")
                self.send_hello()
            else:
                # Seeder mode
                self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                self.sock.bind(('0.0.0.0', self.peer_address[1]))
                self.sock.listen(5)
                print(f"Seeder: Đang lắng nghe kết nối tại 0.0.0.0:{self.peer_address[1]}")
                client_sock, address = self.sock.accept()
                self.active_socket = client_sock
                self.peer_address = address
                print(f"Seeder: Đã chấp nhận kết nối từ: {address[0]}:{address[1]}")

            # Unified communication handling
            self.handle_communication()

        except ConnectionRefusedError:
            print(f"Không thể kết nối đến peer {self.peer_address[0]}:{self.peer_address[1]}")
        except socket.error as e:
            print(f"Lỗi socket: {e}")
            print(f"Chi tiết stack trace:", traceback.format_exc())
        finally:
            self.cleanup()

    def send_hello(self):
        """Gửi tin nhắn HELLO ban đầu từ leecher"""
        hello_msg = json.dumps({"type": "HELLO"})
        print(f"Leecher: Gửi HELLO: {hello_msg}")
        self.send_message(hello_msg)

    def handle_communication(self):
        """Xử lý giao tiếp thống nhất cho cả leecher và seeder"""
        while True:
            try:
                data = self.active_socket.recv(4096)  # Tăng buffer size
                if not data:
                    print("Kết nối đã đóng")
                    break

                message = data.decode('utf-8')
                print(f"Nhận được tin nhắn: {message}")
                self.process_message(message)

            except socket.error as e:
                print(f"Lỗi khi nhận tin nhắn: {e}")
                print(f"Chi tiết stack trace:", traceback.format_exc())
                break

    def process_message(self, message):
        try:
            print(f"Bắt đầu xử lý tin nhắn: {message}")
            msg_data = json.loads(message)
            
            if msg_data['type'] == "HELLO":
                print(f"Seeder nhận HELLO từ {self.peer_address[0]}:{self.peer_address[1]}")
                response = json.dumps({"type": "HELLO_ACK"})
                print(f"Seeder gửi HELLO_ACK")
                self.send_message(response)
                
            elif msg_data['type'] == "HELLO_ACK":
                print(f"Leecher nhận HELLO_ACK từ {self.peer_address[0]}:{self.peer_address[1]}")
                # Bắt đầu yêu cầu piece đầu tiên
                self.request_piece(0)
                
            elif msg_data['type'] == "REQUEST_PIECE":
                piece_index = msg_data['piece_index']
                print(f"Seeder nhận yêu cầu piece {piece_index}")
                # Lấy dữ liệu piece từ node
                piece_data = self.node.get_piece_data(self.node.current_magnet_link, piece_index)
                if piece_data:
                    response = json.dumps({
                        "type": "PIECE_DATA",
                        "piece_index": piece_index,
                        "data": piece_data.hex()  # Convert bytes to hex string
                    })
                    self.send_message(response)
                
            elif msg_data['type'] == "PIECE_DATA":
                piece_index = msg_data['piece_index']
                piece_data = bytes.fromhex(msg_data['data'])  # Convert hex string back to bytes
                print(f"Leecher nhận được piece {piece_index}")
                
                # Lưu piece
                self.node.save_piece(piece_index, piece_data)
                
                # Yêu cầu piece tiếp theo
                next_piece = piece_index + 1
                if next_piece < self.total_pieces:
                    self.request_piece(next_piece)
                else:
                    print("Đã tải xong tất cả pieces")
                    self.node.combine_pieces()

        except json.JSONDecodeError as e:
            print(f"Lỗi khi giải mã JSON: {str(e)}")
            print(f"Tin nhắn gốc: {message}")
        except Exception as e:
            print(f"Lỗi trong process_message: {str(e)}")
            print(f"Chi tiết:", traceback.format_exc())

    def send_message(self, message):
        """Gửi tin nhắn qua socket đang active"""
        try:
            if isinstance(message, str):
                message = message.encode('utf-8')
            self.active_socket.sendall(message)
            print(f"Đã gửi tin nhắn thành công: {message}")
        except Exception as e:
            print(f"Lỗi khi gửi tin nhắn: {str(e)}")
            raise

    def request_piece(self, piece_index):
        """Gửi yêu cầu piece"""
        request = json.dumps({
            "type": "REQUEST_PIECE",
            "piece_index": piece_index
        })
        print(f"Leecher gửi yêu cầu piece {piece_index}")
        self.send_message(request)

    def cleanup(self):
        """Dọn dẹp tài nguyên"""
        if self.active_socket:
            self.active_socket.close()
        if self.sock:
            self.sock.close()
        print("Đã đóng tất cả kết nối")
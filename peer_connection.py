import socket
import threading
import json
import traceback

class PeerConnection(threading.Thread):
    def __init__(self, node, peer_address, is_initiator=True):
        threading.Thread.__init__(self)
        self.node = node
        self.peer_address = peer_address
        self.is_initiator = is_initiator
        self.sock = None
        self.running = True
        self.message_queue = []
        self.queue_lock = threading.Lock()

    def run(self):
        try:
            if self.is_initiator:  # Leecher
                self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                print(f"Leecher: Đang kết nối đến {self.peer_address[0]}:{self.peer_address[1]}")
                self.sock.connect(self.peer_address)
                print(f"Leecher: Đã kết nối thành công đến {self.peer_address[0]}:{self.peer_address[1]}")
            else:  # Seeder
                server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                server_socket.bind(('0.0.0.0', self.node.port))
                server_socket.listen(1)
                print(f"Seeder: Đang lắng nghe tại port {self.node.port}")
                
                self.sock, client_address = server_socket.accept()
                print(f"Seeder: Đã chấp nhận kết nối từ {client_address[0]}:{client_address[1]}")
                server_socket.close()

            # Khởi động thread nhận tin nhắn
            receive_thread = threading.Thread(target=self.receive_messages)
            receive_thread.daemon = True
            receive_thread.start()

            # Khởi động thread gửi tin nhắn
            send_thread = threading.Thread(target=self.process_message_queue)
            send_thread.daemon = True
            send_thread.start()

            if self.is_initiator:
                # Gửi HELLO nếu là leecher
                self.queue_message({"type": "HELLO"})

            # Giữ thread chính chạy
            while self.node.running:  # Thay vì while self.running
                if not (receive_thread.is_alive() and send_thread.is_alive()):
                    print("Một trong các thread đã dừng, kết thúc kết nối")
                    break
                threading.Event().wait(1)

        except Exception as e:
            print(f"Lỗi trong peer connection: {e}")
        finally:
            self.cleanup()

    def queue_message(self, message_dict):
        """Thêm tin nhắn vào hàng đợi để gửi"""
        with self.queue_lock:
            self.message_queue.append(message_dict)

    def process_message_queue(self):
        """Thread xử lý hàng đợi tin nhắn và gửi tin nhắn"""
        role = "Leecher" if self.is_initiator else "Seeder"
        print(f"{role}: Thread gửi tin nhắn bắt đầu")
        
        while self.running:
            try:
                # Kiểm tra và gửi tin nhắn trong hàng đợi
                with self.queue_lock:
                    if self.message_queue:
                        message_dict = self.message_queue.pop(0)
                        self.send_message(message_dict)
                
                # Tránh CPU quá tải
                threading.Event().wait(0.1)
                
            except Exception as e:
                print(f"{role}: Lỗi xử lý hàng đợi tin nhắn: {e}")
                print(traceback.format_exc())
                self.running = False
                break

        print(f"{role}: Thread gửi tin nhắn kết thúc")

    def send_message(self, message_dict):
        """Gửi tin nhắn trực tiếp qua socket"""
        try:
            message = json.dumps(message_dict)
            role = "Leecher" if self.is_initiator else "Seeder"
            print(f"{role}: Đang gửi tin nhắn: {message}")
            self.sock.sendall(message.encode('utf-8'))
            print(f"{role}: Đã gửi tin nhắn thành công")
        except Exception as e:
            print(f"Lỗi gửi tin nhắn: {e}")
            print(traceback.format_exc())
            self.running = False

    def receive_messages(self):
        """Thread nhận tin nhắn"""
        role = "Leecher" if self.is_initiator else "Seeder"
        print(f"{role}: Thread lắng nghe bắt đầu hoạt động")
        
        while self.running:
            try:
                data = self.sock.recv(1024)
                if not data:
                    print(f"{role}: Kết nối đã đóng (không có dữ liệu)")
                    self.running = False
                    break

                message = data.decode('utf-8')
                print(f"{role}: Nhận được tin nhắn: {message}")
                self.handle_message(json.loads(message))

            except Exception as e:
                print(f"{role}: Lỗi nhận tin nhắn: {e}")
                print(traceback.format_exc())
                self.running = False
                break

        print(f"{role}: Thread lắng nghe kết thúc")

    def handle_message(self, message_dict):
        try:
            message_type = message_dict.get('type')
            
            if message_type == "HELLO":
                if not self.is_initiator:  # Seeder
                    print("Seeder: Nhận được HELLO, gửi HELLO_ACK")
                    self.queue_message({"type": "HELLO_ACK"})
            
            elif message_type == "HELLO_ACK":
                if self.is_initiator:  # Leecher
                    print("Leecher: Nhận được HELLO_ACK, bắt đầu yêu cầu piece")
                    self.request_pieces()
            
            elif message_type == "REQUEST_PIECE":
                if not self.is_initiator:  # Seeder
                    piece_index = message_dict.get('piece_index')
                    magnet_link = message_dict.get('magnet_link')
                    piece_data = self.node.get_piece_data(magnet_link, piece_index)
                    if piece_data:
                        self.queue_message({
                            "type": "PIECE_DATA",
                            "piece_index": piece_index,
                            "data": piece_data.hex()
                        })
            
            elif message_type == "PIECE_DATA":
                if self.is_initiator:  # Leecher
                    piece_index = message_dict.get('piece_index')
                    piece_data = bytes.fromhex(message_dict.get('data'))
                    self.node.handle_received_piece(piece_index, piece_data)

        except Exception as e:
            print(f"Lỗi xử lý tin nhắn: {e}")
            print(traceback.format_exc())

    def request_pieces(self):
        """Yêu cầu các piece còn thiếu"""
        needed_pieces = self.node.get_needed_pieces()
        for piece_index in needed_pieces:
            self.queue_message({
                "type": "REQUEST_PIECE",
                "piece_index": piece_index,
                "magnet_link": self.node.current_magnet_link
            })

    def cleanup(self):
        """Dọn dẹp và đóng kết nối"""
        if self.sock:
            try:
                self.sock.shutdown(socket.SHUT_RDWR)
            except:
                pass
            self.sock.close()
            print("Đã đóng kết nối")
        self.running = False

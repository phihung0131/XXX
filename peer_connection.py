import socket
import threading
import json
import traceback
import base64

class PeerConnection(threading.Thread):
    def __init__(self, node, peer_address, assigned_pieces=None, is_initiator=True):
        threading.Thread.__init__(self)
        self.node = node
        self.peer_address = peer_address
        self.is_initiator = is_initiator
        self.assigned_pieces = assigned_pieces or []  # Danh sách các piece được gán
        self.sock = None
        self.running = True
        self.message_queue = []
        self.queue_lock = threading.Lock()
        self.buffer = ""
        self.MESSAGE_END = "\n"

    def run(self):
        try:
            if self.is_initiator:  # Leecher
                self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                print(f"Leecher: Đang kết nối đến {self.peer_address[0]}:{self.peer_address[1]}")
                self.sock.connect(self.peer_address)
                print(f"Leecher: Đã kết nối thành công đến {self.peer_address[0]}:{self.peer_address[1]}")
            else:  # Seeder
                while self.node.running:  # Vòng lặp cho seeder
                    try:
                        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                        server_socket.bind(('0.0.0.0', self.node.port))
                        server_socket.listen(1)
                        print(f"Seeder: Đang lắng nghe tại port {self.node.port}")
                        
                        self.sock, client_address = server_socket.accept()
                        print(f"Seeder: Đã chấp nhận kết nối từ {client_address[0]}:{client_address[1]}")
                        server_socket.close()

                        # Xử lý kết nối hiện tại
                        self.handle_connection()
                        
                        # Sau khi kết nối kết thúc, quay lại lắng nghe
                        print("Seeder: Quay lại lắng nghe kết nối mới...")
                        
                    except Exception as e:
                        print(f"Seeder: Lỗi trong vòng lặp lắng nghe: {e}")
                        threading.Event().wait(1)  # Đợi 1 giây trước khi thử lại
                        
            if self.is_initiator:  # Chỉ xử lý một lần cho leecher
                self.handle_connection()
                
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
                
                break
                
        print(f"{role}: Thread gửi tin nhắn kết thúc")

    def send_message(self, message_dict):
        """Gửi tin nhắn trực tiếp qua socket"""
        try:
            # Thêm ký tự kết thúc vào tin nhắn
            message = json.dumps(message_dict) + self.MESSAGE_END
            role = "Leecher" if self.is_initiator else "Seeder"
            
            # Tạo bản sao của message_dict để in log
            log_message = message_dict.copy()
            if 'data' in log_message:
                log_message['data'] = '<binary data>'
                
            print(f"{role}: Đang gửi tin nhắn: {json.dumps(log_message)}")
            
            self.sock.sendall(message.encode('utf-8'))
            print(f"{role}: Đã gửi tin nhắn thành công")
        except Exception as e:
            print(f"Lỗi gửi tin nhắn: {e}")
            print(traceback.format_exc())
            

    def receive_messages(self):
        """Thread nhận tin nhắn"""
        role = "Leecher" if self.is_initiator else "Seeder"
        print(f"{role}: Thread lắng nghe bắt đầu hoạt động")
        
        while self.running:
            try:
                if self.sock is None:
                    print(f"{role}: Socket is None, exiting receive loop")
                    break

                data = self.sock.recv(4096)
                if not data:
                    print(f"{role}: Kết nối đã đóng (không có dữ liệu)")
                    break

                # Thêm dữ liệu mới vào buffer
                self.buffer += data.decode('utf-8')
                
                # Xử lý từng tin nhắn trong buffer
                while self.MESSAGE_END in self.buffer:
                    message, self.buffer = self.buffer.split(self.MESSAGE_END, 1)
                    if message:
                        # Tạo bản sao của message để in log
                        message_dict = json.loads(message)
                        log_message = message_dict.copy()
                        if 'data' in log_message:
                            log_message['data'] = '<binary data>'
                        print(f"{role}: Nhận được tin nhắn: {json.dumps(log_message)}")
                        self.handle_message(message_dict)
                        
            except Exception as e:
                print(f"{role}: Lỗi nhận tin nhắn: {e}")
                print(traceback.format_exc())
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
                        # Mã hóa piece data bằng base64
                        encoded_data = base64.b64encode(piece_data).decode('utf-8')
                        self.queue_message({
                            "type": "PIECE_DATA",
                            "piece_index": piece_index,
                            "data": encoded_data
                        })
            
            elif message_type == "PIECE_DATA":
                if self.is_initiator:  # Leecher
                    piece_index = message_dict.get('piece_index')
                    # Giải mã base64 thành bytes
                    piece_data = base64.b64decode(message_dict.get('data'))
                    self.node.handle_received_piece(piece_index, piece_data)

        except Exception as e:
            print(f"Lỗi xử lý tin nhắn: {e}")
            print(traceback.format_exc())

    def request_pieces(self):
        """Chỉ yêu cầu các piece được gán cho connection này"""
        for piece_index in self.assigned_pieces:
            if piece_index in self.node.get_needed_pieces():
                self.queue_message({
                    "type": "REQUEST_PIECE",
                    "piece_index": piece_index,
                    "magnet_link": self.node.current_magnet_link
                })

    def cleanup(self):
        """Dọn dẹp và đóng kết nối an toàn"""
        if hasattr(self, 'sock') and self.sock:
            try:
                try:
                    self.sock.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass  # Bỏ qua lỗi nếu socket đã đóng
                self.sock.close()
            except Exception as e:
                print(f"Lỗi khi đóng socket: {e}")
            finally:
                self.sock = None
        
        print(f"Đã đóng kết nối với peer {self.peer_address[0]}:{self.peer_address[1]}")

    def handle_connection(self):
        """Xử lý một kết nối cụ thể"""
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

        # Giữ kết nối cho đến khi một trong các thread dừngg
        while self.running:
            if not (receive_thread.is_alive() and send_thread.is_alive()):
                print("Một trong các thread đã dừng, kết thúc kết nối")
                break
            threading.Event().wait(1)

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

    def run(self):
        try:
            if self.is_initiator:  # Leecher
                self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                print(f"Leecher: Đang kết nối đến {self.peer_address[0]}:{self.peer_address[1]}")
                self.sock.connect(self.peer_address)
                print(f"Leecher: Đã kết nối thành công đến {self.peer_address[0]}:{self.peer_address[1]}")
                
                # Gửi HELLO
                self.send_message({"type": "HELLO"})
                
            else:  # Seeder
                server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                server_socket.bind(('0.0.0.0', self.node.port))
                server_socket.listen(1)
                print(f"Seeder: Đang lắng nghe tại port {self.node.port}")
                
                self.sock, client_address = server_socket.accept()
                print(f"Seeder: Đã chấp nhận kết nối từ {client_address[0]}:{client_address[1]}")
                server_socket.close()

            # Bắt đầu thread lắng nghe tin nhắn
            receive_thread = threading.Thread(target=self.receive_messages)
            receive_thread.daemon = True
            receive_thread.start()

            # Giữ kết nối
            while self.running:
                threading.Event().wait(1)

        except Exception as e:
            print(f"Lỗi kết nối: {e}")
            print(traceback.format_exc())
        finally:
            self.cleanup()

    def send_message(self, message_dict):
        try:
            message = json.dumps(message_dict)
            self.sock.sendall(message.encode('utf-8'))
            role = "Leecher" if self.is_initiator else "Seeder"
            print(f"{role}: Đã gửi tin nhắn: {message}")
        except Exception as e:
            print(f"Lỗi gửi tin nhắn: {e}")
            self.running = False

    def receive_messages(self):
        while self.running:
            try:
                data = self.sock.recv(1024)
                if not data:
                    print("Kết nối đã đóng")
                    self.running = False
                    break

                message = data.decode('utf-8')
                role = "Leecher" if self.is_initiator else "Seeder"
                print(f"{role}: Nhận được tin nhắn: {message}")
                self.handle_message(json.loads(message))

            except Exception as e:
                print(f"Lỗi nhận tin nhắn: {e}")
                self.running = False
                break

    def handle_message(self, message_dict):
        try:
            message_type = message_dict.get('type')
            
            if message_type == "HELLO":
                if not self.is_initiator:  # Seeder
                    print("Seeder: Nhận được HELLO, gửi lại HELLO_ACK")
                    self.send_message({"type": "HELLO_ACK"})
            
            elif message_type == "HELLO_ACK":
                if self.is_initiator:  # Leecher
                    print("Leecher: Nhận được HELLO_ACK, kết nối đã được thiết lập")

        except Exception as e:
            print(f"Lỗi xử lý tin nhắn: {e}")

    def cleanup(self):
        if self.sock:
            self.sock.close()
            print("Đã đóng kết nối")
        self.running = False

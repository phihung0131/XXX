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
        self.client_sock = None
        self.running = True

    def run(self):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            if self.is_initiator:  # Leecher
                print(f"Leecher: Đang kết nối đến {self.peer_address[0]}:{self.peer_address[1]}...")
                self.sock.connect(self.peer_address)
                print(f"Leecher: Đã kết nối thành công với peer: {self.peer_address[0]}:{self.peer_address[1]}")
                
                # Tạo thread lắng nghe cho leecher
                listener_thread = threading.Thread(target=self.listen_for_messages, args=(self.sock,))
                listener_thread.daemon = True
                listener_thread.start()
                
                # Gửi HELLO
                hello_msg = json.dumps({"type": "HELLO"})
                print(f"Leecher: Gửi HELLO: {hello_msg}")
                self.sock.sendall(hello_msg.encode('utf-8'))
                
            else:  # Seeder
                self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                self.sock.bind(('0.0.0.0', self.node.port))
                self.sock.listen(5)
                print(f"Seeder: Đang lắng nghe kết nối tại 0.0.0.0:{self.node.port}")
                self.client_sock, address = self.sock.accept()
                self.peer_address = address
                print(f"Seeder: Đã chấp nhận kết nối từ: {address[0]}:{address[1]}")
                
                # Tạo thread lắng nghe cho seeder
                listener_thread = threading.Thread(target=self.listen_for_messages, args=(self.client_sock,))
                listener_thread.daemon = True
                listener_thread.start()

            # Giữ cho thread chính chạy
            while self.running:
                threading.Event().wait(1)

        except Exception as e:
            print(f"Lỗi trong run: {e}")
            print(traceback.format_exc())
        finally:
            self.cleanup()

    def listen_for_messages(self, sock):
        print(f"{'Leecher' if self.is_initiator else 'Seeder'}: Bắt đầu lắng nghe tin nhắn")
        while self.running:
            try:
                print(f"{'Leecher' if self.is_initiator else 'Seeder'}: Đang đợi tin nhắn...")
                data = sock.recv(1024)
                if not data:
                    print(f"{'Leecher' if self.is_initiator else 'Seeder'}: Kết nối đã đóng")
                    self.running = False
                    break

                message = data.decode('utf-8')
                print(f"{'Leecher' if self.is_initiator else 'Seeder'}: Nhận được tin nhắn: {message}")
                self.process_message(message)

            except socket.error as e:
                print(f"{'Leecher' if self.is_initiator else 'Seeder'}: Lỗi socket khi lắng nghe: {e}")
                print(traceback.format_exc())
                self.running = False
                break
            except Exception as e:
                print(f"{'Leecher' if self.is_initiator else 'Seeder'}: Lỗi không xác định: {e}")
                print(traceback.format_exc())
                self.running = False
                break

    def send_message(self, message):
        try:
            if self.is_initiator:
                print(f"Leecher chuẩn bị gửi: {message}")
                if self.sock:
                    self.sock.sendall(message.encode('utf-8'))
                    print("Leecher đã gửi thành công")
                else:
                    print("Leecher ERROR: sock là None")
            else:
                print(f"Seeder chuẩn bị gửi: {message}")
                if self.client_sock:
                    self.client_sock.sendall(message.encode('utf-8'))
                    print("Seeder đã gửi thành công")
                else:
                    print("Seeder ERROR: client_sock là None")
        except Exception as e:
            print(f"Lỗi khi gửi tin nhắn: {str(e)}")
            print(traceback.format_exc())

    def process_message(self, message):
        try:
            msg_data = json.loads(message)
            
            if msg_data['type'] == "HELLO":
                print(f"Seeder: Nhận HELLO từ {self.peer_address[0]}:{self.peer_address[1]}")
                try:
                    hello_ack = json.dumps({"type": "HELLO_ACK"})
                    print("Seeder: Đã tạo tin nhắn HELLO_ACK")
                    print(f"Seeder: Chuẩn bị gửi: {hello_ack}")
                    if self.client_sock:
                        print("Seeder: Sử dụng client_sock để gửi")
                        self.client_sock.sendall(hello_ack.encode('utf-8'))
                        print("Seeder: Đã gửi HELLO_ACK thành công")
                    else:
                        print("Seeder: ERROR - client_sock là None")
                except Exception as e:
                    print(f"Seeder: Lỗi khi gửi HELLO_ACK: {str(e)}")
                    print(traceback.format_exc())
                
            elif msg_data['type'] == "HELLO_ACK":
                print(f"Leecher: Nhận HELLO_ACK từ {self.peer_address[0]}:{self.peer_address[1]}")
                request = json.dumps({
                    "type": "REQUEST_PIECE",
                    "piece_index": 0
                })
                print("Leecher: Đang gửi yêu cầu piece 0...")
                self.send_message(request)
                
            elif msg_data['type'] == "REQUEST_PIECE":
                piece_index = msg_data['piece_index']
                print(f"Seeder: Nhận yêu cầu piece {piece_index}")
                piece_data = json.dumps({
                    "type": "PIECE_DATA",
                    "piece_index": piece_index,
                    "data": f"TEST_PIECE_{piece_index}"
                })
                print(f"Seeder: Đang gửi piece {piece_index}...")
                self.send_message(piece_data)
                
            elif msg_data['type'] == "PIECE_DATA":
                piece_index = msg_data['piece_index']
                print(f"Leecher: Nhận được piece {piece_index}")
                next_piece = piece_index + 1
                request = json.dumps({
                    "type": "REQUEST_PIECE",
                    "piece_index": next_piece
                })
                print(f"Leecher: Đang gửi yêu cầu piece {next_piece}...")
                self.send_message(request)

        except json.JSONDecodeError as e:
            print(f"Lỗi giải mã JSON: {str(e)}")
            print(f"Tin nhắn gốc: {message}")
        except Exception as e:
            print(f"Lỗi xử lý tin nhắn: {str(e)}")
            print(traceback.format_exc())

    def cleanup(self):
        self.running = False
        if self.client_sock:
            self.client_sock.close()
        if self.sock:
            self.sock.close()
        print("Đã đóng tất cả kết nối")

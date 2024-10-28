import socket
import threading
import json

class PeerConnection(threading.Thread):
    def __init__(self, node, peer_address):
        threading.Thread.__init__(self)
        self.node = node
        self.peer_address = peer_address
        self.sock = None

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
                self.send_message(json.dumps({"type": "HELLO_ACK"}))
            elif msg_data['type'] == "HELLO_ACK":
                print("Leecher: Kết nối đã được thiết lập")
                # Gửi yêu cầu file sau khi kết nối được thiết lập
                self.request_file_info()
            elif msg_data['type'] == "REQUEST_FILE_INFO":
                # Seeder nhận yêu cầu thông tin file
                magnet_link = msg_data.get('magnet_link')
                if magnet_link:
                    file_info = self.node.get_file_info(magnet_link)
                    self.send_message(json.dumps({
                        "type": "FILE_INFO",
                        "file_info": file_info
                    }))
            elif msg_data['type'] == "FILE_INFO":
                # Leecher nhận thông tin file
                file_info = msg_data.get('file_info')
                if file_info:
                    self.start_downloading_pieces(file_info)
            elif msg_data['type'] == "REQUEST_PIECE":
                # Seeder nhận yêu cầu piece
                piece_index = msg_data.get('piece_index')
                magnet_link = msg_data.get('magnet_link')
                if piece_index is not None and magnet_link:
                    piece_data = self.node.get_piece_data(magnet_link, piece_index)
                    if piece_data:
                        self.send_message(json.dumps({
                            "type": "PIECE_DATA",
                            "piece_index": piece_index,
                            "data": piece_data.decode('latin1')
                        }))
            elif msg_data['type'] == "PIECE_DATA":
                # Leecher nhận piece data
                piece_index = msg_data.get('piece_index')
                piece_data = msg_data.get('data')
                if piece_index is not None and piece_data:
                    self.node.save_piece(piece_index, piece_data.encode('latin1'))
                    print(f"Đã nhận và lưu piece {piece_index}")

        except json.JSONDecodeError:
            print(f"Lỗi khi xử lý tin nhắn: {message}")

    def request_file_info(self):
        # Gửi yêu cầu thông tin file với magnet link
        self.send_message(json.dumps({
            "type": "REQUEST_FILE_INFO",
            "magnet_link": self.node.current_magnet_link
        }))

    def start_downloading_pieces(self, file_info):
        # Bắt đầu tải các piece
        total_pieces = file_info.get('total_pieces', 0)
        for piece_index in range(total_pieces):
            self.send_message(json.dumps({
                "type": "REQUEST_PIECE",
                "piece_index": piece_index,
                "magnet_link": self.node.current_magnet_link
            }))

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

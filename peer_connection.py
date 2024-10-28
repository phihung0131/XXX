import socket
import threading
import json
import time

class Node:
    def __init__(self):
        self.ip = "127.0.0.1"  # hoặc socket.gethostbyname(socket.gethostname())
        self.port = 5000
        self.connections = {}  # Lưu trữ các kết nối đang hoạt động
        self.server_socket = None

    def start_listening(self):
        """Khởi động server socket để lắng nghe kết nối"""
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind((self.ip, self.port))
        self.server_socket.listen(5)
        
        # Thread riêng để lắng nghe kết nối mới
        listen_thread = threading.Thread(target=self._accept_connections)
        listen_thread.daemon = True
        listen_thread.start()

    def _accept_connections(self):
        """Xử lý các kết nối đến từ các peer khác"""
        while True:
            try:
                client_socket, address = self.server_socket.accept()
                print(f"Accepted connection from {address}")
                
                # Tạo thread mới để xử lý kết nối này
                client_thread = threading.Thread(
                    target=self._handle_client_connection,
                    args=(client_socket, address)
                )
                client_thread.daemon = True
                client_thread.start()
                
                # Lưu kết nối
                self.connections[address] = client_socket
            except Exception as e:
                print(f"Error accepting connection: {e}")
                time.sleep(1)

    def _handle_client_connection(self, client_socket, address):
        """Xử lý tin nhắn từ một client cụ thể"""
        try:
            while True:
                # Nhận dữ liệu
                data = client_socket.recv(4096)
                if not data:
                    break
                
                # Xử lý dữ liệu nhận được
                message = data.decode('utf-8')
                print(f"Received from {address}: {message}")
                
                # Xử lý yêu cầu và gửi phản hồi
                response = self._process_request(message)
                
                # Gửi phản hồi
                client_socket.send(response.encode('utf-8'))
                
        except Exception as e:
            print(f"Error handling client {address}: {e}")
        finally:
            client_socket.close()
            if address in self.connections:
                del self.connections[address]

    def _process_request(self, message):
        """Xử lý yêu cầu và tạo phản hồi"""
        try:
            request = json.loads(message)
            if request.get('type') == 'piece_request':
                # Xử lý yêu cầu piece
                piece_index = request.get('piece_index')
                # TODO: Thêm logic để lấy piece data
                return json.dumps({
                    'type': 'piece_response',
                    'piece_index': piece_index,
                    'data': f"Piece data for index {piece_index}"
                })
            else:
                return json.dumps({
                    'type': 'error',
                    'message': 'Unknown request type'
                })
        except Exception as e:
            return json.dumps({
                'type': 'error',
                'message': str(e)
            })

    def connect_and_request_piece(self, peer, piece_index):
        """Kết nối tới peer và yêu cầu piece"""
        try:
            # Tạo socket mới để kết nối
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_socket.connect((peer['ip'], peer['port']))
            
            # Gửi yêu cầu piece
            request = json.dumps({
                'type': 'piece_request',
                'piece_index': piece_index
            })
            client_socket.send(request.encode('utf-8'))
            
            # Nhận phản hồi
            response = client_socket.recv(4096).decode('utf-8')
            print(f"Received response: {response}")
            
            # Xử lý phản hồi
            response_data = json.loads(response)
            if response_data.get('type') == 'piece_response':
                # TODO: Xử lý piece data nhận được
                print(f"Got piece {piece_index}")
            else:
                print(f"Error: {response_data.get('message')}")
                
            return response_data
            
        except Exception as e:
            print(f"Error connecting to peer: {e}")
            return None
        finally:
            client_socket.close()

    def stop(self):
        """Dừng node và đóng tất cả kết nối"""
        for socket in self.connections.values():
            socket.close()
        if self.server_socket:
            self.server_socket.close()
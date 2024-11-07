import threading, socket, os, json, math, base64, hashlib, requests, bencodepy, traceback, time
from config import tracker_host

class PeerConnection(threading.Thread):
    MESSAGE_END = "\n"

    def __init__(self, node, peer_address, assigned_pieces=None, is_initiator=True):
        super().__init__()
        self.node = node
        self.peer_address = peer_address 
        self.is_initiator = is_initiator
        self.assigned_pieces = assigned_pieces or []
        self.sock = None
        self.running = True
        self.message_queue = []
        self.queue_lock = threading.Lock()
        self.buffer = ""
        self.role = "Leecher" if is_initiator else "Seeder"

    def run(self):
        try:
            self._setup_connection()
            self.handle_connection()
        except Exception as e:
            print(f"{self.role}: Connection error: {e}")
        finally:
            self.cleanup()

    def _setup_connection(self):
        if self.is_initiator:
            self._connect_as_leecher() 
        else:
            self._listen_as_seeder()

    def _connect_as_leecher(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        print(f"{self.role}: Connecting to {self.peer_address[0]}:{self.peer_address[1]}")
        self.sock.connect(self.peer_address)
        print(f"{self.role}: Connected successfully")

    def _listen_as_seeder(self):
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.settimeout(1)  # Add timeout
            self.server_socket.bind(('0.0.0.0', self.node.port))
            self.server_socket.listen(1)
            print(f"{self.role}: Listening on port {self.node.port}")
            
            while self.running:
                try:
                    self.sock, client_address = self.server_socket.accept()
                    print(f"{self.role}: Accepted connection from {client_address[0]}:{client_address[1]}")
                    break
                except socket.timeout:
                    continue
                except Exception as e:
                    print(f"{self.role}: Accept error: {e}")
                    break
            self.server_socket.close()
        except Exception as e:
            print(f"{self.role}: Listen error: {e}")
            raise

    def handle_connection(self):
        receive_thread = threading.Thread(target=self._receive_messages)
        send_thread = threading.Thread(target=self._process_message_queue)
        receive_thread.daemon = True
        send_thread.daemon = True
        
        receive_thread.start()
        send_thread.start()

        if self.is_initiator:
            self.queue_message({"type": "HELLO"})

        while self.running and receive_thread.is_alive() and send_thread.is_alive():
            threading.Event().wait(1)

    def _process_message_queue(self):
        print(f"{self.role}: Message sending thread started")
        while self.running:
            try:
                with self.queue_lock:
                    if self.message_queue:
                        message = self.message_queue.pop(0)
                        self._send_message(message)
                threading.Event().wait(0.1)
            except Exception as e:
                print(f"{self.role}: Message queue error: {e}")
                break
        print(f"{self.role}: Message sending thread ended")

    def _send_message(self, message_dict):
        try:
            message = json.dumps(message_dict) + self.MESSAGE_END
            log_message = {k: '<binary data>' if k == 'data' else v 
                         for k, v in message_dict.items()}
            print(f"{self.role}: Sending message: {json.dumps(log_message)}")
            
            self.sock.sendall(message.encode('utf-8'))
            print(f"{self.role}: Message sent successfully")
        except Exception as e:
            print(f"Message sending error: {e}")
            raise

    def _receive_messages(self):
        print(f"{self.role}: Listen thread started")
        while self.running:
            try:
                if not self.sock:
                    break

                data = self.sock.recv(4096)
                if not data:
                    break

                self.buffer += data.decode('utf-8')
                while self.MESSAGE_END in self.buffer:
                    message, self.buffer = self.buffer.split(self.MESSAGE_END, 1)
                    if message:
                        self._handle_received_message(message)

            except Exception as e:
                print(f"{self.role}: Receive error: {e}")
                break
        print(f"{self.role}: Listen thread ended")

    def _handle_received_message(self, message):
        message_dict = json.loads(message)
        log_message = {k: '<binary data>' if k == 'data' else v 
                      for k, v in message_dict.items()}
        print(f"{self.role}: Received message: {json.dumps(log_message)}")
        self._handle_message_type(message_dict)

    def _handle_message_type(self, message):
        handlers = {
            "HELLO": self._handle_hello,
            "HELLO_ACK": self._handle_hello_ack,
            "REQUEST_PIECE": self._handle_request_piece,
            "PIECE_DATA": self._handle_piece_data
        }
        handler = handlers.get(message.get('type'))
        if handler:
            handler(message)

    def _handle_hello(self, _):
        if not self.is_initiator:
            self.queue_message({"type": "HELLO_ACK"})
    
    def _handle_hello_ack(self, _):
        if self.is_initiator:
            self.request_pieces()
            
    def _handle_request_piece(self, message):
        if not self.is_initiator:
            piece_data = self.node.get_piece_data(
                message['magnet_link'], 
                message['piece_index']
            )
            if piece_data:
                self.queue_message({
                    "type": "PIECE_DATA",
                    "piece_index": message['piece_index'],
                    "data": base64.b64encode(piece_data).decode()
                })

    def _handle_piece_data(self, message):
        if self.is_initiator:
            piece_data = base64.b64decode(message['data'])
            self.node.handle_received_piece(
                message['piece_index'],
                piece_data
            )

    def request_pieces(self):
        for piece_index in self.assigned_pieces:
            if piece_index in self.node.get_needed_pieces():
                self.queue_message({
                    "type": "REQUEST_PIECE",
                    "piece_index": piece_index,
                    "magnet_link": self.node.current_magnet_link
                })

    def queue_message(self, message_dict):
        with self.queue_lock:
            self.message_queue.append(message_dict)

    def start_listening(self):
        """Start a new seeder connection to listen for incoming peers"""
        try:
            listener = PeerConnection(self, ('0.0.0.0', self.port), is_initiator=False)
            self.peer_connections.append(listener)
            listener.start()
            print(f"Started new listener on port {self.port}")
        except Exception as e:
            print(f"Error starting listener: {e}")

    def cleanup(self):
        """Clean up connection and restart listening if seeder"""
        
        # Close client socket
        if hasattr(self, 'sock') and self.sock:
            try:
                self.sock.shutdown(socket.SHUT_RDWR)
            except:
                pass
            self.sock.close()
            self.sock = None

        # Close server socket
        if hasattr(self, 'server_socket') and self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
            
        # Remove from node's peer connections
        if self in self.node.peer_connections:
            self.node.peer_connections.remove(self)

        # Restart listener if this was a seeder
        if not self.is_initiator:
            print(f"{self.role}: Restarting listening state...")
            try:
                self.node.start_listening()
            except Exception as e:
                print(f"{self.role}: Error restarting listener: {e}")

class DownloadManager(threading.Thread):
    def __init__(self, node):
        threading.Thread.__init__(self)
        self.node = node
        self.downloads = {}  # {magnet_link: download_info}
    
    def run(self):
        while self.node.running:  # Thay vì while True
            # Kiểm tra các file đang tải
            for magnet_link, download_info in list(self.downloads.items()):
                if all(download_info['pieces']):
                    self.finish_download(magnet_link, download_info)
                else:
                    self.request_next_piece(magnet_link, download_info)
            
            # Đợi một khoảng thời gian trước khi kiểm tra lại
            threading.Event().wait(5)

    def finish_download(self, magnet_link, download_info):
        """Hoàn thành quá trình tải"""
        try:
            # Ghép các piece thành file hoàn chỉnh
            self.combine_pieces(magnet_link, download_info)
            print(f"Đã tải xong file: {download_info['file_name']}")
            
            # Ngắt tất cả các kết nối đang hoạt động cho download này
            for conn in download_info['connections']:
                try:
                    conn.cleanup()
                except Exception as e:
                    print(f"Lỗi khi ngắt kết nối: {e}")
            download_info['connections'].clear()
            
            # Ngắt kết nối với tất cả peer từ node
            self.node.disconnect_all_peers()         
            
        except Exception as e:
            print(f"Lỗi khi hoàn thành tải file: {e}")
        finally:
            # Xóa thông tin download
            if magnet_link in self.downloads:
                del self.downloads[magnet_link]
                if all(download_info['pieces']):
                    self.node.start_listening()
                # Yêu cầu lại piece không hợp lệ

    def piece_completed(self, magnet_link, piece_index):
        """Xử lý khi một piece được tải xong"""
        download_info = self.downloads.get(magnet_link)
        if download_info:
            # Cập nhật trạng thái
            download_info['active_pieces'].remove(piece_index)
            download_info['completed_pieces'].add(piece_index)
            
            # Kiểm tra nếu tải xong
            if len(download_info['completed_pieces']) == len(download_info['peers_data']['pieces']):
                self.finish_download(magnet_link, download_info)
            else:
                # Tiếp tục tải các piece khác
                download_info = self.downloads[magnet_link]
                pieces_info = download_info['peers_data']['pieces']
                
                # Chọn các cặp piece-peer 
                selected_pairs = [(piece['piece_index'], piece['nodes'][0]) for piece in pieces_info if piece['nodes']]
                
                for piece_index, peer in selected_pairs:
                    if piece_index not in download_info['active_pieces']:
                        # Tạo kết nối mới và yêu cầu piece
                        peer_conn = self.node.connect_and_request_piece(peer, piece_index)
                        if peer_conn:
                            download_info['connections'].add(peer_conn)
                            download_info['active_pieces'].add(piece_index)
                            download_info['piece_sources'][piece_index] = peer

class Node:
    def __init__(self):
        # Basic node properties
        self.running = True
        self.ip = self.get_ip()
        self.port = 52229
        
        # API endpoints
        self.tracker_url = f"{tracker_host}/api/nodes"
        self.file_share_url = f"{tracker_host}/api/files"
        
        # File handling settings
        self.piece_length = 512 * 1024  # 512KB
        self.setup_directories()
        
        # State tracking
        self.current_magnet_link = None
        self.current_file_name = None
        self.peer_connections = []
        self.shared_files = {}
        self.load_shared_files()
        
        # Components
        self.download_manager = DownloadManager(self)

    def setup_directories(self):
        """Initialize required directories"""
        self.node_data_dir = "node_data"
        self.torrent_dir = os.path.join(self.node_data_dir, "torrents")
        self.pieces_dir = os.path.join(self.node_data_dir, "pieces")
        self.downloads_dir = os.path.join(self.node_data_dir, "downloads")
        self.shared_files_path = os.path.join(self.node_data_dir, "shared_files.json")
        
        for directory in [self.node_data_dir, self.torrent_dir, 
                         self.pieces_dir, self.downloads_dir]:
            os.makedirs(directory, exist_ok=True)

    def get_ip(self):
        """Get node's IP address"""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"

    def run(self):
        """Start the node"""
        self.announce_to_tracker()
        self.download_manager.start()
        threading.Thread(target=self.periodic_announce, daemon=True).start()
        self.start_listening()

    def stop(self):
        """Stop the node"""
        self.running = False
        self.disconnect_all_peers()
        time.sleep(1)  # Give time for sockets to close
        
    def share_file(self, file_path, callback=None):
        """Share a file on the network"""
        threading.Thread(target=self._share_file_thread, 
                       args=(file_path, callback)).start()
        return True

    def download_file(self, magnet_link):
        """Download a file using magnet link"""
        peers_data = self.get_peers_for_file(magnet_link)
        if peers_data:
            self.current_magnet_link = magnet_link
            self.current_file_name = peers_data['name']
            self.connect_and_request_pieces(peers_data)
            return True
        return False

    def announce_to_tracker(self):
        """Announce node to tracker"""
        try:
            response = requests.post(
                self.tracker_url,
                json={"ip": self.ip, "port": self.port},
                timeout=10
            )
            return response.json() if response.status_code == 200 else None
        except Exception as e:
            print(f"Tracker connection error: {e}")
            return None

    def periodic_announce(self):
        """Periodically announce to tracker"""
        while self.running:
            self.announce_to_tracker()
            time.sleep(300)  # 5 minutes

    def start_listening(self):
        """Start listening for peer connections"""
        listener = PeerConnection(self, ('0.0.0.0', self.port), is_initiator=False)
        self.peer_connections.append(listener)
        listener.start()

    def disconnect_all_peers(self):
        """Disconnect all peer connections"""
        for peer in self.peer_connections:
            try:
                peer.cleanup()
                self.peer_connections.remove(peer)
            except Exception as e:
                print(f"Peer disconnect error: {e}")
        self.peer_connections.clear()

    def load_shared_files(self):
        """Load shared files from JSON"""
        try:
            if os.path.exists(self.shared_files_path):
                with open(self.shared_files_path, 'r') as f:
                    self.shared_files = json.load(f)
        except Exception as e:
            print(f"Error loading shared files: {e}")
            self.shared_files = {}

    def save_shared_files(self):
        """Save shared files to JSON"""
        try:
            with open(self.shared_files_path, 'w') as f:
                json.dump(self.shared_files, f, indent=2)
        except Exception as e:
            print(f"Error saving shared files: {e}")
        """Ngắt tất cả các kết nối peer"""
        for peer_conn in list(self.peer_connections):
            try:
                peer_conn.cleanup()
                peer_conn.join(timeout=1)
                self.peer_connections.remove(peer_conn) 
            except Exception as e:
                print(f"Lỗi khi ngắt kết nối: {e}")
        self.peer_connections.clear()
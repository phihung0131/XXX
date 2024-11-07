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
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM) 
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind(('0.0.0.0', self.node.port))
        server_socket.listen(1)
        print(f"{self.role}: Listening on port {self.node.port}")
        
        self.sock, client_address = server_socket.accept()
        print(f"{self.role}: Accepted connection from {client_address[0]}:{client_address[1]}")
        server_socket.close()

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
        try:
            self.running = False
            if self.sock:
                try:
                    self.sock.shutdown(socket.SHUT_RDWR)
                except:
                    pass
                self.sock.close()
                self.sock = None

            # Restart listening if this was a seeder connection
            if not self.is_initiator:
                print(f"{self.role}: Restarting listening state...")
                try:
                    # Remove self from node's peer connections if present
                    if self in self.node.peer_connections:
                        self.node.peer_connections.remove(self)
                    # Start new listener
                    self.node.start_listening()
                except Exception as e:
                    print(f"{self.role}: Error restarting listener: {e}")
        except Exception as e:
            print(f"{self.role}: Cleanup error: {e}")

class DownloadManager(threading.Thread):
    def __init__(self, node):
        threading.Thread.__init__(self)
        self.node = node
        self.downloads = {}  # {magnet_link: download_info}
    
    def run(self):
        while self.node.running: 
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
        self.running = True
        self.ip = self.get_ip()
        self.port = 52229
        self.peers = []
        self.tracker_url = f"{tracker_host}/api/nodes"
        self.file_share_url = f"{tracker_host}/api/files"
        self.download_manager = DownloadManager(self)
        self.piece_length = 512 * 1024  # 512KB
        self.node_data_dir = "node_data"
        self.torrent_dir = os.path.join(self.node_data_dir, "torrents")
        self.pieces_dir = os.path.join(self.node_data_dir, "pieces")
        self.downloads_dir = os.path.join(self.node_data_dir, 'downloads')
        os.makedirs(self.node_data_dir, exist_ok=True)
        os.makedirs(self.torrent_dir, exist_ok=True)
        os.makedirs(self.pieces_dir, exist_ok=True)
        os.makedirs(self.downloads_dir, exist_ok=True)
        self.current_magnet_link = None
        self.current_file_name = None 
        self.shared_files = {}  # Lưu mapping giữa magnet link và thông tin file
        self.shared_files_path = os.path.join(self.node_data_dir, 'shared_files.json')
        self.load_shared_files()  # Load thông tin shared files khi khởi động
        self.peer_connections = []  # Thêm khởi tạo peer_connections

    def stop(self):
        self.running = False

    def get_ip(self):
        try:
            # Tạo một kết nối đến một địa chỉ bên ngoài (ví dụ: Google DNS)
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            # Nếu không thể kết nối, trả về địa chỉ loopback
            return "127.0.0.1"

    def run(self):
        # Thông báo lần đầu đến tracker
        initial_response = self.announce_to_tracker()
        if initial_response:
            print(f"Thông tin node: {initial_response}")

        # Bắt đầu thread để thông báo định kỳ
        announce_thread = threading.Thread(target=self.periodic_announce)
        announce_thread.daemon = True
        announce_thread.start()

        # Các chức năng khác của node
        self.download_manager.start()

    def announce_to_tracker(self):
        data = {
            "ip": self.ip,
            "port": self.port
        }
        try:
            response = requests.post(self.tracker_url, json=data, timeout=10)
            return response.json() if response.status_code == 200 else None
        except Exception as e:
            print(f"Lỗi kết nối đến tracker: {e}")
            return None

    def periodic_announce(self):
        while self.running:  # Thay vì while True
            self.announce_to_tracker()
            time.sleep(300)  # Đợi 5 phút

    def share_file(self, file_path, callback=None):
        """Chia sẻ file với mạng ngang hàng"""
        try:
            # Tạo và chạy thread xử lý chia sẻ file
            share_thread = threading.Thread(
                target=self._share_file_thread,
                args=(file_path, callback)
            )
            share_thread.start()
            return True
        except Exception as e:
            print(f"Lỗi khi khởi tạo chia sẻ file: {e}")
            return False

    def _share_file_thread(self, file_path, callback):
        try:
            # Đọc file và tính toán pieces
            file_name = os.path.basename(file_path)
            file_size = os.path.getsize(file_path)
            total_pieces = math.ceil(file_size / self.piece_length)
            pieces = b''
            
            with open(file_path, 'rb') as f:
                for i in range(total_pieces):
                    piece_data = f.read(self.piece_length)
                    piece_hash = hashlib.sha1(piece_data).digest()
                    pieces += piece_hash
                    
                    # Lưu piece
                    piece_dir = os.path.join(self.pieces_dir, file_name)
                    os.makedirs(piece_dir, exist_ok=True)
                    piece_path = os.path.join(piece_dir, f"piece_{i}")
                    with open(piece_path, 'wb') as piece_file:
                        piece_file.write(piece_data)
                    
                    if callback:
                        callback(i + 1, total_pieces)

            # Tạo thông tin torrent
            info = {
                b'name': file_name.encode(),
                b'piece length': self.piece_length,
                b'pieces': pieces,
                b'length': file_size
            }
            
            torrent = {
                b'info': info,
                b'announce': self.tracker_url.encode()
            }
            
            # Tạo và lưu file torrent
            torrent_file_name = f"{file_name}.torrent"
            torrent_path = os.path.join(self.torrent_dir, torrent_file_name)
            os.makedirs(os.path.dirname(torrent_path), exist_ok=True)
            with open(torrent_path, 'wb') as f:
                f.write(bencodepy.encode(torrent))
                
            # Tạo magnet link
            info_hash = hashlib.sha1(bencodepy.encode(info)).hexdigest()
            magnet_link = f"magnet:?xt=urn:btih:{info_hash}&dn={file_name}"
            
            # Lưu thông tin vào shared_files
            decoded_json_path = os.path.join(self.torrent_dir, f"{file_name}_decoded.json")
            file_info = {
                'file_path': file_path,
                'file_name': file_name,
                'torrent_path': torrent_path,
                'decoded_json_path': decoded_json_path,
                'magnet_link': magnet_link
            }
            self.shared_files[magnet_link] = file_info
            self.save_shared_files()
            
            # Gửi thông tin lên tracker
            with open(torrent_path, 'rb') as torrent_file:
                files = {'torrent_file': torrent_file}
                data = {
                    'magnet_text': magnet_link,
                    'name': file_name,
                    'ip': self.ip,
                    'port': str(self.port)
                }
                response = requests.post(self.file_share_url, files=files, data=data)
            
            if response.status_code == 200:
                print(f"File {file_name} đã được chia sẻ thành công")
                print(f"Tổng số piece: {total_pieces}")
            else:
                print(f"Lỗi khi chia sẻ file: {response.status_code}")
            
            if callback:
                callback(total_pieces, total_pieces, magnet_link, torrent_path)
                
        except Exception as e:
            print(f"Lỗi khi chia sẻ file: {str(e)}")
            traceback.print_exc()
            if callback:
                callback(0, 0, None, None)

    def get_peers_for_file(self, magnet_link):
        data = {
            "magnet_text": magnet_link
        }
        try:
            url = f"{self.file_share_url}/peers" 
            response = requests.post(url, json=data)
            if response.status_code == 200:
                data = response.json()
                print(f"API Response: {data}")  # Debug log
                
                # Giải mã và lưu file torrent
                if 'torrentFile' in data:
                    torrent_data = base64.b64decode(data['torrentFile'])
                    
                    # Lưu file torrent gốc
                    torrent_file_name = f"{data['name']}.torrent"
                    torrent_path = os.path.join(self.torrent_dir, torrent_file_name)
                    with open(torrent_path, 'wb') as f:
                        f.write(torrent_data)
                    print(f"Đã lưu file torrent: {torrent_path}")

                    # Giải mã torrent và lưu JSON
                    decoded_torrent = bencodepy.decode(torrent_data)
                    info = decoded_torrent[b'info']
                    pieces = info[b'pieces']
                    piece_hashes = [pieces[i:i+20].hex() for i in range(0, len(pieces), 20)]
                    
                    decoded_info = {
                        'name': info[b'name'].decode('utf-8'),
                        'piece length': info[b'piece length'],
                        'pieces': piece_hashes,
                        'length': info[b'length']
                    }
                    
                    # Lưu file decoded JSON
                    decoded_json_path = os.path.join(self.torrent_dir, f"{data['name']}_decoded.json")
                    with open(decoded_json_path, 'w', encoding='utf-8') as f:
                        json.dump(decoded_info, f, indent=2)
                    print(f"Đã lưu file decoded JSON: {decoded_json_path}")

                return {
                    'name': data['name'],
                    'pieces': data.get('pieces', []),
                    'decoded_torrent': decoded_info
                }
        except Exception as e:
            print(f"Lỗi khi lấy thông tin peers: {e}")
            print(traceback.format_exc())
        return None

    def start_listening(self):
        listener = PeerConnection(self, ('0.0.0.0', self.port), is_initiator=False)
        listener.start()

    def connect_and_request_pieces(self, peers_data):
        """Tạo nhiều kết nối và phân phối pieces"""
        needed_pieces = self.get_needed_pieces()
        if not needed_pieces:
            return

        # Tạo mapping piece -> nodes có sẵn
        piece_to_nodes = {}
        for piece in peers_data['pieces']:
            piece_index = piece['piece_index']
            if piece_index in needed_pieces:
                piece_to_nodes[piece_index] = piece['nodes']

        # Chọn tối đa 3 node khác nhau
        selected_nodes = set()
        piece_assignments = {}  # {node_address: [piece_indexes]}
        
        for piece_index in needed_pieces:
            if len(selected_nodes) >= 3:  # Giới hạn 3 kết nối
                break
                
            available_nodes = piece_to_nodes.get(piece_index, [])
            for node in available_nodes:
                node_addr = (node['ip'], node['port'])
                if node_addr not in selected_nodes:
                    selected_nodes.add(node_addr)
                    piece_assignments[node_addr] = []
                    break

        # Phân phối pieces cho các node đã chọn
        current_node_index = 0
        selected_node_list = list(selected_nodes)
        
        for piece_index in needed_pieces:
            if not selected_node_list:
                break
                
            node_addr = selected_node_list[current_node_index]
            piece_assignments[node_addr].append(piece_index)
            current_node_index = (current_node_index + 1) % len(selected_node_list)

        # Tạo và khởi động các connection
        for node_addr, assigned_pieces in piece_assignments.items():
            peer_conn = PeerConnection(
                self,
                node_addr,
                assigned_pieces=assigned_pieces,
                is_initiator=True
            )
            self.peer_connections.append(peer_conn)
            peer_conn.start()

    def get_torrent_info(self, magnet_link):
        """Lấy thông tin torrent từ magnet link"""
        try:
            # Kiểm tra trong shared files
            if magnet_link in self.shared_files:
                file_info = self.shared_files[magnet_link]
                decoded_json_path = file_info['decoded_json_path']
                
                # Nếu file decoded JSON không tồn tại, tạo lại từ file torrent
                if not os.path.exists(decoded_json_path):
                    torrent_path = file_info['torrent_path']
                    if os.path.exists(torrent_path):
                        with open(torrent_path, 'rb') as f:
                            torrent_data = bencodepy.decode(f.read())
                            info = torrent_data[b'info']
                            pieces = info[b'pieces']
                            piece_hashes = [pieces[i:i+20].hex() for i in range(0, len(pieces), 20)]
                            
                            decoded_info = {
                                'name': info[b'name'].decode('utf-8'),
                                'piece length': info[b'piece length'],
                                'pieces': piece_hashes,
                                'length': info[b'length']
                            }
                            
                            # Lưu file decoded JSON
                            with open(decoded_json_path, 'w', encoding='utf-8') as f:
                                json.dump(decoded_info, f, indent=2)
                            return decoded_info
                else:
                    # Đọc từ file decoded JSON nếu tồn tại
                    with open(decoded_json_path, 'r', encoding='utf-8') as f:
                        return json.load(f)
                        
            print(f"Không tìm thấy thông tin torrent cho magnet link: {magnet_link}")
            print(f"Danh sách shared files: {self.shared_files}")
            return None
        except Exception as e:
            print(f"Lỗi khi lấy thông tin torrent: {str(e)}")
            print(traceback.format_exc())
            return None

    def get_piece_data(self, magnet_link, piece_index):
        """Lấy dữ liệu của piece từ file đã được chia sẻ"""
        try:
            file_info = self.get_torrent_info(magnet_link)
            if file_info:
                file_name = file_info['name']
                piece_path = os.path.join(self.pieces_dir, file_name, f"piece_{piece_index}")
                if os.path.exists(piece_path):
                    with open(piece_path, 'rb') as f:
                        piece_data = f.read()
                        print(f"Đọc piece {piece_index}, kích thước: {len(piece_data)} bytes")
                        return piece_data
                else:
                    print(f"Không tìm thấy piece {piece_index} tại {piece_path}")
            return None
        except Exception as e:
            print(f"Lỗi khi lấy dữ liệu piece: {str(e)}")
            return None

    def get_piece_hash(self, piece_index):
        # Lấy hash của piece từ file torrent đã giải mã
        torrent_info = self.get_decoded_torrent_info()
        if torrent_info and 'pieces' in torrent_info:
            return torrent_info['pieces'][piece_index]
        return None

    def get_decoded_torrent_info(self):
        try:
            decoded_path = os.path.join(self.torrent_dir, f"{self.current_file_name}_decoded.json")
            if os.path.exists(decoded_path):
                with open(decoded_path, 'r') as f:
                    torrent_info = json.load(f)
                    if 'pieces' not in torrent_info:
                        print("Lỗi: Không tìm thấy thông tin pieces trong file torrent đã giải mã")
                        return None
                    return torrent_info
            else:
                print(f"Lỗi: Không tìm thấy file {decoded_path}")
                return None
        except Exception as e:
            print(f"Lỗi khi đọc thông tin torrent: {str(e)}")
            return None

    def save_piece(self, piece_index, piece_data):
        piece_dir = os.path.join(self.pieces_dir, self.current_file_name)
        os.makedirs(piece_dir, exist_ok=True)
        piece_path = os.path.join(piece_dir, f"piece_{piece_index}")
        with open(piece_path, 'wb') as f:
            f.write(piece_data)
        print(f"Đã lưu piece {piece_index} vào {piece_path}")

    def announce_all_pieces_to_tracker(self, torrent_info):
        """Thông báo tất cả piece cho tracker sau khi tải xong"""
        try:
            tracker_piece_url = f"{tracker_host}/api/pieces"
            total_pieces = len(torrent_info['pieces'])
            
            for piece_index in range(total_pieces):
                piece_data = {
                    "magnet_text": self.current_magnet_link,
                    "piece_index": str(piece_index),
                    "ip": self.ip,
                    "port": str(self.port)
                }
                try:
                    response = requests.put(tracker_piece_url, json=piece_data)
                    if response.status_code != 200:
                        print(f"Lỗi khi thông báo piece {piece_index} cho tracker: {response.status_code}")
                except Exception as e:
                    print(f"Lỗi khi gửi thông báo piece {piece_index}: {e}")
                    continue
            print("Đã thông báo tất cả piece cho tracker")
        except Exception as e:
            print(f"Lỗi khi thông báo pieces cho tracker: {e}")

    def combine_pieces(self):
        """Ghép các piece thành file hoàn chỉnh"""
        piece_dir = os.path.join(self.pieces_dir, self.current_file_name)
        output_path = os.path.join(self.downloads_dir, self.current_file_name)
        
        with open(output_path, 'wb') as outfile:
            piece_index = 0
            while True:
                piece_path = os.path.join(piece_dir, f"piece_{piece_index}")
                if not os.path.exists(piece_path):
                    break
                
                with open(piece_path, 'rb') as piece_file:
                    outfile.write(piece_file.read())
                piece_index += 1
            
        print(f"Đã ghép file thành công: {output_path}")
        
        # Lưu thông tin vào shared_files
        torrent_info = self.get_decoded_torrent_info()
        if torrent_info and self.current_magnet_link:
            file_info = {
                'file_path': output_path,
                'file_name': self.current_file_name,
                'torrent_path': os.path.join(self.torrent_dir, f"{self.current_file_name}.torrent"),
                'decoded_json_path': os.path.join(self.torrent_dir, f"{self.current_file_name}_decoded.json"),
                'magnet_link': self.current_magnet_link
            }
            self.shared_files[self.current_magnet_link] = file_info
            self.save_shared_files()
            
            # Thông báo tất cả piece cho tracker
            self.announce_all_pieces_to_tracker(torrent_info)

    def handle_received_piece(self, piece_index, piece_data):
        """Xử lý piece nhận được từ peer"""
        piece_hash = self.get_piece_hash(piece_index)
        received_hash = hashlib.sha1(piece_data).hexdigest()
        
        if piece_hash == received_hash:
            self.save_piece(piece_index, piece_data)
            self.download_manager.piece_completed(self.current_magnet_link, piece_index)
            
            # Kiểm tra nếu đã tải xong
            self.finish_download()
        else:
            print(f"Piece {piece_index} không hợp lệ")
            self.download_manager.piece_failed(self.current_magnet_link, piece_index)

    def get_needed_pieces(self):
        """Lấy danh sách các piece còn thiếu"""
        piece_dir = os.path.join(self.pieces_dir, self.current_file_name)
        if not os.path.exists(piece_dir):
            os.makedirs(piece_dir)
        
        torrent_info = self.get_decoded_torrent_info()
        if not torrent_info:
            print("Không thể lấy thông tin torrent đã giải mã")
            return []
        
        total_pieces = len(torrent_info['pieces'])
        existing_pieces = set(int(f.split('_')[1]) for f in os.listdir(piece_dir) 
                         if f.startswith('piece_'))
    
        return [i for i in range(total_pieces) if i not in existing_pieces]

    def load_shared_files(self):
        """Load thông tin shared files từ file JSON"""
        try:
            if os.path.exists(self.shared_files_path):
                with open(self.shared_files_path, 'r') as f:
                    self.shared_files = json.load(f)
        except Exception as e:
            print(f"Lỗi khi load shared files: {e}")
            self.shared_files = {}

    def save_shared_files(self):
        """Lưu thông tin shared files vào file JSON"""
        try:
            with open(self.shared_files_path, 'w') as f:
                json.dump(self.shared_files, f, indent=2)
        except Exception as e:
            print(f"Lỗi khi lưu shared files: {e}")

    def finish_download(self):
        """Kiểm tra xem đã tải đủ các piece chưa"""
        piece_dir = os.path.join(self.pieces_dir, self.current_file_name)
        if not os.path.exists(piece_dir):
            return False
            
        torrent_info = self.get_decoded_torrent_info()
        total_pieces = len(torrent_info['pieces'])
        
        existing_pieces = [f for f in os.listdir(piece_dir) if f.startswith('piece_')]

        """Xử lý khi tải file hoàn tất"""
        if len(existing_pieces) == total_pieces:
            try:
                # Ghép các piece thành file hoàn chỉnh
                self.combine_pieces()
                
                # Ngắt kết nối với tất cả peer
                for peer_conn in self.peer_connections:
                    peer_conn.cleanup()
                    
                
                print(f"Đã tải xong file: {self.current_file_name}")
                
                # Cập nhật trạng thái
                self.current_file_name = None
                self.current_magnet_link = None
                self.peer_connections = []
                
            except Exception as e:
                print(f"Lỗi khi hoàn thành tải file: {e}")

    def disconnect_all_peers(self):
        """Ngắt tất cả các kết nối peer"""
        for peer_conn in list(self.peer_connections):
            try:
                peer_conn.cleanup()
                peer_conn.join(timeout=1)
                self.peer_connections.remove(peer_conn) 
            except Exception as e:
                print(f"Lỗi khi ngắt kết nối: {e}")
        self.peer_connections.clear()
import threading
import socket
import bencodepy
import hashlib
import random
import time
import requests
import os
import json
import math
import tempfile
from peer_connection import PeerConnection
from download_manager import DownloadManager
from upload_manager import UploadManager
from config import tracker_host

class Node:
    def __init__(self):
        self.config_file = 'node_config.json'
        self.load_or_create_config()
        self.peers = []
        self.files = {}
        self.pieces = {}
        self.downloading = {}
        self.uploading = {}
        self.tracker_url = f"{tracker_host}/api/nodes"
        self.file_share_url = f"{tracker_host}/api/files"
        self.download_manager = DownloadManager(self)
        self.upload_manager = UploadManager(self)
        self.piece_length = 512 * 1024  # 512KB
        self.node_data_dir = "node_data"
        self.torrent_dir = os.path.join(self.node_data_dir, "torrents")
        self.pieces_dir = os.path.join(self.node_data_dir, "pieces")
        os.makedirs(self.node_data_dir, exist_ok=True)
        os.makedirs(self.torrent_dir, exist_ok=True)
        os.makedirs(self.pieces_dir, exist_ok=True)

    def load_or_create_config(self):
        if os.path.exists(self.config_file):
            with open(self.config_file, 'r') as f:
                config = json.load(f)
            self.ip = config['ip']
            self.port = config['port']
        else:
            self.ip = self.get_ip()
            self.port = self.get_available_port()
            with open(self.config_file, 'w') as f:
                json.dump({'ip': self.ip, 'port': self.port}, f)

    def get_ip(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip

    def get_available_port(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(('', 0))
        port = sock.getsockname()[1]
        sock.close()
        return port

    def parse_magnet(self, magnet_text):
        # Xử lý magnet text
        pass

    def parse_metainfo(self, metainfo_file):
        # Đọc và phân tích metainfo file
        pass

    def connect_to_tracker(self):
        # Kết nối với tracker
        pass

    def announce_files(self):
        # Thông báo files cho tracker
        pass

    def request_file(self, file_hash):
        # Yêu cầu file từ tracker
        pass

    def connect_to_peers(self):
        for peer_data in self.peers:
            peer_ip = peer_data['ip']
            peer_port = peer_data['port']
            print(f"Đang kết nối với peer: {peer_ip}:{peer_port}")
            PeerConnection(self, (peer_ip, peer_port)).start()

    def download_piece(self, piece_index, peer):
        # Tải một piece từ peer
        pass

    def upload_piece(self, piece_index, peer):
        # Upload một piece cho peer
        pass

    def run(self):
        print(f"Node đang chạy trên IP: {self.ip}, Port: {self.port}")
        # Thông báo lần đầu đến tracker
        initial_response = self.announce_to_tracker()
        if initial_response:
            print(f"Thông tin node: {initial_response}")

        # Bắt đầu thread để thông báo định kỳ
        announce_thread = threading.Thread(target=self.periodic_announce)
        announce_thread.daemon = True
        announce_thread.start()

        # Các chức năng khác của node
        self.connect_to_peers()
        self.download_manager.start()
        self.upload_manager.start()

    def announce_to_tracker(self):
        data = {
            "ip": self.ip,
            "port": self.port
        }
        try:
            print(f"Đang kết nối đến tracker: {self.tracker_url}")
            response = requests.post(self.tracker_url, json=data, timeout=10)
            print(f"Phản hồi từ tracker: Status code {response.status_code}")
            if response.status_code == 200:
                print("Đã thông báo thành công đến tracker")
                return response.json()
            else:
                print(f"Lỗi khi thông báo đến tracker: {response.status_code}")
                print(f"Nội dung phản hồi: {response.text}")
        except requests.RequestException as e:
            print(f"Lỗi kết nối đến tracker: {e}")
            print(f"Chi tiết lỗi: {str(e)}")

    def periodic_announce(self):
        while True:
            self.announce_to_tracker()
            time.sleep(120)  # Đợi 2 phút

    def share_file(self, file_path, callback=None):
        thread = threading.Thread(target=self._share_file_thread, args=(file_path, callback))
        thread.start()

    def _share_file_thread(self, file_path, callback):
        try:
            file_name = os.path.basename(file_path)
            file_size = os.path.getsize(file_path)
            pieces = b''
            
            total_pieces = math.ceil(file_size / self.piece_length)
            
            with open(file_path, 'rb') as f:
                for piece_index in range(total_pieces):
                    piece = f.read(self.piece_length)
                    piece_hash = hashlib.sha1(piece).digest()
                    pieces += piece_hash
                    
                    # Lưu piece vào thư mục lưu trữ
                    piece_dir = os.path.join(self.pieces_dir, file_name)
                    os.makedirs(piece_dir, exist_ok=True)
                    with open(os.path.join(piece_dir, f"{piece_index}_{piece_hash.hex()}"), 'wb') as piece_file:
                        piece_file.write(piece)

                    if callback:
                        callback(piece_index + 1, total_pieces)

            info = {
                'name': file_name,
                'piece length': self.piece_length,
                'pieces': pieces,
                'length': file_size
            }
            
            torrent = {
                'info': info,
                'announce': self.tracker_url
            }
            
            # Tạo file torrent
            torrent_file_name = f"{file_name}.torrent"
            torrent_path = os.path.abspath(os.path.join(self.torrent_dir, torrent_file_name))
            print(f"Đang tạo file torrent tại: {torrent_path}")
            print(f"Thư mục torrent tồn tại: {os.path.exists(os.path.dirname(torrent_path))}")
            os.makedirs(os.path.dirname(torrent_path), exist_ok=True)
            with open(torrent_path, 'wb') as f:
                f.write(bencodepy.encode(torrent))
            
            # In ra nội dung file torrent
            self.print_torrent_content(torrent_path)
            
            # Tạo magnet link
            info_hash = hashlib.sha1(bencodepy.encode(info)).hexdigest()
            magnet_link = f"magnet:?xt=urn:btih:{info_hash}&dn={file_name}"
            
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
            import traceback
            traceback.print_exc()
            if callback:
                callback(0, 0, None, None)

    def print_torrent_content(self, torrent_path):
        with open(torrent_path, 'rb') as f:
            torrent_data = bencodepy.decode(f.read())
        
        print("Nội dung file torrent:")
        print(f"Announce: {torrent_data[b'announce'].decode()}")
        print("Info:")
        info = torrent_data[b'info']
        print(f"  Name: {info[b'name'].decode()}")
        print(f"  Piece Length: {info[b'piece length']}")
        print(f"  Length: {info[b'length']}")
        print(f"  Pieces: {len(info[b'pieces'])} bytes")
        print(f"  Number of Pieces: {len(info[b'pieces']) // 20}")  # Mỗi piece hash là 20 bytes

    def get_peers_for_file(self, magnet_link):
        data = {
            "magnet_text": magnet_link
        }
        try:
            url = f"{self.file_share_url}/peers"
            response = requests.post(url, json=data)
            if response.status_code == 200:
                peers_data = response.json()
                return peers_data
            else:
                return None
        except requests.RequestException:
            return None

    def decode_torrent_file(self, torrent_path):
        with open(torrent_path, 'rb') as f:
            torrent_data = bencodepy.decode(f.read())
        
        # Tạo thư mục temp
        temp_dir = tempfile.mkdtemp(prefix="torrent_decoded_")
        
        # Xử lý đặc biệt cho trường 'pieces'
        if b'info' in torrent_data and b'pieces' in torrent_data[b'info']:
            pieces = torrent_data[b'info'][b'pieces']
            piece_hashes = [pieces[i:i+20].hex() for i in range(0, len(pieces), 20)]
            torrent_data[b'info'][b'pieces'] = piece_hashes

        # Xuất nội dung torrent đã giải mã
        decoded_path = os.path.join(temp_dir, "decoded_torrent.json")
        with open(decoded_path, 'w', encoding='utf-8') as f:
            json.dump(self.decode_bytes_in_dict(torrent_data), f, indent=2)
        
        print(f"Nội dung torrent đã được giải mã và lưu tại: {decoded_path}")
        
        # Lấy và xuất danh sách hash piece
        piece_hashes_path = os.path.join(temp_dir, "piece_hashes.json")
        with open(piece_hashes_path, 'w') as f:
            json.dump(piece_hashes, f, indent=2)
        
        print(f"Danh sách hash piece đã được lưu tại: {piece_hashes_path}")
        
        return temp_dir, piece_hashes

    def decode_bytes_in_dict(self, d):
        decoded = {}
        for key, value in d.items():
            if isinstance(key, bytes):
                key = key.decode('utf-8')
            if isinstance(value, bytes):
                value = value.decode('utf-8', errors='replace')
            elif isinstance(value, dict):
                value = self.decode_bytes_in_dict(value)
            elif isinstance(value, list):
                value = [self.decode_bytes_in_dict(item) if isinstance(item, dict) else item for item in value]
            decoded[key] = value
        return decoded

    # Phương thức để sử dụng chức năng này
    def analyze_torrent(self, torrent_file_name):
        torrent_path = os.path.join(self.torrent_dir, torrent_file_name)
        if os.path.exists(torrent_path):
            temp_dir, piece_hashes = self.decode_torrent_file(torrent_path)
            print(f"Số lượng piece: {len(piece_hashes)}")
            return temp_dir, piece_hashes
        else:
            print(f"Không tìm thấy file torrent: {torrent_path}")
            return None, None

    def connect_to_peer(self, peer_ip, peer_port):
        peer_connection = PeerConnection(self, (peer_ip, peer_port))
        peer_connection.start()
        return peer_connection

    def start_listening(self):
        listener = PeerConnection(self, (self.ip, self.port))
        listener.start()

class PeerConnection(threading.Thread):
    def __init__(self, node, peer_address):
        threading.Thread.__init__(self)
        self.node = node
        self.peer_address = peer_address

    def run(self):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect(self.peer_address)
            print(f"Đã kết nối thành công với peer: {self.peer_address[0]}:{self.peer_address[1]}")
            # Thêm logic xử lý kết nối ở đây
        except Exception as e:
            print(f"Không thể kết nối với peer {self.peer_address[0]}:{self.peer_address[1]}: {str(e)}")
        finally:
            sock.close()

class DownloadManager(threading.Thread):
    def __init__(self, node):
        threading.Thread.__init__(self)
        self.node = node

    def run(self):
        # Quản lý quá trình tải
        pass

class UploadManager(threading.Thread):
    def __init__(self, node):
        threading.Thread.__init__(self)
        self.node = node

    def run(self):
        # Quản lý quá trình upload
        pass

class UserInterface:
    def __init__(self, node):
        self.node = node

    def display_stats(self):
        # Hiển thị thống kê
        pass

    def display_peers(self):
        # Hiển thị thông tin về peers
        pass

    def display_progress(self):
        # Hiển thị tiến độ tải/chia sẻ
        pass

    def run(self):
        # Chạy giao diện người dùng
        pass










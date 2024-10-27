import threading
import socket
import bencodepy
import hashlib
import random
import time
import requests
import os
import json
from peer_connection import PeerConnection
from download_manager import DownloadManager
from upload_manager import UploadManager

class Node:
    def __init__(self):
        self.ip = self.get_container_ip()
        self.port = self.get_available_port()
        self.peers = []
        self.files = {}
        self.pieces = {}
        self.downloading = {}
        self.uploading = {}
        self.tracker_url = "http://btl-mmt-tracker.onrender.com/api/nodes"
        self.file_share_url = "http://btl-mmt-tracker.onrender.com/api/files"
        self.download_manager = DownloadManager(self)
        self.upload_manager = UploadManager(self)
        self.piece_length = 512 * 1024  # 512KB
        self.node_id = os.environ.get('NODE_ID', '0')
        self.node_data_dir = f"/app/node_data"
        self.torrent_dir = os.path.join(self.node_data_dir, "torrents")
        os.makedirs(self.torrent_dir, exist_ok=True)

    def get_container_ip(self):
        return socket.gethostbyname(socket.gethostname())

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

    def share_file(self, file_path):
        file_name = os.path.basename(file_path)
        file_size = os.path.getsize(file_path)
        pieces = []
        
        with open(file_path, 'rb') as f:
            while True:
                piece = f.read(self.piece_length)
                if not piece:
                    break
                piece_hash = hashlib.sha1(piece).hexdigest()
                pieces.append(piece_hash)
                
                # Lưu piece vào thư mục lưu trữ
                piece_dir = os.path.join('pieces', file_name)
                os.makedirs(piece_dir, exist_ok=True)
                with open(os.path.join(piece_dir, piece_hash), 'wb') as piece_file:
                    piece_file.write(piece)

        info = {
            'name': file_name,
            'piece length': self.piece_length,
            'pieces': ''.join(pieces),
            'length': file_size
        }
        
        torrent = {
            'info': info,
            'announce': self.tracker_url
        }
        
        # Tạo file torrent
        torrent_file_name = f"{file_name}.torrent"
        torrent_path = os.path.join(self.torrent_dir, torrent_file_name)
        with open(torrent_path, 'wb') as f:
            f.write(bencodepy.encode(torrent))
        
        # Tạo magnet link
        info_hash = hashlib.sha1(bencodepy.encode(info)).hexdigest()
        magnet_link = f"magnet:?xt=urn:btih:{info_hash}&dn={file_name}"
        
        # Gửi thông tin lên tracker
        with open(torrent_path, 'rb') as torrent_file:
            files = {'torrent_file': torrent_file}
            data = {
                'magnet_text': magnet_link, 
                'name': file_name,
                'ip': self.ip,  # Thêm IP
                'port': str(self.port)  # Thêm port (chuyển thành string)
            }
            response = requests.post(self.file_share_url, files=files, data=data)
        
        if response.status_code == 200:
            print(f"File {file_name} đã được chia sẻ thành công")
        else:
            print(f"Lỗi khi chia sẻ file: {response.status_code}")
        
        return magnet_link, torrent_path

    def get_peers_for_file(self, magnet_link):
        data = {
            "magnet_text": magnet_link
        }
        try:
            response = requests.post("http://btl-mmt-tracker.onrender.com/api/files/peers", json=data)
            if response.status_code == 200:
                peers_data = response.json()
                self.save_peers_data(peers_data)
                return peers_data
            else:
                print(f"Lỗi khi lấy danh sách peer: {response.status_code}")
                return None
        except requests.RequestException as e:
            print(f"Lỗi kết nối đến tracker: {e}")
            return None

    def save_peers_data(self, peers_data):
        with open(os.path.join(self.node_data_dir, 'peers_data.json'), 'w') as f:
            json.dump(peers_data, f)
        print("Đã lưu danh sách peer vào file peers_data.json")

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


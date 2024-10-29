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
from config import tracker_host
import base64

class Node:
    def __init__(self):
        # Thêm vào đầu __init__
        self.running = True
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
        self.current_file_name = None  # Thêm dòng này
        self.shared_files = {}  # Lưu mapping giữa magnet link và thông tin file
        self.shared_files_path = os.path.join(self.node_data_dir, 'shared_files.json')
        self.load_shared_files()  # Load thông tin shared files khi khởi động
        self.peer_connections = []  # Thêm khởi tạo peer_connections

    def stop(self):
        self.running = False

    def load_or_create_config(self):
        if os.path.exists(self.config_file):
            with open(self.config_file, 'r') as f:
                config = json.load(f)
            # Luôn cập nhật IP và sử dụng port 52229
            self.ip = self.get_ip()
            self.port = 52229
        else:
            self.ip = self.get_ip()
            self.port = 52229
        
        # Lưu cấu hnh
        with open(self.config_file, 'w') as f:
            json.dump({'ip': self.ip, 'port': self.port}, f)

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
        print("======================VVVVVVVVV=========================")
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

    def announce_to_tracker(self):
        data = {
            "ip": self.ip,
            "port": self.port
        }
        try:
            # print(f"Đang kết nối đến tracker: {self.tracker_url}")
            response = requests.post(self.tracker_url, json=data, timeout=10)
            # print(f"Phản hồi từ tracker: Status code {response.status_code}")
            if response.status_code == 200:
                # print("Đã thông báo thành công đến tracker")
                return response.json()
            else:
                print(f"Lỗi khi thông báo đến tracker: {response.status_code}")
                print(f"Nội dung phản hồi: {response.text}")
        except requests.RequestException as e:
            print(f"Lỗi kết nối đến tracker: {e}")
            print(f"Chi tiết lỗi: {str(e)}")

    def periodic_announce(self):
        while self.running:  # Thay vì while True
            self.announce_to_tracker()
            time.sleep(120)  # Đợi 2 phút

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
            url = f"{self.file_share_url}/peers"  # Đảm bảo endpoint đúng
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
        peer_connection = PeerConnection(self, (peer_ip, peer_port))  # Bỏ tham số is_initiator
        peer_connection.start()
        return peer_connection

    def start_listening(self):
        listener = PeerConnection(self, ('0.0.0.0', self.port), is_initiator=False)
        listener.start()

    def find_peer_with_piece(self, peers_data, piece_index):
        """Tìm peer có piece cần thiết"""
        try:
            if isinstance(peers_data, dict) and 'pieces' in peers_data:
                pieces = peers_data['pieces']
                print(f"Tìm kiếm piece {piece_index} trong danh sách: {pieces}")  # Debug log
                
                # Tìm piece theo index
                for piece in pieces:
                    if piece.get('piece_index') == piece_index:
                        nodes = piece.get('nodes', [])
                        if nodes:
                            print(f"Tìm thấy peer cho piece {piece_index}: {nodes[0]}")
                            return nodes[0]
                
                print(f"Không tìm thấy peer nào có piece {piece_index}")
                print(f"Cấu trúc pieces: {pieces}")
            else:
                print("Dữ liệu peers không đúng định dạng")
                print(f"Peers data: {peers_data}")
        except Exception as e:
            print(f"Lỗi khi tìm peer: {e}")
            print(f"Peers data: {peers_data}")
            print(f"Chi tiết lỗi: {traceback.format_exc()}")
        return None

    def connect_and_request_piece(self, peer, piece_index):
        try:
            peer_conn = PeerConnection(self, (peer['ip'], peer['port']))
            peer_conn.start()
            
            # Gửi yêu cầu piece
            peer_conn.queue_message({
                "type": "REQUEST_PIECE",
                "piece_index": piece_index,
                "magnet_link": self.current_magnet_link
            })
            
            return peer_conn
        except Exception as e:
            print(f"Lỗi khi kết nối đến peer {peer['ip']}:{peer['port']}: {e}")
            return None

    def process_magnet_response(self, response_data):
        if isinstance(response_data, dict):
            if 'torrentFile' in response_data and 'torrentFileSize' in response_data:
                try:
                    # Giải mã base64
                    torrent_data = base64.b64decode(response_data['torrentFile'])
                    
                    # Kiểm tra kích thước
                    if len(torrent_data) == response_data['torrentFileSize']:
                        # Lưu file torrent
                        torrent_file_name = f"{response_data['name']}.torrent"
                        torrent_path = os.path.join(self.torrent_dir, torrent_file_name)
                        with open(torrent_path, 'wb') as f:
                            f.write(torrent_data)
                        print(f"Đã lưu file torrent: {torrent_path}")

                        # Giải mã torrent
                        decoded_torrent = bencodepy.decode(torrent_data)
                        info = decoded_torrent[b'info']
                        
                        # Xử lý pieces
                        pieces = info[b'pieces']
                        piece_hashes = [pieces[i:i+20].hex() for i in range(0, len(pieces), 20)]
                        
                        # Tạo thông tin torrent đã giải mã
                        decoded_info = {
                            'name': info[b'name'].decode('utf-8'),
                            'piece length': info[b'piece length'],
                            'pieces': piece_hashes,
                            'length': info[b'length']
                        }
                        
                        # Lưu thông tin đã giải mã
                        decoded_json_path = os.path.join(self.torrent_dir, f"{response_data['name']}_decoded.json")
                        with open(decoded_json_path, 'w', encoding='utf-8') as f:
                            json.dump(decoded_info, f, indent=2)
                        
                        return {
                            'name': response_data['name'],
                            'pieces': piece_hashes,
                            'decoded_torrent': decoded_info
                        }
                except Exception as e:
                    print(f"Lỗi khi xử lý file torrent: {str(e)}")
                    print(traceback.format_exc())
        return None

    def get_file_info(self, magnet_link):
        # Trả về thông tin về file dựa trên magnet link
        # Thông tin này có thể được lấy từ file torrent đã được lưu
        return {
            'total_pieces': len(self.get_torrent_info(magnet_link)['pieces']),
            'piece_length': self.piece_length
        }

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

    def save_piece(self, piece_index, piece_data):
        # Lưu piece đã nhận được
        if self.current_magnet_link:
            file_info = self.get_torrent_info(self.current_magnet_link)
            if file_info:
                file_name = file_info['name']
                piece_dir = os.path.join(self.pieces_dir, file_name)
                os.makedirs(piece_dir, exist_ok=True)
                piece_path = os.path.join(piece_dir, str(piece_index))
                with open(piece_path, 'wb') as f:
                    f.write(piece_data)

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
            if self.check_download_complete():
                self.finish_download()
        else:
            print(f"Piece {piece_index} không hợp lệ")
            self.download_manager.piece_failed(self.current_magnet_link, piece_index)

    def check_download_complete(self):
        """Kiểm tra xem đã tải đủ các piece chưa"""
        piece_dir = os.path.join(self.pieces_dir, self.current_file_name)
        if not os.path.exists(piece_dir):
            return False
            
        torrent_info = self.get_decoded_torrent_info()
        total_pieces = len(torrent_info['pieces'])
        
        existing_pieces = [f for f in os.listdir(piece_dir) if f.startswith('piece_')]
        return len(existing_pieces) == total_pieces

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
        """Xử lý khi tải file hoàn tất"""
        try:
            # Ghép các piece thành file hoàn chỉnh
            self.combine_pieces()
            
            # Ngắt kết nối với tất cả peer
            for peer_conn in self.peer_connections:
                peer_conn.cleanup()
                
            # In thống kê
            self.print_download_statistics()
            
            print(f"Đã tải xong file: {self.current_file_name}")
            
            # Cập nhật trạng thái
            self.current_file_name = None
            self.current_magnet_link = None
            self.peer_connections = []
            
        except Exception as e:
            print(f"Lỗi khi hoàn thành tải file: {e}")

    def print_download_statistics(self):
        """In thống kê về quá trình tải"""
        if self.current_magnet_link:
            stats = self.download_manager.get_download_stats(self.current_magnet_link)
            if stats:
                print("\n=== Thống kê tải file ===")
                print(f"Tên file: {self.current_file_name}")
                print(f"Thời gian tải: {stats['duration']:.2f} giây")
                print(f"Tổng số piece: {stats['total_pieces']}")
                print("\nThông tin các piece:")
                for piece_index, peer_info in stats['piece_sources'].items():
                    print(f"Piece {piece_index}: Tải từ {peer_info['ip']}:{peer_info['port']}")

    def disconnect_all_peers(self):
        """Ngắt kết nối với tất cả các peer"""
        for peer_conn in list(self.peer_connections):  # Tạo bản sao để tránh lỗi khi xóa
            try:
                peer_conn.cleanup()
                self.peer_connections.remove(peer_conn)
            except Exception as e:
                print(f"Lỗi khi ngắt kết nối peer: {e}")













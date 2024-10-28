import threading
import os
import hashlib

class DownloadManager(threading.Thread):
    def __init__(self, node):
        threading.Thread.__init__(self)
        self.node = node
        self.downloading = {}

    def run(self):
        while self.node.running:  # Thay vì while True
            # Kiểm tra các file đang tải
            for magnet_link, download_info in list(self.downloading.items()):
                if self.is_download_complete(download_info):
                    self.finish_download(magnet_link, download_info)
                else:
                    self.request_next_piece(magnet_link, download_info)
            
            # Đợi một khoảng thời gian trước khi kiểm tra lại
            threading.Event().wait(5)

    def start_download(self, magnet_link, peers_data):
        # Thêm phương thức này
        if magnet_link not in self.downloading:
            self.downloading[magnet_link] = {
                'peers_data': peers_data,
                'pieces': [False] * len(peers_data),
                'downloaded_pieces': []
            }
        print(f"Bắt đầu tải file với magnet link: {magnet_link}")

    def request_next_piece(self, magnet_link, download_info):
        next_piece = self.get_next_piece_to_download(download_info)
        if next_piece is not None:
            peer = self.select_peer(download_info['peers_data'], next_piece)
            if peer:
                self.node.request_piece(peer, magnet_link, next_piece)

    def get_next_piece_to_download(self, download_info):
        for i, downloaded in enumerate(download_info['pieces']):
            if not downloaded:
                return i
        return None

    def select_peer(self, peers_data, piece_index):
        # Implement logic to select a peer that has the piece we need
        # For simplicity, we'll just return the first peer in the list
        for piece_data in peers_data:
            if piece_data['piece_index'] == piece_index and piece_data['nodes']:
                return piece_data['nodes'][0]
        return None

    def is_download_complete(self, download_info):
        return all(download_info['pieces'])

    def finish_download(self, magnet_link, download_info):
        """Hoàn thành quá trình tải"""
        try:
            # Ghép các piece thành file hoàn chỉnh
            self.combine_pieces(magnet_link, download_info)
            print(f"Đã tải xong file: {download_info['file_name']}")
        except Exception as e:
            print(f"Lỗi khi hoàn thành tải file: {e}")
        finally:
            # Xóa thông tin download
            del self.downloading[magnet_link]

    def piece_received(self, magnet_link, piece_index, piece_data):
        download_info = self.downloading.get(magnet_link)
        if download_info:
            expected_hash = download_info['torrent_info']['pieces'][piece_index]
            if self.verify_piece(piece_data, expected_hash):
                self.save_piece(magnet_link, piece_index, piece_data)
                download_info['pieces'][piece_index] = True
            else:
                print(f"Piece {piece_index} verification failed")

    def verify_piece(self, piece_data, expected_hash):
        return hashlib.sha1(piece_data).hexdigest() == expected_hash

    def save_piece(self, magnet_link, piece_index, piece_data):
        file_name = self.downloading[magnet_link]['torrent_info']['name']
        piece_dir = os.path.join(self.node.pieces_dir, file_name)
        os.makedirs(piece_dir, exist_ok=True)
        with open(os.path.join(piece_dir, f"{piece_index}"), 'wb') as f:
            f.write(piece_data)

    def handle_piece_received(self, magnet_link, piece_index, piece_data):
        """Xử lý piece nhận được"""
        if magnet_link in self.downloading:
            download_info = self.downloading[magnet_link]
            
            # Verify piece hash
            if self.verify_piece(piece_data, download_info['piece_hashes'][piece_index]):
                # Lưu piece
                self.save_piece(magnet_link, piece_index, piece_data)
                download_info['pieces'][piece_index] = True
                
                # Kiểm tra nếu đã tải xong
                if self.is_download_complete(download_info):
                    self.finish_download(magnet_link, download_info)
            else:
                # Yêu cầu lại piece không hợp lệ
                self.request_piece(magnet_link, piece_index)

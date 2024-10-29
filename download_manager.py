import threading
import os
import hashlib
import time

class DownloadManager(threading.Thread):
    def __init__(self, node):
        threading.Thread.__init__(self)
        self.node = node
        self.downloads = {}  # {magnet_link: download_info}
        self.piece_managers = {}  # {magnet_link: PieceManager}
        self.download_stats = {}  # {magnet_link: download_statistics}

    def run(self):
        while self.node.running:  # Thay vì while True
            # Kiểm tra các file đang tải
            for magnet_link, download_info in list(self.downloads.items()):
                if self.is_download_complete(download_info):
                    self.finish_download(magnet_link)
                else:
                    self.request_next_pieces(magnet_link)
            
            # Đợi một khoảng thời gian trước khi kiểm tra lại
            threading.Event().wait(5)

    def start_download(self, magnet_link, peers_data):
        if magnet_link not in self.downloads:
            total_pieces = len(peers_data.get('pieces', []))
            
            # Khởi tạo PieceManager cho file này
            piece_manager = PieceManager(total_pieces)
            self.piece_managers[magnet_link] = piece_manager
            
            # Lưu thông tin download
            self.downloads[magnet_link] = {
                'peers_data': peers_data,
                'active_peers': set(),
                'start_time': time.time(),
                'piece_manager': piece_manager
            }
            
            # Bắt đầu tải từ nhiều peer
            self.connect_to_multiple_peers(magnet_link)

    def connect_to_multiple_peers(self, magnet_link):
        download_info = self.downloads[magnet_link]
        peers_data = download_info['peers_data']
        piece_manager = download_info['piece_manager']
        
        # Lấy danh sách piece cần tải
        needed_pieces = piece_manager.get_next_pieces(peers_data['pieces'])
        
        for piece_index in needed_pieces:
            # Tìm peer phù hợp cho piece này
            peer = self.find_best_peer(peers_data, piece_index)
            if peer:
                # Kết nối và yêu cầu piece
                peer_conn = self.node.connect_and_request_piece(peer, piece_index)
                if peer_conn:
                    download_info['active_peers'].add(peer_conn)
                    piece_manager.start_piece(piece_index, peer)

    def handle_piece_completed(self, magnet_link, piece_index, peer_info):
        piece_manager = self.piece_managers.get(magnet_link)
        if piece_manager:
            piece_manager.complete_piece(piece_index)
            
            # Kiểm tra nếu tải xong
            if len(piece_manager.completed_pieces) == piece_manager.total_pieces:
                self.finish_download(magnet_link)
            else:
                # Tải các piece tiếp theo
                self.request_next_pieces(magnet_link)

    def finish_download(self, magnet_link):
        download_info = self.downloads[magnet_link]
        piece_manager = self.piece_managers[magnet_link]
        
        # Lưu thống kê
        end_time = time.time()
        stats = {
            'start_time': download_info['start_time'],
            'end_time': end_time,
            'duration': end_time - download_info['start_time'],
            'piece_statistics': piece_manager.get_statistics()
        }
        self.download_stats[magnet_link] = stats
        
        # Ngắt kết nối với tất cả peer
        for peer_conn in download_info['active_peers']:
            peer_conn.cleanup()
            
        # Xóa thông tin download
        del self.downloads[magnet_link]
        del self.piece_managers[magnet_link]
        
        # In thống kê
        self.print_download_statistics(magnet_link)

    def print_download_statistics(self, magnet_link):
        stats = self.download_stats[magnet_link]
        print("\n=== Thống kê tải file ===")
        print(f"Thời gian tải: {stats['duration']:.2f} giây")
        print("\nThông tin các piece:")
        piece_stats = stats['piece_statistics']
        
        for piece_index, peer_info in piece_stats['piece_sources'].items():
            print(f"Piece {piece_index}: Tải từ {peer_info['ip']}:{peer_info['port']}")
            
        print(f"\nTổng số piece: {piece_stats['total_pieces']}")
        print(f"Hoàn thành: {piece_stats['completion_percentage']:.2f}%")

    def request_next_pieces(self, magnet_link):
        download_info = self.downloads[magnet_link]
        piece_manager = self.piece_managers[magnet_link]
        
        # Lấy danh sách piece cần tải
        needed_pieces = piece_manager.get_next_pieces(download_info['peers_data']['pieces'])
        
        for piece_index in needed_pieces:
            # Tìm peer phù hợp cho piece này
            peer = self.find_best_peer(download_info['peers_data'], piece_index)
            if peer:
                # Kết nối và yêu cầu piece
                peer_conn = self.node.connect_and_request_piece(peer, piece_index)
                if peer_conn:
                    download_info['active_peers'].add(peer_conn)
                    piece_manager.start_piece(piece_index, peer)

    def find_best_peer(self, peers_data, piece_index):
        # Implement logic to select a peer that has the piece we need
        # For simplicity, we'll just return the first peer in the list
        for piece_data in peers_data:
            if piece_data['piece_index'] == piece_index and piece_data['nodes']:
                return piece_data['nodes'][0]
        return None

    def is_download_complete(self, download_info):
        return all(download_info['pieces'])

    def piece_received(self, magnet_link, piece_index, piece_data):
        download_info = self.downloads.get(magnet_link)
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
        file_name = self.downloads[magnet_link]['torrent_info']['name']
        piece_dir = os.path.join(self.node.pieces_dir, file_name)
        os.makedirs(piece_dir, exist_ok=True)
        with open(os.path.join(piece_dir, f"{piece_index}"), 'wb') as f:
            f.write(piece_data)

    def handle_piece_received(self, magnet_link, piece_index, piece_data):
        """Xử lý piece nhận được"""
        if magnet_link in self.downloads:
            download_info = self.downloads[magnet_link]
            
            # Verify piece hash
            if self.verify_piece(piece_data, download_info['piece_hashes'][piece_index]):
                # Lưu piece
                self.save_piece(magnet_link, piece_index, piece_data)
                download_info['pieces'][piece_index] = True
                
                # Kiểm tra nếu đã tải xong
                if self.is_download_complete(download_info):
                    self.finish_download(magnet_link)
            else:
                # Yêu cầu lại piece không hợp lệ
                self.request_piece(magnet_link, piece_index)

import threading
from peer_selector import PeerSelector

class DownloadManager(threading.Thread):
    def __init__(self, node):
        threading.Thread.__init__(self)
        self.node = node
        self.downloads = {}  # {magnet_link: download_info}
        self.peer_selector = PeerSelector()

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
                    # Khởi động lại trạng thái lắng nghee
                    self.node.start_listening()
                # Yêu cầu lại piece không hợp lệ

    def piece_completed(self, magnet_link, piece_index):
        """Xử lý khi một piece được tải xong"""
        download_info = self.downloads.get(magnet_link)
        if download_info:
            # Cập nhật trạng thái
            download_info['active_pieces'].remove(piece_index)
            download_info['completed_pieces'].add(piece_index)
            
            # Cập nhật thống kê cho peer
            peer = download_info['piece_sources'].get(piece_index)
            if peer:
                peer_id = f"{peer['ip']}:{peer['port']}"
                self.peer_selector.update_peer_stats(
                    peer_id, 
                    download_speed=1.0,  # Có thể tính toán tốc độ thực tế
                    success=True
                )
            
            # Kiểm tra nếu tải xong
            if len(download_info['completed_pieces']) == len(download_info['peers_data']['pieces']):
                self.finish_download(magnet_link, download_info)
            else:
                # Tiếp tục tải các piece khác
                download_info = self.downloads[magnet_link]
                pieces_info = download_info['peers_data']['pieces']
                
                # Chọn các cặp piece-peer tốt nhất
                selected_pairs = self.peer_selector.select_best_peers_for_pieces(pieces_info)
                
                for piece_index, peer in selected_pairs:
                    if piece_index not in download_info['active_pieces']:
                        # Tạo kết nối mới và yêu cầu piece
                        peer_conn = self.node.connect_and_request_piece(peer, piece_index)
                        if peer_conn:
                            download_info['connections'].add(peer_conn)
                            download_info['active_pieces'].add(piece_index)
                            download_info['piece_sources'][piece_index] = peer

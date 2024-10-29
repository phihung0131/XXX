class PieceManager:
    def __init__(self, total_pieces):
        self.total_pieces = total_pieces
        self.piece_status = {}  # {piece_index: status}
        self.piece_sources = {}  # {piece_index: peer_info}
        self.active_pieces = set()
        self.completed_pieces = set()
        self.max_concurrent_pieces = 5
        
        for i in range(total_pieces):
            self.piece_status[i] = 'missing'
            
    def get_next_pieces(self, available_peers):
        """Chọn các piece tiếp theo để tải dựa trên peer có sẵn"""
        needed_pieces = []
        
        # Lọc các piece chưa tải và không đang tải
        available_pieces = [
            i for i in range(self.total_pieces)
            if self.piece_status[i] == 'missing' and i not in self.active_pieces
        ]
        
        # Tính toán độ ưu tiên của mỗi piece
        piece_priorities = {}
        for piece_index in available_pieces:
            available_sources = sum(1 for peer in available_peers if piece_index in peer['pieces'])
            piece_priorities[piece_index] = available_sources
            
        # Sắp xếp theo độ ưu tiên (rarest first)
        sorted_pieces = sorted(piece_priorities.items(), key=lambda x: x[1])
        
        # Chọn số piece cần thiết
        needed_count = self.max_concurrent_pieces - len(self.active_pieces)
        for piece_index, _ in sorted_pieces[:needed_count]:
            needed_pieces.append(piece_index)
            
        return needed_pieces

    def start_piece(self, piece_index, peer_info):
        """Bắt đầu tải một piece"""
        self.piece_status[piece_index] = 'downloading'
        self.active_pieces.add(piece_index)
        self.piece_sources[piece_index] = peer_info

    def complete_piece(self, piece_index):
        """Đánh dấu piece đã tải xong"""
        self.piece_status[piece_index] = 'completed'
        self.active_pieces.remove(piece_index)
        self.completed_pieces.add(piece_index)

    def get_statistics(self):
        """Lấy thống kê về quá trình tải"""
        stats = {
            'total_pieces': self.total_pieces,
            'completed_pieces': len(self.completed_pieces),
            'active_pieces': len(self.active_pieces),
            'piece_sources': self.piece_sources,
            'completion_percentage': (len(self.completed_pieces) / self.total_pieces) * 100
        }
        return stats

class PeerSelector:
    def __init__(self):
        self.peer_stats = {}  # {peer_id: {speed: float, success_rate: float}}
        self.active_connections = {}  # {peer_id: count}
        self.max_connections_per_peer = 3

    def select_best_peers_for_pieces(self, pieces_info, num_pieces=5):
        selected_pairs = []
        
        for piece in pieces_info:
            piece_index = piece['piece_index']
            available_nodes = piece['nodes']
            
            if not available_nodes:
                continue
                
            # Tính điểm cho mỗi peer
            peer_scores = []
            for peer in available_nodes:
                peer_id = f"{peer['ip']}:{peer['port']}"

                stats = self.peer_stats.get(peer_id, {})
                speed = stats.get('speed', 1.0)
                success_rate = stats.get('success_rate', 1.0)
                active_connections = self.active_connections.get(peer_id, 0)
                score = (speed * 0.4 + success_rate * 0.6) / (active_connections + 1)

                peer_scores.append((peer, score))
            
            # Sắp xếp theo điểm số
            peer_scores.sort(key=lambda x: x[1], reverse=True)
            
            # Chọn peer tốt nhất chưa quá tải
            for peer, _ in peer_scores:
                peer_id = f"{peer['ip']}:{peer['port']}"
                if self.can_add_connection(peer_id):
                    selected_pairs.append((piece_index, peer))
                    self.add_connection(peer_id)
                    break
                    
            if len(selected_pairs) >= num_pieces:
                break
                
        return selected_pairs

    def can_add_connection(self, peer_id):
        current_connections = self.active_connections.get(peer_id, 0)
        return current_connections < self.max_connections_per_peer

    def add_connection(self, peer_id):
        self.active_connections[peer_id] = self.active_connections.get(peer_id, 0) + 1

    def update_peer_stats(self, peer_id, download_speed, success):
        if peer_id not in self.peer_stats:
            self.peer_stats[peer_id] = {'speed': 0, 'success_rate': 1.0, 'total_attempts': 0}
            
        stats = self.peer_stats[peer_id]
        stats['speed'] = (stats['speed'] + download_speed) / 2
        stats['total_attempts'] = stats['total_attempts'] + 1
        
        if success:
            success_rate = stats.get('success_rate', 1.0)
            stats['success_rate'] = (success_rate * (stats['total_attempts'] - 1) + 1) / stats['total_attempts']
        else:
            success_rate = stats.get('success_rate', 1.0)
            stats['success_rate'] = (success_rate * (stats['total_attempts'] - 1)) / stats['total_attempts']

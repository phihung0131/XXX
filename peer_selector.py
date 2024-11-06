class PeerSelector:
    def __init__(self):
        self.peer_stats = {}  # {peer_id: {speed: float, success_rate: float}}
        self.active_connections = {}  # {peer_id: count}
        self.max_connections_per_peer = 3

    def select_peers(self, pieces_info):
        selected = []
        for piece in pieces_info:
            if piece['nodes']:  # Chọn peer đầu tiên có sẵn
                selected.append((piece['piece_index'], piece['nodes'][0]))
        return selected

    def can_add_connection(self, peer_id):
        current_connections = self.active_connections.get(peer_id, 0)
        return current_connections < self.max_connections_per_peer

    def add_connection(self, peer_id):
        self.active_connections[peer_id] = self.active_connections.get(peer_id, 0) + 1

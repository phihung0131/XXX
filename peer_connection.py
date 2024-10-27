import threading

class PeerConnection(threading.Thread):
    def __init__(self, node, peer_address):
        threading.Thread.__init__(self)
        self.node = node
        self.peer_address = peer_address

    def run(self):
        # Xử lý kết nối với peer
        pass

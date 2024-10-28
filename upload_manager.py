import threading

class UploadManager(threading.Thread):
    def __init__(self, node):
        threading.Thread.__init__(self)
        self.node = node

    def run(self):
        while self.node.running:  # Thay vì while True
            # Quản lý quá trình upload
            threading.Event().wait(5)

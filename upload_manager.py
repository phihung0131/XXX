import threading

class UploadManager(threading.Thread):
    def __init__(self, node):
        threading.Thread.__init__(self)
        self.node = node

    def run(self):
        # Quản lý quá trình upload
        pass

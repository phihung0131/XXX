import tkinter as tk
from tkinter import filedialog, simpledialog
from node import Node
import threading

class NodeGUI:
    def __init__(self, master):
        self.master = master
        self.node = Node()
        master.title("P2P File Sharing")

        self.share_button = tk.Button(master, text="Chia sẻ file", command=self.share_file)
        self.share_button.pack()

        self.download_button = tk.Button(master, text="Tải file", command=self.download_file)
        self.download_button.pack()

        self.status_label = tk.Label(master, text="")
        self.status_label.pack()

        # Khởi chạy node trong một thread riêng biệt
        self.node_thread = threading.Thread(target=self.node.run)
        self.node_thread.daemon = True
        self.node_thread.start()

    def share_file(self):
        file_path = filedialog.askopenfilename()
        if file_path:
            magnet_link, torrent_path = self.node.share_file(file_path)
            self.status_label.config(text=f"File đã được chia sẻ.\nMagnet link: {magnet_link}\nTorrent file: {torrent_path}")

    def download_file(self):
        magnet_link = simpledialog.askstring("Tải file", "Nhập magnet link:")
        if magnet_link:
            peers_data = self.node.get_peers_for_file(magnet_link)
            if peers_data:
                self.status_label.config(text=f"Đã lấy danh sách peer. Số lượng piece: {len(peers_data)}")
            else:
                self.status_label.config(text="Không thể lấy danh sách peer.")

def main():
    root = tk.Tk()
    gui = NodeGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()

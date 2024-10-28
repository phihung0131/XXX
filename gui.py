import tkinter as tk
from tkinter import ttk, filedialog, simpledialog, messagebox
from node import Node
import threading
import os  # Thêm dòng này
import json

class NodeGUI:
    def __init__(self, master):
        self.master = master
        self.node = Node()
        master.title("P2P File Sharing")

        # Thêm xử lý sự kiện đóng cửa sổ
        master.protocol("WM_DELETE_WINDOW", self.on_closing)

        self.share_button = tk.Button(master, text="Chia sẻ file", command=self.share_file)
        self.share_button.pack()

        self.download_button = tk.Button(master, text="Tải file", command=self.download_file)
        self.download_button.pack()

        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(master, variable=self.progress_var, maximum=100)
        self.progress_bar.pack()

        self.status_label = tk.Label(master, text="")
        self.status_label.pack()

        self.info_label = tk.Label(master, text=f"IP: {self.node.ip}, Port: {self.node.port}")
        self.info_label.pack()

        self.analyze_button = tk.Button(master, text="Phân tích Torrent", command=self.analyze_torrent)
        self.analyze_button.pack()

        # Khởi chạy node trong một thread riêng biệt
        self.node_thread = threading.Thread(target=self.node.run)
        self.node_thread.daemon = True
        self.node_thread.start()

        self.node.start_listening()  # Bắt đầu lắng nghe kết nối

    def share_file(self):
        file_path = filedialog.askopenfilename()
        if file_path:
            self.progress_var.set(0)
            self.status_label.config(text="Đang xử lý file...")
            self.node.share_file(file_path, self.update_share_progress)

    def update_share_progress(self, current, total, magnet_link=None, torrent_path=None):
        progress = (current / total) * 100
        self.progress_var.set(progress)
        if magnet_link and torrent_path:
            self.status_label.config(text=f"File đã được chia sẻ.\nMagnet link: {magnet_link}\nTorrent file: {torrent_path}")
        else:
            self.status_label.config(text=f"Đang xử lý: {current}/{total} pieces")
        self.master.update_idletasks()

    def download_file(self):
        magnet_link = simpledialog.askstring("Tải file", "Nhập magnet link:")
        if magnet_link:
            peers_data = self.node.get_peers_for_file(magnet_link)
            if peers_data:
                # Lấy tên file từ peers_data
                if isinstance(peers_data, dict) and 'name' in peers_data:
                    self.node.current_file_name = peers_data['name']
                    self.node.current_magnet_link = magnet_link
                
                self.status_label.config(text=f"Đã lấy danh sách peer. Số lượng piece: {len(peers_data)}")
                peers_data_file = os.path.join(self.node.node_data_dir, 'peers_data.json')
                with open(peers_data_file, 'w') as f:
                    json.dump(peers_data, f, indent=2)
                print(f"Đã lưu thông tin peers vào {peers_data_file}")
                
                # Kết nối với node đầu tiên có piece 1
                first_peer = self.node.find_peer_with_piece(peers_data, 0)
                if first_peer:
                    self.node.connect_and_request_piece(first_peer, 0)
                    messagebox.showinfo("Thông báo", f"Đã kết nối với peer {first_peer['ip']}:{first_peer['port']} và yêu cầu piece 1")
                else:
                    messagebox.showinfo("Thông báo", "Không tìm thấy peer có piece 1")
            else:
                error_message = "Không thể lấy danh sách peer. Vui lòng kiểm tra kết nối và magnet link."
                messagebox.showerror("Lỗi", error_message)
                print(error_message)

    def analyze_torrent(self):
        torrent_file_name = filedialog.askopenfilename(initialdir=self.node.torrent_dir, filetypes=[("Torrent files", "*.torrent")])
        if torrent_file_name:
            temp_dir, piece_hashes = self.node.analyze_torrent(os.path.basename(torrent_file_name))
            if temp_dir and piece_hashes:
                messagebox.showinfo("Phân tích Torrent", f"Kết quả phân tích đã được lưu trong thư mục: {temp_dir}")

    def on_closing(self):
        if messagebox.askokcancel("Thoát", "Bạn có muốn thoát không?"):
            print("Đang dừng tất cả các thread...")
            self.node.stop()  # Dừng node và các thread con
            self.master.destroy()  # Đóng cửa sổ
            os._exit(0)  # Kết thúc toàn bộ chương trình

def main():
    root = tk.Tk()
    gui = NodeGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()

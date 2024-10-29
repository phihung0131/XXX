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
        
        # Frame chính
        main_frame = ttk.Frame(master, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Frame thông tin node
        info_frame = ttk.LabelFrame(main_frame, text="Thông tin Node", padding="5")
        info_frame.pack(fill=tk.X, pady=5)
        ttk.Label(info_frame, text=f"IP: {self.node.ip}").pack(side=tk.LEFT, padx=5)
        ttk.Label(info_frame, text=f"Port: {self.node.port}").pack(side=tk.LEFT, padx=5)
        
        # Frame điều khiển
        control_frame = ttk.LabelFrame(main_frame, text="Điều khiển", padding="5")
        control_frame.pack(fill=tk.X, pady=5)
        ttk.Button(control_frame, text="Chia sẻ file", command=self.share_file).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="Tải file", command=self.download_file).pack(side=tk.LEFT, padx=5)
        
        # Frame tiến độ
        progress_frame = ttk.LabelFrame(main_frame, text="Tiến độ", padding="5")
        progress_frame.pack(fill=tk.X, pady=5)
        
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(progress_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(fill=tk.X, pady=5)
        
        self.status_label = ttk.Label(progress_frame, text="")
        self.status_label.pack(fill=tk.X, pady=5)
        
        # Frame thông tin chi tiết
        details_frame = ttk.LabelFrame(main_frame, text="Thông tin chi tiết", padding="5")
        details_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.details_text = tk.Text(details_frame, height=10, wrap=tk.WORD)
        self.details_text.pack(fill=tk.BOTH, expand=True)
        
        # Khởi động node và GUI
        self.node_thread = threading.Thread(target=self.node.run)
        self.node_thread.daemon = True
        self.node_thread.start()
        self.node.start_listening()
        
        # Cập nhật GUI định kỳ
        self.update_gui()
        
        # Xử lý đóng cửa sổ
        master.protocol("WM_DELETE_WINDOW", self.on_closing)

    def update_gui(self):
        """Cập nhật GUI mỗi giây"""
        try:
            if self.node.current_magnet_link:
                stats = self.node.download_manager.get_download_stats(self.node.current_magnet_link)
                if stats:
                    # Cập nhật thanh tiến độ
                    self.progress_var.set(stats['progress'])
                    
                    # Cập nhật thông tin trạng thái
                    status = f"Đã tải: {stats['completed_pieces']}/{stats['total_pieces']} pieces "
                    status += f"({stats['progress']:.1f}%) - {stats['speed']:.1f} KB/s"
                    self.status_label.config(text=status)
                    
                    # Cập nhật thông tin chi tiết
                    details = f"Tên file: {self.node.current_file_name}\n"
                    details += f"Thời gian tải: {stats['duration']:.1f} giây\n"
                    details += f"Tốc độ tải: {stats['speed']:.1f} KB/s\n"
                    details += f"Tiến độ: {stats['progress']:.1f}%\n"
                    details += f"Pieces đã tải: {stats['completed_pieces']}/{stats['total_pieces']}\n"
                    
                    if stats['piece_sources']:
                        details += "\nNguồn tải:\n"
                        for piece, peer in stats['piece_sources'].items():
                            details += f"Piece {piece}: {peer['ip']}:{peer['port']}\n"
                    
                    self.details_text.delete(1.0, tk.END)
                    self.details_text.insert(tk.END, details)

        except Exception as e:
            print(f"Lỗi cập nhật GUI: {e}")
        finally:
            self.master.after(1000, self.update_gui)

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
                if isinstance(peers_data, dict) and 'name' in peers_data:
                    self.node.current_file_name = peers_data['name']
                    self.node.current_magnet_link = magnet_link
                    
                    # Bắt đầu tải từ nhiều nguồn
                    self.node.connect_and_request_pieces(peers_data)
                    
                    num_pieces = len(peers_data.get('pieces', []))
                    self.status_label.config(text=f"Đang tải {num_pieces} pieces từ nhiều nguồn...")
                else:
                    messagebox.showerror("Lỗi", "Dữ liệu peers không hợp lệ")

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

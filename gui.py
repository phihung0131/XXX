import tkinter as tk
from tkinter import ttk, filedialog, simpledialog, messagebox
from node import Node
import threading
import os 
import sys  
import io   

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
        
        # Thêm StringIO để capture output
        self.output_buffer = io.StringIO()
        sys.stdout = self.output_buffer

        # Cập nhật GUI định kỳ
        self.update_gui()
        
        # Xử lý đóng cửa sổ
        master.protocol("WM_DELETE_WINDOW", self.on_closing)

    def update_gui(self):
        """Cập nhật GUI mỗi giây"""
        try:
            if self.node.current_file_name:
                # Đếm số piece đã tải trong thư mục
                piece_dir = os.path.join(self.node.pieces_dir, self.node.current_file_name)
                if os.path.exists(piece_dir):
                    completed_pieces = len([f for f in os.listdir(piece_dir) if f.startswith('piece_')])
                    
                    # Lấy tổng số piece từ torrent_info
                    torrent_info = self.node.get_decoded_torrent_info()
                    if torrent_info:
                        total_pieces = len(torrent_info['pieces'])
                        
                        # Cập nhật thanh tiến độ
                        progress = (completed_pieces / total_pieces) * 100 if total_pieces > 0 else 0
                        self.progress_var.set(progress)
                        
                        # Cập nhật nhãn trạng thái
                        if completed_pieces == total_pieces:
                            self.status_label.config(text=f"Đã tải xong file: {self.node.current_file_name}")
                        else:
                            self.status_label.config(text=f"Đang tải: {completed_pieces}/{total_pieces} pieces ({progress:.1f}%)")
            
            # Lấy output từ buffer và hiển thị vào details_text
            output = self.output_buffer.getvalue()
            if output:
                self.details_text.delete(1.0, tk.END)
                self.details_text.insert(tk.END, output)
                self.details_text.see(tk.END)  # Tự động cuộn xuốngg
                self.output_buffer.truncate(0)
                self.output_buffer.seek(0)

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

    def on_closing(self):
        if messagebox.askokcancel("Thoát", "Bạn có muốn thoát không?"):
            # Khôi phục stdout gốc
            sys.stdout = sys.__stdout__
            self.node.stop()
            self.master.destroy()
            os._exit(0)

def main():
    root = tk.Tk()
    gui = NodeGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()

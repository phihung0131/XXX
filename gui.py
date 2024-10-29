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
        
        # Frame tải xuống
        self.download_frame = ttk.LabelFrame(main_frame, text="Trạng thái Tải xuống", padding="5")
        self.download_frame.pack(fill=tk.X, pady=5)
        
        self.download_progress = ttk.Progressbar(self.download_frame, mode='determinate')
        self.download_progress.pack(fill=tk.X, pady=5)
        
        stats_frame = ttk.Frame(self.download_frame)
        stats_frame.pack(fill=tk.X)
        
        self.download_status = ttk.Label(stats_frame, text="")
        self.download_status.pack(side=tk.LEFT, padx=5)
        
        self.download_speed = ttk.Label(stats_frame, text="Tốc độ: 0 KB/s")
        self.download_speed.pack(side=tk.RIGHT, padx=5)
        
        self.piece_status = ttk.Label(stats_frame, text="Pieces: 0/0")
        self.piece_status.pack(side=tk.RIGHT, padx=5)
        
        # Frame chia sẻ
        self.upload_frame = ttk.LabelFrame(main_frame, text="File đang chia sẻ", padding="5")
        self.upload_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Treeview cho danh sách file chia sẻ
        columns = ('name', 'size', 'pieces', 'peers', 'speed')
        self.shared_files = ttk.Treeview(self.upload_frame, columns=columns, show='headings')
        self.shared_files.heading('name', text='Tên file')
        self.shared_files.heading('size', text='Kích thước')
        self.shared_files.heading('pieces', text='Pieces')
        self.shared_files.heading('peers', text='Peers')
        self.shared_files.heading('speed', text='Tốc độ')
        self.shared_files.pack(fill=tk.BOTH, expand=True)
        
        # Khởi động cập nhật GUI và node
        self.update_gui()
        self.start_node()

    def get_file_info(self, magnet_link):
        """Hàm bổ trợ để lấy thông tin file"""
        try:
            info = self.node.shared_files.get(magnet_link, {})
            file_path = info.get('file_path', '')
            if os.path.exists(file_path):
                return {
                    'name': info.get('file_name', ''),
                    'size': os.path.getsize(file_path),
                    'pieces': len(info.get('pieces', [])),
                    'peers': len(info.get('peers', [])),
                    'speed': info.get('upload_speed', 0)
                }
        except Exception as e:
            print(f"Lỗi khi lấy thông tin file: {e}")
        return None

    def update_gui(self):
        """Cập nhật GUI mỗi giây"""
        try:
            # Cập nhật thông tin tải xuống
            if self.node.current_magnet_link:
                stats = self.node.download_manager.get_download_stats(self.node.current_magnet_link)
                if stats:
                    progress = (stats['completed_pieces'] / stats['total_pieces']) * 100
                    self.download_progress['value'] = progress
                    self.piece_status['text'] = f"Pieces: {stats['completed_pieces']}/{stats['total_pieces']}"
                    self.download_speed['text'] = f"Tốc độ: {stats.get('speed', 0):.1f} KB/s"
                    
                    if progress == 100:
                        self.download_status['text'] = "Hoàn tất"
                    else:
                        self.download_status['text'] = "Đang tải..."

            # Cập nhật danh sách file chia sẻ
            self.update_shared_files()
            
        except Exception as e:
            print(f"Lỗi cập nhật GUI: {str(e)}")
        finally:
            self.master.after(1000, self.update_gui)

    def share_file(self):
        """Xử lý chia sẻ file"""
        file_path = filedialog.askopenfilename()
        if file_path:
            self.download_status['text'] = "Đang xử lý file..."
            self.download_progress['value'] = 0
            self.node.share_file(file_path, self.update_share_progress)

    def update_share_progress(self, current, total, magnet_link=None, torrent_path=None):
        """Cập nhật tiến độ xử lý file chia sẻ"""
        progress = (current / total) * 100
        self.download_progress['value'] = progress
        
        if magnet_link and torrent_path:
            self.download_status['text'] = "Đã chia sẻ file thành công"
            messagebox.showinfo("Thành công", 
                f"File đã được chia sẻ.\nMagnet link: {magnet_link}\nTorrent file: {torrent_path}")
        else:
            self.download_status['text'] = f"Đang xử lý: {current}/{total} pieces"
        self.master.update_idletasks()

    def download_file(self):
        """Xử lý tải file"""
        magnet_link = simpledialog.askstring("Tải file", "Nhập magnet link:")
        if magnet_link:
            peers_data = self.node.get_peers_for_file(magnet_link)
            if peers_data:
                if isinstance(peers_data, dict) and 'name' in peers_data:
                    self.node.current_file_name = peers_data['name']
                    self.node.current_magnet_link = magnet_link
                    
                    # Bắt đầu tải từ nhiều nguồn
                    self.node.connect_and_request_pieces(peers_data)
                    
                    self.download_status['text'] = "Đang tải file..."
                    self.piece_status['text'] = f"Pieces: 0/{len(peers_data.get('pieces', []))}"
                else:
                    messagebox.showerror("Lỗi", "Dữ liệu peers không hợp lệ")

    def start_node(self):
        """Khởi động node trong thread riêng"""
        self.node_thread = threading.Thread(target=self.node.run)
        self.node_thread.daemon = True
        self.node_thread.start()

    def on_closing(self):
        """Xử lý khi đóng cửa sổ"""
        if messagebox.askokcancel("Thoát", "Bạn có muốn thoát không?"):
            self.node.running = False
            self.master.destroy()

    def update_shared_files(self):
        """Cập nhật danh sách file chia sẻ"""
        for item in self.shared_files.get_children():
            self.shared_files.delete(item)
            
        for magnet_link, info in self.node.shared_files.items():
            try:
                file_info = self.get_file_info(magnet_link)
                if file_info:
                    self.shared_files.insert('', 'end', values=(
                        file_info['name'],
                        self.format_size(os.path.getsize(info['file_path'])),
                        f"0/{file_info['pieces']}", 
                        file_info['peers'],
                        f"{file_info['speed']:.1f} KB/s"
                    ))
            except Exception as e:
                print(f"Lỗi khi cập nhật thông tin file {magnet_link}: {str(e)}")

    @staticmethod
    def format_size(size):
        """Format kích thước file"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"

def main():
    root = tk.Tk()
    gui = NodeGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()

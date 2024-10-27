import os
import json
from node import Node

def main():
    node = Node()
    node_id = os.environ.get('NODE_ID', '0')
    print(f"Node {node_id} đang chạy...")
    node.run()
    
    while True:
        command = input(f"Node {node_id} - Nhập lệnh (share/download/exit/show_peers): ")
        if command == "share":
            file_name = input("Nhập tên file trong thư mục shared_files: ")
            file_path = os.path.join('/app/shared_files', file_name)
            if os.path.exists(file_path):
                magnet_link, torrent_path = node.share_file(file_path)
                print(f"File đã được chia sẻ.\nMagnet link: {magnet_link}\nTorrent file: {torrent_path}")
            else:
                print(f"File {file_name} không tồn tại trong thư mục shared_files.")
        elif command == "download":
            magnet_link = input("Nhập magnet link: ")
            peers_data = node.get_peers_for_file(magnet_link)
            if peers_data:
                print(f"Đã lấy danh sách peer. Số lượng piece: {len(peers_data)}")
                # Ở đây bạn sẽ thêm logic để tải file
            else:
                print("Không thể lấy danh sách peer.")
        elif command == "exit":
            break
        elif command == "show_peers":
            try:
                with open('peers_data.json', 'r') as f:
                    peers_data = json.load(f)
                print("Nội dung của peers_data.json:")
                print(json.dumps(peers_data, indent=2))
            except FileNotFoundError:
                print("File peers_data.json không tồn tại.")
            except json.JSONDecodeError:
                print("Không thể đọc nội dung của peers_data.json.")
        else:
            print("Lệnh không hợp lệ.")

if __name__ == "__main__":
    main()

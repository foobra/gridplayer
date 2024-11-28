import http.server
import socketserver
import json
import threading
import select
import atexit

# 定义全局status
GLOBAL_STATUS = []

# 定义一个停止服务器的事件
stop_server_event = threading.Event()

def add_global_status(url, current_pos, offset=0):
    """添加一个新的全局对象"""
    global_item = {
        'url': url,
        'current_pos': current_pos,
        'offset': offset
    }
    GLOBAL_STATUS.append(global_item)

def get_global_status(url):
    """获取指定 URL 的全局对象"""
    for item in GLOBAL_STATUS:
        if item['url'] == url:
            return item
    return None

def update_global_status(url, current_pos, offset):
    """更新指定 URL 的全局对象"""
    for item in GLOBAL_STATUS:
        if item['url'] == url:
            item['current_pos'] = current_pos if  current_pos else  item['current_pos']
            item['offset'] = offset if offset else item['offset']
            return
    # 如果没有找到对应的对象,则添加一个新的
    add_global_status(url, current_pos, offset)

class RequestHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        """处理 GET 请求"""
        if self.path == '/status':
            self.send_response_only(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            response = json.dumps(GLOBAL_STATUS, indent=2)
            self.wfile.write(response.encode())
        else:
            self.send_response_only(404)
            self.end_headers()



def run_server():
    PORT = 8005
    with socketserver.TCPServer(("", PORT), RequestHandler) as httpd:
        print(f"Serving at port {PORT}")
        try:
            # 在服务器循环中检查停止事件
            while not stop_server_event.is_set():
                # 使用 select 等待事件
                if httpd.socket.fileno() in select.select([httpd.socket.fileno()], [], [], 0.1)[0]:
                    httpd.handle_request()
        finally:
            # 停止事件触发时关闭服务器
            httpd.server_close()
            print("Server stopped")

def init_server():
    server_thread = threading.Thread(target=run_server)
    server_thread.daemon = True
    server_thread.start()

def stop_server():
    """Signal the server to stop"""
    stop_server_event.set()


    # 注册退出清理函数
def cleanup():
    stop_server()

atexit.register(cleanup)
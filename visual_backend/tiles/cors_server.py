from http.server import HTTPServer, SimpleHTTPRequestHandler
import sys
import os


class CORSRequestHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET')
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
        return super().end_headers()

if __name__ == '__main__':
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 9999
    server_address = ('', port)
    httpd = HTTPServer(server_address, CORSRequestHandler)
    print(f"正在端口 {port} 上启动带 CORS 支持的瓦片服务器...")
    print(f"根目录: {os.getcwd()}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("服务器已停止")
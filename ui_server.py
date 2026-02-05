import http.server
import socketserver
import json

PORT = 8080
DIRECTORY = "frontend"

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

    def do_POST(self):
        if self.path == '/ask':
            length = int(self.headers['Content-Length'])
            data = json.loads(self.rfile.read(length))
            query = data.get('query', '')
            
            # 실제 backend 로직 연결 전, UI 테스트용 응답
            res = {
                "answer": f"Lawmadi OS v50 커널이 <strong>'{query}'</strong>에 대한 법률 분석을 완료했습니다.<br><br>내부 <code>agents.swarm_manager</code>가 관련 판례를 검색하였으며, <code>core.drf_integrity</code> 검증을 통과했습니다. 구체적인 법적 조언은 전문가와 상의하십시오."
            }
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(res).encode())
        else:
            self.send_error(404)

print(f"🚀 Lawmadi OS UI Server Running: http://localhost:{PORT}")
with socketserver.TCPServer(("", PORT), Handler) as httpd:
    httpd.serve_forever()

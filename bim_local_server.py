import http.server
import json
import os
import socketserver
import subprocess
import sys
import tempfile

APP_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, APP_DIR)
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_MB", "100")) * 1024 * 1024
PORT = int(os.getenv("PORT", "8765"))
DWG_CONVERTER_CANDIDATES = [
    os.getenv("ACCORECONSOLE_PATH", ""),
    r"D:\AutoCAD 2023\accoreconsole.exe",
    r"C:\Program Files\Autodesk\AutoCAD 2023\accoreconsole.exe",
]
DWG_CONVERTER = next((path for path in DWG_CONVERTER_CANDIDATES if path and os.path.isfile(path)), "")
os.chdir(APP_DIR)


class BimRequestHandler(http.server.SimpleHTTPRequestHandler):
    extensions_map = {
        **http.server.SimpleHTTPRequestHandler.extensions_map,
        ".wasm": "application/wasm",
        ".ifc": "application/octet-stream",
        ".webmanifest": "application/manifest+json",
    }

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(204)
        self.end_headers()

    def do_GET(self):
        if self.path == "/health":
            payload = json.dumps({
                "status": "ok",
                "service": "bim-material-api-local",
                "max_upload_mb": MAX_UPLOAD_BYTES // (1024 * 1024),
                "dwg_conversion": bool(DWG_CONVERTER),
            }).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        super().do_GET()

    def do_POST(self):
        if self.path == "/api/convert-dwg":
            self.convert_dwg()
            return
        if self.path != "/api/material-takeoff":
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0 or length > MAX_UPLOAD_BYTES:
            self.send_error(400, "Invalid IFC file size")
            return
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(prefix="bim_takeoff_", suffix=".ifc", delete=False) as temp_file:
                temp_path = temp_file.name
                remaining = length
                while remaining:
                    chunk = self.rfile.read(min(1024 * 1024, remaining))
                    if not chunk:
                        raise ValueError("IFC upload ended unexpectedly")
                    temp_file.write(chunk)
                    remaining -= len(chunk)
            with open(temp_path, "rb") as uploaded:
                header = uploaded.read(4096).lstrip(b"\xef\xbb\xbf\x00\t\r\n ")
            if not header.startswith(b"ISO-10303-21;"):
                raise ValueError("유효한 IFC STEP 파일이 아닙니다.")
            from ifc_material_takeoff import analyze_ifc
            result = analyze_ifc(temp_path, allow_geometry=True, max_geometry_elements=400)
            payload = json.dumps(result, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        except Exception as error:
            payload = json.dumps({"error": str(error)}, ensure_ascii=False).encode("utf-8")
            self.send_response(500)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        finally:
            if temp_path and os.path.exists(temp_path):
                os.unlink(temp_path)

    def convert_dwg(self):
        if not DWG_CONVERTER:
            self.send_json_error(503, "AutoCAD Core Console을 찾지 못했습니다. ACCORECONSOLE_PATH를 설정하세요.")
            return
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0 or length > MAX_UPLOAD_BYTES:
            self.send_json_error(400, "유효하지 않은 DWG 파일 크기입니다.")
            return
        try:
            with tempfile.TemporaryDirectory(prefix="bim_dwg_") as temp_dir:
                dwg_path = os.path.join(temp_dir, "source.dwg")
                dxf_path = os.path.join(temp_dir, "converted.dxf")
                script_path = os.path.join(temp_dir, "convert.scr")
                with open(dwg_path, "wb") as uploaded:
                    remaining = length
                    while remaining:
                        chunk = self.rfile.read(min(1024 * 1024, remaining))
                        if not chunk:
                            raise ValueError("DWG 업로드가 중간에 종료되었습니다.")
                        uploaded.write(chunk)
                        remaining -= len(chunk)
                with open(dwg_path, "rb") as uploaded:
                    if not uploaded.read(6).startswith(b"AC10"):
                        raise ValueError("유효한 DWG 파일이 아닙니다.")
                script = "\n".join([
                    "FILEDIA", "0", "_.DXFOUT",
                    f'"{dxf_path.replace(os.sep, "/")}"',
                    "16", "_.QUIT", "",
                ])
                with open(script_path, "w", encoding="ascii", newline="\n") as script_file:
                    script_file.write(script)
                completed = subprocess.run(
                    [DWG_CONVERTER, "/i", dwg_path, "/s", script_path, "/l", "en-US"],
                    cwd=temp_dir,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    timeout=180,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                    check=False,
                )
                if completed.returncode != 0 or not os.path.isfile(dxf_path):
                    raise RuntimeError(f"AutoCAD DWG 변환 실패 (종료 코드 {completed.returncode})")
                with open(dxf_path, "rb") as converted:
                    payload = converted.read()
                if not payload.lstrip().startswith(b"0") or b"SECTION" not in payload[:1024]:
                    raise RuntimeError("변환된 DXF 형식이 올바르지 않습니다.")
                self.send_response(200)
                self.send_header("Content-Type", "application/dxf")
                self.send_header("Content-Disposition", 'attachment; filename="converted.dxf"')
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
        except subprocess.TimeoutExpired:
            self.send_json_error(504, "DWG 변환 시간이 3분을 초과했습니다.")
        except Exception as error:
            self.send_json_error(500, str(error))

    def send_json_error(self, status, message):
        payload = json.dumps({"error": message}, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


with socketserver.TCPServer(("127.0.0.1", PORT), BimRequestHandler) as httpd:
    print(f"BIM viewer running at http://127.0.0.1:{PORT}/index.html", flush=True)
    httpd.serve_forever()

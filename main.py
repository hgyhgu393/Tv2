from flask import Flask, Response
import requests
import os

app = Flask(__name__)

# ลิ้งก์ไฟล์หลักบน GitHub ของแทน
GITHUB_SOURCE = "https://raw.githubusercontent.com/hgyhgu393/O0.1/main/server.txt"

@app.route('/')
def home():
    try:
        # ดึงโค้ดจาก GitHub มาประมวลผล
        res = requests.get(GITHUB_SOURCE)
        code = res.text
        
        if not code.strip():
            return "", 204 # ส่งสถานะว่างเปล่าเพื่อให้แอปขึ้น Error
            
        # ส่งกลับไปให้ WebView ใน Android รัน
        return Response(code, mimetype='text/html')
    except:
        return "", 500

if __name__ == "__main__":
    # Render จะกำหนด Port ให้เองผ่าน Environment Variable
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)

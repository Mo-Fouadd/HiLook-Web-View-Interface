import os
import threading
import time
import cv2
import numpy as np
import requests
import concurrent.futures
from requests.auth import HTTPDigestAuth
from flask import Flask, Response, render_template_string
from dotenv import load_dotenv

os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp|stimeout;3000000"

app = Flask(__name__)
load_dotenv()




USER = os.getenv('CAM_USER')
PASS = os.getenv('CAM_PASS')
IP = os.getenv('CAM_IP')
STREAM = os.getenv('CAM_STREAM')

POLL_INTERVAL = float(os.getenv('POLL_INTERVAL'))

TARGET_CAMERAS = [int(x) for x in os.getenv('TARGET_CAMERAS').split(',')]
GROUP_1 = [int(x) for x in os.getenv('GROUP_1').split(',')]
GROUP_2 = [int(x) for x in os.getenv('GROUP_2').split(',')]

no_signal_frame = np.zeros((360, 640, 3), dtype=np.uint8)
cv2.putText(no_signal_frame, "NO SIGNAL / OFFLINE", (120, 180), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
_, no_signal_jpeg = cv2.imencode('.jpg', no_signal_frame)
NO_SIGNAL_BYTES = no_signal_jpeg.tobytes()

frames = {cam_id: NO_SIGNAL_BYTES for cam_id in TARGET_CAMERAS}
auth = HTTPDigestAuth(USER, PASS)
session = requests.Session()
session.headers.update({'Connection': 'close'})

def fetch_single(cam_id):
    url = f"http://{IP}/ISAPI/Streaming/channels/{cam_id}01/picture"
    try:
        res = session.get(url, auth=auth, timeout=1.0)
        if res.status_code == 200 and len(res.content) > 1000:
            frames[cam_id] = res.content
        else:
            frames[cam_id] = NO_SIGNAL_BYTES
    except Exception:
        frames[cam_id] = NO_SIGNAL_BYTES

def update_loop():
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        while True:
            futures_g1 = [executor.submit(fetch_single, cam) for cam in GROUP_1]
            concurrent.futures.wait(futures_g1)
            time.sleep(POLL_INTERVAL)

            futures_g2 = [executor.submit(fetch_single, cam) for cam in GROUP_2]
            concurrent.futures.wait(futures_g2)
            time.sleep(POLL_INTERVAL)

thread = threading.Thread(target=update_loop, daemon=True)
thread.start()

def rtsp_generator(cam_id):
    rtsp_url = f"rtsp://{USER}:{PASS}@{IP}:554/Streaming/Channels/{cam_id}0{STREAM}"
    cap = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    
    timeout_start = time.time()
    while not cap.isOpened():
        if time.time() - timeout_start > 3:
            break
        time.sleep(0.1)

    while cap.isOpened():
        success, frame = cap.read()
        if not success: 
            break
        _, buffer = cv2.imencode('.jpg', frame)
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
    
    if cap.isOpened():
        cap.release()
        
    yield (b'--frame\r\n'
           b'Content-Type: image/jpeg\r\n\r\n' + NO_SIGNAL_BYTES + b'\r\n')

@app.route('/')
def index():
    html = """
    <html>
    <head>
        <title>HiLook Smart-View</title>
        <style>
            body { 
                background: #000; margin: 0; padding: 0; color: white; 
                font-family: monospace; overflow: hidden; width: 100vw; height: 100vh;
            }
            .grid { 
                display: grid; 
                grid-template-columns: repeat(3, 1fr); 
                grid-template-rows: repeat(3, 1fr); 
                width: 100vw; height: 100vh; gap: 2px; 
            }
            .cam { 
                border: 1px solid #222; position: relative; 
                background: #111; cursor: pointer; display: flex; 
                align-items: center; justify-content: center;
                transition: all 0.3s ease-in-out; z-index: 1;
            }
            .cam img { 
                width: 100%; height: 100%; object-fit: fill; display: block; 
                transition: all 0.3s ease-in-out;
            }
            .label { 
                position: absolute; top: 5px; left: 5px; background: rgba(0,0,0,0.8); 
                padding: 2px 5px; font-size: 12px; z-index: 10; 
            }
            .loader {
                position: absolute; width: 40px; height: 40px; border: 4px solid rgba(255,255,255,0.2);
                border-top: 4px solid #fff; border-radius: 50%; animation: spin 1s linear infinite; z-index: 20;
            }
            @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
            
            .fullscreen { 
                position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; 
                z-index: 1000; background: #000; border: none; margin: 0; 
            }
            .fullscreen img { 
                width: 100vw; height: 100vh; object-fit: fill; 
            }
            .hidden { 
                opacity: 0; pointer-events: none; position: absolute; z-index: -1;
            }
        </style>
    </head>
    <body>
        <div class="grid" id="mainGrid">
            {% for i in TARGET_CAMERAS %}
            <div class="cam" id="container-{{ i }}" data-id="{{ i }}" ondblclick="toggleView({{ i }})">
                <div class="label">CAM {{ i }}</div>
                <div class="loader hidden" id="loader-{{ i }}"></div>
                <img id="img-{{ i }}" src="/snapshot/{{ i }}">
            </div>
            {% endfor %}
        </div>

        <script>
            const cameras = {{ TARGET_CAMERAS | tojson }};
            let activeFullscreenId = null;
            let refreshInterval = null;

            function toggleView(camId) {
                if (activeFullscreenId === null) enterFullscreen(camId);
                else exitFullscreen();
            }

            function enterFullscreen(camId) {
                activeFullscreenId = camId;
                clearInterval(refreshInterval);
                
                document.querySelectorAll('.cam').forEach(c => {
                    const img = c.querySelector('img');
                    const loader = c.querySelector('.loader');
                    
                    if (c.dataset.id == camId) {
                        c.classList.remove('hidden');
                        c.classList.add('fullscreen');
                        loader.classList.remove('hidden');
                        
                        img.onload = () => { loader.classList.add('hidden'); };
                        img.src = '/rtsp_stream/' + camId;
                    } else {
                        c.classList.add('hidden');
                        setTimeout(() => { img.src = ''; }, 300); 
                    }
                });
            }

            function exitFullscreen() {
                activeFullscreenId = null;
                document.querySelectorAll('.cam').forEach(c => {
                    c.classList.remove('fullscreen', 'hidden');
                    const img = c.querySelector('img');
                    const loader = c.querySelector('.loader');
                    
                    loader.classList.add('hidden');
                    img.onload = null;
                    img.src = '/snapshot/' + c.dataset.id;
                });
                startPolling();
            }

            function navigate(direction) {
                if (activeFullscreenId === null) return;
                let currentIndex = cameras.indexOf(activeFullscreenId);
                let nextIndex = (currentIndex + direction + cameras.length) % cameras.length;
                enterFullscreen(cameras[nextIndex]);
            }

            window.addEventListener('keydown', (e) => {
                if (activeFullscreenId === null) return;
                if (e.key === "ArrowRight" || e.key === "ArrowUp") navigate(1);
                if (e.key === "ArrowLeft" || e.key === "ArrowDown") navigate(-1);
                if (e.key === "Escape") exitFullscreen();
            });

            function startPolling() {
                refreshInterval = setInterval(() => {
                    if (activeFullscreenId !== null) return;
                    document.querySelectorAll('.cam img').forEach(img => {
                        const camId = img.id.split('-')[1];
                        const newImg = new Image();
                        newImg.onload = () => { img.src = newImg.src; };
                        newImg.src = '/snapshot/' + camId + '?t=' + Date.now();
                    });
                }, 400); 
            }

            startPolling();
        </script>
    </body>
    </html>
    """
    return render_template_string(html, TARGET_CAMERAS=TARGET_CAMERAS)

@app.route('/snapshot/<int:cam_id>')
def snapshot(cam_id):
    return Response(frames.get(cam_id, NO_SIGNAL_BYTES), mimetype='image/jpeg')

@app.route('/rtsp_stream/<int:cam_id>')
def rtsp_stream(cam_id):
    return Response(rtsp_generator(cam_id), mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, threaded=True)
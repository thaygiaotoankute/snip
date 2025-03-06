from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import os
import io
import tempfile
import base64
import json
import time
import hashlib
import requests
from datetime import datetime
from PIL import Image
import google.generativeai as genai
from flask_session import Session
from functools import wraps

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "default_secret_key")
app.config["SESSION_TYPE"] = "filesystem"
app.config["SESSION_PERMANENT"] = False
Session(app)

# Set your Gemini API key - you should set this as an environment variable in Render
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "YOUR_GEMINI_API_KEY_HERE")

# URL của file users.json và check-convert trên GitHub
USERS_FILE_URL = "https://raw.githubusercontent.com/thayphuctoan/pconvert/refs/heads/main/user.json"
ACTIVATION_FILE_URL = "https://raw.githubusercontent.com/thayphuctoan/pconvert/main/check-convert"

# Cache các dữ liệu từ GitHub
users_cache = {"data": None, "timestamp": 0}
activation_cache = {"data": None, "timestamp": 0}

# Kết quả xử lý và tiến trình
processing_tasks = {}

# ------------------------------ Utility Functions ------------------------------
def get_users():
    """Lấy danh sách người dùng từ GitHub với cache 5 phút"""
    current_time = time.time()
    if users_cache["data"] is None or current_time - users_cache["timestamp"] > 300:
        try:
            response = requests.get(USERS_FILE_URL)
            if response.status_code == 200:
                users_cache["data"] = json.loads(response.text)
                users_cache["timestamp"] = current_time
                return users_cache["data"]
            else:
                return {}
        except Exception as e:
            print(f"Lỗi khi lấy danh sách người dùng: {str(e)}")
            return {}
    return users_cache["data"]

def get_activated_ids():
    """Lấy danh sách ID đã kích hoạt từ GitHub với cache 5 phút"""
    current_time = time.time()
    if activation_cache["data"] is None or current_time - activation_cache["timestamp"] > 300:
        try:
            response = requests.get(ACTIVATION_FILE_URL)
            if response.status_code == 200:
                activation_cache["data"] = response.text.strip().split('\n')
                activation_cache["timestamp"] = current_time
                return activation_cache["data"]
            else:
                return []
        except Exception as e:
            print(f"Lỗi khi lấy danh sách ID kích hoạt: {str(e)}")
            return []
    return activation_cache["data"]

def authenticate_user(username, password):
    """Xác thực người dùng"""
    users = get_users()
    if username in users and users[username] == password:
        return True
    return False

def generate_hardware_id(username):
    """Tạo hardware ID cố định từ username"""
    hardware_id = hashlib.md5(username.encode()).hexdigest().upper()
    formatted_id = '-'.join([hardware_id[i:i+8] for i in range(0, len(hardware_id), 8)])
    return formatted_id + "-Premium"

def check_activation(hardware_id):
    """Kiểm tra kích hoạt"""
    activated_ids = get_activated_ids()
    return hardware_id in activated_ids

def login_required(f):
    """Decorator yêu cầu đăng nhập"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session or not session['logged_in']:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def activation_required(f):
    """Decorator yêu cầu kích hoạt"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session or not session['logged_in']:
            return redirect(url_for('login'))
        
        if 'activation_status' not in session or session['activation_status'] != "ĐÃ KÍCH HOẠT":
            return redirect(url_for('activation_status'))
            
        return f(*args, **kwargs)
    return decorated_function

# ------------------------------ Routes ------------------------------
@app.route('/')
@login_required
def index():
    return render_template('index.html', username=session.get('username', ''))

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        if authenticate_user(username, password):
            session['logged_in'] = True
            session['username'] = username
            
            # Kiểm tra trạng thái kích hoạt
            hardware_id = generate_hardware_id(username)
            is_activated = check_activation(hardware_id)
            
            session['hardware_id'] = hardware_id
            session['activation_status'] = "ĐÃ KÍCH HOẠT" if is_activated else "CHƯA KÍCH HOẠT"
            
            return redirect(url_for('index'))
        else:
            error = 'Tên đăng nhập hoặc mật khẩu không đúng!'
    
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/activation-status')
@login_required
def activation_status():
    hardware_id = session.get('hardware_id', '')
    activation_status = session.get('activation_status', 'CHƯA KÍCH HOẠT')
    
    return render_template('activation.html', hardware_id=hardware_id, status=activation_status)

@app.route('/upload', methods=['POST'])
@login_required
def upload_image():
    if 'file' not in request.files and 'screenshot' not in request.form:
        return jsonify({'error': 'No image provided'}), 400
    
    try:
        if 'file' in request.files:
            # Handle file upload
            file = request.files['file']
            img = Image.open(file.stream)
        else:
            # Handle base64 screenshot data
            screenshot_data = request.form['screenshot']
            # Remove the data:image/png;base64, prefix
            if 'base64,' in screenshot_data:
                screenshot_data = screenshot_data.split('base64,')[1]
            img = Image.open(io.BytesIO(base64.b64decode(screenshot_data)))
        
        # Store image in session as base64 for later use
        buffered = io.BytesIO()
        img.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode('utf-8')
        session['current_image'] = img_str
        
        return jsonify({'success': True, 'message': 'Image successfully processed'})
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/extract-text', methods=['POST'])
@login_required
def extract_text():
    if 'current_image' not in session:
        return jsonify({'error': 'No image available'}), 400
    
    try:
        # Get custom API key if provided
        api_key = request.json.get('api_key', GEMINI_API_KEY)
        if not api_key or api_key == "YOUR_GEMINI_API_KEY_HERE":
            return jsonify({'error': 'Gemini API key is not configured. Please provide your API key.'}), 400
        
        # Configure Gemini with the API key
        genai.configure(api_key=api_key)
        
        # Get image from session
        img_data = base64.b64decode(session['current_image'])
        img = Image.open(io.BytesIO(img_data))
        
        # Extract text using Gemini
        text = convert_image_to_text(img)
        
        return jsonify({'success': True, 'text': text})
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def convert_image_to_text(img):
    # Convert PIL Image to bytes
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='PNG')
    img_byte_arr = img_byte_arr.getvalue()
    
    # Create a temporary file
    with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as temp_file:
        temp_file.write(img_byte_arr)
        temp_file_path = temp_file.name
    
    try:
        # Create a Gemini "uploaded file" from the temporary file
        uploaded_file = genai.upload_file(path=temp_file_path, mime_type="image/png")
        
        prompt = """
        Hãy nhận diện và gõ lại [CHÍNH XÁC] file ảnh thành văn bản, tất cả công thức Toán Latex, bọc trong dấu $
        [TUYỆT ĐỐI] không thêm nội dung khác ngoài nội dung PDF, [CHỈ ĐƯỢC PHÉP] gõ lại nội dung file ảnh thành văn bản.
        """
        
        # Create a Gemini Pro Vision model
        model = genai.GenerativeModel('gemini-pro-vision')
        
        # Generate response from Gemini
        response = model.generate_content([prompt, uploaded_file])
        
        # Return the recognized text
        return response.text
    finally:
        # Clean up the temporary file
        os.unlink(temp_file_path)

if __name__ == '__main__':
    # Get port from environment variable for Render compatibility
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)

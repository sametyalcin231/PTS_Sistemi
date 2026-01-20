from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from datetime import datetime
import os, pandas as pd, io

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'pts_v11_mobile_pro')

# --- VERİTABANI BAĞLANTI ---
uri = os.environ.get('DATABASE_URL', 'sqlite:///pts_v11.db')
if uri and uri.startswith("postgres://"):
    uri = uri.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = uri
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# --- GÜNCELLENMİŞ MODELLER ---
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(20), default='personel')
    # Yeni Alanlar
    full_name = db.Column(db.String(100))
    tc_no = db.Column(db.String(11))
    email = db.Column(db.String(100))
    nfc_id = db.Column(db.String(100), unique=True, nullable=True)

class Message(db.Model): # Sohbet Sistemi İçin
    id = db.Column(db.Integer, primary_key=True)
    sender = db.Column(db.String(50))
    receiver = db.Column(db.String(50)) # 'all' ise genel sohbet
    content = db.Column(db.String(500))
    timestamp = db.Column(db.DateTime, default=datetime.now)

class Attendance(db.Model): # Devamsızlık Takibi
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50))
    date = db.Column(db.Date, default=datetime.now().date())
    status = db.Column(db.String(20)) # 'Gelmedi', 'İzinli', 'Raporlu'

class Activity(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50))
    type = db.Column(db.String(30)) 
    detail = db.Column(db.String(500))
    file_path = db.Column(db.String(200), nullable=True)
    status = db.Column(db.String(20), default='Tamamlandı')
    created_at = db.Column(db.DateTime, default=datetime.now)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- ROTALAR ---

@app.route('/')
@login_required
def index():
    # Sohbet mesajlarını çek
    messages = Message.query.order_by(Message.timestamp.desc()).limit(20).all()
    my_logs = Activity.query.filter_by(username=current_user.username).order_by(Activity.created_at.desc()).all()
    active_status = Activity.query.filter_by(username=current_user.username, status='Aktif').first()
    return render_template('index.html', logs=my_logs, active_status=active_status, messages=messages, login_page=False)

# NFC Okuma Noktası (Mobil Cihaz Buraya İstek Atar)
@app.route('/nfc_scan/<nfc_id>')
def nfc_scan(nfc_id):
    user = User.query.filter_by(nfc_id=nfc_id).first()
    if user:
        # Otomatik Giriş-Çıkış İşlemi
        act = Activity(username=user.username, type='NFC-Giriş', detail=f"Kart Okutuldu: {user.full_name}", status='Tamamlandı')
        db.session.add(act)
        db.session.commit()
        return {"status": "success", "user": user.full_name}, 200
    return {"status": "error", "message": "Kart Tanımsız"}, 404

@app.route('/send_msg', methods=['POST'])
@login_required
def send_msg():
    content = request.form.get('content')
    if content:
        msg = Message(sender=current_user.username, receiver='all', content=content)
        db.session.add(msg)
        db.session.commit()
    return redirect(url_for('index'))

# ... Diğer Login, Register, Terminal rotaları (eski kodun aynısı kalacak) ...

# --- BAŞLATMA ---
with app.app_context():
    db.create_all()
    if not User.query.filter_by(username='admin').first():
        admin = User(username='admin', password='admin', role='admin', full_name='Sistem Yöneticisi', tc_no='00000000000')
        db.session.add(admin)
        db.session.commit()

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)

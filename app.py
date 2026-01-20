from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_mail import Mail, Message as MailMessage
from datetime import datetime
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'pts_ultra_v4_final')

# --- DOSYA YÜKLEME AYARLARI ---
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# --- VERİTABANI BAĞLANTISI ---
uri = os.environ.get('DATABASE_URL', 'sqlite:///pts_final_v4.db')
if uri and uri.startswith("postgres://"):
    uri = uri.replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_DATABASE_URI'] = uri
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# --- MAİL AYARLARI (RENDER ENVIRONMENT VARIABLES ÜZERİNDEN) ---
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_USERNAME')

db = SQLAlchemy(app)
mail = Mail(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# --- VERİ MODELLERİ ---
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    full_name = db.Column(db.String(100))
    tc_no = db.Column(db.String(11))
    email = db.Column(db.String(100))
    role = db.Column(db.String(20), default='personel')

class Request(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50))
    req_type = db.Column(db.String(50)) 
    content = db.Column(db.String(500))
    amount = db.Column(db.String(50), nullable=True)
    status = db.Column(db.String(20), default='Beklemede')
    created_at = db.Column(db.DateTime, default=datetime.now)

class Activity(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50))
    type = db.Column(db.String(30)) 
    detail = db.Column(db.String(500))
    file_path = db.Column(db.String(200), nullable=True)
    status = db.Column(db.String(20), default='Aktif')
    created_at = db.Column(db.DateTime, default=datetime.now)

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender = db.Column(db.String(50))
    content = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.now)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- ANA SAYFA VE SEKMELER ---
@app.route('/')
@login_required
def index():
    # Aktif Dışarıdakiler
    outsiders = db.session.query(User.full_name).join(Activity, User.username == Activity.username).filter(Activity.status == 'Aktif', Activity.type == 'Terminal').all()
    # Personelin Kendi Talepleri
    my_requests = Request.query.filter_by(username=current_user.username).order_by(Request.created_at.desc()).all()
    # Sohbet Mesajları
    msgs = Message.query.order_by(Message.created_at.desc()).limit(20).all()
    # Aktif Terminal Durumu
    active_status = Activity.query.filter_by(username=current_user.username, status='Aktif', type='Terminal').first()
    
    return render_template('index.html', outsiders=outsiders, requests=my_requests, messages=msgs, active_status=active_status)

# --- KAYIT VE GİRİŞ ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form.get('username'), password=request.form.get('password')).first()
        if user:
            login_user(user)
            return redirect(url_for('index'))
        flash('Kullanıcı adı veya şifre hatalı!', 'danger')
    return render_template('index.html', login_page=True, auth_mode='login')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        new_user = User(username=request.form.get('username'), password=request.form.get('password'),
                        full_name=request.form.get('full_name'), tc_no=request.form.get('tc_no'), email=request.form.get('email'))
        db.session.add(new_user)
        db.session.commit()
        flash('Kayıt başarılı! Şimdi giriş yapabilirsiniz.', 'success')
        return redirect(url_for('login'))
    return render_template('index.html', login_page=True, auth_mode='register')

@app.route('/forgot_password', methods=['POST'])
def forgot_password():
    email = request.form.get('email')
    user = User.query.filter_by(email=email).first()
    if user:
        try:
            msg = MailMessage("PTS PRO Şifre Hatırlatma", recipients=[email])
            msg.body = f"Sayın {user.full_name}, PTS sistemine giriş şifreniz: {user.password}"
            mail.send(msg)
            flash('Şifreniz mail adresinize gönderildi.', 'success')
        except:
            flash('Mail gönderilirken hata oluştu.', 'danger')
    else:
        flash('Bu mail adresi sistemde kayıtlı değil.', 'danger')
    return redirect(url_for('login'))

# --- TALEP VE RAPOR İŞLEMLERİ ---
@app.route('/submit_request', methods=['POST'])
@login_required
def submit_request():
    db.session.add(Request(username=current_user.username, req_type=request.form.get('req_type'),
                           content=request.form.get('content'), amount=request.form.get('amount')))
    db.session.commit()
    flash('Talebiniz başarıyla gönderildi!', 'success')
    return redirect(url_for('index'))

@app.route('/upload_report', methods=['POST'])
@login_required
def upload_report():
    file = request.files.get('report_file')
    detail = request.form.get('report_detail')
    filename = None
    if file and allowed_file(file.filename):
        filename = secure_filename(f"{current_user.username}_{datetime.now().strftime('%Y%m%d%H%M')}_{file.filename}")
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
    
    db.session.add(Activity(username=current_user.username, type='Rapor', detail=detail, file_path=filename, status='Tamamlandı'))
    db.session.commit()
    flash('Rapor ve belge başarıyla sisteme yüklendi!', 'success')
    return redirect(url_for('index'))

@app.route('/terminal/<action>')
@login_required
def terminal(action):
    if action == 'out':
        db.session.add(Activity(username=current_user.username, type='Terminal', detail='Dışarı Çıktı', status='Aktif'))
        flash('Çıkış işleminiz kaydedildi.', 'warning')
    else:
        act = Activity.query.filter_by(username=current_user.username, status='Aktif', type='Terminal').first()
        if act: act.status = 'Tamamlandı'
        flash('Giriş işleminiz başarılı. Hoş geldiniz!', 'success')
    db.session.commit()
    return redirect(url_for('index'))

@app.route('/send_msg', methods=['POST'])
@login_required
def send_msg():
    c = request.form.get('content')
    if c:
        db.session.add(Message(sender=current_user.username, content=c))
        db.session.commit()
    return redirect(url_for('index'))

@app.route('/admin_panel')
@login_required
def admin_panel():
    if current_user.role != 'admin': return redirect(url_for('index'))
    return render_template('admin.html', users=User.query.all(), logs=Activity.query.all(), reqs=Request.query.all())

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('login'))

# --- VERİTABANI BAŞLATICI ---
with app.app_context():
    db.create_all()
    if not User.query.filter_by(username='admin').first():
        db.session.add(User(username='admin', password='123', role='admin', full_name='Yönetici', email='admin@pts.com'))
        db.session.commit()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))

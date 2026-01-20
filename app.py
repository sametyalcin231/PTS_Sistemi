from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_mail import Mail, Message as MailMessage
from datetime import datetime
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'pts_ultra_v2026_security')

# --- VERİTABANI ---
uri = os.environ.get('DATABASE_URL', 'sqlite:///pts_final.db')
if uri and uri.startswith("postgres://"):
    uri = uri.replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_DATABASE_URI'] = uri
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# --- MAİL AYARLARI (GÜVENLİ YÖNTEM) ---
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME') # Koda yazma, Render'a yaz!
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD') # Koda yazma, Render'a yaz!
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_USERNAME')

db = SQLAlchemy(app)
mail = Mail(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# --- MODELLER ---
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    full_name = db.Column(db.String(100))
    tc_no = db.Column(db.String(11))
    email = db.Column(db.String(100))
    role = db.Column(db.String(20), default='personel')

class Request(db.Model): # İzin ve Avans için yeni tablo
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50))
    req_type = db.Column(db.String(50)) 
    content = db.Column(db.String(500))
    amount = db.Column(db.String(50), nullable=True)
    status = db.Column(db.String(20), default='Onay Bekliyor')
    created_at = db.Column(db.DateTime, default=datetime.now)

class Activity(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50))
    type = db.Column(db.String(30)) 
    detail = db.Column(db.String(500))
    status = db.Column(db.String(20), default='İletildi')
    created_at = db.Column(db.DateTime, default=datetime.now)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- ROTALAR ---
@app.route('/')
@login_required
def index():
    my_logs = Activity.query.filter_by(username=current_user.username).order_by(Activity.created_at.desc()).all()
    my_requests = Request.query.filter_by(username=current_user.username).order_by(Request.created_at.desc()).all()
    active_status = Activity.query.filter_by(username=current_user.username, status='Aktif').first()
    return render_template('index.html', logs=my_logs, requests=my_requests, active_status=active_status)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form.get('username').strip(), 
                                    password=request.form.get('password').strip()).first()
        if user:
            login_user(user)
            return redirect(url_for('index'))
        flash('Hatalı giriş!', 'danger')
    return render_template('index.html', login_page=True, auth_mode='login')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        new_user = User(
            username=request.form.get('username').strip(),
            password=request.form.get('password').strip(),
            full_name=request.form.get('full_name'),
            tc_no=request.form.get('tc_no'),
            email=request.form.get('email')
        )
        db.session.add(new_user)
        db.session.commit()
        flash('Kayıt başarılı!', 'success')
        return redirect(url_for('login'))
    return render_template('index.html', login_page=True, auth_mode='register')

@app.route('/forgot_password', methods=['POST'])
def forgot_password():
    email = request.form.get('email')
    user = User.query.filter_by(email=email).first()
    if user:
        try:
            msg = MailMessage("PTS Şifre Hatırlatma", recipients=[email])
            msg.body = f"Merhaba {user.full_name}, Şifreniz: {user.password}"
            mail.send(msg)
            flash('Şifreniz mail adresinize gönderildi.', 'success')
        except Exception as e:
            flash(f'Mail hatası: {str(e)}', 'danger')
    return redirect(url_for('login'))

@app.route('/submit_request', methods=['POST'])
@login_required
def submit_request():
    new_req = Request(
        username=current_user.username,
        req_type=request.form.get('req_type'),
        content=request.form.get('content'),
        amount=request.form.get('amount')
    )
    db.session.add(new_req)
    db.session.commit()
    flash('Talebiniz başarıyla iletildi.', 'success')
    return redirect(url_for('index'))

@app.route('/upload_report', methods=['POST'])
@login_required
def upload_report():
    detail = request.form.get('report_detail')
    db.session.add(Activity(username=current_user.username, type='Rapor', detail=detail))
    db.session.commit()
    flash('Rapor sisteme işlendi.', 'success')
    return redirect(url_for('index'))

@app.route('/terminal/<action>')
@login_required
def terminal(action):
    if action == 'out':
        db.session.add(Activity(username=current_user.username, type='Terminal', detail='Dışarıda', status='Aktif'))
    else:
        act = Activity.query.filter_by(username=current_user.username, status='Aktif').first()
        if act: act.status = 'Tamamlandı'
    db.session.commit()
    return redirect(url_for('index'))

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('login'))

# --- VERİTABANI BAŞLATICI ---
with app.app_context():
    db.drop_all() # Tabloları "zorla" yenilemek için
    db.create_all()
    if not User.query.filter_by(username='admin').first():
        db.session.add(User(username='admin', password='123', role='admin', full_name='Yönetici', email='admin@test.com'))
        db.session.commit()

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)

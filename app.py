from flask import Flask, render_template, request, redirect, url_for, flash, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_mail import Mail, Message as MailMessage # Mail kütüphanesi
from datetime import datetime
import os, pandas as pd, io

app = Flask(__name__)
app.config['SECRET_KEY'] = 'pts_ultra_v13'

# --- VERİTABANI ---
uri = os.environ.get('DATABASE_URL', 'sqlite:///pts_v13.db')
if uri and uri.startswith("postgres://"):
    uri = uri.replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_DATABASE_URI'] = uri
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# --- MAİL AYARLARI (GMAIL) ---
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'SENIN_MAILIN@gmail.com' # Kendi mailini yaz
app.config['MAIL_PASSWORD'] = 'SENIN_UYGULAMA_SIFRESI' # Google'dan aldığın uygulama şifresini yaz
app.config['MAIL_DEFAULT_SENDER'] = 'SENIN_MAILIN@gmail.com'

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
    email = db.Column(db.String(100)) # Mail için gerekli
    role = db.Column(db.String(20), default='personel')

class Activity(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50))
    type = db.Column(db.String(30)) 
    detail = db.Column(db.String(500))
    status = db.Column(db.String(20), default='Tamamlandı')
    created_at = db.Column(db.DateTime, default=datetime.now)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- ŞİFRE SIFIRLAMA MAİL ROTASI ---
@app.route('/forgot_password', methods=['POST'])
def forgot_password():
    email = request.form.get('email')
    user = User.query.filter_by(email=email).first()
    if user:
        msg = MailMessage("PTS PRO - Şifre Hatırlatma", recipients=[email])
        msg.body = f"Merhaba {user.full_name}, Şifreniz: {user.password} \nLütfen giriş yaptıktan sonra şifrenizi değiştirin."
        mail.send(msg)
        flash('Şifreniz mail adresinize gönderildi.', 'success')
    else:
        flash('Bu mail adresi sistemde kayıtlı değil.', 'danger')
    return redirect(url_for('login'))

# --- ADMİN PANELİ (DÜZELTİLDİ) ---
@app.route('/admin_panel')
@login_required
def admin_panel():
    if current_user.role != 'admin':
        return redirect(url_for('index'))
    users = User.query.all()
    logs = Activity.query.order_by(Activity.created_at.desc()).all()
    return render_template('admin.html', users=users, logs=logs)

# ... Diğer index, login, terminal rotalarını koru ...

@app.route('/')
@login_required
def index():
    my_logs = Activity.query.filter_by(username=current_user.username).order_by(Activity.created_at.desc()).all()
    active_status = Activity.query.filter_by(username=current_user.username, status='Aktif').first()
    return render_template('index.html', logs=my_logs, active_status=active_status)

with app.app_context():
    db.create_all()
    if not User.query.filter_by(username='admin').first():
        admin = User(username='admin', password='123', role='admin', full_name='Sistem Yöneticisi', email='admin@test.com')
        db.session.add(admin)
        db.session.commit()

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)

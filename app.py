from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from datetime import datetime
import os, pandas as pd, io

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'pts_ultra_2026')

# --- VERİTABANI ---
uri = os.environ.get('DATABASE_URL', 'sqlite:///pts_final.db')
if uri and uri.startswith("postgres://"):
    uri = uri.replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_DATABASE_URI'] = uri
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# --- MODELLER ---
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    full_name = db.Column(db.String(100))
    tc_no = db.Column(db.String(11))
    role = db.Column(db.String(20), default='personel')
    recovery_key = db.Column(db.String(50)) # Şifre sıfırlama için

class Activity(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50))
    type = db.Column(db.String(30)) 
    detail = db.Column(db.String(500))
    status = db.Column(db.String(20), default='Beklemede')
    created_at = db.Column(db.DateTime, default=datetime.now)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- ROTALAR ---
@app.route('/')
@login_required
def index():
    my_logs = Activity.query.filter_by(username=current_user.username).order_by(Activity.created_at.desc()).all()
    outsiders = Activity.query.filter_by(status='Aktif', type='Terminal').all()
    active_status = Activity.query.filter_by(username=current_user.username, status='Aktif').first()
    out_duration = ""
    if active_status:
        diff = datetime.now() - active_status.created_at
        out_duration = f"{int(diff.total_seconds() // 60)} dk"
    return render_template('index.html', logs=my_logs, outsiders=outsiders, active_status=active_status, out_duration=out_duration)

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
        u = request.form.get('username').strip()
        if not User.query.filter_by(username=u).first():
            new_user = User(
                username=u, 
                password=request.form.get('password').strip(),
                full_name=request.form.get('full_name'),
                tc_no=request.form.get('tc_no'),
                recovery_key=request.form.get('recovery_key') # Sıfırlama anahtarı
            )
            db.session.add(new_user)
            db.session.commit()
            flash('Kayıt başarılı! Giriş yapabilirsiniz.', 'success')
            return redirect(url_for('login'))
    return render_template('index.html', login_page=True, auth_mode='register')

@app.route('/reset_password', methods=['POST'])
def reset_password():
    u = request.form.get('username')
    key = request.form.get('recovery_key')
    new_p = request.form.get('new_password')
    user = User.query.filter_by(username=u, recovery_key=key).first()
    if user:
        user.password = new_p
        db.session.commit()
        flash('Şifreniz güncellendi!', 'success')
    else:
        flash('Bilgiler uyuşmuyor!', 'danger')
    return redirect(url_for('login'))

@app.route('/terminal/<action>')
@login_required
def terminal(action):
    if action == 'out':
        db.session.add(Activity(username=current_user.username, type='Terminal', detail='Dışarıda', status='Aktif'))
    else:
        act = Activity.query.filter_by(username=current_user.username, status='Aktif').first()
        if act:
            act.status = 'Tamamlandı'
            act.detail = f"Geri Döndü ({int((datetime.now()-act.created_at).total_seconds()//60)} dk)"
    db.session.commit()
    return redirect(url_for('index'))

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('login'))

# --- VERİTABANI KURULUM ---
with app.app_context():
    db.create_all()
    if not User.query.filter_by(username='admin').first():
        db.session.add(User(username='admin', password='123', role='admin', full_name='Yönetici', recovery_key='admin123'))
        db.session.commit()

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)

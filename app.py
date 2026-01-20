from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_mail import Mail, Message as MailMessage
from datetime import datetime
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'pts_final_2026_key')

# --- VERİTABANI AYARI ---
uri = os.environ.get('DATABASE_URL', 'sqlite:///pts_v14.db')
if uri and uri.startswith("postgres://"):
    uri = uri.replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_DATABASE_URI'] = uri
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# --- MAİL AYARLARI (GMAIL) ---
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'rubycharoncar@gmail.com' # Değiştir!
app.config['MAIL_PASSWORD'] = 'zgme nxhc zokw ngrv' # Uygulama Şifren!
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
    email = db.Column(db.String(100))
    role = db.Column(db.String(20), default='personel')

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender = db.Column(db.String(50))
    content = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.now)

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

# --- ROTALAR ---
@app.route('/')
@login_required
def index():
    my_logs = Activity.query.filter_by(username=current_user.username).order_by(Activity.created_at.desc()).all()
    outsiders = Activity.query.filter_by(status='Aktif', type='Terminal').all()
    messages = Message.query.order_by(Message.created_at.desc()).limit(15).all()
    active_status = Activity.query.filter_by(username=current_user.username, status='Aktif').first()
    out_duration = ""
    if active_status:
        diff = datetime.now() - active_status.created_at
        out_duration = f"{int(diff.total_seconds() // 60)} dk"
    return render_template('index.html', logs=my_logs, outsiders=outsiders, active_status=active_status, out_duration=out_duration, messages=messages)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        u, p = request.form.get('username').strip(), request.form.get('password').strip()
        user = User.query.filter_by(username=u, password=p).first()
        if user:
            login_user(user)
            return redirect(url_for('index'))
        flash('Kullanıcı adı veya şifre hatalı!', 'danger')
    return render_template('index.html', login_page=True, auth_mode='login')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        u = request.form.get('username').strip()
        if not User.query.filter_by(username=u).first():
            new_user = User(
                username=u, password=request.form.get('password').strip(),
                full_name=request.form.get('full_name'), tc_no=request.form.get('tc_no'),
                email=request.form.get('email')
            )
            db.session.add(new_user)
            db.session.commit()
            flash('Kayıt başarılı! Giriş yapabilirsiniz.', 'success')
            return redirect(url_for('login'))
        flash('Bu kullanıcı adı zaten alınmış.', 'warning')
    return render_template('index.html', login_page=True, auth_mode='register')

@app.route('/forgot_password', methods=['POST'])
def forgot_password():
    target_email = request.form.get('email')
    user = User.query.filter_by(email=target_email).first()
    if user:
        try:
            msg = MailMessage("PTS PRO - Şifre Hatırlatma", recipients=[target_email])
            msg.body = f"Merhaba {user.full_name},\n\nŞifreniz: {user.password}\n\nLütfen giriş yaptıktan sonra şifrenizi güncelleyin."
            mail.send(msg)
            flash('Şifreniz mail adresinize gönderildi.', 'success')
        except:
            flash('Mail gönderim hatası!', 'danger')
    else:
        flash('Bu mail sistemde kayıtlı değil.', 'danger')
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

@app.route('/send_msg', methods=['POST'])
@login_required
def send_msg():
    c = request.form.get('content').strip()
    if c:
        db.session.add(Message(sender=current_user.username, content=c))
        db.session.commit()
    return redirect(url_for('index'))

@app.route('/admin_panel')
@login_required
def admin_panel():
    if current_user.role != 'admin':
        return redirect(url_for('index'))
    users = User.query.all()
    logs = Activity.query.order_by(Activity.created_at.desc()).all()
    return render_template('admin.html', users=users, logs=logs)

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('login'))

# --- VERİTABANI BAŞLATICI ---
with app.app_context():
    # Sütun hatasını çözmek için veritabanını temizle ve kur
    db.drop_all() 
    db.create_all()
    if not User.query.filter_by(username='admin').first():
        admin = User(username='admin', password='123', role='admin', 
                     full_name='Sistem Yöneticisi', email='admin@test.com', tc_no='00000000000')
        db.session.add(admin)
        db.session.commit()

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)

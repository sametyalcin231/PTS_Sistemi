from flask import Flask, render_template, request, redirect, url_for, flash, make_response
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_mail import Mail, Message as MailMessage
from datetime import datetime
import os
import io
import csv
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'pts_ultra_v5_final')

# --- DOSYA YÜKLEME AYARLARI ---
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# --- VERİTABANI BAĞLANTISI ---
uri = os.environ.get('DATABASE_URL', 'sqlite:///pts_final_v5.db')
if uri and uri.startswith("postgres://"):
    uri = uri.replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_DATABASE_URI'] = uri
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# --- MAİL AYARLARI ---
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

# --- MODELLER ---
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
    end_at = db.Column(db.DateTime, nullable=True) # Yeni sütun

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender = db.Column(db.String(50))
    content = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.now)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- EXCEL / CSV DIŞA AKTARIM ---
@app.route('/admin/export')
@login_required
def export_data():
    if current_user.role != 'admin': return redirect(url_for('index'))
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Personel', 'Islem Tipi', 'Detay', 'Durum', 'Baslangic', 'Bitis'])
    activities = Activity.query.all()
    for a in activities:
        writer.writerow([a.username, a.type, a.detail, a.status, a.created_at, a.end_at])
    response = make_response(output.getvalue())
    response.headers["Content-Disposition"] = "attachment; filename=pts_rapor.csv"
    response.headers["Content-type"] = "text/csv"
    return response

# --- ANA SAYFA ---
@app.route('/')
@login_required
def index():
    outsiders = db.session.query(User.full_name).join(Activity, User.username == Activity.username).filter(Activity.status == 'Aktif', Activity.type == 'Terminal').all()
    my_requests = Request.query.filter_by(username=current_user.username).order_by(Request.created_at.desc()).all()
    msgs = Message.query.order_by(Message.created_at.desc()).limit(20).all()
    active_status = Activity.query.filter_by(username=current_user.username, status='Aktif', type='Terminal').first()
    return render_template('index.html', outsiders=outsiders, requests=my_requests, messages=msgs, active_status=active_status)

# --- AUTH (GİRİŞ/KAYIT) ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form.get('username'), password=request.form.get('password')).first()
        if user: login_user(user); return redirect(url_for('index'))
        flash('Hatalı giriş!', 'danger')
    return render_template('index.html', login_page=True, auth_mode='login')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        u = request.form.get('username')
        if User.query.filter_by(username=u).first(): flash('Bu kullanıcı adı alınmış!', 'danger'); return redirect(url_for('register'))
        new_user = User(username=u, password=request.form.get('password'), full_name=request.form.get('full_name'), tc_no=request.form.get('tc_no'), email=request.form.get('email'))
        db.session.add(new_user); db.session.commit()
        flash('Kayıt başarılı! Giriş yapabilirsiniz.', 'success'); return redirect(url_for('login'))
    return render_template('index.html', login_page=True, auth_mode='register')

@app.route('/forgot_password', methods=['POST'])
def forgot_password():
    email = request.form.get('email')
    user = User.query.filter_by(email=email).first()
    if user:
        try:
            msg = MailMessage("PTS PRO Şifre Hatırlatma", recipients=[email])
            msg.body = f"Şifreniz: {user.password}"; mail.send(msg)
            flash('Şifre mailinize gönderildi.', 'success')
        except: flash('Mail hatası!', 'danger')
    else: flash('E-posta bulunamadı!', 'danger')
    return redirect(url_for('login'))

# --- İŞLEMLER ---
@app.route('/submit_request', methods=['POST'])
@login_required
def submit_request():
    db.session.add(Request(username=current_user.username, req_type=request.form.get('req_type'), content=request.form.get('content'), amount=request.form.get('amount')))
    db.session.commit(); flash('Talep iletildi!', 'success'); return redirect(url_for('index'))

@app.route('/upload_report', methods=['POST'])
@login_required
def upload_report():
    file = request.files.get('report_file')
    if file and allowed_file(file.filename):
        filename = secure_filename(f"{current_user.username}_{datetime.now().strftime('%Y%m%d%H%M')}_{file.filename}")
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        db.session.add(Activity(username=current_user.username, type='Rapor', detail=request.form.get('report_detail'), file_path=filename, status='Beklemede'))
        db.session.commit(); flash('Rapor yüklendi!', 'success')
    else: flash('Dosya seçilmedi veya geçersiz format!', 'danger')
    return redirect(url_for('index'))

@app.route('/terminal/<action>')
@login_required
def terminal(action):
    if action == 'out':
        db.session.add(Activity(username=current_user.username, type='Terminal', detail='Dışarıda', status='Aktif'))
        flash('Çıkış yapıldı.', 'warning')
    else:
        act = Activity.query.filter_by(username=current_user.username, status='Aktif', type='Terminal').first()
        if act: 
            act.status = 'Tamamlandı'
            act.end_at = datetime.now()
        flash('Giriş yapıldı.', 'success')
    db.session.commit(); return redirect(url_for('index'))

@app.route('/send_msg', methods=['POST'])
@login_required
def send_msg():
    c = request.form.get('content')
    if c: db.session.add(Message(sender=current_user.username, content=c)); db.session.commit()
    return redirect(url_for('index'))

# --- ADMİN PANELİ ---
@app.route('/admin_panel')
@login_required
def admin_panel():
    if current_user.role != 'admin': return redirect(url_for('index'))
    def get_duration(start, end):
        if not end: end = datetime.now()
        diff = end - start
        m, s = divmod(diff.seconds, 60)
        h, m = divmod(m, 60)
        return f"{h}s {m}dk"
    return render_template('admin.html', users=User.query.all(), logs=Activity.query.order_by(Activity.created_at.desc()).all(), reqs=Request.query.filter_by(status='Beklemede').all(), get_duration=get_duration)

@app.route('/admin/action/<target>/<int:id>/<status>')
@login_required
def admin_action(target, id, status):
    if current_user.role != 'admin': return redirect(url_for('index'))
    if target == 'request':
        item = Request.query.get(id)
        if item: item.status = status
    elif target == 'activity':
        item = Activity.query.get(id)
        if item: item.status = status
    db.session.commit(); flash(f'İşlem: {status}', 'success'); return redirect(url_for('admin_panel'))

@app.route('/logout')
def logout(): logout_user(); return redirect(url_for('login'))

# --- VERİTABANI BAŞLATMA VE SIFIRLAMA ---
with app.app_context():
    # Sütun hatasını çözmek için veritabanını sıfırlıyoruz
    db.drop_all() 
    db.create_all()
    if not User.query.filter_by(username='admin').first():
        db.session.add(User(username='admin', password='123', role='admin', full_name='Admin', email='admin@test.com'))
        db.session.commit()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))

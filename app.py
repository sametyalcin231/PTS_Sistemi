from flask import Flask, render_template, request, redirect, url_for, flash, make_response
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_mail import Mail, Message as MailMessage
from itsdangerous import URLSafeTimedSerializer
from datetime import datetime
import os
import io
import csv
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'pts_ultra_v5_final')

# --- ŞİFRE SIFIRLAMA NESNESİ (Hata Alınan Kısım Düzeltildi) ---
s = URLSafeTimedSerializer(app.config['SECRET_KEY'])

# --- MAİL AYARLARI (Bağlantı Sorunları İçin Optimize Edildi) ---
app.config.update(
    MAIL_SERVER='smtp.gmail.com',
    MAIL_PORT=465,
    MAIL_USE_TLS=False,
    MAIL_USE_SSL=True,
    MAIL_USERNAME=os.environ.get('MAIL_USERNAME'),
    MAIL_PASSWORD=os.environ.get('MAIL_PASSWORD'),
    MAIL_DEFAULT_SENDER=os.environ.get('MAIL_USERNAME'),
    MAIL_ASCII_ATTACHMENTS=False
)
app.config['MAIL_TIMEOUT'] = 30 
mail = Mail(app)

# --- DOSYA YÜKLEME AYARLARI ---
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# --- VERİTABANI AYARLARI ---
uri = os.environ.get('DATABASE_URL', 'sqlite:///pts_final_v5.db')
if uri and uri.startswith("postgres://"):
    uri = uri.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = uri
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    "pool_pre_ping": True,
    "pool_recycle": 300,
}

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
    end_at = db.Column(db.DateTime, nullable=True)

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender = db.Column(db.String(50))
    content = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.now)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def calculate_duration(start, end):
    if not start: return "N/A"
    diff = (end or datetime.now()) - start
    h, m = divmod(diff.seconds // 60, 60)
    return f"{h}s {m}dk"

# --- ROTALAR ---

@app.route('/')
@login_required
def index():
    outsiders = db.session.query(User.full_name).join(Activity, User.username == Activity.username).filter(Activity.status == 'Aktif', Activity.type == 'Terminal').all()
    my_requests = Request.query.filter_by(username=current_user.username).order_by(Request.created_at.desc()).all()
    msgs = Message.query.order_by(Message.created_at.desc()).limit(20).all()
    active_status = Activity.query.filter_by(username=current_user.username, status='Aktif', type='Terminal').first()
    return render_template('index.html', outsiders=outsiders, requests=my_requests, messages=msgs, active_status=active_status)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form.get('username'), password=request.form.get('password')).first()
        if user: 
            login_user(user)
            return redirect(url_for('index'))
        flash('Kullanıcı adı veya şifre hatalı!', 'danger')
    return render_template('index.html', login_page=True, auth_mode='login')

@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        user = User.query.filter_by(email=email).first()
        if user:
            try:
                token = s.dumps(email, salt='reset-password')
                link = url_for('reset_password', token=token, _external=True)
                msg = MailMessage('PTS PRO | Şifre Sıfırlama Talebi', recipients=[email])
                msg.body = f'Şifrenizi sıfırlamak için şu bağlantıya tıklayın: {link}'
                mail.send(msg)
                flash('Sıfırlama bağlantısı e-postanıza gönderildi!', 'success')
            except Exception as e:
                flash('Mail gönderilirken hata oluştu. Ayarları kontrol edin.', 'danger')
        else:
            flash('Bu e-posta adresi sistemde kayıtlı değil.', 'danger')
    return render_template('index.html', login_page=True, auth_mode='forgot')

@app.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    try:
        email = s.loads(token, salt='reset-password', max_age=3600)
    except:
        flash('Bağlantı geçersiz veya süresi dolmuş!', 'danger')
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        user = User.query.filter_by(email=email).first()
        if user:
            user.password = request.form.get('password')
            db.session.commit()
            flash('Şifreniz güncellendi! Giriş yapabilirsiniz.', 'success')
            return redirect(url_for('login'))
    return render_template('index.html', login_page=True, auth_mode='reset', token=token)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        u = request.form.get('username')
        if User.query.filter_by(username=u).first(): 
            flash('Bu kullanıcı adı zaten alınmış!', 'danger')
            return redirect(url_for('register'))
        new_user = User(username=u, 
                        password=request.form.get('password'), 
                        full_name=request.form.get('full_name'), 
                        tc_no=request.form.get('tc_no'), 
                        email=request.form.get('email'))
        db.session.add(new_user)
        db.session.commit()
        flash('Kayıt başarılı! Giriş yapabilirsiniz.', 'success')
        return redirect(url_for('login'))
    return render_template('index.html', login_page=True, auth_mode='register')

@app.route('/terminal/<action>')
@login_required
def terminal(action):
    if action == 'out':
        db.session.add(Activity(username=current_user.username, type='Terminal', detail='Dışarıda', status='Aktif'))
        flash('Dışarı çıkışınız kaydedildi!', 'warning')
    else:
        act = Activity.query.filter_by(username=current_user.username, status='Aktif', type='Terminal').first()
        if act: 
            act.status = 'Tamamlandı'
            act.end_at = datetime.now()
            flash('Hoş geldiniz! Girişiniz yapıldı.', 'success')
    db.session.commit()
    return redirect(url_for('index', _anchor='main'))

@app.route('/submit_request', methods=['POST'])
@login_required
def submit_request():
    db.session.add(Request(username=current_user.username, req_type=request.form.get('req_type'), content=request.form.get('content'), amount=request.form.get('amount')))
    db.session.commit()
    flash('Talebiniz yönetime başarıyla iletildi!', 'success')
    return redirect(url_for('index', _anchor='requests'))

@app.route('/upload_report', methods=['POST'])
@login_required
def upload_report():
    file = request.files.get('report_file')
    if file and allowed_file(file.filename):
        filename = secure_filename(f"{current_user.username}_{datetime.now().strftime('%Y%m%d%H%M')}_{file.filename}")
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        db.session.add(Activity(username=current_user.username, type='Rapor', detail=request.form.get('report_detail'), file_path=filename, status='Beklemede'))
        db.session.commit()
        flash('Rapor/Belge başarıyla yüklendi!', 'success')
    else:
        flash('Geçersiz dosya formatı!', 'danger')
    return redirect(url_for('index', _anchor='main'))

@app.route('/send_msg', methods=['POST'])
@login_required
def send_msg():
    c = request.form.get('content')
    if c: 
        db.session.add(Message(sender=current_user.username, content=c))
        db.session.commit()
    return redirect(url_for('index', _anchor='chat'))

@app.route('/admin_panel')
@login_required
def admin_panel():
    if current_user.role != 'admin': return redirect(url_for('index'))
    return render_template('admin.html', 
                           users=User.query.all(), 
                           logs=Activity.query.order_by(Activity.created_at.desc()).all(), 
                           reqs=Request.query.order_by(Request.created_at.desc()).all(),
                           get_duration=calculate_duration)

@app.route('/admin/set_role/<int:uid>/<role>')
@login_required
def set_role(uid, role):
    if current_user.role == 'admin':
        user = User.query.get(uid)
        if user: 
            user.role = role
            db.session.commit()
            flash(f'{user.full_name} yetkisi {role} olarak güncellendi.', 'success')
    return redirect(url_for('admin_panel'))

@app.route('/admin/action/<target>/<int:id>/<status>')
@login_required
def admin_action(target, id, status):
    if current_user.role != 'admin': return redirect(url_for('index'))
    item = Request.query.get(id) if target == 'request' else Activity.query.get(id)
    if item: 
        item.status = status
        db.session.commit()
        flash(f'İşlem {status} olarak işaretlendi.', 'success')
    return redirect(url_for('admin_panel'))

@app.route('/admin/export')
@login_required
def export_data():
    if current_user.role != 'admin': return redirect(url_for('index'))
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Personel', 'Islem Tipi', 'Detay', 'Durum', 'Baslangic', 'Bitis', 'Toplam Sure'])
    
    activities = Activity.query.all()
    for a in activities:
        duration = calculate_duration(a.created_at, a.end_at) if a.type == 'Terminal' else ""
        writer.writerow([a.username, a.type, a.detail, a.status, a.created_at, a.end_at, duration])
    
    reqs = Request.query.all()
    for r in reqs:
        writer.writerow([r.username, r.req_type, r.content, r.status, r.created_at, "-", "-"])

    response = make_response(output.getvalue())
    response.headers["Content-Disposition"] = "attachment; filename=PTS_Sistem_Raporu.csv"
    response.headers["Content-type"] = "text/csv"
    return response

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('login'))

with app.app_context():
    db.create_all()
    if not User.query.filter_by(username='admin').first():
        db.session.add(User(username='admin', password='123', role='admin', full_name='Sistem Admin', email='admin@pts.com'))
        db.session.commit()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))


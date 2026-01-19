from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from datetime import datetime
import os, pandas as pd, io

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'pts_v10_global_2026')

# --- KRİTİK VERİTABANI AYARI ---
# Eğer Render/Heroku gibi bir yerdeyse oradaki DATABASE_URL'i kullanır, yoksa yerelde sqlite açar.
uri = os.environ.get('DATABASE_URL', 'sqlite:///pts_final_v10.db')
if uri.startswith("postgres://"):
    uri = uri.replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_DATABASE_URI'] = uri
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

app.config['UPLOAD_FOLDER'] = 'uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# --- MODELLER ---
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(20), default='personel')

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

# --- ROTALAR (ÖNCEKİ SÜRÜMLE AYNI, SADECE WEB UYUMLU) ---
@app.route('/uploads/<filename>')
@login_required
def download_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/')
@login_required
def index():
    my_logs = Activity.query.filter_by(username=current_user.username).order_by(Activity.created_at.desc()).all()
    outsiders = Activity.query.filter_by(status='Aktif', type='Terminal').all()
    active_status = Activity.query.filter_by(username=current_user.username, status='Aktif').first()
    out_duration = f"{int((datetime.now() - active_status.created_at).total_seconds() // 60)} dk" if active_status else ""
    return render_template('index.html', logs=my_logs, outsiders=outsiders, active_status=active_status, out_duration=out_duration, login_page=False)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form.get('username').strip(), password=request.form.get('password').strip()).first()
        if user: login_user(user); return redirect(url_for('index'))
        flash('Hatalı giriş!', 'danger')
    return render_template('index.html', login_page=True, auth_mode='login')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        u, p = request.form.get('username').strip(), request.form.get('password').strip()
        if not User.query.filter_by(username=u).first():
            db.session.add(User(username=u, password=p)); db.session.commit()
            flash('Kayıt başarılı! Giriş yapabilirsiniz.', 'success'); return redirect(url_for('login'))
    return render_template('index.html', login_page=True, auth_mode='register')

@app.route('/terminal/<action>')
@login_required
def terminal(action):
    if action == 'out':
        db.session.add(Activity(username=current_user.username, type='Terminal', detail='Dışarıda', status='Aktif'))
    else:
        act = Activity.query.filter_by(username=current_user.username, status='Aktif').first()
        if act:
            min_out = int((datetime.now() - act.created_at).total_seconds() // 60)
            act.detail, act.status = f"Geri Döndü ({min_out} dk dışarıda kaldı)", 'Tamamlandı'
    db.session.commit(); return redirect(url_for('index'))

@app.route('/request', methods=['POST'])
@login_required
def make_request():
    t, d, date_val = request.form.get('type'), request.form.get('detail'), request.form.get('date')
    full_detail = f"{d} | Tarih: {date_val}" if date_val else d
    filename = None
    if 'file' in request.files and request.files['file'].filename != '':
        file = request.files['file']
        filename = f"{current_user.username}_{datetime.now().strftime('%H%M%S')}_{file.filename}"
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
    db.session.add(Activity(username=current_user.username, type=t, detail=full_detail, file_path=filename, status='Beklemede'))
    db.session.commit(); flash('Talep iletildi.', 'success'); return redirect(url_for('index'))

@app.route('/admin_panel')
@login_required
def admin_panel():
    if current_user.role != 'admin': return redirect(url_for('index'))
    return render_template('admin.html', users=User.query.all(), requests=Activity.query.filter_by(status='Beklemede').all(), logs=Activity.query.order_by(Activity.created_at.desc()).all())

@app.route('/export/<mode>')
@login_required
def export_data(mode):
    acts = Activity.query.filter_by(type='Terminal').all() if mode == 'terminal' else Activity.query.all()
    df = pd.DataFrame([{"Personel": a.username, "Tür": a.type, "İşlem": a.detail, "Zaman": a.created_at.strftime('%d.%m.%Y %H:%M')} for a in acts])
    output = io.BytesIO()
    with pd.ExcelWriter(output) as writer: df.to_excel(writer, index=False)
    output.seek(0); return send_file(output, mimetype='application/vnd.ms-excel', as_attachment=True, download_name='PTS_Rapor.xlsx')

@app.route('/approve/<int:id>')
@login_required
def approve(id):
    req = Activity.query.get(id)
    if req: req.status = 'Onaylandı'; db.session.commit()
    return redirect(url_for('admin_panel'))

@app.route('/logout')
def logout(): logout_user(); return redirect(url_for('login'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        if not User.query.filter_by(username='admin').first():
            db.session.add(User(username='admin', password='admin', role='admin')); db.session.commit()
    app.run(debug=True)
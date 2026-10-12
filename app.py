from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from config import Config
from models import db, User, Achievement, Photo, ScheduleItem
import os
from datetime import datetime
from werkzeug.utils import secure_filename
from olympiad_parser import get_olympiads_from_web

app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'



def teacher_required(f):
    from functools import wraps
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if not current_user.is_teacher_or_admin():
            flash('У вас нет прав для этого действия', 'error')
            return redirect(url_for('index'))
        return f(*args, **kwargs)

    return decorated


@app.route('/moderation')
@teacher_required
def moderation():
    pending = Achievement.query.filter_by(status='pending').order_by(Achievement.date.desc()).all()
    return render_template('moderation.html', achievements=pending)


@app.route('/approve/<int:achievement_id>')
@teacher_required
def approve(achievement_id):
    achievement = Achievement.query.get_or_404(achievement_id)
    achievement.status = 'approved'
    achievement.reviewed_by_id = current_user.id
    achievement.reviewed_at = datetime.utcnow()
    db.session.commit()
    flash(f'Достижение "{achievement.title}" одобрено!', 'success')
    return redirect(url_for('moderation'))


@app.route('/reject/<int:achievement_id>', methods=['POST'])
@teacher_required
def reject(achievement_id):
    achievement = Achievement.query.get_or_404(achievement_id)
    reason = request.form.get('reason', 'Не соответствует требованиям')

    achievement.status = 'rejected'
    achievement.reviewed_by_id = current_user.id
    achievement.reviewed_at = datetime.utcnow()
    achievement.rejection_reason = reason
    db.session.commit()

    flash(f'Достижение "{achievement.title}" отклонено', 'error')
    return redirect(url_for('moderation'))

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        name = request.form.get('name')
        password = request.form.get('password')
        password_confirm = request.form.get('password_confirm')

        if User.query.filter_by(username=username).first():
            flash('Такой логин уже занят', 'error')
            return redirect(url_for('register'))

        if password != password_confirm:
            flash('Пароли не совпадают', 'error')
            return redirect(url_for('register'))

        if len(password) < 6:
            flash('Пароль должен быть не короче 6 символов', 'error')
            return redirect(url_for('register'))

        # Создаём пользователя
        user = User(username=username, name=name, role='student')
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        flash('Регистрация успешна! Войдите в систему', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password):
            login_user(user)
            flash('Вы вошли в систему', 'success')
            return redirect(url_for('index'))
        else:
            flash('Неверный логин или пароль', 'error')

    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Вы вышли из системы', 'success')
    return redirect(url_for('index'))


@app.route('/achievements')
def achievements():
    if current_user.is_authenticated:
        items = Achievement.query.filter(
            db.or_(
                Achievement.status == 'approved',
                Achievement.author_id == current_user.id
            )
        ).order_by(Achievement.date.desc()).all()
    else:
        items = Achievement.query.filter_by(status='approved').order_by(Achievement.date.desc()).all()

    return render_template('achievements.html', achievements=items)


@app.route('/gallery')
def gallery():
    photos = Photo.query.order_by(Photo.uploaded_at.desc()).all()
    return render_template('gallery.html', photos=photos)


@app.route('/schedule')
def schedule():
    days = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота']
    schedule_data = {}
    for day in days:
        items = ScheduleItem.query.filter_by(day_of_week=day).order_by(ScheduleItem.lesson_number).all()
        if items:
            schedule_data[day] = items
    return render_template('schedule.html', schedule=schedule_data)


ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/add_achievement', methods=['GET', 'POST'])
@login_required
def add_achievement():
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        date_str = request.form.get('date')
        file = request.files.get('image')

        if not file or file.filename == '':
            flash('Необходимо прикрепить фото-доказательство (грамота, диплом)', 'error')
            return redirect(url_for('add_achievement'))

        if not allowed_file(file.filename):
            flash('Неподдерживаемый формат файла. Используйте jpg, png или gif', 'error')
            return redirect(url_for('add_achievement'))

        image_filename = secure_filename(file.filename)
        # Добавляем уникальность к имени файла
        unique_filename = f"{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{image_filename}"
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], unique_filename))

        try:
            date_obj = datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else datetime.utcnow().date()
        except ValueError:
            date_obj = datetime.utcnow().date()

        new_achievement = Achievement(
            title=title,
            description=description,
            date=date_obj,
            image=unique_filename,
            author_id=current_user.id,
            status='pending'
        )
        db.session.add(new_achievement)
        db.session.commit()

        flash('Достижение отправлено на модерацию! Оно появится на сайте после проверки.', 'success')
        return redirect(url_for('achievements'))

    return render_template('add_achievement.html')


@app.route('/add_photo', methods=['GET', 'POST'])
@login_required
def add_photo():
    if request.method == 'POST':
        caption = request.form.get('caption')
        file = request.files.get('photo')

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

            new_photo = Photo(filename=filename, caption=caption)
            db.session.add(new_photo)
            db.session.commit()

            flash('Фотография успешно добавлена!', 'success')
            return redirect(url_for('gallery'))
        else:
            flash('Ошибка: файл не выбран или формат не поддерживается (jpg, png, gif)', 'error')

    return render_template('add_photo.html')


@app.route('/olympiads')
def olympiads():
    web_olympiads = get_olympiads_from_web()
    return render_template('olympiads.html', olympiads=web_olympiads)


with app.app_context():
    db.drop_all()
    db.create_all()

    # Создаём админа
    if not User.query.first():
        admin = User(username='admin', name='Администратор', role='admin')
        admin.set_password('admin123')

        # Создаём учителя для тестов
        teacher = User(username='teacher', name='Мария Ивановна', role='teacher')
        teacher.set_password('teacher123')

        # Создаём обычного ученика
        student = User(username='student', name='Иван Петров', role='student')
        student.set_password('student123')

        db.session.add_all([admin, teacher, student])
        db.session.commit()
        print('Созданы тестовые пользователи:')
        print('admin / admin123     (может одобрять)')
        print('teacher / teacher123 (может одобрять)')
        print('student / student123  (может только добавлять)')


if __name__ == '__main__':
    app.run(debug=True)
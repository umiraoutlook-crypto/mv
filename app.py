"""
Application Management & Job Portal System
Features:
- Admin Portal: Dashboard analytics, full CRUD for Job Openings, Candidate Application review with workflow statuses and internal notes
- Candidate Portal: Browse active openings with search and department filtering, streamlined application with resume upload, and application tracking dashboard
"""

import os
import datetime
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, session, abort
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_wtf import FlaskForm, CSRFProtect
from wtforms import StringField, TextAreaField, SelectField, DateField, IntegerField, FileField, EmailField, PasswordField
from wtforms.validators import DataRequired, Email, EqualTo, Optional, Length
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from pymongo import MongoClient
from bson.objectid import ObjectId
import cloudinary
import cloudinary.uploader

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-super-safe-987123')
csrf = CSRFProtect(app)

# Local upload directory fallback
UPLOAD_FOLDER = os.path.join(app.root_path, 'static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access this page.'
login_manager.login_message_category = 'info'

# MongoDB Configuration
MONGODB_URI = os.environ.get('MONGODB_URI', 'mongodb+srv://umiraoutlook_db_user:umira123@cluster0.x4b4h0j.mongodb.net/')
MONGODB_DB_NAME = os.environ.get('MONGODB_DB_NAME', 'app_management')

client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
db = client[MONGODB_DB_NAME]
users_collection = db.users
openings_collection = db.openings
applications_collection = db.applications

# Cloudinary Configuration
cloudinary.config(
    cloud_name=os.environ.get('CLOUDINARY_CLOUD_NAME', 'dg3rlnf8q'),
    api_key=os.environ.get('CLOUDINARY_API_KEY', '266774597493594'),
    api_secret=os.environ.get('CLOUDINARY_API_SECRET', '266774597493594')
)

# Indexes
try:
    users_collection.create_index([('email', 1)], unique=True)
    applications_collection.create_index([('applicant_id', 1), ('opening_id', 1)], unique=True)
except Exception as e:
    print(f"Index initialization note: {e}")

# Admin User Definition
ADMIN_ID = '000000000000000000000001'
ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME', 'admin')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'admin123')

ADMIN_DATA = {
    '_id': ObjectId(ADMIN_ID),
    'name': 'System Administrator',
    'email': ADMIN_USERNAME,
    'role': 'admin'
}


class User(UserMixin):
    def __init__(self, user_data):
        self.id = str(user_data['_id'])
        self.name = user_data.get('name', 'User')
        self.email = user_data.get('email', '')
        self.role = user_data.get('role', 'user')

    def is_admin(self):
        return self.role == 'admin'

    def get_id(self):
        return self.id


@login_manager.user_loader
def load_user(user_id):
    # Support hardcoded/system admin
    if str(user_id) == ADMIN_ID:
        return User(ADMIN_DATA)
    try:
        user_data = users_collection.find_one({'_id': ObjectId(user_id)})
        if user_data:
            return User(user_data)
        return None
    except Exception:
        return None


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.is_authenticated and current_user.role == 'admin':
            return f(*args, **kwargs)
        if current_user.is_authenticated:
            logout_user()
        flash('Administrator privileges required. Opening the Admin Portal login.', 'info')
        return redirect(url_for('login', next=request.path, role='admin'))
    return decorated_function


@login_manager.unauthorized_handler
def unauthorized():
    next_url = request.path
    if next_url.startswith('/admin'):
        return redirect(url_for('login', next=next_url, role='admin'))
    flash(login_manager.login_message, login_manager.login_message_category)
    return redirect(url_for('login', next=next_url))


# Jinja Custom Filters
@app.template_filter('format_date')
def format_date_filter(val, fmt='%b %d, %Y'):
    if not val:
        return 'N/A'
    if isinstance(val, (datetime.datetime, datetime.date)):
        return val.strftime(fmt)
    try:
        dt = datetime.datetime.fromisoformat(str(val))
        return dt.strftime(fmt)
    except Exception:
        return str(val)


# Forms
class LoginForm(FlaskForm):
    email = StringField('Email / Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])


class RegisterForm(FlaskForm):
    name = StringField('Full Name', validators=[DataRequired(), Length(min=2, max=80)])
    email = EmailField('Email Address', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6, message='Password must be at least 6 characters')])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password', message='Passwords must match')])


class OpeningForm(FlaskForm):
    title = StringField('Job Title', validators=[DataRequired(), Length(max=150)])
    department = SelectField('Department', choices=[
        ('Engineering', 'Engineering / Software'),
        ('Product', 'Product Management'),
        ('Design', 'UI/UX Design'),
        ('Marketing', 'Marketing & Growth'),
        ('Sales', 'Sales & Business Dev'),
        ('Operations', 'Operations & Logistics'),
        ('Human Resources', 'Human Resources'),
        ('Finance', 'Finance & Accounting'),
        ('Other', 'Other')
    ], default='Engineering')
    job_type = SelectField('Job Type', choices=[
        ('Full-Time', 'Full-Time'),
        ('Part-Time', 'Part-Time'),
        ('Remote', 'Remote'),
        ('Hybrid', 'Hybrid'),
        ('Contract', 'Contract'),
        ('Internship', 'Internship')
    ], default='Full-Time')
    location = StringField('Location', validators=[DataRequired()], default='Remote')
    salary_range = StringField('Salary Range (e.g. $80k - $110k)', validators=[Optional()])
    experience_level = SelectField('Experience Level', choices=[
        ('Entry Level', 'Entry Level (0-2 years)'),
        ('Mid Level', 'Mid Level (2-5 years)'),
        ('Senior Level', 'Senior Level (5+ years)'),
        ('Lead / Executive', 'Lead / Executive')
    ], default='Mid Level')
    description = TextAreaField('Job Description & Responsibilities', validators=[DataRequired()])
    requirements = TextAreaField('Key Requirements & Qualifications', validators=[Optional()])
    deadline = DateField('Application Deadline', validators=[DataRequired()])
    status = SelectField('Status', choices=[('active', 'Active (Open for applications)'), ('closed', 'Closed')], default='active')


class ApplicationForm(FlaskForm):
    name = StringField('Full Name', validators=[DataRequired()])
    email = EmailField('Email Address', validators=[DataRequired(), Email()])
    phone = StringField('Phone Number (Optional)', validators=[Optional()])
    portfolio_url = StringField('Portfolio / LinkedIn URL (Optional)', validators=[Optional()])
    resume = FileField('Resume / CV (PDF or DOCX)', validators=[DataRequired()])
    cover_letter = TextAreaField('Cover Letter / Pitch', validators=[DataRequired()])


class ApplicationStatusForm(FlaskForm):
    status = SelectField('Application Status', choices=[
        ('Submitted', 'Submitted (New)'),
        ('Under Review', 'Under Review'),
        ('Shortlisted', 'Shortlisted'),
        ('Interview Scheduled', 'Interview Scheduled'),
        ('Accepted', 'Accepted / Offered'),
        ('Rejected', 'Rejected')
    ], validators=[DataRequired()])
    admin_notes = TextAreaField('Internal Hiring Notes / Feedback', validators=[Optional()])


class AdminEnterForm(FlaskForm):
    pass


# File Upload Helper
ALLOWED_RESUME_EXTENSIONS = {'.pdf', '.doc', '.docx'}


def allowed_resume(filename):
    ext = os.path.splitext(filename or '')[1].lower()
    return ext in ALLOWED_RESUME_EXTENSIONS


def upload_resume_file(file_data):
    if not file_data or not file_data.filename:
        return None
    if not allowed_resume(file_data.filename):
        return None
    try:
        # Try uploading to Cloudinary
        result = cloudinary.uploader.upload(
            file_data,
            resource_type='auto',
            folder='portal_resumes'
        )
        return result.get('secure_url')
    except Exception as e:
        print(f"Cloudinary upload fallback: {e}")
        # Local upload fallback so candidates never get blocked
        filename = secure_filename(f"{int(datetime.datetime.utcnow().timestamp())}_{file_data.filename}")
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file_data.seek(0)
        file_data.save(file_path)
        return f"/static/uploads/{filename}"


# Seed default openings if collection is completely empty
def seed_initial_openings_if_empty():
    try:
        if openings_collection.count_documents({}) == 0:
            sample_openings = [
                {
                    'title': 'Senior Full Stack Python / React Engineer',
                    'department': 'Engineering',
                    'job_type': 'Full-Time',
                    'location': 'Remote (Global)',
                    'salary_range': '$110,000 - $140,000 / year',
                    'experience_level': 'Senior Level',
                    'description': 'We are looking for an experienced Full Stack Engineer to lead web application development using Python (Flask/FastAPI), modern frontend frameworks, and distributed cloud services.',
                    'requirements': '• 4+ years of Python and React/TypeScript development\n• Experience with REST APIs and MongoDB/PostgreSQL\n• Strong system design and unit testing practices',
                    'deadline': datetime.datetime.utcnow() + datetime.timedelta(days=30),
                    'status': 'active',
                    'created_at': datetime.datetime.utcnow()
                },
                {
                    'title': 'Product & UI/UX Designer',
                    'department': 'Design',
                    'job_type': 'Full-Time',
                    'location': 'New York, NY / Hybrid',
                    'salary_range': '$95,000 - $125,000 / year',
                    'experience_level': 'Mid Level',
                    'description': 'Help us craft seamless, intuitive user experiences across our core application management suite and candidate dashboards.',
                    'requirements': '• Strong portfolio showcasing web & mobile product design\n• Expertise in Figma, prototyping, and design systems\n• Empathy for end-users and analytical mindset',
                    'deadline': datetime.datetime.utcnow() + datetime.timedelta(days=21),
                    'status': 'active',
                    'created_at': datetime.datetime.utcnow()
                },
                {
                    'title': 'Technical Product Manager',
                    'department': 'Product',
                    'job_type': 'Full-Time',
                    'location': 'San Francisco, CA / Remote',
                    'salary_range': '$120,000 - $155,000 / year',
                    'experience_level': 'Senior Level',
                    'description': 'Drive roadmap vision, coordinate cross-functional engineering teams, and deliver game-changing recruitment workflow automation.',
                    'requirements': '• 3+ years in tech product management\n• Proven track record shipping SaaS features from 0 to 1\n• Superb communication and backlog prioritization skills',
                    'deadline': datetime.datetime.utcnow() + datetime.timedelta(days=45),
                    'status': 'active',
                    'created_at': datetime.datetime.utcnow()
                }
            ]
            openings_collection.insert_many(sample_openings)
            print("Seeded sample job openings successfully.")
    except Exception as e:
        print(f"Could not seed openings: {e}")


# Run seed once on startup
try:
    seed_initial_openings_if_empty()
except Exception:
    pass


# ==================== ROUTES ====================

@app.route('/')
def home():
    now = datetime.datetime.utcnow()
    # Find active openings whose deadline hasn't passed
    query = {
        'status': {'$ne': 'closed'},
        'deadline': {'$gte': now - datetime.timedelta(days=1)}
    }
    openings = list(openings_collection.find(query).sort('created_at', -1))
    
    # Check which openings current user has applied for
    applied_ids = set()
    if current_user.is_authenticated and current_user.role == 'user':
        user_apps = applications_collection.find({'applicant_id': ObjectId(current_user.id)}, {'opening_id': 1})
        applied_ids = {str(app_item['opening_id']) for app_item in user_apps}

    # Collect distinct departments for search filter
    departments = sorted(list({o.get('department', 'Engineering') for o in openings if o.get('department')}))

    return render_template('home.html', openings=openings, applied_ids=applied_ids, departments=departments)


@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        if current_user.role == 'admin':
            return redirect(url_for('admin_dashboard'))
        return redirect(url_for('home'))

    form = RegisterForm()
    if form.validate_on_submit():
        existing_user = users_collection.find_one({'email': form.email.data.strip().lower()})
        if existing_user:
            flash('This email address is already registered. Please login.', 'warning')
            return redirect(url_for('login'))

        user_data = {
            'name': form.name.data.strip(),
            'email': form.email.data.strip().lower(),
            'password': generate_password_hash(form.password.data),
            'role': 'user',
            'created_at': datetime.datetime.utcnow()
        }
        users_collection.insert_one(user_data)
        flash('Account created successfully! Please log in to continue.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html', form=form)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        if current_user.role == 'admin':
            return redirect(url_for('admin_dashboard'))
        return redirect(url_for('home'))

    form = LoginForm()
    next_page = request.args.get('next')

    if form.validate_on_submit():
        email_or_user = form.email.data.strip()
        pwd = form.password.data

        # 1. Check Hardcoded / Environment Admin Credentials
        if (email_or_user.lower() == ADMIN_USERNAME.lower() or email_or_user.lower() == 'admin') and pwd == ADMIN_PASSWORD:
            login_user(User(ADMIN_DATA))
            flash('Welcome to the Admin Portal!', 'success')
            return redirect(next_page or url_for('admin_dashboard'))

        # 2. Check Database Users
        user_data = users_collection.find_one({'email': email_or_user.lower()})
        if user_data and check_password_hash(user_data['password'], pwd):
            user_obj = User(user_data)
            login_user(user_obj)
            flash(f'Welcome back, {user_obj.name}!', 'success')
            if user_obj.role == 'admin':
                return redirect(next_page or url_for('admin_dashboard'))
            return redirect(next_page or url_for('home'))

        flash('Invalid email/username or password. Please try again.', 'danger')

    return render_template('login.html', form=form, next_page=next_page)


@app.route('/admin/login')
def admin_login_redirect():
    """Direct convenience route to guide users straight to admin authentication"""
    if current_user.is_authenticated:
        if current_user.role == 'admin':
            return redirect(url_for('admin_dashboard'))
        flash('Switched out of your candidate session so you can enter the Admin Portal.', 'info')
        logout_user()
    return redirect(url_for('login', next=url_for('admin_dashboard'), role='admin'))


@app.route('/admin/enter', methods=['GET', 'POST'], endpoint='admin_enter')
def admin_enter():
    """One-click demo login into the Admin Portal."""
    if request.method == 'POST':
        form = AdminEnterForm()
        if not form.validate_on_submit():
            flash('Could not verify the request. Please try Admin Portal again.', 'warning')
            return redirect(url_for('login', role='admin', next=url_for('admin_dashboard')))
    if current_user.is_authenticated and current_user.role == 'admin':
        return redirect(url_for('admin_dashboard'))
    if current_user.is_authenticated:
        logout_user()
    login_user(User(ADMIN_DATA))
    flash('Welcome to the Admin Portal!', 'success')
    return redirect(url_for('admin_dashboard'))


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out successfully.', 'info')
    return redirect(url_for('home'))


@app.route('/opening/<id>')
def opening_detail(id):
    try:
        opening = openings_collection.find_one({'_id': ObjectId(id)})
    except Exception:
        flash('Invalid opening ID format.', 'danger')
        return redirect(url_for('home'))

    if not opening:
        flash('Job opening not found or no longer active.', 'danger')
        return redirect(url_for('home'))

    applied = False
    existing_application = None
    if current_user.is_authenticated and current_user.role == 'user':
        existing_application = applications_collection.find_one({
            'applicant_id': ObjectId(current_user.id),
            'opening_id': ObjectId(id)
        })
        applied = existing_application is not None

    # Calculate days left
    days_left = None
    if opening.get('deadline'):
        delta = opening['deadline'] - datetime.datetime.utcnow()
        days_left = max(0, delta.days)

    return render_template('opening_detail.html', opening=opening, applied=applied, existing_application=existing_application, days_left=days_left)


@app.route('/apply/<id>', methods=['GET', 'POST'])
@login_required
def apply(id):
    if current_user.role != 'user':
        flash('Administrators cannot submit candidate applications.', 'warning')
        return redirect(url_for('opening_detail', id=id))

    try:
        opening = openings_collection.find_one({'_id': ObjectId(id)})
    except Exception:
        flash('Invalid opening ID.', 'danger')
        return redirect(url_for('home'))

    if not opening:
        flash('Job opening not found.', 'danger')
        return redirect(url_for('home'))

    # Check if deadline passed
    if opening.get('deadline') and opening['deadline'] < datetime.datetime.utcnow():
        flash('The application deadline for this opening has passed.', 'warning')
        return redirect(url_for('opening_detail', id=id))

    # Check if already applied
    already_applied = applications_collection.find_one({
        'applicant_id': ObjectId(current_user.id),
        'opening_id': ObjectId(id)
    })
    if already_applied:
        flash('You have already applied for this opening.', 'info')
        return redirect(url_for('my_applications'))

    form = ApplicationForm()

    # Pre-populate fields from current user on GET
    if request.method == 'GET':
        form.name.data = current_user.name
        form.email.data = current_user.email

    if form.validate_on_submit():
        if not allowed_resume(form.resume.data.filename if form.resume.data else ''):
            flash('Please upload a PDF or Word document (.pdf, .doc, .docx).', 'danger')
            return render_template('apply.html', form=form, opening=opening)

        resume_url = upload_resume_file(form.resume.data)
        if not resume_url:
            flash('Error processing your resume file. Please upload a valid document (.pdf, .docx).', 'danger')
            return render_template('apply.html', form=form, opening=opening)

        application_data = {
            'applicant_id': ObjectId(current_user.id),
            'opening_id': ObjectId(id),
            'opening_title': opening.get('title', 'Position'),
            'department': opening.get('department', 'General'),
            'name': form.name.data.strip(),
            'email': form.email.data.strip(),
            'phone': form.phone.data.strip() if form.phone.data else '',
            'portfolio_url': form.portfolio_url.data.strip() if form.portfolio_url.data else '',
            'resume': resume_url,
            'cover_letter': form.cover_letter.data.strip(),
            'status': 'Submitted',
            'admin_notes': '',
            'applied_at': datetime.datetime.utcnow(),
            'updated_at': datetime.datetime.utcnow()
        }

        try:
            applications_collection.insert_one(application_data)
            flash('Your application was submitted successfully! You can track its status in "My Applications".', 'success')
            return redirect(url_for('my_applications'))
        except Exception as e:
            flash(f'An error occurred while saving your application: {e}', 'danger')

    return render_template('apply.html', form=form, opening=opening)


@app.route('/my-applications')
@login_required
def my_applications():
    if current_user.role != 'user':
        flash('Access denied.', 'danger')
        return redirect(url_for('home'))

    applications = list(applications_collection.find({'applicant_id': ObjectId(current_user.id)}).sort('applied_at', -1))

    # Enrich applications with current opening info (title, location, active status)
    for app_item in applications:
        opening = openings_collection.find_one({'_id': app_item['opening_id']})
        if opening:
            app_item['opening_title'] = opening.get('title', 'Position')
            app_item['opening_department'] = opening.get('department', 'General')
            app_item['opening_location'] = opening.get('location', 'Remote')
            app_item['opening_status'] = opening.get('status', 'active')
        else:
            app_item['opening_title'] = app_item.get('opening_title', 'Archived Position')
            app_item['opening_department'] = app_item.get('department', 'General')
            app_item['opening_location'] = 'N/A'
            app_item['opening_status'] = 'archived'

    return render_template('my_applications.html', applications=applications)


@app.route('/application/<id>/withdraw', methods=['POST'])
@login_required
def withdraw_application(id):
    if current_user.role != 'user':
        abort(403)
    try:
        res = applications_collection.delete_one({
            '_id': ObjectId(id),
            'applicant_id': ObjectId(current_user.id),
            'status': {'$in': ['Submitted', 'Under Review']}
        })
        if res.deleted_count > 0:
            flash('Your application was withdrawn successfully.', 'info')
        else:
            flash('Application could not be withdrawn.', 'warning')
    except Exception as e:
        flash(f'Error withdrawing application: {e}', 'danger')

    return redirect(url_for('my_applications'))


# ==================== ADMIN PORTAL ROUTES ====================

@app.route('/admin')
@admin_required
def admin_dashboard():
    openings = list(openings_collection.find().sort('created_at', -1))
    applications = list(applications_collection.find().sort('applied_at', -1))

    # Build opening lookup map & count applicants per opening
    openings_map = {str(o['_id']): o for o in openings}
    openings_app_counts = {str(o['_id']): 0 for o in openings}

    for app_item in applications:
        op_id_str = str(app_item.get('opening_id'))
        if op_id_str in openings_map:
            app_item['opening_title'] = openings_map[op_id_str].get('title', 'Job Opening')
            app_item['opening_department'] = openings_map[op_id_str].get('department', '')
            openings_app_counts[op_id_str] = openings_app_counts.get(op_id_str, 0) + 1
        else:
            app_item['opening_title'] = app_item.get('opening_title', 'Archived Opening')
            app_item['opening_department'] = app_item.get('department', 'General')

    for o in openings:
        o['applicant_count'] = openings_app_counts.get(str(o['_id']), 0)

    # Compute high-level dashboard metrics
    total_openings = len(openings)
    active_openings = sum(1 for o in openings if o.get('status', 'active') == 'active' and (not o.get('deadline') or o['deadline'] >= datetime.datetime.utcnow()))
    total_applications = len(applications)
    pending_reviews = sum(1 for a in applications if a.get('status') in ['Submitted', 'Under Review'])
    shortlisted_accepted = sum(1 for a in applications if a.get('status') in ['Shortlisted', 'Interview Scheduled', 'Accepted'])

    stats = {
        'total_openings': total_openings,
        'active_openings': active_openings,
        'total_applications': total_applications,
        'pending_reviews': pending_reviews,
        'shortlisted_accepted': shortlisted_accepted
    }

    return render_template('admin.html', openings=openings, applications=applications, stats=stats)


@app.route('/admin/create-opening', methods=['GET', 'POST'])
@admin_required
def create_opening():
    form = OpeningForm()
    if form.validate_on_submit():
        # Set deadline to end of chosen day (23:59:59)
        deadline_dt = datetime.datetime.combine(form.deadline.data, datetime.time(23, 59, 59))
        
        opening_data = {
            'title': form.title.data.strip(),
            'department': form.department.data,
            'job_type': form.job_type.data,
            'location': form.location.data.strip(),
            'salary_range': form.salary_range.data.strip() if form.salary_range.data else '',
            'experience_level': form.experience_level.data,
            'description': form.description.data.strip(),
            'requirements': form.requirements.data.strip() if form.requirements.data else '',
            'deadline': deadline_dt,
            'status': form.status.data,
            'created_at': datetime.datetime.utcnow(),
            'updated_at': datetime.datetime.utcnow()
        }
        openings_collection.insert_one(opening_data)
        flash(f'Job opening "{form.title.data}" created successfully!', 'success')
        return redirect(url_for('admin_dashboard'))

    return render_template('create_opening.html', form=form, is_edit=False)


@app.route('/admin/opening/<id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_opening(id):
    try:
        opening = openings_collection.find_one({'_id': ObjectId(id)})
    except Exception:
        flash('Invalid opening ID.', 'danger')
        return redirect(url_for('admin_dashboard'))

    if not opening:
        flash('Opening not found.', 'danger')
        return redirect(url_for('admin_dashboard'))

    form = OpeningForm()

    if request.method == 'GET':
        form.title.data = opening.get('title', '')
        form.department.data = opening.get('department', 'Engineering')
        form.job_type.data = opening.get('job_type', 'Full-Time')
        form.location.data = opening.get('location', 'Remote')
        form.salary_range.data = opening.get('salary_range', '')
        form.experience_level.data = opening.get('experience_level', 'Mid Level')
        form.description.data = opening.get('description', '')
        form.requirements.data = opening.get('requirements', '')
        if opening.get('deadline'):
            form.deadline.data = opening['deadline'].date() if isinstance(opening['deadline'], datetime.datetime) else opening['deadline']
        form.status.data = opening.get('status', 'active')

    if form.validate_on_submit():
        deadline_dt = datetime.datetime.combine(form.deadline.data, datetime.time(23, 59, 59))
        updates = {
            'title': form.title.data.strip(),
            'department': form.department.data,
            'job_type': form.job_type.data,
            'location': form.location.data.strip(),
            'salary_range': form.salary_range.data.strip() if form.salary_range.data else '',
            'experience_level': form.experience_level.data,
            'description': form.description.data.strip(),
            'requirements': form.requirements.data.strip() if form.requirements.data else '',
            'deadline': deadline_dt,
            'status': form.status.data,
            'updated_at': datetime.datetime.utcnow()
        }
        openings_collection.update_one({'_id': ObjectId(id)}, {'$set': updates})
        flash(f'Job opening "{form.title.data}" updated successfully!', 'success')
        return redirect(url_for('admin_dashboard'))

    return render_template('create_opening.html', form=form, is_edit=True, opening=opening)


@app.route('/admin/opening/<id>/toggle-status', methods=['POST'])
@admin_required
def toggle_opening_status(id):
    try:
        opening = openings_collection.find_one({'_id': ObjectId(id)})
        if opening:
            current_status = opening.get('status', 'active')
            new_status = 'closed' if current_status == 'active' else 'active'
            openings_collection.update_one({'_id': ObjectId(id)}, {'$set': {'status': new_status, 'updated_at': datetime.datetime.utcnow()}})
            flash(f'Opening "{opening.get("title")}" marked as {new_status.upper()}.', 'info')
    except Exception as e:
        flash(f'Error updating opening status: {e}', 'danger')

    return redirect(url_for('admin_dashboard'))


@app.route('/admin/opening/<id>/delete', methods=['POST'])
@admin_required
def delete_opening(id):
    try:
        res = openings_collection.delete_one({'_id': ObjectId(id)})
        if res.deleted_count > 0:
            flash('Opening deleted successfully.', 'success')
        else:
            flash('Opening not found.', 'warning')
    except Exception as e:
        flash(f'Error deleting opening: {e}', 'danger')

    return redirect(url_for('admin_dashboard'))


@app.route('/admin/application/<id>', methods=['GET'])
@admin_required
def view_application(id):
    try:
        application = applications_collection.find_one({'_id': ObjectId(id)})
    except Exception:
        flash('Invalid application ID.', 'danger')
        return redirect(url_for('admin_dashboard'))

    if not application:
        flash('Application not found.', 'danger')
        return redirect(url_for('admin_dashboard'))

    opening = openings_collection.find_one({'_id': application.get('opening_id')})
    status_form = ApplicationStatusForm()
    status_form.status.data = application.get('status', 'Submitted')
    status_form.admin_notes.data = application.get('admin_notes', '')

    return render_template('view_application.html', application=application, opening=opening, status_form=status_form)


@app.route('/admin/application/<id>/status', methods=['POST'])
@admin_required
def update_application_status(id):
    status_form = ApplicationStatusForm()
    if status_form.validate_on_submit():
        new_status = status_form.status.data
        notes = status_form.admin_notes.data or ''
        try:
            applications_collection.update_one(
                {'_id': ObjectId(id)},
                {
                    '$set': {
                        'status': new_status,
                        'admin_notes': notes,
                        'updated_at': datetime.datetime.utcnow()
                    }
                }
            )
            flash(f'Application status updated to "{new_status}".', 'success')
        except Exception as e:
            flash(f'Error updating application status: {e}', 'danger')
    return redirect(url_for('view_application', id=id))


@app.route('/admin/application/<id>/delete', methods=['POST'])
@admin_required
def delete_application(id):
    try:
        applications_collection.delete_one({'_id': ObjectId(id)})
        flash('Application removed successfully.', 'info')
    except Exception as e:
        flash(f'Error deleting application: {e}', 'danger')
    return redirect(url_for('admin_dashboard'))


# Make common variables available to all templates
@app.context_processor
def inject_common_variables():
    return {
        'now': datetime.datetime.utcnow(),
        'admin_username': ADMIN_USERNAME,
        'str': str
    }


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

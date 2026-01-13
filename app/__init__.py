from flask import Flask
from pymongo import MongoClient

app = Flask(__name__, template_folder='templates')
app.config['SECRET_KEY'] = '3f34d03d85aacf85899832be427defb2'

# Database configuration
client = MongoClient('mongodb://localhost:27017') 
db = client['UniDatabase']

staff_collection = db['Staff Collection']
courses_collection = db['Courses Collection']
programs_collection = db['Programs Collection']
schools_collection = db['Schools Collection']
departments_collection = db['Departments Collection']
students_collection = db['Student Information']
student_courses_collection = db['Student-Courses Collection']
grades_collection = db['Grades']
mock_grades_collection = db['Mock Grades']  
ca_collection = db['Continus Assessment']
accounts_collection = db['Accounts']
news_collection = db['News']
users_collection = db ['Users']
exam_slip_config_collection = db['exam_slip_config']
audit_log_collection = db['Audit Logs']

from app.routes import (home, staff, courses_program, student, grades, ca, accounts,
 news_feed, login, contact, exam_slip, grades_modify, modify_accounts, audit_log)

app.register_blueprint(home.bp)
app.register_blueprint(staff.bp)
app.register_blueprint(courses_program.bp)
app.register_blueprint(student.bp)
app.register_blueprint(grades.bp)
app.register_blueprint(ca.bp)
app.register_blueprint(accounts.bp)
app.register_blueprint(news_feed.bp)
app.register_blueprint(login.bp)
app.register_blueprint(contact.bp)
app.register_blueprint(exam_slip.bp)
app.register_blueprint(grades_modify.bp)
app.register_blueprint(modify_accounts.modify_bp)
app.register_blueprint(audit_log.bp)

# Add this to your app initialization
def create_grades_indexes():
    grades_collection.create_index([('student_id', 1), ('exam_type', 1), ('academic_year', 1), ('semester', 1)])
    grades_collection.create_index([('course_id', 1)])
    grades_collection.create_index([('entered_at', -1)])
    
    # Create indexes for mock grades collection
    mock_grades_collection.create_index([('student_id', 1), ('academic_year', 1), ('semester', 1)])
    mock_grades_collection.create_index([('course_id', 1)])
    mock_grades_collection.create_index([('entered_at', -1)])
    
create_grades_indexes()

# Create indexes for better performance
users_collection.create_index([('username', 1)], unique=True, sparse=True)
users_collection.create_index([('student_number', 1)], unique=True, sparse=True)
users_collection.create_index([('email', 1)], unique=True)
users_collection.create_index([('student_id', 1)], unique=True, sparse=True)
users_collection.create_index([('staff_id', 1)], unique=True, sparse=True)


def create_audit_indexes():
    audit_log_collection.create_index([('timestamp', -1)])
    audit_log_collection.create_index([('user_id', 1)])
    audit_log_collection.create_index([('action', 1)])
    audit_log_collection.create_index([('category', 1)])
    audit_log_collection.create_index([('status', 1)])
    audit_log_collection.create_index([('username', 1)])
    audit_log_collection.create_index([('ip_address', 1)])
    audit_log_collection.create_index([('student_id', 1)])
    audit_log_collection.create_index([('staff_id', 1)])
    audit_log_collection.create_index([('collection_name', 1)])

create_audit_indexes()

@app.template_filter('number_format')
def number_format(value):
    """Format numbers with thousands separators"""
    if value is None:
        return "0"
    try:
        return f"{int(value):,}"
    except (ValueError, TypeError):
        return str(value)
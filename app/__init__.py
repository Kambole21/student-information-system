from flask import Flask
from pymongo import MongoClient

app = Flask(__name__, template_folder='templates')
app.config['SECRET_KEY'] = '3f34d03d85aacf85899832be427defb2'

# Database configuration
client = MongoClient('mongodb://localhost:27017/') 
db = client['Uniberg_b']

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

from app.routes import home, staff, courses_program, student, grades, ca

app.register_blueprint(home.bp)
app.register_blueprint(staff.bp)
app.register_blueprint(courses_program.bp)
app.register_blueprint(student.bp)
app.register_blueprint(grades.bp)
app.register_blueprint(ca.bp)

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
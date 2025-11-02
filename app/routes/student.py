from flask import Blueprint, render_template, request, flash, redirect, url_for, session, jsonify
from werkzeug.security import generate_password_hash
from werkzeug.utils import secure_filename
import os
from app import students_collection, schools_collection, programs_collection, courses_collection, student_courses_collection, grades_collection, mock_grades_collection  # Added mock_grades_collection
from bson import ObjectId
import uuid
from datetime import datetime
import random
import string

bp = Blueprint('student', __name__)

def generate_auto_password(length=4):
    """Generate auto password with letters and numbers"""
    characters = string.ascii_letters + string.digits
    return ''.join(random.choice(characters) for _ in range(length))

# Allowed extensions for profile images
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
UPLOAD_FOLDER = 'app/static/uploads/students'

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_academic_years():
    """Generate academic years from 2020 to 2030"""
    current_year = datetime.now().year
    academic_years = []
    for year in range(2019, 2050):
        academic_years.append(f"{year}/{year+1}")
    return academic_years

@bp.route('/Student')
def student_management():
    """Student management dashboard"""
    total_students = students_collection.count_documents({})
    active_students = students_collection.count_documents({'status': 'active'})
    return render_template('users/student/student_dashboard.html', 
                         total_students=total_students,
                         active_students=active_students)

@bp.route('/student/registration')
def student_registration():
    """Student registration page"""
    schools = list(schools_collection.find({'status': 'active'}))
    programs = list(programs_collection.find({'status': 'active'}))
    academic_years = get_academic_years()
    return render_template('users/student/student_registration.html', 
                         schools=schools, 
                         programs=programs,
                         academic_years=academic_years,
                         datetime=datetime)

@bp.route('/student/list')
def student_list():
    """Student list page"""
    students = list(students_collection.find())
    # Get school and program names for display
    schools_dict = {str(school['_id']): school['name'] for school in schools_collection.find()}
    programs_dict = {str(program['_id']): program['name'] for program in programs_collection.find()}
    
    return render_template('users/student/student_list.html', 
                         students=students,
                         schools_dict=schools_dict,
                         programs_dict=programs_dict)

@bp.route('/student/profile/<student_id>')
def student_profile(student_id):
    """Student profile page"""
    try:
        student = students_collection.find_one({'_id': ObjectId(student_id)})
        if not student:
            flash('Student not found!', 'error')
            return redirect(url_for('student.student_list'))
        
        # Get school and program details
        school = schools_collection.find_one({'_id': ObjectId(student['school_id'])}) if student.get('school_id') else None
        program = programs_collection.find_one({'_id': ObjectId(student['program_id'])}) if student.get('program_id') else None
        
        # Get enrolled courses - only show 5 most recent
        enrolled_courses = list(student_courses_collection.find(
            {'student_id': ObjectId(student_id)}
        ).sort([('enrolled_at', -1)]).limit(5)) # Sort by enrollment date, get only 5
        
        courses_info = []
        
        for ec in enrolled_courses:
            try:
                course = courses_collection.find_one({'_id': ObjectId(ec['course_id'])})
                if course:
                    # Get course program and school info for display
                    course_program = programs_collection.find_one({'_id': ObjectId(course['program_id'])}) if course.get('program_id') else None
                    course_school = None
                    if course_program and course_program.get('school_id'):
                        course_school = schools_collection.find_one({'_id': ObjectId(course_program['school_id'])})
                    
                    courses_info.append({
                        'course': course,
                        'semester': ec.get('semester', 'N/A'),
                        'academic_year': ec.get('academic_year', 'N/A'),
                        'status': ec.get('status', 'enrolled'),
                        'program': course_program,
                        'school': course_school,
                        'enrolled_at': ec.get('enrolled_at', datetime.utcnow())
                    })
                else:
                    # Course not found, but enrollment exists - this might indicate data inconsistency
                    print(f"Warning: Course {ec['course_id']} not found for student {student_id}")
            except Exception as e:
                print(f"Error processing enrolled course: {str(e)}")
                continue
        
        # Get total course count for the "View All" link
        total_courses_count = student_courses_collection.count_documents({'student_id': ObjectId(student_id)})
        
        return render_template('users/student/student_profile.html',
                             student=student,
                             school=school,
                             program=program,
                             enrolled_courses=courses_info,
                             total_courses_count=total_courses_count,
                             grades_collection=grades_collection) 
        
    except Exception as e:
        flash(f'Error loading student profile: {str(e)}', 'error')
        return redirect(url_for('student.student_list'))
    except Exception as e:
        flash(f'Error loading student profile: {str(e)}', 'error')
        return redirect(url_for('student.student_list'))

@bp.route('/student/courses/<student_id>')
def student_courses(student_id):
    """Page to view all courses for a student"""
    try:
        student = students_collection.find_one({'_id': ObjectId(student_id)})
        if not student:
            flash('Student not found!', 'error')
            return redirect(url_for('student.student_list'))
        
        # Get school and program details
        school = schools_collection.find_one({'_id': ObjectId(student['school_id'])}) if student.get('school_id') else None
        program = programs_collection.find_one({'_id': ObjectId(student['program_id'])}) if student.get('program_id') else None
        
        # Get all enrolled courses
        enrolled_courses = list(student_courses_collection.find(
            {'student_id': ObjectId(student_id)}
        ).sort([('academic_year', -1), ('semester', 1), ('enrolled_at', -1)]))
        
        courses_info = []
        
        for ec in enrolled_courses:
            try:
                course = courses_collection.find_one({'_id': ObjectId(ec['course_id'])})
                if course:
                    # Get course program and school info for display
                    course_program = programs_collection.find_one({'_id': ObjectId(course['program_id'])}) if course.get('program_id') else None
                    course_school = None
                    if course_program and course_program.get('school_id'):
                        course_school = schools_collection.find_one({'_id': ObjectId(course_program['school_id'])})
                    
                    courses_info.append({
                        'course': course,
                        'semester': ec.get('semester', 'N/A'),
                        'academic_year': ec.get('academic_year', 'N/A'),
                        'status': ec.get('status', 'enrolled'),
                        'program': course_program,
                        'school': course_school,
                        'enrolled_at': ec.get('enrolled_at', datetime.utcnow())
                    })
            except Exception as e:
                print(f"Error processing enrolled course: {str(e)}")
                continue
        
        # Group courses by academic year and semester
        courses_by_semester = {}
        for course_info in courses_info:
            key = f"{course_info['academic_year']} - Semester {course_info['semester']}"
            if key not in courses_by_semester:
                courses_by_semester[key] = []
            courses_by_semester[key].append(course_info)
        
        return render_template('users/student/student_courses.html',
                             student=student,
                             school=school,
                             program=program,
                             courses_by_semester=courses_by_semester,
                             total_courses=len(courses_info))
    except Exception as e:
        flash(f'Error loading student courses: {str(e)}', 'error')
        return redirect(url_for('student.student_profile', student_id=student_id))

@bp.route('/student/add', methods=['POST'])
def add_student():
    """Add new student"""
    try:
        # Get form data (existing fields)
        f_name = request.form['f_name']
        l_name = request.form['l_name']
        email = request.form['email']
        phone_number = request.form ['phone_number']
        student_number = request.form['student_number']
        gender = request.form['gender']
        national_id = request.form['national_id']
        residential_address = request.form['residential_address']
        town = request.form['town']
        country = request.form['country']
        year_of_enrollment = request.form['year_of_enrollment']
        exam_location = request.form['exam_location']
        school_id = request.form['school_id']
        program_id = request.form['program_id']
    
        birthday = request.form.get('birthday')
        password = request.form.get('password', generate_auto_password())
        
        # NEW FIELDS: Next of Kin Information
        nok_name = request.form.get('nok_name')
        nok_relationship = request.form.get('nok_relationship')
        nok_address = request.form.get('nok_address')
        nok_town = request.form.get('nok_town')
        nok_country = request.form.get('nok_country')
        nok_phone = request.form.get('nok_phone')
        nok_email = request.form.get('nok_email')
        
        # Check if student number or email already exists
        existing_student = students_collection.find_one({
            '$or': [
                {'email': email},
                {'student_number': student_number},
                {'national_id': national_id}
            ]
        })
        
        if existing_student:
            flash('Student number, email or national ID already exists!', 'error')
            return redirect(url_for('student.student_registration'))

        # Handle file upload (existing code)
        profile_image = 'profile.svg'
        if 'profile_image' in request.files:
            file = request.files['profile_image']
            if file and file.filename != '' and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                unique_filename = f"{uuid.uuid4()}_{filename}"
                file_path = os.path.join(UPLOAD_FOLDER, unique_filename)
                
                os.makedirs(UPLOAD_FOLDER, exist_ok=True)
                file.save(file_path)
                profile_image = unique_filename

        # Create student document with new fields
        student_data = {
            'f_name': f_name,
            'l_name': l_name,
            'email': email,
            'student_number': student_number,
            'gender': gender,
            'national_id': national_id,
            'residential_address': residential_address,
            'town': town,
            'country': country,
            'profile_image': profile_image,
            'year_of_enrollment': year_of_enrollment,
            'exam_location': exam_location,
            'school_id': ObjectId(school_id),
            'program_id': ObjectId(program_id),
            'privilege_level': 'student',
            'status': 'active',
            'created_at': datetime.utcnow(),
            
            # NEW FIELDS
            'birthday': datetime.strptime(birthday, '%Y-%m-%d') if birthday else None,
            'password': generate_password_hash(password),
            
            # Next of Kin Information
            'next_of_kin': {
                'name': nok_name,
                'relationship': nok_relationship,
                'address': nok_address,
                'town': nok_town,
                'country': nok_country,
                'phone': nok_phone,
                'email': nok_email
            } if nok_name else None
        }

        # Insert into database
        result = students_collection.insert_one(student_data)
        flash(f'Student registered successfully! Auto-generated password: {password}', 'success')
        
    except Exception as e:
        flash(f'Error registering student: {str(e)}', 'error')
    
    return redirect(url_for('student.student_list'))


@bp.route('/student/edit/<student_id>')
def edit_student(student_id):
    """Edit student page"""
    try:
        student = students_collection.find_one({'_id': ObjectId(student_id)})
        if not student:
            flash('Student not found!', 'error')
            return redirect(url_for('student.student_list'))
        
        schools = list(schools_collection.find({'status': 'active'}))
        programs = list(programs_collection.find({'status': 'active'}))
        academic_years = get_academic_years()
        
        return render_template('users/student/student_edit.html', 
                             student=student,
                             schools=schools,
                             programs=programs,
                             academic_years=academic_years,
                             datetime=datetime)
    except Exception as e:
        flash('Invalid student ID!', 'error')
        return redirect(url_for('student.student_list'))

@bp.route('/student/update/<student_id>', methods=['POST'])
def update_student(student_id):
    """Update student information"""
    try:
        # Get form data (existing fields)
        f_name = request.form['f_name']
        l_name = request.form['l_name']
        email = request.form['email']
        phone_number = request.form['phone_number']
        student_number = request.form['student_number']
        gender = request.form['gender']
        national_id = request.form['national_id']
        residential_address = request.form['residential_address']
        town = request.form['town']
        country = request.form['country']
        year_of_enrollment = request.form['year_of_enrollment']
        exam_location = request.form['exam_location']
        school_id = request.form['school_id']
        program_id = request.form['program_id']
        status = request.form.get('status', 'active')
        
        # NEW FIELDS: Birthday and Password
        birthday = request.form.get('birthday')
        password = request.form.get('password')
        
        # NEW FIELDS: Next of Kin Information
        nok_name = request.form.get('nok_name')
        nok_relationship = request.form.get('nok_relationship')
        nok_address = request.form.get('nok_address')
        nok_town = request.form.get('nok_town')
        nok_country = request.form.get('nok_country')
        nok_phone = request.form.get('nok_phone')
        nok_email = request.form.get('nok_email')

        # Check if student number or email already exists (excluding current student)
        existing_student = students_collection.find_one({
            '_id': {'$ne': ObjectId(student_id)},
            '$or': [
                {'email': email},
                {'student_number': student_number},
                {'national_id': national_id}
            ]
        })
        
        if existing_student:
            flash('Student number, email or national ID already exists!', 'error')
            return redirect(url_for('student.edit_student', student_id=student_id))

        # Handle file upload (existing code)
        update_data = {
            'f_name': f_name,
            'l_name': l_name,
            'email': email,
            'phone_number': phone_number,
            'student_number': student_number,
            'gender': gender,
            'national_id': national_id,
            'residential_address': residential_address,
            'town': town,
            'country': country,
            'year_of_enrollment': year_of_enrollment,
            'exam_location': exam_location,
            'school_id': ObjectId(school_id),
            'program_id': ObjectId(program_id),
            'status': status,
            'updated_at': datetime.utcnow(),
            
            # NEW FIELDS
            'birthday': datetime.strptime(birthday, '%Y-%m-%d') if birthday else None,
            
            # Next of Kin Information
            'next_of_kin': {
                'name': nok_name,
                'relationship': nok_relationship,
                'address': nok_address,
                'town': nok_town,
                'country': nok_country,
                'phone': nok_phone,
                'email': nok_email
            } if nok_name else None
        }

        # Update password only if provided
        if password and password.strip():
            update_data['password'] = generate_password_hash(password)

        # Handle profile image update (existing code)
        if 'profile_image' in request.files:
            file = request.files['profile_image']
            if file and file.filename != '' and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                unique_filename = f"{uuid.uuid4()}_{filename}"
                file_path = os.path.join(UPLOAD_FOLDER, unique_filename)
                
                os.makedirs(UPLOAD_FOLDER, exist_ok=True)
                file.save(file_path)
                update_data['profile_image'] = unique_filename

        # Update student in database
        students_collection.update_one(
            {'_id': ObjectId(student_id)},
            {'$set': update_data}
        )
        
        flash('Student updated successfully!', 'success')
        
    except Exception as e:
        flash(f'Error updating student: {str(e)}', 'error')
    
    return redirect(url_for('student.student_list'))

@bp.route('/student/delete/<student_id>')
def delete_student(student_id):
    """Delete student"""
    try:
        result = students_collection.delete_one({'_id': ObjectId(student_id)})
        if result.deleted_count:
            # Also delete student course registrations
            student_courses_collection.delete_many({'student_id': ObjectId(student_id)})
            flash('Student deleted successfully!', 'success')
        else:
            flash('Student not found!', 'error')
            
    except Exception as e:
        flash(f'Error deleting student: {str(e)}', 'error')
    
    return redirect(url_for('student.student_list'))

@bp.route('/student/course_registration/<student_id>')
def course_registration(student_id):
    """Course registration page for student"""
    try:
        student = students_collection.find_one({'_id': ObjectId(student_id)})
        if not student:
            flash('Student not found!', 'error')
            return redirect(url_for('student.student_list'))
        
        # Get student's school and program for display
        school = schools_collection.find_one({'_id': ObjectId(student['school_id'])}) if student.get('school_id') else None
        program = programs_collection.find_one({'_id': ObjectId(student['program_id'])}) if student.get('program_id') else None
        
        # Get all schools for filtering
        all_schools = list(schools_collection.find({'status': 'active'}))
        
        # Get available courses for student's program AND courses from other schools
        available_courses = list(courses_collection.find({
            '$or': [
                {'program_id': ObjectId(student['program_id'])},  # Courses from student's program
                {'program_id': {'$ne': ObjectId(student['program_id'])}}  # Courses from other programs
            ],
            'status': 'active'
        }))
        
        # Enhance courses with program and school information
        enhanced_courses = []
        for course in available_courses:
            course_program = programs_collection.find_one({'_id': ObjectId(course['program_id'])}) if course.get('program_id') else None
            course_school = None
            if course_program and course_program.get('school_id'):
                course_school = schools_collection.find_one({'_id': ObjectId(course_program['school_id'])})
            
            enhanced_course = course.copy()
            enhanced_course['program_name'] = course_program['name'] if course_program else 'Unknown Program'
            enhanced_course['school_name'] = course_school['name'] if course_school else 'Unknown School'
            enhanced_course['school_id'] = str(course_school['_id']) if course_school else None
            enhanced_course['is_student_program'] = course.get('program_id') == student.get('program_id')
            enhanced_courses.append(enhanced_course)
        
        # Get already enrolled courses
        enrolled_courses = list(student_courses_collection.find({
            'student_id': ObjectId(student_id)
        }))
        enrolled_course_ids = [str(ec['course_id']) for ec in enrolled_courses]
        
        academic_years = get_academic_years()
        
        return render_template('users/student/course_registration.html',
                             student=student,
                             school=school,
                             program=program,
                             all_schools=all_schools,
                             available_courses=enhanced_courses,
                             enrolled_course_ids=enrolled_course_ids,
                             academic_years=academic_years)
    except Exception as e:
        flash(f'Error loading course registration: {str(e)}', 'error')
        return redirect(url_for('student.student_list'))

@bp.route('/student/enroll_courses/<student_id>', methods=['POST'])
def enroll_courses(student_id):
    """Enroll student in courses"""
    try:
        selected_courses = request.form.getlist('courses')
        semester = request.form['semester']
        academic_year = request.form['academic_year']
        
        if not selected_courses:
            flash('No courses selected for enrollment!', 'error')
            return redirect(url_for('student.course_registration', student_id=student_id))
        
        if not semester:
            flash('Please select a semester!', 'error')
            return redirect(url_for('student.course_registration', student_id=student_id))
        
        if not academic_year:
            flash('Please select an academic year!', 'error')
            return redirect(url_for('student.course_registration', student_id=student_id))
        
        # Remove existing enrollments for this semester and academic year
        delete_result = student_courses_collection.delete_many({
            'student_id': ObjectId(student_id),
            'semester': semester,
            'academic_year': academic_year
        })
        print(f"Deleted {delete_result.deleted_count} existing enrollments for semester {semester}, {academic_year}")
        
        # Add new enrollments
        enrolled_count = 0
        for course_id in selected_courses:
            try:
                # Verify course exists
                course = courses_collection.find_one({'_id': ObjectId(course_id)})
                if not course:
                    print(f"Warning: Course {course_id} not found, skipping enrollment")
                    continue
                    
                enrollment_data = {
                    'student_id': ObjectId(student_id),
                    'course_id': ObjectId(course_id),
                    'semester': semester,
                    'academic_year': academic_year,
                    'status': 'enrolled',
                    'enrolled_at': datetime.utcnow()
                }
                result = student_courses_collection.insert_one(enrollment_data)
                enrolled_count += 1
                
            except Exception as e:
                continue
        
        
        if enrolled_count > 0:
            flash(f'Successfully enrolled in {enrolled_count} courses for {academic_year}, Semester {semester}!', 'success')
        else:
            flash('No courses were enrolled. Please check your selection and try again.', 'warning')
        
    except Exception as e:
        flash(f'Error enrolling courses: {str(e)}', 'error')
    
    return redirect(url_for('student.student_profile', student_id=student_id))

@bp.route('/get_programs_by_school/<school_id>')
def get_programs_by_school(school_id):
    """Get programs for a specific school"""
    try:
        programs = list(programs_collection.find({
            'school_id': ObjectId(school_id),
            'status': 'active'
        }))
        programs_data = [{'id': str(program['_id']), 'name': program['name']} for program in programs]
        return jsonify(programs_data)
    except Exception as e:
        return jsonify([])

@bp.route('/get_courses_by_school/<school_id>')
def get_courses_by_school(school_id):
    """Get courses for a specific school"""
    try:
        # Get all programs for the school
        programs = list(programs_collection.find({
            'school_id': ObjectId(school_id),
            'status': 'active'
        }))
        
        program_ids = [program['_id'] for program in programs]
        
        # Get courses for these programs
        courses = list(courses_collection.find({
            'program_id': {'$in': program_ids},
            'status': 'active'
        }))
        
        # Enhance courses with program information
        programs_dict = {str(program['_id']): program['name'] for program in programs}
        courses_data = []
        
        for course in courses:
            courses_data.append({
                'id': str(course['_id']),
                'code': course['code'],
                'name': course['name'],
                'credits': course['credits'],
                'semester': course.get('semester', 'N/A'),
                'program_name': programs_dict.get(str(course['program_id']), 'Unknown Program'),
                'description': course.get('description', '')
            })
        
        return jsonify(courses_data)
    except Exception as e:
        return jsonify([])
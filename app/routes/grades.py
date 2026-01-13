from flask import Blueprint, render_template, request, flash, url_for, redirect, jsonify, session
from app import students_collection, courses_collection, programs_collection, schools_collection, student_courses_collection, grades_collection, mock_grades_collection, staff_collection
from bson import ObjectId
from datetime import datetime

# Replace the import line with this:
from app.utils import can_view_semester_grades, get_semester_balance, get_semester_fees, get_staff_privilege_level, has_staff_privilege
from app.config import SystemConfig

bp = Blueprint('grades', __name__)

# Grade scale and definitions
GRADE_SCALE = {
    'A+': {'range': (86, 100), 'description': 'Distinction'},
    'A': {'range': (76, 85), 'description': 'Distinction'},
    'B+': {'range': (66, 75), 'description': 'Meritorious'},
    'B': {'range': (60, 65), 'description': 'Credit'},
    'C+': {'range': (55, 59), 'description': 'Clear Pass'},
    'C': {'range': (50, 54), 'description': 'Bare Pass'},
    'D+': {'range': (45, 49), 'description': 'Bare Fail'},
    'D': {'range': (0, 44), 'description': 'Definite Fail'},
    'F': {'range': None, 'description': 'Fail in Supplementary Exam'},
    'U': {'range': None, 'description': 'Unsatisfactory - Fail in Practical/Thesis/Oral'},
    'P': {'range': None, 'description': 'Pass in Supplementary/Practical'},
    'S': {'range': None, 'description': 'Satisfactory - Pass in Practical/Oral'},
    'WP': {'range': None, 'description': 'Withdraw with Permission'},
    'DC': {'range': None, 'description': 'Deceased during Course'},
    'EX': {'range': None, 'description': 'Exempted'},
    'INC': {'range': None, 'description': 'Incomplete'},
    'DEF': {'range': None, 'description': 'Deferred Exam'},
    'SP': {'range': None, 'description': 'Supplementary Exam'},
    'DISQ': {'range': None, 'description': 'Disqualified'}
}

def calculate_grade(marks):
    """Calculate grade based on marks"""
    if marks is None:
        return None
    
    for grade, info in GRADE_SCALE.items():
        if info['range'] and info['range'][0] <= marks <= info['range'][1]:
            return grade
    return 'D'  # Default to D if no range matches

def get_grade_description(grade):
    """Get description for a grade"""
    return GRADE_SCALE.get(grade, {}).get('description', 'Unknown')

def is_passing_grade(grade):
    """Check if grade is passing (50 and above)"""
    passing_grades = ['A+', 'A', 'B+', 'B', 'C+', 'C', 'P', 'S', 'EX']
    return grade in passing_grades

def get_remarks(grade):
    """Get remarks based on grade - either 'Proceed' or 'Repeat'"""
    if is_passing_grade(grade):
        return 'Proceed'
    else:
        return 'Repeat'

@bp.route('/Grades')
def grades_dashboard():
    """Grades management dashboard"""
    return render_template('grades/grades_dashboard.html')

@bp.route('/grades/final')
def final_grades():
    """Final grades management page"""
    schools = list(schools_collection.find({'status': 'active'}))
    programs = list(programs_collection.find({'status': 'active'}))
    academic_years = ['2036/2037','2035/2036','2034/2035','2033/2034','2032/2033','2031/2032','2030/2031','2029/2030','2028/2029','2027/2028','2026/2027','2025/2026', '2024/2025', '2023/2024', '2022/2023', '2021/2022','2020/2021', '2019/2020']  # Expanded list
    semesters = ['1', '2']
    
    return render_template('grades/final/final_grades.html',
                         schools=schools,
                         programs=programs,
                         academic_years=academic_years,
                         semesters=semesters,
                         grade_scale=GRADE_SCALE)

@bp.route('/grades/mock')
def mock_grades():
    """Mock grades management page"""
    schools = list(schools_collection.find({'status': 'active'}))
    programs = list(programs_collection.find({'status': 'active'}))
    academic_years = ['2025/2026', '2024/2025', '2023/2024']
    semesters = ['1', '2']
    
    return render_template('grades/mock/mock_grades.html',
                         schools=schools,
                         programs=programs,
                         academic_years=academic_years,
                         semesters=semesters,
                         grade_scale=GRADE_SCALE)

@bp.route('/grades/search_students')
def search_students():
    """Search students by various criteria"""
    try:
        search_term = request.args.get('search', '')
        school_id = request.args.get('school_id', '')
        program_id = request.args.get('program_id', '')
        academic_year = request.args.get('academic_year', '')
        course_type = request.args.get('course_type', '')
        course_code = request.args.get('course_code', '')
        
        query = {'status': 'active'}
        
        if search_term:
            query['$or'] = [
                {'student_number': {'$regex': search_term, '$options': 'i'}},
                {'f_name': {'$regex': search_term, '$options': 'i'}},
                {'l_name': {'$regex': search_term, '$options': 'i'}},
                {'email': {'$regex': search_term, '$options': 'i'}}
            ]
        
        if school_id:
            query['school_id'] = ObjectId(school_id)
        
        if program_id:
            query['program_id'] = ObjectId(program_id)
        
        students = list(students_collection.find(query).limit(50))  # Limit results
        
        # Filter by academic year, course type, and course code if specified
        filtered_students = []
        for student in students:
            # Check if student has courses matching the filters
            course_query = {'student_id': student['_id']}
            
            if academic_year:
                course_query['academic_year'] = academic_year
            
            # Get student's enrolled courses to check course type and code
            enrolled_courses = list(student_courses_collection.find(course_query))
            
            if enrolled_courses:
                course_ids = [ec['course_id'] for ec in enrolled_courses]
                courses = list(courses_collection.find({'_id': {'$in': course_ids}}))
                
                # Apply course code filter if specified
                if course_code:
                    matching_courses = [c for c in courses if course_code.upper() in c.get('code', '').upper()]
                    if not matching_courses:
                        continue  # Skip student if no courses match the course code
                
                # Apply course type filter if specified
                if course_type:
                    if course_type == 'graded':
                        graded_courses = [c for c in courses if c.get('grading_system') in ['letter', 'percentage', 'points']]
                        if not graded_courses:
                            continue  # Skip student if no graded courses match
                    elif course_type == 'ungraded':
                        ungraded_courses = [c for c in courses if c.get('grading_system') in ['pass_fail', 'satisfactory', 'credit']]
                        if not ungraded_courses:
                            continue  # Skip student if no ungraded courses match
            else:
                # If no enrolled courses and we have course-related filters, skip this student
                if course_code or course_type:
                    continue
            
            # If we get here, student matches all filters
            school = schools_collection.find_one({'_id': ObjectId(student['school_id'])}) if student.get('school_id') else None
            program = programs_collection.find_one({'_id': ObjectId(student['program_id'])}) if student.get('program_id') else None
            
            # Get current academic year for display
            current_enrollment = student_courses_collection.find_one(
                {'student_id': student['_id']},
                sort=[('academic_year', -1)]
            )
            
            # Get matching course names for display if course code filter is used
            matching_course_names = []
            if course_code and enrolled_courses:
                matching_courses = [c for c in courses if course_code.upper() in c.get('code', '').upper()]
                matching_course_names = [c['code'] for c in matching_courses]
            
            student_data = {
                'id': str(student['_id']),
                'student_number': student['student_number'],
                'f_name': student['f_name'],
                'l_name': student['l_name'],
                'email': student['email'],
                'school_name': school['name'] if school else 'Unknown',
                'program_name': program['name'] if program else 'Unknown',
                'academic_year': current_enrollment.get('academic_year') if current_enrollment else 'N/A'
            }
            
            # Add matching courses info if course code filter was used
            if matching_course_names:
                student_data['matching_courses'] = ', '.join(matching_course_names)
            
            filtered_students.append(student_data)
        
        return jsonify(filtered_students)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/grades/get_student_courses/<student_id>')
def get_student_courses(student_id):
    """Get courses for a specific student"""
    try:
        academic_year = request.args.get('academic_year', '2025/2026')
        semester = request.args.get('semester', '1')
        course_type = request.args.get('course_type', '')
        course_code = request.args.get('course_code', '')  # New course code filter
        
        # Get student's enrolled courses for specific academic year and semester
        query = {
            'student_id': ObjectId(student_id),
            'academic_year': academic_year,
            'semester': semester
        }
        enrolled_courses = list(student_courses_collection.find(query))
        
        courses_data = []
        for ec in enrolled_courses:
            course = courses_collection.find_one({'_id': ObjectId(ec['course_id'])})
            if course:
                # Apply course code filter if specified
                if course_code and course_code.upper() not in course.get('code', '').upper():
                    continue
                
                # Apply course type filter if specified
                if course_type:
                    if course_type == 'graded' and course.get('grading_system') not in ['letter', 'percentage', 'points']:
                        continue
                    elif course_type == 'ungraded' and course.get('grading_system') not in ['pass_fail', 'satisfactory', 'credit']:
                        continue
                
                program = programs_collection.find_one({'_id': ObjectId(course['program_id'])})
                courses_data.append({
                    'course_id': str(course['_id']),
                    'course_code': course['code'],
                    'course_name': course['name'],
                    'grading_system': course.get('grading_system', 'letter'),
                    'semester': ec.get('semester', '1'),
                    'academic_year': ec.get('academic_year', '2025/2026'),
                    'program_name': program['name'] if program else 'Unknown'
                })
        
        return jsonify(courses_data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/grades/get_grades/<student_id>/<exam_type>')
def get_grades(student_id, exam_type):
    """Get grades for a specific student and exam type"""
    try:
        academic_year = request.args.get('academic_year', '2025/2026')
        semester = request.args.get('semester', '1')
        
        # Check if current user is staff with privileges
        staff_id = session.get('staff_id')
        staff_privilege = get_staff_privilege_level(staff_id) if staff_id else None
        has_staff_privilege = staff_privilege in ['admin', 'registrar', 'finance', 'academic']
        
        # Choose the appropriate collection based on exam type
        if exam_type == 'mock':
            collection = mock_grades_collection
        else:
            collection = grades_collection
        
        # Find the grade document
        grade_doc = collection.find_one({
            'student_id': ObjectId(student_id),
            'academic_year': academic_year,
            'semester': semester
        })
        
        if grade_doc:
            grades_data = grade_doc.get('grades', [])
            
            # Check if grades are published
            is_published = grade_doc.get('published', False)
            
            # Staff can always view, students can only view if published AND have paid fees
            if has_staff_privilege:
                can_view = True
                reason = None
            else:
                # For students: must be published AND have sufficient payment
                if is_published:
                    can_view = can_view_semester_grades(student_id, semester, academic_year)
                    reason = 'Outstanding balance' if not can_view else None
                else:
                    can_view = False
                    reason = 'Grades not yet published'
            
            # Enhance grades data with course information
            enhanced_grades = []
            for grade_entry in grades_data:
                course = courses_collection.find_one({'_id': ObjectId(grade_entry['course_id'])})
                if course:
                    if can_view:
                        enhanced_grades.append({
                            'course_id': grade_entry['course_id'],
                            'course_code': course['code'],
                            'course_name': course['name'],
                            'marks': grade_entry.get('marks'),
                            'grade': grade_entry.get('grade'),
                            'remarks': grade_entry.get('remarks', get_remarks(grade_entry.get('grade', ''))),
                            'can_view': True,
                            'withheld_reason': None
                        })
                    else:
                        enhanced_grades.append({
                            'course_id': grade_entry['course_id'],
                            'course_code': course['code'],
                            'course_name': course['name'],
                            'marks': None,
                            'grade': 'HIDDEN',
                            'remarks': f'Results withheld - {reason}',
                            'can_view': False,
                            'withheld_reason': reason
                        })
            return jsonify(enhanced_grades)
        else:
            return jsonify([])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/grades/save_grades/<student_id>/<exam_type>', methods=['POST'])
def save_grades(student_id, exam_type):
    """Save grades for a student - each semester as a separate document"""
    try:
        data = request.get_json()
        academic_year = data.get('academic_year', '2025/2026')
        semester = data.get('semester', '1')
        grades_data = data.get('grades', [])
        
        # Prepare grades with automatic remarks
        prepared_grades = []
        for grade_entry in grades_data:
            grade = grade_entry.get('grade')
            prepared_grades.append({
                'course_id': grade_entry['course_id'],
                'marks': grade_entry.get('marks'),
                'grade': grade,
                'remarks': get_remarks(grade)  # Auto-generate remarks
            })
        
        # Choose the appropriate collection based on exam type
        if exam_type == 'mock':
            collection = mock_grades_collection
            exam_type_display = 'Mock'
        else:
            collection = grades_collection
            exam_type_display = 'Final'
        
        
        grade_doc = {
            'student_id': ObjectId(student_id),
            'exam_type': exam_type,
            'academic_year': academic_year,
            'semester': semester,
            'grades': prepared_grades,
            'entered_by': 'System',
            'entered_at': datetime.utcnow(),
            'updated_at': datetime.utcnow(),
            'published': False,  # Add this field - default to unpublished
            'published_at': None,  # Add publication timestamp
            'published_by': None   # Add who published the grades
        }
        
        collection.update_one(
            {
                'student_id': ObjectId(student_id),
                'academic_year': academic_year,
                'semester': semester
            },
            {'$set': grade_doc},
            upsert=True
        )
        
        return jsonify({
            'success': True,
            'message': f'{exam_type_display} grades saved successfully for {academic_year} Semester {semester}!'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500



@bp.route('/grades/upload_grades/<exam_type>', methods=['POST'])
def upload_grades(exam_type):
    """Upload grades via CSV file"""
    try:
        if 'file' not in request.files:
            flash('No file selected!', 'error')
            return redirect(url_for(f'grades.{exam_type}_grades'))
        
        file = request.files['file']
        if file.filename == '':
            flash('No file selected!', 'error')
            return redirect(url_for(f'grades.{exam_type}_grades'))
        
        if file and file.filename.endswith('.csv'):
            # Process CSV file
            # This is a simplified version - you'd need to implement CSV parsing
            flash('CSV upload functionality to be implemented', 'info')
        else:
            flash('Please upload a CSV file', 'error')
        
        return redirect(url_for(f'grades.{exam_type}_grades'))
    except Exception as e:
        flash(f'Error uploading grades: {str(e)}', 'error')
        return redirect(url_for(f'grades.{exam_type}_grades'))


@bp.route('/grades/get_course_codes')
def get_course_codes():
    """Get all unique course codes for auto-suggest"""
    try:
        # Get distinct course codes from courses collection
        course_codes = courses_collection.distinct('code')
        return jsonify(sorted(course_codes))
    except Exception as e:
        return jsonify([])


#semester grading
from app.config import SystemConfig

@bp.route('/grades/student_results/<student_id>')
def student_results(student_id):
    """Page to view all results for a specific student with balance checks"""
    try:
        student = students_collection.find_one({'_id': ObjectId(student_id)})
        if not student:
            flash('Student not found!', 'error')
            return redirect(url_for('grades.final_grades'))
        
        # Get school and program details
        school = schools_collection.find_one({'_id': ObjectId(student['school_id'])}) if student.get('school_id') else None
        program = programs_collection.find_one({'_id': ObjectId(student['program_id'])}) if student.get('program_id') else None
        
        # Get all grade documents for this student from both collections
        final_grades = list(grades_collection.find({
            'student_id': ObjectId(student_id)
        }).sort([('academic_year', -1), ('semester', -1)]))
        
        mock_grades = list(mock_grades_collection.find({
            'student_id': ObjectId(student_id)
        }).sort([('academic_year', -1), ('semester', -1)]))
        
        # Calculate total courses for each type
        final_total_courses = 0
        for grade_doc in final_grades:
            final_total_courses += len(grade_doc.get('grades', []))
            
        mock_total_courses = 0
        for grade_doc in mock_grades:
            mock_total_courses += len(grade_doc.get('grades', []))
        
        # Check staff privileges
        staff_has_privilege = has_staff_privilege()
        
        # Check which semesters can be viewed based on publication status, balance AND staff privileges
        viewable_semesters = {}
        for grade_doc in final_grades + mock_grades:
            academic_year = grade_doc['academic_year']
            semester = grade_doc['semester']
            key = f"{academic_year}_semester_{semester}"
            
            if key not in viewable_semesters:
                is_published = grade_doc.get('published', False)
                
                # Staff can always view, students can only view if published AND have paid fees
                if staff_has_privilege:
                    can_view = True
                else:
                    can_view = is_published and can_view_semester_grades(student_id, semester, academic_year)
                
                viewable_semesters[key] = {
                    'can_view': can_view,
                    'is_published': is_published,
                    'has_payment': can_view_semester_grades(student_id, semester, academic_year)
                }
        
        # Get all courses for course name lookup
        all_courses = list(courses_collection.find({}))
        courses_dict = {str(course['_id']): course for course in all_courses}
        
        return render_template('grades/student_results.html',
                             student=student,
                             school=school,
                             program=program,
                             final_grades=final_grades,
                             mock_grades=mock_grades,
                             final_total_courses=final_total_courses,
                             mock_total_courses=mock_total_courses,
                             courses_dict=courses_dict,
                             viewable_semesters=viewable_semesters,
                             SystemConfig=SystemConfig,
                             has_staff_access=staff_has_privilege)
    except Exception as e:
        flash(f'Error loading student results: {str(e)}', 'error')
        return redirect(url_for('grades.final_grades'))

@bp.route('/grades/get_student_all_grades/<student_id>')
def get_student_all_grades(student_id):
    """Get all grades for a student with balance and privilege checks"""
    try:
        # Check if current user is staff with privileges
        staff_id = session.get('staff_id')
        staff_privilege = get_staff_privilege_level(staff_id) if staff_id else None
        has_staff_privilege = staff_privilege in ['admin', 'registrar', 'finance', 'academic']
        
        # Get all grade documents for this student from both collections
        final_grade_docs = list(grades_collection.find({
            'student_id': ObjectId(student_id)
        }).sort([('academic_year', -1), ('semester', -1)]))
        
        mock_grade_docs = list(mock_grades_collection.find({
            'student_id': ObjectId(student_id)
        }).sort([('academic_year', -1), ('semester', -1)]))
        
        grades_data = []
        
        # Process final grades
        for doc in final_grade_docs:
            academic_year = doc['academic_year']
            semester = doc['semester']
            
            # Check if grades can be viewed
            can_view = has_staff_privilege or can_view_semester_grades(student_id, semester, academic_year)
            
            enhanced_grades = []
            for grade_entry in doc.get('grades', []):
                course = courses_collection.find_one({'_id': ObjectId(grade_entry['course_id'])})
                if course:
                    enhanced_grades.append({
                        'course_code': course['code'],
                        'course_name': course['name'],
                        'marks': grade_entry.get('marks') if can_view else None,
                        'grade': grade_entry.get('grade') if can_view else 'HIDDEN',
                        'remarks': grade_entry.get('remarks') if can_view else 'Results withheld due to outstanding balance',
                        'can_view': can_view,
                        'withheld_reason': None if can_view else 'Outstanding balance'
                    })
            
            grades_data.append({
                'exam_type': 'final',
                'academic_year': academic_year,
                'semester': semester,
                'entered_at': doc.get('entered_at', datetime.utcnow()).strftime('%Y-%m-%d %H:%M'),
                'grades': enhanced_grades,
                'can_view': can_view,
                'viewed_by_staff': has_staff_privilege
            })
        
        # Process mock grades
        for doc in mock_grade_docs:
            academic_year = doc['academic_year']
            semester = doc['semester']
            
            # Check if grades can be viewed
            can_view = has_staff_privilege or can_view_semester_grades(student_id, semester, academic_year)
            
            enhanced_grades = []
            for grade_entry in doc.get('grades', []):
                course = courses_collection.find_one({'_id': ObjectId(grade_entry['course_id'])})
                if course:
                    enhanced_grades.append({
                        'course_code': course['code'],
                        'course_name': course['name'],
                        'marks': grade_entry.get('marks') if can_view else None,
                        'grade': grade_entry.get('grade') if can_view else 'HIDDEN',
                        'remarks': grade_entry.get('remarks') if can_view else 'Results withheld due to outstanding balance',
                        'can_view': can_view,
                        'withheld_reason': None if can_view else 'Outstanding balance'
                    })
            
            grades_data.append({
                'exam_type': 'mock',
                'academic_year': academic_year,
                'semester': semester,
                'entered_at': doc.get('entered_at', datetime.utcnow()).strftime('%Y-%m-%d %H:%M'),
                'grades': enhanced_grades,
                'can_view': can_view,
                'viewed_by_staff': has_staff_privilege
            })
        
        # Sort all grades by academic year and semester
        grades_data.sort(key=lambda x: (x['academic_year'], x['semester']), reverse=True)
        
        return jsonify(grades_data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/grades/publish_grades/<exam_type>', methods=['POST'])
def publish_grades(exam_type):
    """Publish grades for a specific semester"""
    try:
        data = request.get_json()
        academic_year = data.get('academic_year')
        semester = data.get('semester')
        
        if not academic_year or not semester:
            return jsonify({'success': False, 'error': 'Academic year and semester are required'}), 400
        
        # Choose the appropriate collection
        collection = mock_grades_collection if exam_type == 'mock' else grades_collection
        
        # Update all grade documents for this semester to published
        result = collection.update_many(
            {
                'academic_year': academic_year,
                'semester': semester
            },
            {
                '$set': {
                    'published': True,
                    'published_at': datetime.utcnow(),
                    'published_by': session.get('staff_id', 'System')
                }
            }
        )
        
        return jsonify({
            'success': True,
            'message': f'Successfully published {result.modified_count} {exam_type} grade records for {academic_year} Semester {semester}',
            'count': result.modified_count
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/grades/unpublish_grades/<exam_type>', methods=['POST'])
def unpublish_grades(exam_type):
    """Unpublish grades for a specific semester"""
    try:
        data = request.get_json()
        academic_year = data.get('academic_year')
        semester = data.get('semester')
        
        if not academic_year or not semester:
            return jsonify({'success': False, 'error': 'Academic year and semester are required'}), 400
        
        # Choose the appropriate collection
        collection = mock_grades_collection if exam_type == 'mock' else grades_collection
        
        # Update all grade documents for this semester to unpublished
        result = collection.update_many(
            {
                'academic_year': academic_year,
                'semester': semester
            },
            {
                '$set': {
                    'published': False,
                    'published_at': None,
                    'published_by': None
                }
            }
        )
        
        return jsonify({
            'success': True,
            'message': f'Successfully unpublished {result.modified_count} {exam_type} grade records for {academic_year} Semester {semester}',
            'count': result.modified_count
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/grades/get_publication_status/<exam_type>')
def get_publication_status(exam_type):
    """Get publication status for semesters"""
    try:
        academic_year = request.args.get('academic_year', '')
        semester = request.args.get('semester', '')
        
        collection = mock_grades_collection if exam_type == 'mock' else grades_collection
        
        # Build query
        query = {}
        if academic_year:
            query['academic_year'] = academic_year
        if semester:
            query['semester'] = semester
        
        # Get distinct semesters with publication status
        pipeline = [
            {'$match': query},
            {'$group': {
                '_id': {
                    'academic_year': '$academic_year',
                    'semester': '$semester'
                },
                'total_records': {'$sum': 1},
                'published_records': {
                    '$sum': {'$cond': [{'$eq': ['$published', True]}, 1, 0]}
                },
                'last_published': {'$max': '$published_at'}
            }},
            {'$sort': {'_id.academic_year': -1, '_id.semester': -1}}
        ]
        
        status_data = list(collection.aggregate(pipeline))
        
        # Format the response
        formatted_status = []
        for status in status_data:
            formatted_status.append({
                'academic_year': status['_id']['academic_year'],
                'semester': status['_id']['semester'],
                'total_records': status['total_records'],
                'published_records': status['published_records'],
                'publication_percentage': round((status['published_records'] / status['total_records']) * 100, 1) if status['total_records'] > 0 else 0,
                'last_published': status['last_published'].strftime('%Y-%m-%d %H:%M') if status['last_published'] else None,
                'is_fully_published': status['published_records'] == status['total_records'] and status['total_records'] > 0
            })
        
        return jsonify(formatted_status)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
# Add these new routes to your grades.py file

@bp.route('/grades/final_student_results/<student_id>')
def final_student_results(student_id):
    """Page to view only final exam results for a specific student"""
    try:
        student = students_collection.find_one({'_id': ObjectId(student_id)})
        if not student:
            flash('Student not found!', 'error')
            return redirect(url_for('grades.final_grades'))
        
        # Get school and program details
        school = schools_collection.find_one({'_id': ObjectId(student['school_id'])}) if student.get('school_id') else None
        program = programs_collection.find_one({'_id': ObjectId(student['program_id'])}) if student.get('program_id') else None
        
        # Get only final grade documents for this student
        final_grades = list(grades_collection.find({
            'student_id': ObjectId(student_id)
        }).sort([('academic_year', -1), ('semester', -1)]))
        
        # Calculate total courses
        total_courses = 0
        for grade_doc in final_grades:
            total_courses += len(grade_doc.get('grades', []))
        
        # Check staff privileges
        staff_has_privilege = has_staff_privilege()
        
        # Check which semesters can be viewed based on publication status, balance AND staff privileges
        viewable_semesters = {}
        for grade_doc in final_grades:
            academic_year = grade_doc['academic_year']
            semester = grade_doc['semester']
            key = f"{academic_year}_semester_{semester}"
            
            if key not in viewable_semesters:
                is_published = grade_doc.get('published', False)
                
                # Staff can always view, students can only view if published AND have paid fees
                if staff_has_privilege:
                    can_view = True
                else:
                    can_view = is_published and can_view_semester_grades(student_id, semester, academic_year)
                
                viewable_semesters[key] = {
                    'can_view': can_view,
                    'is_published': is_published,
                    'has_payment': can_view_semester_grades(student_id, semester, academic_year)
                }
        
        # Get all courses for course name lookup
        all_courses = list(courses_collection.find({}))
        courses_dict = {str(course['_id']): course for course in all_courses}
        
        return render_template('grades/final_student_results.html',
                             student=student,
                             school=school,
                             program=program,
                             final_grades=final_grades,
                             total_courses=total_courses,
                             courses_dict=courses_dict,
                             viewable_semesters=viewable_semesters,
                             SystemConfig=SystemConfig,
                             has_staff_access=staff_has_privilege)
    except Exception as e:
        flash(f'Error loading final exam results: {str(e)}', 'error')
        return redirect(url_for('grades.final_grades'))

@bp.route('/grades/mock_student_results/<student_id>')
def mock_student_results(student_id):
    """Page to view only mock exam results for a specific student"""
    try:
        student = students_collection.find_one({'_id': ObjectId(student_id)})
        if not student:
            flash('Student not found!', 'error')
            return redirect(url_for('grades.mock_grades'))
        
        # Get school and program details
        school = schools_collection.find_one({'_id': ObjectId(student['school_id'])}) if student.get('school_id') else None
        program = programs_collection.find_one({'_id': ObjectId(student['program_id'])}) if student.get('program_id') else None
        
        # Get only mock grade documents for this student
        mock_grades = list(mock_grades_collection.find({
            'student_id': ObjectId(student_id)
        }).sort([('academic_year', -1), ('semester', -1)]))
        
        # Calculate total courses
        total_courses = 0
        for grade_doc in mock_grades:
            total_courses += len(grade_doc.get('grades', []))
        
        # Check staff privileges
        staff_has_privilege = has_staff_privilege()
        
        # Check which semesters can be viewed based on publication status, balance AND staff privileges
        viewable_semesters = {}
        for grade_doc in mock_grades:
            academic_year = grade_doc['academic_year']
            semester = grade_doc['semester']
            key = f"{academic_year}_semester_{semester}"
            
            if key not in viewable_semesters:
                is_published = grade_doc.get('published', False)
                
                # Staff can always view, students can only view if published AND have paid fees
                if staff_has_privilege:
                    can_view = True
                else:
                    can_view = is_published and can_view_semester_grades(student_id, semester, academic_year)
                
                viewable_semesters[key] = {
                    'can_view': can_view,
                    'is_published': is_published,
                    'has_payment': can_view_semester_grades(student_id, semester, academic_year)
                }
        
        # Get all courses for course name lookup
        all_courses = list(courses_collection.find({}))
        courses_dict = {str(course['_id']): course for course in all_courses}
        
        return render_template('grades/mock_student_results.html',
                             student=student,
                             school=school,
                             program=program,
                             mock_grades=mock_grades,
                             total_courses=total_courses,
                             courses_dict=courses_dict,
                             viewable_semesters=viewable_semesters,
                             SystemConfig=SystemConfig,
                             has_staff_access=staff_has_privilege)
    except Exception as e:
        flash(f'Error loading mock exam results: {str(e)}', 'error')
        return redirect(url_for('grades.mock_grades'))
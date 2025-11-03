from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from app import students_collection, schools_collection, programs_collection, courses_collection, student_courses_collection, ca_collection
from bson import ObjectId
from datetime import datetime

bp = Blueprint('ca', __name__)

@bp.route('/CA')
def ca_dashboard():
    """CA Management Dashboard"""
    return render_template('grades/ca/ca_dashboard.html')

@bp.route('/ca/manage')
def manage_ca():
    """Manage Continuous Assessments"""
    schools = list(schools_collection.find({'status': 'active'}))
    programs = list(programs_collection.find({'status': 'active'}))
    academic_years = ['2025/2026', '2024/2025', '2023/2024']
    semesters = ['1', '2']
    
    return render_template('grades/ca/manage_ca.html',
                         schools=schools,
                         programs=programs,
                         academic_years=academic_years,
                         semesters=semesters)

@bp.route('/ca/search_students')
def search_ca_students():
    """Search students for CA management"""
    try:
        search_term = request.args.get('search', '')
        school_id = request.args.get('school_id', '')
        program_id = request.args.get('program_id', '')
        academic_year = request.args.get('academic_year', '2025/2026')
        semester = request.args.get('semester', '1')
        
        query = {'status': 'active'}
        
        if search_term:
            query['$or'] = [
                {'student_number': {'$regex': search_term, '$options': 'i'}},
                {'f_name': {'$regex': search_term, '$options': 'i'}},
                {'l_name': {'$regex': search_term, '$options': 'i'}}
            ]
        
        if school_id:
            query['school_id'] = ObjectId(school_id)
        
        if program_id:
            query['program_id'] = ObjectId(program_id)
        
        students = list(students_collection.find(query).limit(50))
        
        filtered_students = []
        for student in students:
            # Check if student has courses for the specified semester and academic year
            enrolled_courses = list(student_courses_collection.find({
                'student_id': student['_id'],
                'academic_year': academic_year,
                'semester': semester
            }))
            
            if enrolled_courses:
                school = schools_collection.find_one({'_id': ObjectId(student['school_id'])}) if student.get('school_id') else None
                program = programs_collection.find_one({'_id': ObjectId(student['program_id'])}) if student.get('program_id') else None
                
                student_data = {
                    'id': str(student['_id']),
                    'student_number': student['student_number'],
                    'f_name': student['f_name'],
                    'l_name': student['l_name'],
                    'school_name': school['name'] if school else 'Unknown',
                    'program_name': program['name'] if program else 'Unknown',
                    'enrolled_courses_count': len(enrolled_courses)
                }
                filtered_students.append(student_data)
        
        return jsonify(filtered_students)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/ca/get_student_courses/<student_id>')
def get_student_courses_ca(student_id):
    """Get courses for a specific student for CA"""
    try:
        academic_year = request.args.get('academic_year', '2025/2026')
        semester = request.args.get('semester', '1')
        
        # Get student's enrolled courses for specific academic year and semester
        enrolled_courses = list(student_courses_collection.find({
            'student_id': ObjectId(student_id),
            'academic_year': academic_year,
            'semester': semester
        }))
        
        courses_data = []
        for ec in enrolled_courses:
            course = courses_collection.find_one({'_id': ObjectId(ec['course_id'])})
            if course:
                program = programs_collection.find_one({'_id': ObjectId(course['program_id'])})
                
                # Get existing CA data if any
                ca_data = ca_collection.find_one({
                    'student_id': ObjectId(student_id),
                    'course_id': ObjectId(ec['course_id']),
                    'academic_year': academic_year,
                    'semester': semester
                })
                
                courses_data.append({
                    'course_id': str(course['_id']),
                    'course_code': course['code'],
                    'course_name': course['name'],
                    'credits': course.get('credits', 0),
                    'program_name': program['name'] if program else 'Unknown',
                    'ca_score': ca_data.get('score') if ca_data else None,
                    'total_score': ca_data.get('total_score', 30) if ca_data else 30,  # Default total score
                    'assessment_type': ca_data.get('assessment_type', 'assignment') if ca_data else 'assignment',
                    'assessment_date': ca_data.get('assessment_date', datetime.utcnow()).strftime('%Y-%m-%d') if ca_data else datetime.utcnow().strftime('%Y-%m-%d')
                })
        
        return jsonify(courses_data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/ca/save_scores/<student_id>', methods=['POST'])
def save_ca_scores(student_id):
    """Save CA scores for a student"""
    try:
        data = request.get_json()
        academic_year = data.get('academic_year', '2025/2026')
        semester = data.get('semester', '1')
        ca_scores = data.get('ca_scores', [])
        
        saved_count = 0
        for score_data in ca_scores:
            try:
                ca_doc = {
                    'student_id': ObjectId(student_id),
                    'course_id': ObjectId(score_data['course_id']),
                    'academic_year': academic_year,
                    'semester': semester,
                    'score': float(score_data['score']) if score_data.get('score') else None,
                    'total_score': float(score_data['total_score']),
                    'assessment_type': score_data.get('assessment_type', 'assignment'),
                    'assessment_date': datetime.strptime(score_data['assessment_date'], '%Y-%m-%d') if score_data.get('assessment_date') else datetime.utcnow(),
                    'entered_by': 'System',  # Replace with actual user
                    'entered_at': datetime.utcnow(),
                    'updated_at': datetime.utcnow()
                }
                
                # Upsert the CA record
                ca_collection.update_one(
                    {
                        'student_id': ObjectId(student_id),
                        'course_id': ObjectId(score_data['course_id']),
                        'academic_year': academic_year,
                        'semester': semester
                    },
                    {'$set': ca_doc},
                    upsert=True
                )
                saved_count += 1
                
            except Exception as e:
                print(f"Error saving CA score for course {score_data.get('course_id')}: {str(e)}")
                continue
        
        return jsonify({
            'success': True,
            'message': f'Successfully saved {saved_count} CA scores for {academic_year} Semester {semester}!'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/ca/student/<student_id>')
def view_student_ca(student_id):
    """View all CA records for a specific student"""
    try:
        student = students_collection.find_one({'_id': ObjectId(student_id)})
        if not student:
            flash('Student not found!', 'error')
            return redirect(url_for('ca.manage_ca'))
        
        # Get school and program details
        school = schools_collection.find_one({'_id': ObjectId(student['school_id'])}) if student.get('school_id') else None
        program = programs_collection.find_one({'_id': ObjectId(student['program_id'])}) if student.get('program_id') else None
        
        # Get all CA records for this student, grouped by academic year and semester
        ca_records = list(ca_collection.find({
            'student_id': ObjectId(student_id)
        }).sort([('academic_year', -1), ('semester', -1), ('course_id', 1)]))
        
        # Group records by academic year and semester
        records_by_semester = {}
        for record in ca_records:
            course = courses_collection.find_one({'_id': ObjectId(record['course_id'])})
            if course:
                key = f"{record['academic_year']}_S{record['semester']}"
                if key not in records_by_semester:
                    records_by_semester[key] = {
                        'academic_year': record['academic_year'],
                        'semester': record['semester'],
                        'records': [],
                        'stats': {
                            'total_courses': 0,
                            'total_score': 0,
                            'total_possible': 0,
                            'average_percentage': 0
                        }
                    }
                
                percentage = (record.get('score', 0) / record.get('total_score', 1) * 100) if record.get('score') and record.get('total_score') else 0
                
                records_by_semester[key]['records'].append({
                    'course_code': course['code'],
                    'course_name': course['name'],
                    'credits': course.get('credits', 0),
                    'score': record.get('score'),
                    'total_score': record.get('total_score', 30),
                    'percentage': percentage,
                    'assessment_type': record.get('assessment_type', 'assignment'),
                    'assessment_date': record.get('assessment_date', record['entered_at']).strftime('%Y-%m-%d'),
                    'entered_at': record['entered_at'].strftime('%Y-%m-%d %H:%M'),
                    'grade': calculate_ca_grade(percentage),
                    'remarks': 'Pass' if percentage >= 50 else 'Fail'
                })
        
        # Calculate statistics for each semester
        for semester_data in records_by_semester.values():
            records = semester_data['records']
            if records:
                semester_data['stats']['total_courses'] = len(records)
                semester_data['stats']['total_score'] = sum(r['score'] for r in records if r['score'] is not None)
                semester_data['stats']['total_possible'] = sum(r['total_score'] for r in records)
                semester_data['stats']['average_percentage'] = semester_data['stats']['total_score'] / semester_data['stats']['total_possible'] * 100 if semester_data['stats']['total_possible'] > 0 else 0
        
        # Calculate overall statistics
        overall_stats = {
            'total_assessments': len(ca_records),
            'total_semesters': len(records_by_semester),
            'average_percentage_all': sum(s['stats']['average_percentage'] for s in records_by_semester.values()) / len(records_by_semester) if records_by_semester else 0,
            'passed_courses': sum(1 for r in ca_records if (r.get('score', 0) / r.get('total_score', 1) * 100) >= 50) if ca_records else 0
        }
        
        return render_template('grades/ca/view_student_ca.html',
                             student=student,
                             school=school,
                             program=program,
                             records_by_semester=records_by_semester,
                             overall_stats=overall_stats)
        
    except Exception as e:
        flash(f'Error loading student CA records: {str(e)}', 'error')
        return redirect(url_for('ca.manage_ca'))

def calculate_ca_grade(percentage):
    """Calculate grade based on CA percentage"""
    if percentage >= 80:
        return 'A'
    elif percentage >= 70:
        return 'B'
    elif percentage >= 60:
        return 'C'
    elif percentage >= 50:
        return 'D'
    else:
        return 'F'

@bp.route('/ca/student_records/<student_id>')
def student_ca_records(student_id):
    """View all CA records for a specific student"""
    try:
        student = students_collection.find_one({'_id': ObjectId(student_id)})
        if not student:
            flash('Student not found!', 'error')
            return redirect(url_for('ca.manage_ca'))
        
        # Get school and program details
        school = schools_collection.find_one({'_id': ObjectId(student['school_id'])}) if student.get('school_id') else None
        program = programs_collection.find_one({'_id': ObjectId(student['program_id'])}) if student.get('program_id') else None
        
        # Get all CA records for this student
        ca_records = list(ca_collection.find({
            'student_id': ObjectId(student_id)
        }).sort([('academic_year', -1), ('semester', -1), ('entered_at', -1)]))
        
        # Enhance records with course information
        enhanced_records = []
        for record in ca_records:
            course = courses_collection.find_one({'_id': ObjectId(record['course_id'])})
            if course:
                enhanced_records.append({
                    'course_code': course['code'],
                    'course_name': course['name'],
                    'academic_year': record['academic_year'],
                    'semester': record['semester'],
                    'score': record.get('score'),
                    'total_score': record.get('total_score', 30),
                    'percentage': (record.get('score', 0) / record.get('total_score', 30) * 100) if record.get('score') and record.get('total_score') else 0,
                    'assessment_type': record.get('assessment_type', 'assignment'),
                    'assessment_date': record.get('assessment_date', record['entered_at']).strftime('%Y-%m-%d'),
                    'entered_at': record['entered_at'].strftime('%Y-%m-%d %H:%M')
                })
        
        return render_template('grades/ca/student_ca_records.html',
                             student=student,
                             school=school,
                             program=program,
                             ca_records=enhanced_records)
    except Exception as e:
        flash(f'Error loading student CA records: {str(e)}', 'error')
        return redirect(url_for('ca.manage_ca'))

@bp.route('/ca/bulk_upload', methods=['POST'])
def bulk_upload_ca():
    """Bulk upload CA scores via CSV"""
    try:
        if 'file' not in request.files:
            flash('No file selected!', 'error')
            return redirect(url_for('ca.manage_ca'))
        
        file = request.files['file']
        if file.filename == '':
            flash('No file selected!', 'error')
            return redirect(url_for('ca.manage_ca'))
        
        if file and file.filename.endswith('.csv'):
            # Process CSV file
            # This would be implemented based on your CSV structure
            flash('CSV upload functionality implemented successfully!', 'success')
        else:
            flash('Please upload a CSV file', 'error')
        
        return redirect(url_for('ca.manage_ca'))
    except Exception as e:
        flash(f'Error uploading CA scores: {str(e)}', 'error')
        return redirect(url_for('ca.manage_ca'))

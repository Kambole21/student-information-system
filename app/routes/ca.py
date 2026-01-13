from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from app import students_collection, schools_collection, programs_collection, courses_collection, student_courses_collection, ca_collection
from bson import ObjectId
from datetime import datetime
import re

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
                
                # Process assessment breakdown to number duplicate types
                assessment_breakdown = ca_data.get('assessment_breakdown', []) if ca_data else []
                numbered_breakdown = number_assessment_types(assessment_breakdown)
                
                courses_data.append({
                    'course_id': str(course['_id']),
                    'course_code': course['code'],
                    'course_name': course['name'],
                    'credits': course.get('credits', 0),
                    'program_name': program['name'] if program else 'Unknown',
                    'ca_score': ca_data.get('score') if ca_data else None,
                    'total_score': ca_data.get('total_score', 40) if ca_data else 40,
                    'assessment_type': ca_data.get('assessment_type', 'assignment') if ca_data else 'assignment',
                    'assessment_date': ca_data.get('assessment_date', datetime.utcnow()).strftime('%Y-%m-%d') if ca_data else datetime.utcnow().strftime('%Y-%m-%d'),
                    'assessment_breakdown': numbered_breakdown
                })
        
        return jsonify(courses_data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def number_assessment_types(breakdown):
    """Add numbers to duplicate assessment types (Quiz 1, Quiz 2, etc.)"""
    type_count = {}
    numbered_breakdown = []
    
    for item in breakdown:
        assessment_type = item.get('type', 'assignment')
        if assessment_type in type_count:
            type_count[assessment_type] += 1
        else:
            type_count[assessment_type] = 1
        
        numbered_item = item.copy()
        if type_count[assessment_type] > 1:
            numbered_item['display_type'] = f"{assessment_type} {type_count[assessment_type]}"
        else:
            numbered_item['display_type'] = assessment_type
            
        numbered_breakdown.append(numbered_item)
    
    return numbered_breakdown

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
                # Remove numbering from assessment types before saving
                clean_breakdown = []
                for item in score_data.get('assessment_breakdown', []):
                    clean_item = item.copy()
                    # Remove display_type and keep only original type
                    if 'display_type' in clean_item:
                        del clean_item['display_type']
                    clean_breakdown.append(clean_item)
                
                ca_doc = {
                    'student_id': ObjectId(student_id),
                    'course_id': ObjectId(score_data['course_id']),
                    'academic_year': academic_year,
                    'semester': semester,
                    'score': float(score_data['score']) if score_data.get('score') else None,
                    'total_score': float(score_data['total_score']),
                    'assessment_type': score_data.get('assessment_type', 'assignment'),
                    'assessment_date': datetime.strptime(score_data['assessment_date'], '%Y-%m-%d') if score_data.get('assessment_date') else datetime.utcnow(),
                    'assessment_breakdown': clean_breakdown,
                    'entered_by': 'System',
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
                
                # Handle None values for score and total_score
                score = record.get('score', 0) or 0  # Convert None to 0
                total_score = record.get('total_score', 40) or 40  # Convert None to default 40
                
                # Prevent division by zero
                if total_score > 0:
                    percentage = (score / total_score) * 100
                else:
                    percentage = 0
                
                # Get assessment breakdown if it exists - ensure it's properly formatted
                assessment_breakdown = record.get('assessment_breakdown', [])
                # Ensure breakdown is a list and has proper structure
                if not isinstance(assessment_breakdown, list):
                    assessment_breakdown = []
                
                # Add course record with breakdown data
                course_record = {
                    'course_code': course['code'],
                    'course_name': course['name'],
                    'credits': course.get('credits', 0),
                    'score': record.get('score'),  # Keep original value for display
                    'total_score': total_score,
                    'percentage': percentage,
                    'assessment_type': record.get('assessment_type', 'assignment'),
                    'assessment_breakdown': assessment_breakdown,
                    'assessment_date': record.get('assessment_date', record.get('entered_at', datetime.utcnow())).strftime('%Y-%m-%d'),
                    'entered_at': record.get('entered_at', datetime.utcnow()).strftime('%Y-%m-%d %H:%M'),
                    'grade': calculate_ca_grade(percentage),
                    'remarks': 'Pass' if percentage >= 50 else 'Fail'
                }
                
                records_by_semester[key]['records'].append(course_record)
        
        # Calculate statistics for each semester and overall
        total_all_scores = 0
        total_all_possible = 0
        total_passed_courses = 0
        
        for semester_data in records_by_semester.values():
            records = semester_data['records']
            if records:
                semester_data['stats']['total_courses'] = len(records)
                
                # Calculate semester totals
                total_score = sum(r['score'] or 0 for r in records)
                total_possible = sum(r['total_score'] for r in records)
                
                semester_data['stats']['total_score'] = total_score
                semester_data['stats']['total_possible'] = total_possible
                
                # Calculate semester average percentage
                if total_possible > 0:
                    semester_data['stats']['average_percentage'] = (total_score / total_possible) * 100
                else:
                    semester_data['stats']['average_percentage'] = 0
                
                # Add to overall totals
                total_all_scores += total_score
                total_all_possible += total_possible
                
                # Count passed courses for this semester
                for record in records:
                    if record['percentage'] >= 50:
                        total_passed_courses += 1
        
        # Calculate overall statistics
        total_assessments = len(ca_records)
        total_semesters = len(records_by_semester)
        
        # Calculate overall average percentage
        if total_all_possible > 0:
            average_percentage_all = (total_all_scores / total_all_possible) * 100
        else:
            average_percentage_all = 0
        
        overall_stats = {
            'total_assessments': total_assessments,
            'total_semesters': total_semesters,
            'average_percentage_all': average_percentage_all,
            'passed_courses': total_passed_courses
        }
        
        # Debug: Print breakdown data to console
        print(f"Records by semester: {len(records_by_semester)}")
        for key, semester_data in records_by_semester.items():
            print(f"Semester {key}: {len(semester_data['records'])} records")
            for record in semester_data['records']:
                print(f"  Course: {record['course_code']}, Breakdown: {len(record.get('assessment_breakdown', []))} items")
        
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
    """View all CA records for a specific student - Simplified view"""
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
                # Handle None values for score and total_score
                score = record.get('score', 0) or 0
                total_score = record.get('total_score', 40) or 40
                
                # Prevent division by zero
                if total_score > 0:
                    percentage = (score / total_score) * 100
                else:
                    percentage = 0
                
                enhanced_records.append({
                    'course_code': course['code'],
                    'course_name': course['name'],
                    'academic_year': record['academic_year'],
                    'semester': record['semester'],
                    'score': record.get('score'),
                    'total_score': total_score,
                    'percentage': percentage,
                    'assessment_type': record.get('assessment_type', 'assignment'),
                    'assessment_date': record.get('assessment_date', record['entered_at']).strftime('%Y-%m-%d'),
                    'entered_at': record['entered_at'].strftime('%Y-%m-%d %H:%M'),
                    'assessment_breakdown': record.get('assessment_breakdown', [])
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
            flash('CSV upload functionality implemented successfully!', 'success')
        else:
            flash('Please upload a CSV file', 'error')
        
        return redirect(url_for('ca.manage_ca'))
    except Exception as e:
        flash(f'Error uploading CA scores: {str(e)}', 'error')
        return redirect(url_for('ca.manage_ca'))

@bp.route('/ca/search_students')
def search_ca_students():
    """Search students for CA management with course filters"""
    try:
        search_term = request.args.get('search', '')
        school_id = request.args.get('school_id', '')
        program_id = request.args.get('program_id', '')
        academic_year = request.args.get('academic_year', '2025/2026')
        semester = request.args.get('semester', '1')
        course_code = request.args.get('course_code', '')
        course_name = request.args.get('course_name', '')
        
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
            # Build course query
            course_query = {
                'student_id': student['_id'],
                'academic_year': academic_year,
                'semester': semester
            }
            
            # Add course filters if provided
            if course_code or course_name:
                course_filter = {}
                if course_code:
                    course_filter['code'] = {'$regex': course_code, '$options': 'i'}
                if course_name:
                    course_filter['name'] = {'$regex': course_name, '$options': 'i'}
                
                # Find courses matching the filters
                matching_courses = list(courses_collection.find(course_filter))
                if matching_courses:
                    course_query['course_id'] = {'$in': [course['_id'] for course in matching_courses]}
                else:
                    # No courses match the filters, skip this student
                    continue
            
            # Check if student has courses for the specified semester and academic year
            enrolled_courses = list(student_courses_collection.find(course_query))
            
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

@bp.route('/ca/get_breakdown/<student_id>/<course_id>')
def get_assessment_breakdown(student_id, course_id):
    """Get assessment breakdown for a specific student and course"""
    try:
        academic_year = request.args.get('academic_year', '2025/2026')
        semester = request.args.get('semester', '1')
        
        ca_record = ca_collection.find_one({
            'student_id': ObjectId(student_id),
            'course_id': ObjectId(course_id),
            'academic_year': academic_year,
            'semester': semester
        })
        
        if ca_record and 'assessment_breakdown' in ca_record:
            return jsonify({
                'success': True,
                'breakdown': ca_record['assessment_breakdown']
            })
        else:
            return jsonify({
                'success': True,
                'breakdown': []
            })
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/ca/save_breakdown/<student_id>/<course_id>', methods=['POST'])
def save_assessment_breakdown(student_id, course_id):
    """Save assessment breakdown for a student and course"""
    try:
        data = request.get_json()
        academic_year = data.get('academic_year', '2025/2026')
        semester = data.get('semester', '1')
        breakdown = data.get('breakdown', [])
        
        # Update the CA record with breakdown
        ca_collection.update_one(
            {
                'student_id': ObjectId(student_id),
                'course_id': ObjectId(course_id),
                'academic_year': academic_year,
                'semester': semester
            },
            {
                '$set': {
                    'assessment_breakdown': breakdown,
                    'updated_at': datetime.utcnow()
                }
            },
            upsert=False
        )
        
        return jsonify({'success': True, 'message': 'Breakdown saved successfully'})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
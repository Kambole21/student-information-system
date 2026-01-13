from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify, session, send_file
from app import students_collection, schools_collection, programs_collection, courses_collection, student_courses_collection, accounts_collection
from bson import ObjectId
from datetime import datetime
import random
import string
from io import BytesIO
import qrcode  # Replace barcode with qrcode
from app.utils import get_semester_balance, get_semester_fees, has_staff_privilege

bp = Blueprint('exam_slip', __name__)

# Exam slip configuration
class ExamSlipConfig:
    THRESHOLD_PERCENTAGE = 80  # Default threshold

@bp.route('/slips')
def exam_slip_dashboard():
    """Exam slip management dashboard"""
    try:
        total_students = students_collection.count_documents({'status': 'active'})
        
        # Calculate qualified vs unqualified students (simplified calculation)
        qualified_students = 0  # You might want to implement actual calculation
        unqualified_students = total_students - qualified_students
        
        # Get recent activity (last 10 exam slip accesses)
        recent_activity = get_recent_exam_slip_activity()
        
        academic_years = get_academic_years()
        
        return render_template('academics/exam-slips/exam_slip_dashboard.html',
                             total_students=total_students,
                             qualified_students=qualified_students,
                             unqualified_students=unqualified_students,
                             current_threshold=ExamSlipConfig.THRESHOLD_PERCENTAGE,
                             recent_activity=recent_activity,
                             academic_years=academic_years)
    
    except Exception as e:
        flash(f'Error loading exam slip dashboard: {str(e)}', 'error')
        return render_template('academics/exam-slips/exam_slip_dashboard.html',
                             total_students=0,
                             qualified_students=0,
                             unqualified_students=0,
                             current_threshold=ExamSlipConfig.THRESHOLD_PERCENTAGE,
                             recent_activity=[],
                             academic_years=[])

@bp.route('/slips/config')
def exam_slip_config():
    """Exam slip configuration page"""
    try:
        total_students = students_collection.count_documents({'status': 'active'})
        staff_privileges = ['admin', 'registrar', 'finance', 'academics', 'admin_dvc', 'ict', 'admin_vc']
        
        return render_template('academics/exam-slips/exam_slip_config.html',
                             current_threshold=ExamSlipConfig.THRESHOLD_PERCENTAGE,
                             total_students=total_students,
                             staff_privileges=staff_privileges,
                             last_updated=datetime.now().strftime('%Y-%m-%d %H:%M'))
    
    except Exception as e:
        flash(f'Error loading configuration: {str(e)}', 'error')
        return redirect(url_for('exam_slip.exam_slip_dashboard'))

@bp.route('/slips/update_threshold', methods=['POST'])
def update_exam_slip_threshold():
    """Update exam slip threshold percentage"""
    try:
        # Check if request is JSON
        if not request.is_json:
            return jsonify({'success': False, 'error': 'Content-Type must be application/json'}), 400
        
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No JSON data provided'}), 400
            
        new_threshold = data.get('new_threshold')
        reason = data.get('reason', '').strip()
        
        # Validate new_threshold
        if new_threshold is None:
            return jsonify({'success': False, 'error': 'new_threshold is required'}), 400
        
        try:
            new_threshold = int(new_threshold)
        except (ValueError, TypeError):
            return jsonify({'success': False, 'error': 'Threshold must be a valid number'}), 400
        
        if new_threshold < 0 or new_threshold > 100:
            return jsonify({'success': False, 'error': 'Threshold must be between 0 and 100'}), 400
        
        if not reason:
            return jsonify({'success': False, 'error': 'Reason for change is required'}), 400
        
        # Update the threshold
        ExamSlipConfig.THRESHOLD_PERCENTAGE = new_threshold
        
        # Log the change
        print(f"Exam slip threshold updated to {new_threshold}% by {session.get('staff_id', 'unknown')}. Reason: {reason}")
        
        return jsonify({
            'success': True, 
            'message': f'Exam slip threshold updated to {new_threshold}% successfully',
            'new_threshold': new_threshold
        })
    
    except Exception as e:
        print(f"Error updating exam slip threshold: {str(e)}")
        return jsonify({'success': False, 'error': f'Server error: {str(e)}'}), 500

@bp.route('/slips/search_students', methods=['POST'])
def search_students():
    """Search students for exam slip viewing"""
    try:
        data = request.get_json()
        search_term = data.get('search_term', '')
        academic_year = data.get('academic_year', '2025/2026')
        semester = data.get('semester', '1')
        
        query = {'status': 'active'}
        
        # Build search query
        if search_term:
            query['$or'] = [
                {'student_number': {'$regex': search_term, '$options': 'i'}},
                {'f_name': {'$regex': search_term, '$options': 'i'}},
                {'l_name': {'$regex': search_term, '$options': 'i'}}
            ]
        
        # Sort students by name for consistent display
        students = list(students_collection.find(query).sort('f_name', 1).limit(20))
        
        students_data = []
        for student in students:
            # Get program and school info
            program = programs_collection.find_one({'_id': ObjectId(student['program_id'])}) if student.get('program_id') else None
            school = schools_collection.find_one({'_id': ObjectId(student['school_id'])}) if student.get('school_id') else None
            
            # Check qualification status
            qualified = is_student_qualified_for_exam_slip(student['_id'], semester, academic_year)
            
            students_data.append({
                'id': str(student['_id']),
                'student_number': student.get('student_number', 'N/A'),
                'name': f"{student.get('f_name', '')} {student.get('l_name', '')}",
                'program': program['name'] if program else 'N/A',
                'school': school['name'] if school else 'N/A',
                'qualified': qualified
            })
        
        return jsonify({'success': True, 'students': students_data})
    
    except Exception as e:
        print(f"Error in search_students: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@bp.route('/slips/view/<student_id>/<academic_year>/<semester>')
def view_exam_slip(student_id, academic_year, semester):
    """View exam slip for a student"""
    try:
        # Replace URL-encoded slashes in academic year
        academic_year = academic_year.replace('_', '/')
        
        student = students_collection.find_one({'_id': ObjectId(student_id)})
        if not student:
            flash('Student not found!', 'error')
            return redirect(url_for('exam_slip.exam_slip_dashboard'))
        
        # Get program and school info
        program = programs_collection.find_one({'_id': ObjectId(student['program_id'])}) if student.get('program_id') else None
        school = schools_collection.find_one({'_id': ObjectId(student['school_id'])}) if student.get('school_id') else None
        
        # Get enrolled courses for the semester
        enrolled_courses = get_enrolled_courses_for_semester(student_id, semester, academic_year)
        
        # Get complete financial summary using the updated function
        from app.utils import get_semester_financial_summary
        financial_summary = get_semester_financial_summary(student_id, semester, academic_year)
        
        total_fees = financial_summary['total_fees']
        current_balance = financial_summary['current_balance']
        amount_paid = financial_summary['amount_paid']
        paid_percentage = financial_summary['paid_percentage']
        has_actual_billing = financial_summary['has_actual_billing']
        billing_transactions = financial_summary['billing_transactions']
        payment_transactions = financial_summary['payment_transactions']
        
        # Check qualification
        qualified = is_student_qualified_for_exam_slip(student_id, semester, academic_year)
        
        # Generate QR code data
        qr_data = generate_qr_code_data(student, academic_year, semester, qualified)
        
        # Log access
        log_exam_slip_access(student_id, academic_year, semester, qualified)
        
        return render_template('academics/exam-slips/exam_slip.html',
                             student=student,
                             program=program,
                             school=school,
                             enrolled_courses=enrolled_courses,
                             academic_year=academic_year,
                             semester=semester,
                             total_fees=total_fees,
                             current_balance=current_balance,
                             amount_paid=amount_paid,
                             paid_percentage=paid_percentage,
                             qualified=qualified,
                             threshold_percentage=ExamSlipConfig.THRESHOLD_PERCENTAGE,
                             generated_date=datetime.now(),
                             qr_data=qr_data,
                             has_actual_billing=has_actual_billing,
                             billing_transactions=billing_transactions,
                             payment_transactions=payment_transactions)
    
    except Exception as e:
        flash(f'Error loading exam slip: {str(e)}', 'error')
        return redirect(url_for('exam_slip.exam_slip_dashboard'))

@bp.route('/slips/my_exam_slip')
def view_my_exam_slip():
    """View own exam slip (for students)"""
    try:
        if session.get('user_type') != 'student':
            flash('Access denied. Students only.', 'error')
            return redirect(url_for('exam_slip.exam_slip_dashboard'))
        
        student_id = session.get('profile_id')
        student = students_collection.find_one({'_id': ObjectId(student_id)})
        
        if not student:
            flash('Student profile not found!', 'error')
            return redirect(url_for('exam_slip.exam_slip_dashboard'))
        
        # Get current academic year and semester (you might want to make this dynamic)
        academic_year = '2025/2026'
        semester = '1'
        
        # Use URL-safe academic year for the redirect
        academic_year_safe = academic_year.replace('/', '_')
        
        return redirect(url_for('exam_slip.view_exam_slip', 
                              student_id=student_id, 
                              academic_year=academic_year_safe, 
                              semester=semester))
    
    except Exception as e:
        flash(f'Error accessing exam slip: {str(e)}', 'error')
        return redirect(url_for('exam_slip.exam_slip_dashboard'))

@bp.route('/slips/generate_qr/<student_id>/<academic_year>/<semester>')
def generate_qr_code(student_id, academic_year, semester):
    """Generate QR code for student exam slip"""
    try:
        # Replace URL-encoded slashes in academic year
        academic_year = academic_year.replace('_', '/')
        
        student = students_collection.find_one({'_id': ObjectId(student_id)})
        if not student:
            return send_file(BytesIO(b''), mimetype='image/png')
        
        # Generate QR code data
        qr_data = generate_qr_code_data(student, academic_year, semester, True)
        
        # Create QR code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(qr_data)
        qr.make(fit=True)
        
        # Create QR code image
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Save to bytes buffer
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        
        return send_file(buffer, mimetype='image/png', as_attachment=False)
    
    except Exception as e:
        print(f"Error generating QR code: {str(e)}")
        # Return empty image on error
        return send_file(BytesIO(b''), mimetype='image/png')

@bp.route('/slips/override_qualification/<student_id>', methods=['POST'])
def override_qualification(student_id):
    """Override qualification status for a student"""
    try:
        if not has_staff_privilege():
            return jsonify({'success': False, 'error': 'Insufficient privileges'})
        
        # Log the override
        print(f"Qualification overridden for student {student_id} by staff {session.get('staff_id')}")
        
        return jsonify({'success': True, 'message': 'Qualification overridden successfully'})
    
    except Exception as e:
        print(f"Error overriding qualification: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

def generate_qr_code_data(student, academic_year, semester, qualified):
    """Generate data for QR code"""
    base_url = request.host_url.rstrip('/')
    verification_url = f"{base_url}/slips/verify/{student['_id']}/{academic_year.replace('/', '_')}/{semester}"
    
    qr_data = {
        'student_name': f"{student['f_name']} {student['l_name']}",
        'student_number': student['student_number'],
        'academic_year': academic_year,
        'semester': semester,
        'qualified': qualified,
        'verification_url': verification_url,
        'timestamp': datetime.now().isoformat()
    }
    
    # Return as JSON string for QR code
    import json
    return json.dumps(qr_data, indent=2)

@bp.route('/slips/verify/<student_id>/<academic_year>/<semester>')
def verify_exam_slip(student_id, academic_year, semester):
    """Verification page for QR code scanning"""
    try:
        # Replace URL-encoded slashes in academic year
        academic_year = academic_year.replace('_', '/')
        
        student = students_collection.find_one({'_id': ObjectId(student_id)})
        if not student:
            return render_template('academics/exam-slips/verification.html',
                                 error="Student not found",
                                 valid=False)
        
        # Get program and school info
        program = programs_collection.find_one({'_id': ObjectId(student['program_id'])}) if student.get('program_id') else None
        school = schools_collection.find_one({'_id': ObjectId(student['school_id'])}) if student.get('school_id') else None
        
        # Check qualification
        qualified = is_student_qualified_for_exam_slip(student_id, semester, academic_year)
        
        return render_template('academics/exam-slips/verification.html',
                             student=student,
                             program=program,
                             school=school,
                             academic_year=academic_year,
                             semester=semester,
                             qualified=qualified,
                             valid=True,
                             verification_time=datetime.now())
    
    except Exception as e:
        return render_template('academics/exam-slips/verification.html',
                             error="Verification failed",
                             valid=False)

def is_student_qualified_for_exam_slip(student_id, semester, academic_year):
    """Check if student is qualified to access exam slip"""
    try:
        # Staff can always access
        if has_staff_privilege():
            return True
        
        # Calculate financial status
        total_fees = get_semester_fees(student_id, semester, academic_year)
        current_balance = get_semester_balance(student_id, semester, academic_year)
        amount_paid = total_fees - current_balance
        
        if total_fees <= 0:
            return True  # No fees configured
        
        paid_percentage = (amount_paid / total_fees) * 100
        return paid_percentage >= ExamSlipConfig.THRESHOLD_PERCENTAGE
    
    except Exception as e:
        print(f"Error checking qualification: {str(e)}")
        return False

def get_enrolled_courses_for_semester(student_id, semester, academic_year):
    """Get enrolled courses for a specific semester"""
    try:
        enrolled_courses = list(student_courses_collection.find({
            'student_id': ObjectId(student_id),
            'semester': semester,
            'academic_year': academic_year
        }))
        
        courses_info = []
        for ec in enrolled_courses:
            course = courses_collection.find_one({'_id': ObjectId(ec['course_id'])})
            if course:
                courses_info.append({
                    'course_code': course.get('code', 'N/A'),
                    'course_name': course.get('name', 'N/A'),
                    'credits': course.get('credits', 0),
                    'exam_date': None,  # You might want to add exam scheduling
                    'venue': None       # You might want to add venue information
                })
        
        return courses_info
    
    except Exception as e:
        print(f"Error getting enrolled courses: {str(e)}")
        return []

def get_recent_exam_slip_activity(limit=10):
    """Get recent exam slip access activity"""
    # This would typically come from a dedicated collection
    # For now, return empty list
    return []

def get_academic_years():
    """Generate academic years"""
    current_year = datetime.now().year
    return [f"{year}/{year+1}" for year in range(2020, 2030)]

def log_exam_slip_access(student_id, academic_year, semester, qualified):

    print(f"Exam slip accessed - Student: {student_id}, {academic_year} Sem {semester}, Qualified: {qualified}")

@bp.route('/slips/student_dashboard')
def student_exam_slip_dashboard():
    """Student exam slip dashboard"""
    try:
        if session.get('user_type') != 'student':
            flash('Access denied. Students only.', 'error')
            return redirect(url_for('exam_slip.exam_slip_dashboard'))
        
        student_id = session.get('profile_id')
        student = students_collection.find_one({'_id': ObjectId(student_id)})
        
        if not student:
            flash('Student profile not found!', 'error')
            return redirect(url_for('home.dashboard'))
        
        # Get program and school info
        program = programs_collection.find_one({'_id': ObjectId(student['program_id'])}) if student.get('program_id') else None
        school = schools_collection.find_one({'_id': ObjectId(student['school_id'])}) if student.get('school_id') else None
        
        academic_years = get_academic_years()
        
        return render_template('academics/exam-slips/student_exam_slip_dashboard.html',
                             student=student,
                             program=program,
                             school=school,
                             academic_years=academic_years,
                             threshold_percentage=ExamSlipConfig.THRESHOLD_PERCENTAGE)
    
    except Exception as e:
        flash(f'Error loading student exam slip dashboard: {str(e)}', 'error')
        return redirect(url_for('home.dashboard'))

@bp.route('/slips/get_student_slips', methods=['POST'])
def get_student_slips():
    """Get exam slips for a student with filtering"""
    try:
        data = request.get_json()
        student_id = data.get('student_id')
        academic_year_filter = data.get('academic_year', '')
        semester_filter = data.get('semester', '')
        
        if not student_id:
            return jsonify({'success': False, 'error': 'Student ID is required'})
        
        # Get all semesters the student has enrolled courses in
        pipeline = [
            {
                '$match': {
                    'student_id': ObjectId(student_id)
                }
            },
            {
                '$group': {
                    '_id': {
                        'academic_year': '$academic_year',
                        'semester': '$semester'
                    }
                }
            },
            {
                '$project': {
                    'academic_year': '$_id.academic_year',
                    'semester': '$_id.semester',
                    '_id': 0
                }
            },
            {
                '$sort': {
                    'academic_year': -1,
                    'semester': 1
                }
            }
        ]
        
        # Add filters if provided
        match_stage = {'$match': {'student_id': ObjectId(student_id)}}
        if academic_year_filter:
            match_stage['$match']['academic_year'] = academic_year_filter
        if semester_filter:
            match_stage['$match']['semester'] = semester_filter
        
        pipeline[0] = match_stage
        
        semesters = list(student_courses_collection.aggregate(pipeline))
        
        exam_slips = []
        total_courses = 0
        qualified_slips = 0
        total_fees = 0
        
        for semester_data in semesters:
            academic_year = semester_data['academic_year']
            semester = semester_data['semester']
            
            # Get enrolled courses for this semester
            enrolled_courses = get_enrolled_courses_for_semester(student_id, semester, academic_year)
            
            # Get financial summary
            from app.utils import get_semester_financial_summary
            financial_summary = get_semester_financial_summary(student_id, semester, academic_year)
            
            # Check qualification
            qualified = is_student_qualified_for_exam_slip(student_id, semester, academic_year)
            
            exam_slip_data = {
                'academic_year': academic_year,
                'semester': semester,
                'courses_count': len(enrolled_courses),
                'total_fees': financial_summary['total_fees'],
                'current_balance': financial_summary['current_balance'],
                'amount_paid': financial_summary['amount_paid'],
                'paid_percentage': financial_summary['paid_percentage'],
                'qualified': qualified,
                'has_actual_billing': financial_summary['has_actual_billing']
            }
            
            exam_slips.append(exam_slip_data)
            
            # Update stats
            total_courses += len(enrolled_courses)
            if qualified:
                qualified_slips += 1
            total_fees += financial_summary['total_fees']
        
        stats = {
            'total_courses': total_courses,
            'qualified_slips': qualified_slips,
            'total_fees': total_fees,
            'total_slips': len(exam_slips)
        }
        
        return jsonify({
            'success': True,
            'exam_slips': exam_slips,
            'stats': stats
        })
    
    except Exception as e:
        print(f"Error getting student slips: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})
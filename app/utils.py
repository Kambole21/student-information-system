from flask import session
from app import students_collection, programs_collection, courses_collection, student_courses_collection, accounts_collection, staff_collection
from bson import ObjectId
from app.config import SystemConfig
from datetime import datetime

def get_semester_fees(student_id, semester, academic_year):
    """Calculate total semester fees for a student"""
    try:
        student = students_collection.find_one({'_id': ObjectId(student_id)})
        if not student:
            return 0
        
        # Get student's program level
        program = programs_collection.find_one({'_id': ObjectId(student['program_id'])})
        level = program.get('level', 'undergraduate').lower() if program else 'undergraduate'
        
        # Map level to fee category
        level_mapping = {
            'certificate': 'certificate',
            'diploma': 'diploma', 
            'undergraduate': 'undergraduate',
            'bachelor': 'undergraduate',
            'postgraduate': 'postgraduate',
            'masters': 'postgraduate',
            'phd': 'postgraduate'
        }
        
        fee_category = level_mapping.get(level, 'undergraduate')
        base_fee = SystemConfig.DEFAULT_SEMESTER_FEES.get(fee_category, 1000.00)
        
        # Get additional course fees for the semester
        enrolled_courses = list(student_courses_collection.find({
            'student_id': ObjectId(student_id),
            'semester': semester,
            'academic_year': academic_year
        }))
        
        course_fees = 0
        for ec in enrolled_courses:
            course = courses_collection.find_one({'_id': ObjectId(ec['course_id'])})
            if course and course.get('course_fee'):
                course_fees += course.get('course_fee', 0)
        
        return base_fee + course_fees
        
    except Exception as e:
        print(f"Error calculating semester fees: {str(e)}")
        return SystemConfig.DEFAULT_SEMESTER_FEES['undergraduate']

def get_semester_balance(student_id, semester, academic_year):
    """Calculate balance for a specific semester"""
    try:
        # Get all transactions for the semester
        transactions = list(accounts_collection.find({
            'student_id': ObjectId(student_id),
            'semester': semester,
            'academic_year': academic_year
        }).sort('created_at', 1))
        
        balance = 0
        for transaction in transactions:
            if transaction['type'] == 'Billing':
                balance += transaction.get('debit', 0)
            else:  # Clearing
                balance -= transaction.get('credit', 0)
        
        print(f"Semester balance for {student_id}, {academic_year} Sem {semester}: {balance}")
        return balance
        
    except Exception as e:
        print(f"Error calculating semester balance: {str(e)}")
        return 0

def can_view_semester_grades(student_id, semester, academic_year, staff_id=None):
    """Check if student or staff can view grades for a semester"""
    try:
        # First check if current user has staff privileges (highest priority)
        if has_staff_privilege():
            print(f"Staff override: allowing grade view for {student_id}, {academic_year} Sem {semester}")
            return True
        
        # If specific staff_id is provided and staff has privilege, allow access
        if staff_id:
            staff = staff_collection.find_one({'_id': ObjectId(staff_id)})
            if staff and staff.get('privilege_level') in SystemConfig.GRADE_VIEW_PRIVILEGES:
                print(f"Staff {staff_id} has privilege to view grades")
                return True
        
        # Regular student balance check
        semester_balance = get_semester_balance(student_id, semester, academic_year)
        semester_fees = get_semester_fees(student_id, semester, academic_year)
        
        print(f"Checking grade view permission for {student_id}, {academic_year} Sem {semester}")
        print(f"Semester fees: {semester_fees}, Semester balance: {semester_balance}")
        
        if semester_fees <= 0:
            print("No fees configured, allowing access")
            return True  # No fees configured, allow access
        
        amount_paid = semester_fees - semester_balance
        paid_percentage = (amount_paid / semester_fees) * 100 if semester_fees > 0 else 100
        
        can_view = paid_percentage >= SystemConfig.BALANCE_THRESHOLD_PERCENTAGE
        
        print(f"Amount paid: {amount_paid}, Paid %: {paid_percentage:.2f}%, Threshold: {SystemConfig.BALANCE_THRESHOLD_PERCENTAGE}%, Can view: {can_view}")
        
        return can_view
        
    except Exception as e:
        print(f"Error checking grade view permission: {str(e)}")
        return False

def get_staff_privilege_level(staff_id):
    """Get staff privilege level"""
    try:
        staff = staff_collection.find_one({'_id': ObjectId(staff_id)})
        return staff.get('privilege_level') if staff else None
    except Exception as e:
        print(f"Error getting staff privilege: {str(e)}")
        return None

def has_staff_privilege():
    """Check if current user has staff viewing privileges"""
    try:
        if session.get('staff_id'):
            staff = staff_collection.find_one({'_id': ObjectId(session['staff_id'])})
            if staff and staff.get('privilege_level') in SystemConfig.GRADE_VIEW_PRIVILEGES:
                print(f"Staff {session['staff_id']} has privilege level: {staff.get('privilege_level')}")
                return True
        print(f"No staff privilege - staff_id: {session.get('staff_id')}")
        return False
    except Exception as e:
        print(f"Error checking staff privilege: {str(e)}")
        return False
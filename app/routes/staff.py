from flask import Blueprint, render_template, request, flash, redirect, url_for, session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os
from app import staff_collection, schools_collection, departments_collection, students_collection, users_collection
from bson import ObjectId
import uuid
from datetime import datetime

bp = Blueprint('staff', __name__)

# Allowed extensions for profile images
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
UPLOAD_FOLDER = 'app/static/uploads/staff'

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@bp.route('/staff')
def staff_dashboard():
    """Staff management dashboard"""
    total_staff = staff_collection.count_documents({})
    active_staff = staff_collection.count_documents({'status': 'active'})
    return render_template('users/staff/staff_dashboard.html', 
                         total_staff=total_staff,
                         active_staff=active_staff)

@bp.route('/staff/registration')
def staff_registration():
    """Staff registration page"""
    schools = list(schools_collection.find())
    return render_template('users/staff/staff_registration.html', schools=schools)

@bp.route('/staff/list')
def staff_list():
    """Staff list page"""
    staff_members = list(staff_collection.find())
    return render_template('users/staff/staff_list.html', staff_members=staff_members)

@bp.route('/staff/add', methods=['POST'])
def add_staff():
    try:
        # Get form data
        f_name = request.form['f_name']
        l_name = request.form['l_name']
        email = request.form['email']
        username = request.form['username']
        password = request.form['password']
        phone_number = request.form['phone_number']
        residential_address = request.form['residential_address']
        town = request.form['town']
        country = request.form['country']
        privilege_level = request.form['privilege_level']
        department = request.form.get('department', '')
        school_id = request.form.get('school_id', '')

        # Check if username or email already exists in staff collection
        existing_staff = staff_collection.find_one({
            '$or': [
                {'email': email},
                {'username': username}
            ]
        })
        
        if existing_staff:
            flash('Username or email already exists!', 'error')
            return redirect(url_for('staff.staff_registration'))

        # Check if username or email already exists in users collection
        existing_user = users_collection.find_one({
            '$or': [
                {'email': email},
                {'username': username}
            ]
        })
        
        if existing_user:
            flash('Username or email already exists in user accounts!', 'error')
            return redirect(url_for('staff.staff_registration'))

        # Handle file upload
        profile_image = 'profile.svg'
        if 'profile_image' in request.files:
            file = request.files['profile_image']
            if file and file.filename != '' and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                # Generate unique filename
                unique_filename = f"{uuid.uuid4()}_{filename}"
                file_path = os.path.join(UPLOAD_FOLDER, unique_filename)
                
                # Ensure upload directory exists
                os.makedirs(UPLOAD_FOLDER, exist_ok=True)
                file.save(file_path)
                profile_image = unique_filename

        # Create staff document
        staff_data = {
            'f_name': f_name,
            'l_name': l_name,
            'email': email,
            'username': username,
            'password': generate_password_hash(password),
            'phone_number': phone_number,
            'residential_address': residential_address,
            'town': town,
            'country': country,
            'privilege_level': privilege_level,
            'department': department,
            'school_id': ObjectId(school_id) if school_id else None,
            'profile_image': profile_image,
            'status': 'active',
            'created_at': datetime.utcnow()
        }

        # Insert into staff collection and get the result
        result = staff_collection.insert_one(staff_data)
        
        # Create user account for login
        user_data = {
            'staff_id': result.inserted_id,
            'username': username,
            'email': email,
            'password': generate_password_hash(password),  # Hash password again for users collection
            'user_type': 'staff',
            'privilege_level': privilege_level,
            'status': 'active',
            'created_at': datetime.utcnow(),
            'last_login': None
        }

        # Insert into users collection
        users_collection.insert_one(user_data)
        
        flash('Staff member registered successfully!', 'success')
        
    except Exception as e:
        flash(f'Error registering staff: {str(e)}', 'error')
        print(f"Error details: {str(e)}")  # For debugging
    
    return redirect(url_for('staff.staff_list'))

@bp.route('/staff/edit/<staff_id>')
def edit_staff(staff_id):
    """Edit staff page"""
    try:
        staff = staff_collection.find_one({'_id': ObjectId(staff_id)})
        if not staff:
            flash('Staff member not found!', 'error')
            return redirect(url_for('staff.staff_list'))
        
        schools = list(schools_collection.find())
        return render_template('users/staff/staff_edit.html', 
                             staff=staff, 
                             schools=schools)
    except Exception as e:
        flash('Invalid staff ID!', 'error')
        return redirect(url_for('staff.staff_list'))


@bp.route('/staff/update/<staff_id>', methods=['POST'])
def update_staff(staff_id):
    """Update staff information"""
    try:
        # Get form data
        f_name = request.form['f_name']
        l_name = request.form['l_name']
        email = request.form['email']
        username = request.form['username']
        phone_number = request.form['phone_number']
        residential_address = request.form['residential_address']
        town = request.form['town']
        country = request.form['country']
        privilege_level = request.form['privilege_level']
        department = request.form.get('department', '')
        school_id = request.form.get('school_id', '')
        status = request.form.get('status', 'active')

        # Check if username or email already exists (excluding current staff)
        existing_staff = staff_collection.find_one({
            '_id': {'$ne': ObjectId(staff_id)},
            '$or': [
                {'email': email},
                {'username': username}
            ]
        })
        
        if existing_staff:
            flash('Username or email already exists!', 'error')
            return redirect(url_for('staff.edit_staff', staff_id=staff_id))

        # Handle file upload
        update_data = {
            'f_name': f_name,
            'l_name': l_name,
            'email': email,
            'username': username,
            'phone_number': phone_number,
            'residential_address': residential_address,
            'town': town,
            'country': country,
            'privilege_level': privilege_level,
            'department': department,
            'school_id': ObjectId(school_id) if school_id else None,
            'status': status,
            'updated_at': datetime.utcnow()
        }

        # Handle password update if provided
        new_password = request.form.get('password')
        if new_password and new_password.strip():
            update_data['password'] = generate_password_hash(new_password)

        # Handle profile image update
        if 'profile_image' in request.files:
            file = request.files['profile_image']
            if file and file.filename != '' and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                unique_filename = f"{uuid.uuid4()}_{filename}"
                file_path = os.path.join(UPLOAD_FOLDER, unique_filename)
                
                os.makedirs(UPLOAD_FOLDER, exist_ok=True)
                file.save(file_path)
                update_data['profile_image'] = unique_filename

        # Update staff in database
        staff_collection.update_one(
            {'_id': ObjectId(staff_id)},
            {'$set': update_data}
        )
        
        # Also update the users collection
        user_update_data = {
            'username': username,
            'email': email,
            'privilege_level': privilege_level,
            'status': status,
            'updated_at': datetime.utcnow()
        }
        
        # Update password in users collection if changed
        if new_password and new_password.strip():
            user_update_data['password'] = generate_password_hash(new_password)
        
        users_collection.update_one(
            {'staff_id': ObjectId(staff_id)},
            {'$set': user_update_data}
        )
        
        flash('Staff member updated successfully!', 'success')
        
    except Exception as e:
        flash(f'Error updating staff: {str(e)}', 'error')
    
    return redirect(url_for('staff.staff_list'))

@bp.route('/staff/delete/<staff_id>')
def delete_staff(staff_id):
    """Delete staff member"""
    try:
        # Prevent self-deletion
        current_user_id = session.get('user_id')
        if str(current_user_id) == staff_id:
            flash('You cannot delete your own account!', 'error')
            return redirect(url_for('staff.staff_list'))
        
        result = staff_collection.delete_one({'_id': ObjectId(staff_id)})
        if result.deleted_count:
            # Also delete from users collection
            users_collection.delete_one({'staff_id': ObjectId(staff_id)})
            flash('Staff member deleted successfully!', 'success')
        else:
            flash('Staff member not found!', 'error')
            
    except Exception as e:
        flash(f'Error deleting staff: {str(e)}', 'error')
    
    return redirect(url_for('staff.staff_list'))

@bp.route('/staff/change_role/<staff_id>', methods=['POST'])
def change_role(staff_id):
    """Change staff role/privilege level"""
    try:
        new_role = request.form['privilege_level']
        department = request.form.get('department', '')
        school_id = request.form.get('school_id', '')
        
        update_data = {
            'privilege_level': new_role,
            'department': department,
            'school_id': school_id if school_id else None,
            'updated_at': datetime.utcnow()
        }
        
        staff_collection.update_one(
            {'_id': ObjectId(staff_id)},
            {'$set': update_data}
        )
        
        flash('Staff role updated successfully!', 'success')
        
    except Exception as e:
        flash(f'Error updating role: {str(e)}', 'error')
    
    return redirect(url_for('staff.staff_list'))

@bp.route('/get_departments/<school_id>')
def get_departments(school_id):
    try:
        departments = list(departments_collection.find({'school_id': ObjectId(school_id)}))
        departments_data = [{'id': str(dept['_id']), 'name': dept['name']} for dept in departments]
        return jsonify(departments_data)
    except Exception as e:
        return jsonify([])
        
@bp.route('/staff/profile')
@bp.route('/staff/profile/<staff_id>')
def staff_profile(staff_id=None):
    """Staff profile page - can be accessed by ID or by logged-in staff"""
    try:
        # If no staff_id provided, use logged-in staff's ID
        if staff_id is None:
            if 'user_type' not in session or session['user_type'] != 'staff':
                flash('Please log in as staff to view your profile.', 'error')
                return redirect(url_for('auth.login'))
            staff_id = session.get('profile_id')
        
        staff = staff_collection.find_one({'_id': ObjectId(staff_id)})
        if not staff:
            flash('Staff member not found!', 'error')
            return redirect(url_for('staff.staff_list'))
        
        # Check if the logged-in user is viewing their own profile
        is_own_profile = False
        if 'user_type' in session and session['user_type'] == 'staff':
            is_own_profile = session.get('profile_id') == staff_id
        
        # Get school name if exists
        school_name = None
        if staff.get('school_id'):
            school = schools_collection.find_one({'_id': ObjectId(staff['school_id'])})
            if school:
                school_name = school['name']
        
        return render_template('users/staff/staff_profile.html', 
                             staff=staff, 
                             school_name=school_name,
                             is_own_profile=is_own_profile)
    except Exception as e:
        flash('Invalid staff ID!', 'error')
        return redirect(url_for('staff.staff_list'))

@bp.route('/user_management')
def user_management():
    """User management dashboard"""
    # Get statistics from database
    total_students = students_collection.count_documents({})
    total_staff = staff_collection.count_documents({})
    total_lecturers = staff_collection.count_documents({'role': 'lecturer'})
    total_admin = staff_collection.count_documents({'role': {'$in': ['admin', 'administrator']}})
    
    # Get recent activity (you'll need to implement this)
    recent_activity = []  # This would come from your activity log
    
    return render_template('users/user_management.html',
                         total_students=total_students,
                         total_staff=total_staff,
                         total_lecturers=total_lecturers,
                         total_admin=total_admin,
                         recent_activity=recent_activity)
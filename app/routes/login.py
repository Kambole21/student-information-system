from flask import Blueprint, render_template, request, flash, redirect, url_for, session, jsonify
from werkzeug.security import check_password_hash
from app.forms import LoginForm
from app import users_collection, students_collection, staff_collection
from bson import ObjectId
import datetime

bp = Blueprint('auth', __name__)

@bp.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    
    if form.validate_on_submit():
        username = form.username.data
        password = form.password.data
        remember = form.remember.data
        
        # Find user by username, email, or student number
        user = users_collection.find_one({
            '$or': [
                {'username': username},
                {'email': username},
                {'student_number': username}
            ]
        })
        
        if user and check_password_hash(user['password'], password):
            if user['status'] != 'active':
                flash('Your account is inactive. Please contact administrator.', 'error')
                return render_template('auth/login.html', form=form)
            
            # Set session variables
            session['user_id'] = str(user['_id'])
            session['username'] = user.get('username') or user.get('student_number')
            session['email'] = user['email']
            session['user_type'] = user['user_type']
            session['privilege_level'] = user.get('privilege_level', 'student')
            
            # Store the actual user ID (student_id or staff_id) for profile access
            if user['user_type'] == 'student':
                session['profile_id'] = str(user['student_id'])
                # Get student details for session
                student = students_collection.find_one({'_id': ObjectId(user['student_id'])})
                if student:
                    session['full_name'] = f"{student['f_name']} {student['l_name']}"
                    session['profile_image'] = student.get('profile_image', 'profile.svg')
            else:  # staff
                session['profile_id'] = str(user['staff_id'])
                # Get staff details for session
                staff = staff_collection.find_one({'_id': ObjectId(user['staff_id'])})
                if staff:
                    session['full_name'] = f"{staff['f_name']} {staff['l_name']}"
                    session['profile_image'] = staff.get('profile_image', 'profile.svg')
            
            # Update last login
            users_collection.update_one(
                {'_id': user['_id']},
                {'$set': {'last_login': datetime.datetime.utcnow()}}
            )
            
            # Redirect based on user type
            if user['user_type'] == 'staff':
                flash(f'Welcome back, {session.get("full_name", "Staff")}!', 'success')
                return redirect(url_for('news_feed.news_dashboard'))
            else:
                flash(f'Welcome back, {session.get("full_name", "Student")}!', 'success')
                return redirect(url_for('news_feed.news_dashboard'))
        else:
            flash('Invalid username/student number or password.', 'error')
    
    return render_template('login.html', form=form)

@bp.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out successfully.', 'success')
    return redirect(url_for('auth.login'))

@bp.route('/profile')
def user_profile():
    """Redirect to the appropriate profile page based on user type"""
    if 'user_id' not in session:
        flash('Please log in to view your profile.', 'error')
        return redirect(url_for('auth.login'))
    
    user_type = session.get('user_type')
    profile_id = session.get('profile_id')
    
    if user_type == 'student' and profile_id:
        return redirect(url_for('student.student_profile', student_id=profile_id))
    elif user_type == 'staff' and profile_id:
        return redirect(url_for('staff.staff_profile', staff_id=profile_id))
    else:
        flash('Profile not found.', 'error')
        return redirect(url_for('news_feed.news_dashboard'))
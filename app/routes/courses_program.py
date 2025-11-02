from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from app import courses_collection, programs_collection, schools_collection
from bson import ObjectId

bp = Blueprint('courses_programs', __name__)

@bp.app_template_filter('max')
def max_filter(value, other):
    return max(value, other)



@bp.route('/academic-manager')
def academic_manager():
    # Get all data needed for the template
    schools = list(schools_collection.find())
    programs = list(programs_collection.find())
    courses = list(courses_collection.find())
    
    # Get counts
    schools_count = len(schools)
    programs_count = len(programs)
    courses_count = len(courses)
    
    # Get active counts
    active_schools_count = len([s for s in schools if s.get('status') == 'active'])
    active_programs_count = len([p for p in programs if p.get('status') == 'active'])
    active_courses_count = len([c for c in courses if c.get('status') == 'active'])
    
    # Get recent items (last 5)
    recent_schools = list(schools_collection.find().sort('_id', -1).limit(5))
    recent_programs = list(programs_collection.find().sort('_id', -1).limit(5))
    recent_courses = list(courses_collection.find().sort('_id', -1).limit(5))
    
    # Get dictionaries for names
    schools_dic = {str(s['_id']): s['name'] for s in schools}
    programs_dic = {str(p['_id']): p['name'] for p in programs}
    
    return render_template('academics/academic_manager.html',
                         schools_count=schools_count,
                         programs_count=programs_count,
                         courses_count=courses_count,
                         active_schools_count=active_schools_count,
                         active_programs_count=active_programs_count,
                         active_courses_count=active_courses_count,
                         recent_schools=recent_schools,
                         recent_programs=recent_programs,
                         recent_courses=recent_courses,
                         schools=schools,  # Pass schools for the program modal
                         programs=programs,  # Pass programs for the course modal
                         schools_dic=schools_dic,
                         programs_dic=programs_dic)

@bp.route('/schools-management')
def schools_management():
    schools = list(schools_collection.find())
    return render_template('academics/courses_program/schools.html', schools=schools)

@bp.route('/programs-management')
def programs_management():
    schools = list(schools_collection.find())
    programs = list(programs_collection.find())
    schools_dic = {str(s['_id']): s['name'] for s in schools}
    return render_template('academics/courses_program/programs.html', 
                         programs=programs, schools=schools, schools_dic=schools_dic)

@bp.route('/courses-management')
def courses_management():
    schools = list(schools_collection.find())
    programs = list(programs_collection.find())
    courses = list(courses_collection.find())
    
    schools_dic = {str(s['_id']): s['name'] for s in schools}
    programs_dic = {str(p['_id']): p['name'] for p in programs}
    
    return render_template('academics/courses_program/courses.html', 
                         courses=courses, programs=programs, schools_dic=schools_dic, programs_dic=programs_dic)

@bp.route('/Courses_Programs-Management')
def courses_programs_management():
    schools = list(schools_collection.find())
    programs = list(programs_collection.find())
    courses = list(courses_collection.find())

    schools_dic = {str(s['_id']): s['name'] for s in schools}
    programs_dic = {str(p['_id']): p['name'] for p in programs}
    return render_template('academics/courses_program/courses_programs.html', 
                         schools=schools, programs=programs, courses=courses,
                         schools_dic=schools_dic, programs_dic=programs_dic)

# School Management Routes
@bp.route('/add_school', methods=['POST'])
def add_school():
    try:
        school_data = {
            'name': request.form['name'],
            'code': request.form['code'],
            'description': request.form.get('description', ''),
            'dean': request.form.get('dean', ''),
            'status': request.form.get('status', 'active')
        }
        schools_collection.insert_one(school_data)
        flash('School added successfully!✅', 'success')
    except Exception as e:
        flash(f'Error adding school: {str(e)}', 'error')
    return redirect(url_for('courses_programs.academic_manager'))

@bp.route('/edit_school/<school_id>', methods=['POST'])
def edit_school(school_id):
    try:
        update_data = {
            'name': request.form['name'],
            'code': request.form['code'],
            'description': request.form.get('description', ''),
            'dean': request.form.get('dean', ''),
            'status': request.form.get('status', 'active')
        }
        schools_collection.update_one({'_id': ObjectId(school_id)}, {'$set': update_data})
        flash('School updated successfully!✅', 'success')
    except Exception as e:
        flash(f'Error updating school: {str(e)}', 'error')
    return redirect(url_for('courses_programs.academic_manager'))

@bp.route('/delete_school/<school_id>')
def delete_school(school_id):
    try:
        # Check if school has programs before deleting
        programs_count = programs_collection.count_documents({'school_id': ObjectId(school_id)})
        if programs_count > 0:
            flash('Cannot delete school with existing programs!', 'error')
        else:
            schools_collection.delete_one({'_id': ObjectId(school_id)})
            flash('School deleted successfully!✅', 'success')
    except Exception as e:
        flash(f'Error deleting school: {str(e)}', 'error')
    return redirect(url_for('courses_programs.academic_manager'))

# Program Management Routes
@bp.route('/add_program', methods=['POST'])
def add_program():
    try:
        program_data = {
            'name': request.form['name'],
            'code': request.form['code'],
            'school_id': ObjectId(request.form['school_id']),
            'duration': request.form['duration'],
            'credits_required': int(request.form['credits_required']),
            'description': request.form.get('description', ''),
            'level': request.form.get('level', 'undergraduate'),
            'status': request.form.get('status', 'active')
        }
        programs_collection.insert_one(program_data)
        flash('Program added successfully!✅', 'success')
    except Exception as e:
        flash(f'Error adding program: {str(e)}', 'error')
    return redirect(url_for('courses_programs.academic_manager'))

@bp.route('/edit_program/<program_id>', methods=['POST'])
def edit_program(program_id):
    try:
        update_data = {
            'name': request.form['name'],
            'code': request.form['code'],
            'school_id': ObjectId(request.form['school_id']),
            'duration': request.form['duration'],
            'credits_required': int(request.form['credits_required']),
            'description': request.form.get('description', ''),
            'level': request.form.get('level', 'undergraduate'),
            'status': request.form.get('status', 'active')
        }
        programs_collection.update_one({'_id': ObjectId(program_id)}, {'$set': update_data})
        flash('Program updated successfully!✅', 'success')
    except Exception as e:
        flash(f'Error updating program: {str(e)}', 'error')
    return redirect(url_for('courses_programs.academic_manager'))

@bp.route('/delete_program/<program_id>')
def delete_program(program_id):
    try:
        # Check if program has courses before deleting
        courses_count = courses_collection.count_documents({'program_id': ObjectId(program_id)})
        if courses_count > 0:
            flash('Cannot delete program with existing courses!', 'error')
        else:
            programs_collection.delete_one({'_id': ObjectId(program_id)})
            flash('Program deleted successfully!✅', 'success')
    except Exception as e:
        flash(f'Error deleting program: {str(e)}', 'error')
    return redirect(url_for('courses_programs.academic_manager'))

# Course Management Routes
@bp.route('/add_course', methods=['POST'])
def add_course():
    try:
        course_data = {
            'name': request.form['name'],
            'code': request.form['code'],
            'program_id': ObjectId(request.form['program_id']),
            'credits': int(request.form['credits']),
            'description': request.form.get('description', ''),
            'semester': request.form.get('semester', '1'),
            'level': request.form.get('level', '100'),
            'prerequisites': request.form.get('prerequisites', '').split(','),
            'status': request.form.get('status', 'active')
        }
        courses_collection.insert_one(course_data)
        flash('Course added successfully!✅', 'success')
    except Exception as e:
        flash(f'Error adding course: {str(e)}', 'error')
    return redirect(url_for('courses_programs.academic_manager'))

@bp.route('/edit_course/<course_id>', methods=['POST'])
def edit_course(course_id):
    try:
        update_data = {
            'name': request.form['name'],
            'code': request.form['code'],
            'program_id': ObjectId(request.form['program_id']),
            'credits': int(request.form['credits']),
            'description': request.form.get('description', ''),
            'semester': request.form.get('semester', '1'),
            'level': request.form.get('level', '100'),
            'prerequisites': request.form.get('prerequisites', '').split(','),
            'status': request.form.get('status', 'active')
        }
        courses_collection.update_one({'_id': ObjectId(course_id)}, {'$set': update_data})
        flash('Course updated successfully!✅', 'success')
    except Exception as e:
        flash(f'Error updating course: {str(e)}', 'error')
    return redirect(url_for('courses_programs.academic_manager'))

@bp.route('/delete_course/<course_id>')
def delete_course(course_id):
    try:
        courses_collection.delete_one({'_id': ObjectId(course_id)})
        flash('Course deleted successfully!✅', 'success')
    except Exception as e:
        flash(f'Error deleting course: {str(e)}', 'error')
    return redirect(url_for('courses_programs.academic_manager'))

# API Routes for dropdown data
@bp.route('/get_programs/<school_id>')
def get_programs(school_id):
    programs = list(programs_collection.find({'school_id': ObjectId(school_id)}))
    programs_data = [{'id': str(program['_id']), 'name': program['name']} for program in programs]
    return jsonify(programs_data)
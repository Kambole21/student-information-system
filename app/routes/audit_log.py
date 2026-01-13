from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify, session
from app import audit_log_collection, users_collection, staff_collection, students_collection
from bson import ObjectId
from datetime import datetime
from functools import wraps

bp = Blueprint('audit_log', __name__)

# Activity categories
ACTIVITY_CATEGORIES = {
    'login': 'Authentication',
    'logout': 'Authentication',
    'create': 'Data Creation',
    'update': 'Data Modification',
    'delete': 'Data Deletion',
    'view': 'Data Access',
    'publish': 'Publication',
    'download': 'File Operations',
    'upload': 'File Operations',
    'approve': 'Approval',
    'reject': 'Approval',
    'export': 'Data Export',
    'import': 'Data Import',
    'override': 'System Override'
}

# Action descriptions
ACTION_DESCRIPTIONS = {
    'login': 'User logged into the system',
    'logout': 'User logged out of the system',
    'create_student': 'Created new student record',
    'update_student': 'Updated student information',
    'delete_student': 'Deleted student record',
    'create_staff': 'Created new staff record',
    'update_staff': 'Updated staff information',
    'delete_staff': 'Deleted staff record',
    'create_invoice': 'Created financial invoice',
    'update_invoice': 'Updated financial invoice',
    'create_payment': 'Recorded payment',
    'create_semester_invoice': 'Created semester invoice',
    'update_threshold': 'Updated system threshold',
    'publish_grades': 'Published grades',
    'unpublish_grades': 'Unpublished grades',
    'create_news': 'Created news article',
    'update_news': 'Updated news article',
    'delete_news': 'Deleted news article',
    'enroll_courses': 'Enrolled in courses',
    'upload_ca': 'Uploaded CA scores',
    'save_grades': 'Saved grades',
    'create_course': 'Created new course',
    'update_course': 'Updated course information',
    'create_program': 'Created new program',
    'update_program': 'Updated program information',
    'create_school': 'Created new school',
    'update_school': 'Updated school information',
    'override_qualification': 'Overrode qualification status',
    'download_report': 'Downloaded report',
    'export_data': 'Exported data',
    'import_data': 'Imported data'
}

def log_activity(action, description=None, details=None, student_id=None, staff_id=None, 
                 collection_name=None, document_id=None, status='success'):
    """
    Log user activity to the audit trail
    
    Args:
        action: The action performed (e.g., 'login', 'create_student')
        description: Custom description (optional, will use default if not provided)
        details: Additional details about the action (dict)
        student_id: Associated student ID (if applicable)
        staff_id: Associated staff ID (if applicable)
        collection_name: MongoDB collection name where action occurred
        document_id: MongoDB document ID where action occurred
        status: 'success', 'failure', or 'warning'
    """
    try:
        user_id = session.get('user_id')
        user_type = session.get('user_type')
        username = session.get('username')
        full_name = session.get('full_name')
        ip_address = request.remote_addr if request else '127.0.0.1'
        user_agent = request.headers.get('User-Agent') if request else ''
        
        # Get category from action
        action_key = action.split('_')[0] if '_' in action else action
        category = ACTIVITY_CATEGORIES.get(action_key, 'Other')
        
        # Get description
        if not description:
            description = ACTION_DESCRIPTIONS.get(action, f"Performed {action}")
        
        # Prepare audit log entry
        audit_entry = {
            'timestamp': datetime.utcnow(),
            'action': action,
            'description': description,
            'category': category,
            'status': status,
            'user_id': ObjectId(user_id) if user_id else None,
            'user_type': user_type,
            'username': username,
            'full_name': full_name,
            'ip_address': ip_address,
            'user_agent': user_agent,
            'student_id': ObjectId(student_id) if student_id else None,
            'staff_id': ObjectId(staff_id) if staff_id else None,
            'collection_name': collection_name,
            'document_id': ObjectId(document_id) if document_id else None,
            'details': details or {},
            'session_id': session.get('session_id', ''),
            'referrer': request.referrer if request else ''
        }
        
        # Insert into audit log collection
        result = audit_log_collection.insert_one(audit_entry)
        return str(result.inserted_id)
        
    except Exception as e:
        print(f"Error logging activity: {str(e)}")
        return None

def audit_decorator(action, description=None, collection_name=None):
    """
    Decorator to automatically log function calls
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                # Call the original function
                result = func(*args, **kwargs)
                
                # Extract relevant info from kwargs
                student_id = kwargs.get('student_id')
                staff_id = kwargs.get('staff_id')
                document_id = kwargs.get('document_id')
                
                # Log the activity
                log_activity(
                    action=action,
                    description=description,
                    details={'function': func.__name__, 'kwargs': kwargs},
                    student_id=student_id,
                    staff_id=staff_id,
                    collection_name=collection_name,
                    document_id=document_id,
                    status='success'
                )
                
                return result
            except Exception as e:
                # Log failure
                log_activity(
                    action=action,
                    description=f"Failed: {description}",
                    details={'error': str(e), 'function': func.__name__, 'kwargs': kwargs},
                    status='failure'
                )
                raise e
        return wrapper
    return decorator

@bp.route('/audit-logs')
def audit_logs_dashboard():
    """Audit logs main dashboard"""
    try:
        # Get statistics
        total_logs = audit_log_collection.count_documents({})
        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        today_logs = audit_log_collection.count_documents({'timestamp': {'$gte': today}})
        
        # Get activity by user type
        user_activity = list(audit_log_collection.aggregate([
            {'$group': {
                '_id': '$user_type',
                'count': {'$sum': 1},
                'last_activity': {'$max': '$timestamp'}
            }},
            {'$sort': {'count': -1}}
        ]))
        
        # Get top actions
        top_actions = list(audit_log_collection.aggregate([
            {'$group': {
                '_id': '$action',
                'count': {'$sum': 1},
                'description': {'$first': '$description'}
            }},
            {'$sort': {'count': -1}},
            {'$limit': 10}
        ]))
        
        # Get recent activities - CONVERT ObjectId TO STRINGS
        recent_activities_cursor = audit_log_collection.find(
            {},
            {
                '_id': 1,
                'timestamp': 1,
                'action': 1,
                'description': 1,
                'username': 1,
                'full_name': 1,
                'user_type': 1,
                'status': 1,
                'ip_address': 1,
                'category': 1
            }
        ).sort('timestamp', -1).limit(50)
        
        recent_activities = []
        for log in recent_activities_cursor:
            log_dict = {
                'id': str(log['_id']),  # Convert ObjectId to string
                'timestamp': log['timestamp'],
                'timestamp_formatted': log['timestamp'].strftime('%Y-%m-%d %H:%M:%S'),
                'time_ago': get_time_ago(log['timestamp']),
                'action': log.get('action', ''),
                'description': log.get('description', ''),
                'username': log.get('username', ''),
                'full_name': log.get('full_name', ''),
                'user_type': log.get('user_type', ''),
                'status': log.get('status', ''),
                'ip_address': log.get('ip_address', ''),
                'category': log.get('category', '')
            }
            recent_activities.append(log_dict)
        
        return render_template('audit/audit_dashboard.html',
                             total_logs=total_logs,
                             today_logs=today_logs,
                             user_activity=user_activity,
                             top_actions=top_actions,
                             recent_activities=recent_activities,
                             categories=ACTIVITY_CATEGORIES)
    
    except Exception as e:
        flash(f'Error loading audit logs: {str(e)}', 'error')
        return render_template('audit/audit_dashboard.html',
                             total_logs=0,
                             today_logs=0,
                             user_activity=[],
                             top_actions=[],
                             recent_activities=[],
                             categories=ACTIVITY_CATEGORIES)

@bp.route('/audit-logs/search', methods=['POST'])
def search_audit_logs():
    """Search audit logs with filters"""
    try:
        data = request.get_json()
        
        # Build query based on filters
        query = {}
        
        # Date range filter
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        if start_date and end_date:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            end_dt = datetime.strptime(end_date, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
            query['timestamp'] = {'$gte': start_dt, '$lte': end_dt}
        
        # User type filter
        user_type = data.get('user_type')
        if user_type and user_type != 'all':
            query['user_type'] = user_type
        
        # Action filter
        action = data.get('action')
        if action and action != 'all':
            query['action'] = action
        
        # Category filter
        category = data.get('category')
        if category and category != 'all':
            query['category'] = category
        
        # Status filter
        status = data.get('status')
        if status and status != 'all':
            query['status'] = status
        
        # User search
        user_search = data.get('user_search')
        if user_search:
            query['$or'] = [
                {'username': {'$regex': user_search, '$options': 'i'}},
                {'full_name': {'$regex': user_search, '$options': 'i'}}
            ]
        
        # IP address search
        ip_search = data.get('ip_search')
        if ip_search:
            query['ip_address'] = {'$regex': ip_search, '$options': 'i'}
        
        # Pagination
        page = int(data.get('page', 1))
        per_page = int(data.get('per_page', 50))
        skip = (page - 1) * per_page
        
        # Get logs with proper projection
        logs = list(audit_log_collection.find(
            query,
            {
                '_id': 1,
                'timestamp': 1,
                'action': 1,
                'description': 1,
                'username': 1,
                'full_name': 1,
                'user_type': 1,
                'status': 1,
                'ip_address': 1,
                'category': 1,
                'details': 1
            }
        ).sort('timestamp', -1).skip(skip).limit(per_page))
        
        # Get total count for pagination
        total_count = audit_log_collection.count_documents(query)
        
        # Format logs for display - CONVERT ObjectId TO STRING
        formatted_logs = []
        for log in logs:
            # Create a new dict with serializable values
            formatted_log = {
                'id': str(log.get('_id', '')),
                'timestamp': log.get('timestamp', datetime.utcnow()),
                'timestamp_formatted': log.get('timestamp', datetime.utcnow()).strftime('%Y-%m-%d %H:%M:%S'),
                'time_ago': get_time_ago(log.get('timestamp', datetime.utcnow())),
                'action': log.get('action', ''),
                'description': log.get('description', ''),
                'username': log.get('username', ''),
                'full_name': log.get('full_name', ''),
                'user_type': log.get('user_type', ''),
                'status': log.get('status', ''),
                'ip_address': log.get('ip_address', ''),
                'category': log.get('category', ''),
                'details_formatted': format_details(log.get('details', {}))
            }
            formatted_logs.append(formatted_log)
        
        return jsonify({
            'success': True,
            'logs': formatted_logs,
            'total_count': total_count,
            'page': page,
            'per_page': per_page,
            'total_pages': (total_count + per_page - 1) // per_page
        })
    
    except Exception as e:
        print(f"Error searching audit logs: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@bp.route('/audit-logs/stats')
def get_audit_stats():
    """Get audit log statistics"""
    try:
        # Get stats for last 30 days
        thirty_days_ago = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        thirty_days_ago = thirty_days_ago.replace(day=thirty_days_ago.day - 30)
        
        # Daily activity for last 30 days
        daily_activity = list(audit_log_collection.aggregate([
            {'$match': {'timestamp': {'$gte': thirty_days_ago}}},
            {'$group': {
                '_id': {
                    'year': {'$year': '$timestamp'},
                    'month': {'$month': '$timestamp'},
                    'day': {'$dayOfMonth': '$timestamp'}
                },
                'count': {'$sum': 1}
            }},
            {'$sort': {'_id.year': 1, '_id.month': 1, '_id.day': 1}},
            {'$limit': 30}
        ]))
        
        # Activity by hour of day
        hourly_activity = list(audit_log_collection.aggregate([
            {'$group': {
                '_id': {'$hour': '$timestamp'},
                'count': {'$sum': 1}
            }},
            {'$sort': {'_id': 1}}
        ]))
        
        # Top users by activity
        top_users = list(audit_log_collection.aggregate([
            {'$group': {
                '_id': '$username',
                'full_name': {'$first': '$full_name'},
                'user_type': {'$first': '$user_type'},
                'count': {'$sum': 1},
                'last_activity': {'$max': '$timestamp'}
            }},
            {'$sort': {'count': -1}},
            {'$limit': 10}
        ]))
        
        # Status distribution
        status_distribution = list(audit_log_collection.aggregate([
            {'$group': {
                '_id': '$status',
                'count': {'$sum': 1}
            }}
        ]))
        
        # User type distribution for chart
        user_type_distribution = list(audit_log_collection.aggregate([
            {'$group': {
                '_id': '$user_type',
                'count': {'$sum': 1}
            }}
        ]))
        
        # Convert to serializable format
        serializable_daily_activity = []
        for item in daily_activity:
            serializable_daily_activity.append({
                '_id': {
                    'year': item['_id']['year'],
                    'month': item['_id']['month'],
                    'day': item['_id']['day']
                },
                'count': item['count']
            })
        
        serializable_hourly_activity = []
        for item in hourly_activity:
            serializable_hourly_activity.append({
                '_id': item['_id'],
                'count': item['count']
            })
        
        serializable_top_users = []
        for item in top_users:
            serializable_top_users.append({
                '_id': item['_id'],
                'full_name': item['full_name'],
                'user_type': item['user_type'],
                'count': item['count'],
                'last_activity': item['last_activity'].isoformat() if item['last_activity'] else None
            })
        
        serializable_status_distribution = []
        for item in status_distribution:
            serializable_status_distribution.append({
                '_id': item['_id'],
                'count': item['count']
            })
        
        serializable_user_type_distribution = []
        for item in user_type_distribution:
            serializable_user_type_distribution.append({
                '_id': item['_id'],
                'count': item['count']
            })
        
        return jsonify({
            'success': True,
            'daily_activity': serializable_daily_activity,
            'hourly_activity': serializable_hourly_activity,
            'top_users': serializable_top_users,
            'status_distribution': serializable_status_distribution,
            'user_type_distribution': serializable_user_type_distribution
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@bp.route('/audit-logs/user/<user_id>')
def user_activity_logs(user_id):
    """Get activity logs for a specific user"""
    try:
        # Determine if user is student or staff
        user = users_collection.find_one({'_id': ObjectId(user_id)})
        if not user:
            flash('User not found', 'error')
            return redirect(url_for('audit_log.audit_logs_dashboard'))
        
        # Get user details
        if user['user_type'] == 'student':
            profile = students_collection.find_one({'_id': ObjectId(user['student_id'])})
            profile_type = 'student'
        else:
            profile = staff_collection.find_one({'_id': ObjectId(user['staff_id'])})
            profile_type = 'staff'
        
        # Get user's activity logs - CONVERT ObjectId TO STRINGS
        logs_cursor = audit_log_collection.find(
            {'user_id': ObjectId(user_id)},
            {
                '_id': 1,
                'timestamp': 1,
                'action': 1,
                'description': 1,
                'status': 1,
                'ip_address': 1,
                'category': 1,
                'details': 1
            }
        ).sort('timestamp', -1).limit(100)
        
        logs = []
        for log in logs_cursor:
            log_dict = {
                'id': str(log['_id']),
                'timestamp': log['timestamp'],
                'timestamp_formatted': log['timestamp'].strftime('%Y-%m-%d %H:%M:%S'),
                'time_ago': get_time_ago(log['timestamp']),
                'action': log.get('action', ''),
                'description': log.get('description', ''),
                'status': log.get('status', ''),
                'ip_address': log.get('ip_address', ''),
                'category': log.get('category', ''),
                'details_formatted': format_details(log.get('details', {}))
            }
            logs.append(log_dict)
        
        # Get user statistics
        total_actions = len(logs)
        success_count = sum(1 for log in logs if log.get('status') == 'success')
        failure_count = total_actions - success_count
        
        # Most common actions
        from collections import Counter
        action_counts = Counter(log.get('action', '') for log in logs)
        common_actions = action_counts.most_common(5)
        
        return render_template('audit/user_activity.html',
                             user=user,
                             profile=profile,
                             profile_type=profile_type,
                             logs=logs,
                             total_actions=total_actions,
                             success_count=success_count,
                             failure_count=failure_count,
                             common_actions=common_actions)
    
    except Exception as e:
        flash(f'Error loading user activity: {str(e)}', 'error')
        return redirect(url_for('audit_log.audit_logs_dashboard'))

@bp.route('/audit-logs/export')
def export_audit_logs():
    """Export audit logs to CSV"""
    try:
        # Get filters from query parameters
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        query = {}
        if start_date and end_date:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            end_dt = datetime.strptime(end_date, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
            query['timestamp'] = {'$gte': start_dt, '$lte': end_dt}
        
        # Get logs
        logs = list(audit_log_collection.find(query).sort('timestamp', -1))
        
        # Convert to CSV format
        import csv
        from io import StringIO
        
        output = StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow([
            'Timestamp', 'Action', 'Description', 'Category', 'Status',
            'Username', 'Full Name', 'User Type', 'IP Address',
            'Student ID', 'Staff ID', 'Collection', 'Document ID'
        ])
        
        # Write data - CONVERT ObjectId TO STRINGS
        for log in logs:
            writer.writerow([
                log.get('timestamp', '').strftime('%Y-%m-%d %H:%M:%S'),
                log.get('action', ''),
                log.get('description', ''),
                log.get('category', ''),
                log.get('status', ''),
                log.get('username', ''),
                log.get('full_name', ''),
                log.get('user_type', ''),
                log.get('ip_address', ''),
                str(log.get('student_id', '')) if log.get('student_id') else '',
                str(log.get('staff_id', '')) if log.get('staff_id') else '',
                log.get('collection_name', ''),
                str(log.get('document_id', '')) if log.get('document_id') else ''
            ])
        
        # Create response
        from flask import Response
        response = Response(
            output.getvalue(),
            mimetype="text/csv",
            headers={"Content-disposition": "attachment; filename=audit_logs.csv"}
        )
        
        return response
    
    except Exception as e:
        flash(f'Error exporting audit logs: {str(e)}', 'error')
        return redirect(url_for('audit_log.audit_logs_dashboard'))

@bp.route('/audit-logs/details/<log_id>')
def get_log_details(log_id):
    """Get detailed information for a specific log entry"""
    try:
        log = audit_log_collection.find_one({'_id': ObjectId(log_id)})
        if not log:
            return jsonify({'success': False, 'error': 'Log entry not found'})
        
        # Format the log for display - CONVERT ALL ObjectId TO STRINGS
        formatted_log = {
            'id': str(log.get('_id', '')),
            'timestamp': log.get('timestamp', datetime.utcnow()),
            'timestamp_formatted': log.get('timestamp', datetime.utcnow()).strftime('%Y-%m-%d %H:%M:%S'),
            'action': log.get('action', ''),
            'description': log.get('description', ''),
            'category': log.get('category', ''),
            'status': log.get('status', ''),
            'username': log.get('username', ''),
            'full_name': log.get('full_name', ''),
            'user_type': log.get('user_type', ''),
            'ip_address': log.get('ip_address', ''),
            'user_agent': log.get('user_agent', ''),
            'referrer': log.get('referrer', ''),
            'session_id': log.get('session_id', ''),
            'collection_name': log.get('collection_name', ''),
            'details': log.get('details', {}),
            'details_formatted': format_details(log.get('details', {}))
        }
        
        # Convert ObjectId fields to strings
        if log.get('user_id'):
            formatted_log['user_id'] = str(log['user_id'])
        else:
            formatted_log['user_id'] = None
            
        if log.get('student_id'):
            formatted_log['student_id'] = str(log['student_id'])
        else:
            formatted_log['student_id'] = None
            
        if log.get('staff_id'):
            formatted_log['staff_id'] = str(log['staff_id'])
        else:
            formatted_log['staff_id'] = None
            
        if log.get('document_id'):
            formatted_log['document_id'] = str(log['document_id'])
        else:
            formatted_log['document_id'] = None
        
        # Get user details if available
        if log.get('user_id'):
            user = users_collection.find_one({'_id': ObjectId(log['user_id'])})
            if user:
                formatted_log['user_email'] = user.get('email', 'N/A')
            else:
                formatted_log['user_email'] = 'N/A'
        else:
            formatted_log['user_email'] = 'N/A'
        
        return jsonify({'success': True, 'log': formatted_log})
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@bp.route('/audit-logs/clear-old')
def clear_old_logs():
    """Clear audit logs older than specified days"""
    try:
        # Only admin can clear logs
        if session.get('privilege_level') != 'admin':
            flash('Administrator privileges required', 'error')
            return redirect(url_for('audit_log.audit_logs_dashboard'))
        
        days_to_keep = 90  # Keep logs for 90 days by default
        
        cutoff_date = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        cutoff_date = cutoff_date.replace(day=cutoff_date.day - days_to_keep)
        
        result = audit_log_collection.delete_many({'timestamp': {'$lt': cutoff_date}})
        
        flash(f'Cleared {result.deleted_count} audit logs older than {days_to_keep} days', 'success')
        return redirect(url_for('audit_log.audit_logs_dashboard'))
    
    except Exception as e:
        flash(f'Error clearing old logs: {str(e)}', 'error')
        return redirect(url_for('audit_log.audit_logs_dashboard'))

def get_time_ago(timestamp):
    """Calculate how long ago the timestamp was"""
    now = datetime.utcnow()
    diff = now - timestamp

    seconds = diff.total_seconds()
    minutes = seconds / 60
    hours = minutes / 60
    days = hours / 24
    
    if diff.days > 365:
        years = diff.days // 365
        return f"{years} year{'s' if years > 1 else ''} ago"
    elif diff.days > 30:
        months = diff.days // 30
        return f"{months} month{'s' if months > 1 else ''} ago"
    elif diff.days > 0:
        return f"{diff.days} day{'s' if diff.days > 1 else ''} ago"
    elif diff.seconds > 3600:
        hours = diff.seconds // 3600
        return f"{hours} hour{'s' if hours > 1 else ''} ago"
    elif diff.seconds > 60:
        minutes = diff.seconds // 60
        return f"{minutes} minute{'s' if minutes > 1 else ''} ago"
    else:
        return "Just now"

def format_details(details):
    """Format details dictionary for display"""
    if not details:
        return "No additional details"
    
    formatted = []
    for key, value in details.items():
        if isinstance(value, dict):
            formatted.append(f"{key}:")
            for sub_key, sub_value in value.items():
                formatted.append(f"  {sub_key}: {sub_value}")
        else:
            formatted.append(f"{key}: {value}")
    
    return "<br>".join(formatted)

# Helper function to add audit logging to existing routes
def add_audit_logging_to_existing_routes():
    """
    This function shows how you can modify existing routes to add audit logging.
    You would call the log_activity function in each route handler.
    """
    pass
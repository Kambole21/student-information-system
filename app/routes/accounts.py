from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from app import accounts_collection, students_collection, schools_collection, programs_collection, courses_collection
from bson import ObjectId
from datetime import datetime
import random
import string

bp = Blueprint('accounts', __name__)

def generate_transaction_code():
    """Generate transaction code: 3 random uppercase letters + 4 numbers"""
    letters = ''.join(random.choices(string.ascii_uppercase, k=3))
    numbers = ''.join(random.choices(string.digits, k=4))
    return f"{letters}{numbers}"

def get_student_balance(student_id):
    """Calculate current balance for a student"""
    try:
        # Get all transactions for the student, sorted by date
        transactions = list(accounts_collection.find({
            'student_id': ObjectId(student_id)
        }).sort('created_at', 1))
        
        balance = 0
        for transaction in transactions:
            if transaction['type'] == 'Billing':
                balance += transaction.get('debit', 0)
            else:  # Clearing
                balance -= transaction.get('credit', 0)
        
        print(f"Balance for student {student_id}: {balance}")
        return balance
        
    except Exception as e:
        print(f"Error calculating balance for student {student_id}: {str(e)}")
        return 0

def recalculate_student_balance(student_id):
    """Recalculate and update all balances for a student after transaction update"""
    try:
        # Get all transactions for the student, sorted by date
        transactions = list(accounts_collection.find({
            'student_id': ObjectId(student_id)
        }).sort('created_at', 1))
        
        balance = 0
        for transaction in transactions:
            if transaction['type'] == 'Billing':
                balance += transaction.get('debit', 0)
            else:  # Clearing
                balance -= transaction.get('credit', 0)
            
            # Update the balance_after field for each transaction
            accounts_collection.update_one(
                {'_id': transaction['_id']},
                {'$set': {'balance_after': balance}}
            )
        
        return balance
    except Exception as e:
        print(f"Error recalculating balance for student {student_id}: {str(e)}")
        return 0

@bp.route('/Accounts')
def accounts_management():
    """Accounts management dashboard"""
    try:
        total_students = students_collection.count_documents({})
        total_transactions = accounts_collection.count_documents({})
        
        # Calculate total revenue (sum of all billing transactions)
        pipeline = [
            {'$match': {'type': 'Billing'}},
            {'$group': {'_id': None, 'total_billing': {'$sum': '$debit'}}}
        ]
        billing_result = list(accounts_collection.aggregate(pipeline))
        total_billing = billing_result[0]['total_billing'] if billing_result else 0
        
        # Calculate total payments (sum of all clearing transactions)
        pipeline = [
            {'$match': {'type': 'Clearing'}},
            {'$group': {'_id': None, 'total_clearing': {'$sum': '$credit'}}}
        ]
        clearing_result = list(accounts_collection.aggregate(pipeline))
        total_clearing = clearing_result[0]['total_clearing'] if clearing_result else 0
        
        outstanding_balance = total_billing - total_clearing
        
        # Get schools and programs for filters
        schools = list(schools_collection.find({'status': 'active'}))
        programs = list(programs_collection.find({'status': 'active'}))
        
        return render_template('accounts/accounts_management.html',
                             total_students=total_students,
                             total_transactions=total_transactions,
                             total_billing=total_billing,
                             total_clearing=total_clearing,
                             outstanding_balance=outstanding_balance,
                             schools=schools,
                             programs=programs)
    except Exception as e:
        flash(f'Error loading accounts dashboard: {str(e)}', 'error')
        return render_template('accounts/accounts_management.html',
                             total_students=0,
                             total_transactions=0,
                             total_billing=0,
                             total_clearing=0,
                             outstanding_balance=0,
                             schools=[],
                             programs=[])

@bp.route('/accounts/create_invoice')
def create_invoice():
    """Create invoice page"""
    schools = list(schools_collection.find({'status': 'active'}))
    programs = list(programs_collection.find({'status': 'active'}))
    courses = list(courses_collection.find({'status': 'active'}))
    
    return render_template('accounts/create_invoice.html',
                         schools=schools,
                         programs=programs,
                         courses=courses)

@bp.route('/accounts/get_students', methods=['POST'])
def get_students():
    """Get students based on filters"""
    try:
        data = request.get_json()
        filter_type = data.get('filter_type')
        filter_value = data.get('filter_value')
        search_term = data.get('search_term', '')
        
        query = {'status': 'active'}
        
        if filter_type == 'all':
            # Get all active students
            if search_term:
                query['$or'] = [
                    {'student_number': {'$regex': search_term, '$options': 'i'}},
                    {'f_name': {'$regex': search_term, '$options': 'i'}},
                    {'l_name': {'$regex': search_term, '$options': 'i'}}
                ]
            students = list(students_collection.find(query))
        elif filter_type == 'program' and filter_value:
            query['program_id'] = ObjectId(filter_value)
            if search_term:
                query['$or'] = [
                    {'student_number': {'$regex': search_term, '$options': 'i'}},
                    {'f_name': {'$regex': search_term, '$options': 'i'}},
                    {'l_name': {'$regex': search_term, '$options': 'i'}}
                ]
            students = list(students_collection.find(query))
        elif filter_type == 'school' and filter_value:
            query['school_id'] = ObjectId(filter_value)
            if search_term:
                query['$or'] = [
                    {'student_number': {'$regex': search_term, '$options': 'i'}},
                    {'f_name': {'$regex': search_term, '$options': 'i'}},
                    {'l_name': {'$regex': search_term, '$options': 'i'}}
                ]
            students = list(students_collection.find(query))
        elif filter_type == 'course' and filter_value:
            # Get students enrolled in this course using aggregation
            pipeline = [
                {
                    '$match': {
                        'course_id': ObjectId(filter_value),
                        'status': 'enrolled'
                    }
                },
                {
                    '$lookup': {
                        'from': 'students',
                        'localField': 'student_id',
                        'foreignField': '_id',
                        'as': 'student_info'
                    }
                },
                {
                    '$unwind': '$student_info'
                },
                {
                    '$match': {
                        'student_info.status': 'active'
                    }
                }
            ]
            
            # Add search filter if provided
            if search_term:
                pipeline.append({
                    '$match': {
                        '$or': [
                            {'student_info.student_number': {'$regex': search_term, '$options': 'i'}},
                            {'student_info.f_name': {'$regex': search_term, '$options': 'i'}},
                            {'student_info.l_name': {'$regex': search_term, '$options': 'i'}}
                        ]
                    }
                })
            
            pipeline.append({
                '$replaceRoot': {'newRoot': '$student_info'}
            })
            
            students = list(student_courses_collection.aggregate(pipeline))
        elif filter_type == 'level' and filter_value:
            # Map level to program types
            level_mapping = {
                'certificate': 'Certificate',
                'diploma': 'Diploma', 
                'undergraduate': 'Undergraduate',
                'postgraduate': 'Postgraduate'
            }
            level_name = level_mapping.get(filter_value, filter_value)
            
            # Get programs with this level
            programs = list(programs_collection.find({
                'level': level_name,
                'status': 'active'
            }))
            
            program_ids = [program['_id'] for program in programs]
            if program_ids:
                query['program_id'] = {'$in': program_ids}
                if search_term:
                    query['$or'] = [
                        {'student_number': {'$regex': search_term, '$options': 'i'}},
                        {'f_name': {'$regex': search_term, '$options': 'i'}},
                        {'l_name': {'$regex': search_term, '$options': 'i'}}
                    ]
                students = list(students_collection.find(query))
            else:
                students = []
        elif filter_type == 'individual':
            # Search for individual students
            if search_term:
                query['$or'] = [
                    {'student_number': {'$regex': search_term, '$options': 'i'}},
                    {'f_name': {'$regex': search_term, '$options': 'i'}},
                    {'l_name': {'$regex': search_term, '$options': 'i'}}
                ]
                students = list(students_collection.find(query).limit(50))  # Limit results for performance
            else:
                students = []
        else:
            students = []
        
        students_data = []
        for student in students:
            if not student:  # Skip if student is None
                continue
                
            # Get program and school info
            program = programs_collection.find_one({'_id': ObjectId(student['program_id'])}) if student.get('program_id') else None
            school = schools_collection.find_one({'_id': ObjectId(student['school_id'])}) if student.get('school_id') else None
            
            students_data.append({
                'id': str(student['_id']),
                'student_number': student.get('student_number', 'N/A'),
                'name': f"{student.get('f_name', '')} {student.get('l_name', '')}",
                'program': program['name'] if program else 'N/A',
                'school': school['name'] if school else 'N/A',
                'current_balance': get_student_balance(student['_id'])
            })
        
        return jsonify({'success': True, 'students': students_data})
    
    except Exception as e:
        print(f"Error in get_students: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@bp.route('/accounts/create_transaction', methods=['POST'])
def create_transaction():
    """Create a transaction (invoice or payment)"""
    try:
        data = request.get_json()
        transaction_type = data.get('type')  # 'Billing' or 'Clearing'
        amount = float(data.get('amount', 0))
        description = data.get('description', '')
        student_ids = data.get('student_ids', [])
        filter_type = data.get('filter_type', '')
        filter_value = data.get('filter_value', '')
        
        print(f"Creating transaction: type={transaction_type}, amount={amount}, students={len(student_ids)}, filter_type={filter_type}")
        
        if not student_ids:
            return jsonify({'success': False, 'error': 'No students selected'})
        
        if amount <= 0:
            return jsonify({'success': False, 'error': 'Amount must be greater than 0'})
        
        # Generate a single transaction code for this batch
        transaction_code = generate_transaction_code()
        created_count = 0
        
        # Get filter description for reference
        filter_description = f"Filter: {filter_type}"
        if filter_value:
            if filter_type == 'program':
                program = programs_collection.find_one({'_id': ObjectId(filter_value)})
                filter_description += f" - {program['name'] if program else filter_value}"
            elif filter_type == 'school':
                school = schools_collection.find_one({'_id': ObjectId(filter_value)})
                filter_description += f" - {school['name'] if school else filter_value}"
            elif filter_type == 'course':
                course = courses_collection.find_one({'_id': ObjectId(filter_value)})
                filter_description += f" - {course['name'] if course else filter_value}"
            elif filter_type == 'level':
                filter_description += f" - {filter_value}"
            elif filter_type == 'individual':
                filter_description += " - Selected Students"
        
        for student_id in student_ids:
            try:
                student = students_collection.find_one({'_id': ObjectId(student_id)})
                if not student:
                    print(f"Student {student_id} not found")
                    continue
                
                # Get current balance before transaction
                current_balance = get_student_balance(student_id)
                
                # Create transaction data with filter reference
                transaction_data = {
                    'transaction_code': transaction_code,
                    'student_id': ObjectId(student_id),
                    'type': transaction_type,
                    'description': description,
                    'filter_reference': filter_description,
                    'debit': amount if transaction_type == 'Billing' else 0,
                    'credit': amount if transaction_type == 'Clearing' else 0,
                    'balance_after': current_balance + (amount if transaction_type == 'Billing' else -amount),
                    'created_at': datetime.utcnow(),
                    'created_by': 'system',  # You can replace this with actual user from session
                    'batch_transaction': True if len(student_ids) > 1 else False
                }
                
                # Insert transaction
                result = accounts_collection.insert_one(transaction_data)
                created_count += 1
                
                print(f"Created transaction {transaction_code} for student {student_id}")
                
            except Exception as e:
                print(f"Error creating transaction for student {student_id}: {str(e)}")
                continue
        
        if created_count > 0:
            transaction_type_name = "invoice" if transaction_type == 'Billing' else "payment"
            message = f'Successfully created {transaction_type_name} for {created_count} student(s) with transaction code: {transaction_code}'
            return jsonify({
                'success': True,
                'message': message,
                'transaction_code': transaction_code
            })
        else:
            return jsonify({'success': False, 'error': 'No transactions were created'})
    
    except Exception as e:
        print(f"Error in create_transaction: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@bp.route('/accounts/student_transactions/<student_id>')
def student_transactions(student_id):
    """View transactions for a specific student"""
    try:
        student = students_collection.find_one({'_id': ObjectId(student_id)})
        if not student:
            flash('Student not found!', 'error')
            return redirect(url_for('accounts.accounts_management'))
        
        # Get program and school info
        program = programs_collection.find_one({'_id': ObjectId(student['program_id'])}) if student.get('program_id') else None
        school = schools_collection.find_one({'_id': ObjectId(student['school_id'])}) if student.get('school_id') else None
        
        # Get all transactions for this student - SORTED BY DATE DESCENDING (newest first)
        transactions = list(accounts_collection.find({
            'student_id': ObjectId(student_id)
        }).sort('created_at', -1))
        
        # Calculate current balance
        current_balance = get_student_balance(student_id)
        
        return render_template('accounts/student_transactions.html',
                             student=student,
                             program=program,
                             school=school,
                             transactions=transactions,
                             current_balance=current_balance)
    
    except Exception as e:
        flash(f'Error loading student transactions: {str(e)}', 'error')
        return redirect(url_for('accounts.accounts_management'))

@bp.route('/accounts/transaction_history')
def transaction_history():
    """View all transactions history"""
    try:
        # Get all transactions with student information using aggregation - SORTED BY DATE DESCENDING
        pipeline = [
            {
                '$lookup': {
                    'from': 'students',
                    'localField': 'student_id',
                    'foreignField': '_id',
                    'as': 'student_info'
                }
            },
            {
                '$unwind': {
                    'path': '$student_info',
                    'preserveNullAndEmptyArrays': True
                }
            },
            {
                '$lookup': {
                    'from': 'programs',
                    'localField': 'student_info.program_id',
                    'foreignField': '_id',
                    'as': 'program_info'
                }
            },
            {
                '$unwind': {
                    'path': '$program_info',
                    'preserveNullAndEmptyArrays': True
                }
            },
            {
                '$sort': {'created_at': -1}  # Ensure newest transactions come first
            },
            {
                '$project': {
                    'transaction_code': 1,
                    'type': 1,
                    'description': 1,
                    'filter_reference': 1,
                    'batch_transaction': 1,
                    'debit': 1,
                    'credit': 1,
                    'balance_after': 1,
                    'created_at': 1,
                    'student_name': {
                        '$cond': {
                            'if': {'$ne': ['$student_info', None]},
                            'then': {'$concat': ['$student_info.f_name', ' ', '$student_info.l_name']},
                            'else': 'Unknown Student'
                        }
                    },
                    'student_number': {
                        '$cond': {
                            'if': {'$ne': ['$student_info', None]},
                            'then': '$student_info.student_number',
                            'else': 'N/A'
                        }
                    },
                    'program_name': {
                        '$cond': {
                            'if': {'$ne': ['$program_info', None]},
                            'then': '$program_info.name',
                            'else': 'N/A'
                        }
                    }
                }
            }
        ]
        
        transactions = list(accounts_collection.aggregate(pipeline))
        
        # Calculate summary statistics
        total_billing = sum(t.get('debit', 0) for t in transactions)
        total_clearing = sum(t.get('credit', 0) for t in transactions)
        outstanding_balance = total_billing - total_clearing
        
        return render_template('accounts/transaction_history.html',
                             transactions=transactions,
                             total_billing=total_billing,
                             total_clearing=total_clearing,
                             outstanding_balance=outstanding_balance)
    
    except Exception as e:
        print(f"Error in transaction_history: {str(e)}")
        flash(f'Error loading transaction history: {str(e)}', 'error')
        return redirect(url_for('accounts.accounts_management'))

@bp.route('/accounts/get_transaction/<transaction_id>')
def get_transaction(transaction_id):
    """Get transaction details for editing"""
    try:
        transaction = accounts_collection.find_one({'_id': ObjectId(transaction_id)})
        if not transaction:
            return jsonify({'success': False, 'error': 'Transaction not found'})
        
        # Convert ObjectId to string for JSON serialization
        transaction['_id'] = str(transaction['_id'])
        transaction['student_id'] = str(transaction['student_id'])
        
        return jsonify({'success': True, 'transaction': transaction})
    
    except Exception as e:
        print(f"Error getting transaction: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@bp.route('/accounts/update_transaction/<transaction_id>', methods=['POST'])
def update_transaction(transaction_id):
    """Update transaction details"""
    try:
        data = request.get_json()
        description = data.get('description', '')
        amount = float(data.get('amount', 0))
        
        if not description.strip():
            return jsonify({'success': False, 'error': 'Description is required'})
        
        if amount <= 0:
            return jsonify({'success': False, 'error': 'Amount must be greater than 0'})
        
        # Get the original transaction
        transaction = accounts_collection.find_one({'_id': ObjectId(transaction_id)})
        if not transaction:
            return jsonify({'success': False, 'error': 'Transaction not found'})
        
        # Update the transaction
        update_data = {
            'description': description,
        }
        
        # Update amount based on transaction type
        if transaction['type'] == 'Billing':
            update_data['debit'] = amount
            update_data['credit'] = 0
        else:  # Clearing
            update_data['credit'] = amount
            update_data['debit'] = 0
        
        accounts_collection.update_one(
            {'_id': ObjectId(transaction_id)},
            {'$set': update_data}
        )
        
        # Recalculate balances for the student
        student_id = transaction['student_id']
        recalculate_student_balance(student_id)
        
        return jsonify({'success': True, 'message': 'Transaction updated successfully'})
    
    except Exception as e:
        print(f"Error updating transaction: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@bp.route('/accounts/search_students_transactions', methods=['POST'])
def search_students_transactions():
    """Search students for transaction viewing"""
    try:
        data = request.get_json()
        search_term = data.get('search_term', '')
        school_id = data.get('school_id', '')
        program_id = data.get('program_id', '')
        
        query = {'status': 'active'}
        
        # Build search query
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
        
        # Sort students by name for consistent display
        students = list(students_collection.find(query).sort('f_name', 1).limit(50))
        
        students_data = []
        for student in students:
            # Get program and school info
            program = programs_collection.find_one({'_id': ObjectId(student['program_id'])}) if student.get('program_id') else None
            school = schools_collection.find_one({'_id': ObjectId(student['school_id'])}) if student.get('school_id') else None
            
            # Calculate financial statistics
            student_id = student['_id']
            current_balance = get_student_balance(student_id)
            
            # Get total billing and payments - sorted by date for accurate calculation
            billing_transactions = list(accounts_collection.find({
                'student_id': student_id,
                'type': 'Billing'
            }).sort('created_at', 1))
            payment_transactions = list(accounts_collection.find({
                'student_id': student_id,
                'type': 'Clearing'
            }).sort('created_at', 1))
            
            total_billing = sum(t.get('debit', 0) for t in billing_transactions)
            total_payments = sum(t.get('credit', 0) for t in payment_transactions)
            
            students_data.append({
                'id': str(student['_id']),
                'student_number': student.get('student_number', 'N/A'),
                'name': f"{student.get('f_name', '')} {student.get('l_name', '')}",
                'program': program['name'] if program else 'N/A',
                'school': school['name'] if school else 'N/A',
                'current_balance': current_balance,
                'total_billing': total_billing,
                'total_payments': total_payments
            })
        
        return jsonify({'success': True, 'students': students_data})
    
    except Exception as e:
        print(f"Error in search_students_transactions: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@bp.route('/accounts/get_student_balance/<student_id>')
def get_student_balance_api(student_id):
    """API to get student balance"""
    try:
        balance = get_student_balance(student_id)
        return jsonify({'success': True, 'balance': balance})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
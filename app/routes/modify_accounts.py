from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify, session
from app import accounts_collection, students_collection, programs_collection, schools_collection
from bson import ObjectId
from datetime import datetime
import random
import string

modify_bp = Blueprint('modify_accounts', __name__)

def generate_reversal_code():
    """Generate reversal transaction code: REV + 3 random letters + 4 numbers"""
    letters = ''.join(random.choices(string.ascii_uppercase, k=3))
    numbers = ''.join(random.choices(string.digits, k=4))
    return f"REV{letters}{numbers}"

@modify_bp.route('/accounts/modify_transactions')
def modify_transactions_page():
    """Main page for modifying transactions"""
    return render_template('accounts/modify_transactions.html')

@modify_bp.route('/accounts/search_transactions', methods=['POST'])
def search_transactions():
    """Search transactions for modification"""
    try:
        data = request.get_json()
        search_type = data.get('search_type', 'all')
        search_value = data.get('search_value', '')
        date_from = data.get('date_from', '')
        date_to = data.get('date_to', '')
        transaction_type = data.get('transaction_type', '')
        
        query = {}
        
        # Build search query based on search type
        if search_type == 'transaction_code' and search_value:
            query['transaction_code'] = {'$regex': search_value, '$options': 'i'}
        elif search_type == 'student' and search_value:
            # Find student first
            students = list(students_collection.find({
                '$or': [
                    {'student_number': {'$regex': search_value, '$options': 'i'}},
                    {'f_name': {'$regex': search_value, '$options': 'i'}},
                    {'l_name': {'$regex': search_value, '$options': 'i'}}
                ],
                'status': 'active'
            }))
            
            if students:
                student_ids = [student['_id'] for student in students]
                query['student_id'] = {'$in': student_ids}
            else:
                return jsonify({'success': True, 'transactions': []})
        elif search_type == 'description' and search_value:
            query['description'] = {'$regex': search_value, '$options': 'i'}
        
        # Filter by transaction type
        if transaction_type:
            query['type'] = transaction_type
        
        # Filter by date range
        if date_from and date_to:
            try:
                start_date = datetime.strptime(date_from, '%Y-%m-%d')
                end_date = datetime.strptime(date_to, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
                query['created_at'] = {'$gte': start_date, '$lte': end_date}
            except ValueError:
                pass
        
        # Get transactions with student information
        pipeline = [
            {'$match': query},
            {'$sort': {'created_at': -1}},  # Newest first
            {'$limit': 100},  # Limit results for performance
            {
                '$lookup': {
                    'from': 'students',
                    'localField': 'student_id',
                    'foreignField': '_id',
                    'as': 'student_info'
                }
            },
            {'$unwind': {'path': '$student_info', 'preserveNullAndEmptyArrays': True}},
            {
                '$lookup': {
                    'from': 'programs',
                    'localField': 'student_info.program_id',
                    'foreignField': '_id',
                    'as': 'program_info'
                }
            },
            {'$unwind': {'path': '$program_info', 'preserveNullAndEmptyArrays': True}},
            {
                '$project': {
                    '_id': {'$toString': '$_id'},
                    'transaction_code': 1,
                    'type': 1,
                    'description': 1,
                    'debit': 1,
                    'credit': 1,
                    'balance_after': 1,
                    'created_at': 1,
                    'batch_transaction': 1,
                    'filter_reference': 1,
                    'is_reversed': 1,
                    'reversal_code': 1,
                    'original_transaction_id': 1,
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
                    },
                    'can_modify': {
                        '$cond': {
                            'if': {'$or': [
                                {'$eq': ['$is_reversed', True]},
                                {'$ne': ['$original_transaction_id', None]}
                            ]},
                            'then': False,
                            'else': True
                        }
                    }
                }
            }
        ]
        
        transactions = list(accounts_collection.aggregate(pipeline))
        
        # Convert ObjectId and datetime to string for JSON serialization
        for transaction in transactions:
            # Convert ObjectId fields
            if 'original_transaction_id' in transaction and transaction['original_transaction_id']:
                if isinstance(transaction['original_transaction_id'], ObjectId):
                    transaction['original_transaction_id'] = str(transaction['original_transaction_id'])
            
            # Convert datetime fields
            if 'created_at' in transaction and isinstance(transaction['created_at'], datetime):
                transaction['created_at'] = transaction['created_at'].isoformat()
        
        return jsonify({'success': True, 'transactions': transactions})
    
    except Exception as e:
        print(f"Error searching transactions: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@modify_bp.route('/accounts/get_transaction_details/<transaction_id>')
def get_transaction_details(transaction_id):
    """Get detailed information about a transaction"""
    try:
        transaction = accounts_collection.find_one({'_id': ObjectId(transaction_id)})
        
        if not transaction:
            return jsonify({'success': False, 'error': 'Transaction not found'})
        
        # Get student information
        student = students_collection.find_one({'_id': ObjectId(transaction['student_id'])})
        
        # Get program information
        program = None
        if student and 'program_id' in student:
            program = programs_collection.find_one({'_id': ObjectId(student['program_id'])})
        
        # Get school information
        school = None
        if student and 'school_id' in student:
            school = schools_collection.find_one({'_id': ObjectId(student['school_id'])})
        
        # Check if transaction can be modified
        can_modify = not transaction.get('is_reversed', False) and not transaction.get('original_transaction_id')
        
        transaction_data = {
            '_id': str(transaction['_id']),
            'transaction_code': transaction.get('transaction_code', ''),
            'type': transaction.get('type', ''),
            'description': transaction.get('description', ''),
            'debit': transaction.get('debit', 0),
            'credit': transaction.get('credit', 0),
            'balance_after': transaction.get('balance_after', 0),
            'created_at': transaction.get('created_at', '').isoformat() if isinstance(transaction.get('created_at'), datetime) else '',
            'batch_transaction': transaction.get('batch_transaction', False),
            'filter_reference': transaction.get('filter_reference', ''),
            'is_reversed': transaction.get('is_reversed', False),
            'reversal_code': transaction.get('reversal_code', ''),
            'original_transaction_id': str(transaction.get('original_transaction_id', '')) if transaction.get('original_transaction_id') else '',
            'student_id': str(transaction['student_id']),
            'student_name': f"{student.get('f_name', '')} {student.get('l_name', '')}" if student else 'Unknown',
            'student_number': student.get('student_number', 'N/A') if student else 'N/A',
            'program_name': program.get('name', 'N/A') if program else 'N/A',
            'school_name': school.get('name', 'N/A') if school else 'N/A',
            'can_modify': can_modify
        }
        
        return jsonify({'success': True, 'transaction': transaction_data})
    
    except Exception as e:
        print(f"Error getting transaction details: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@modify_bp.route('/accounts/edit_transaction/<transaction_id>', methods=['POST'])
def edit_transaction(transaction_id):
    """Edit transaction details (description and amount only)"""
    try:
        data = request.get_json()
        description = data.get('description', '').strip()
        amount = float(data.get('amount', 0))
        
        # Validate input
        if not description:
            return jsonify({'success': False, 'error': 'Description is required'})
        
        if amount <= 0:
            return jsonify({'success': False, 'error': 'Amount must be greater than 0'})
        
        # Get the original transaction
        transaction = accounts_collection.find_one({'_id': ObjectId(transaction_id)})
        
        if not transaction:
            return jsonify({'success': False, 'error': 'Transaction not found'})
        
        # Check if transaction can be modified
        if transaction.get('is_reversed', False) or transaction.get('original_transaction_id'):
            return jsonify({'success': False, 'error': 'Cannot edit a reversed or adjusted transaction'})
        
        # Calculate the difference
        old_amount = transaction['debit'] if transaction['type'] == 'Billing' else transaction['credit']
        amount_difference = amount - old_amount
        
        # Update the transaction
        update_data = {
            'description': description,
            'updated_at': datetime.utcnow(),
            'updated_by': session.get('user_id', 'system'),
            'is_edited': True,
            'edit_history': {
                'old_description': transaction.get('description', ''),
                'old_amount': old_amount,
                'new_amount': amount,
                'edited_at': datetime.utcnow(),
                'edited_by': session.get('user_id', 'system')
            }
        }
        
        # Update amount based on transaction type
        if transaction['type'] == 'Billing':
            update_data['debit'] = amount
        else:  # Clearing
            update_data['credit'] = amount
        
        # Update the transaction
        accounts_collection.update_one(
            {'_id': ObjectId(transaction_id)},
            {'$set': update_data}
        )
        
        # Recalculate balances for the student
        student_id = transaction['student_id']
        recalculate_student_balance(student_id)
        
        return jsonify({
            'success': True,
            'message': 'Transaction updated successfully'
        })
    
    except Exception as e:
        print(f"Error editing transaction: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@modify_bp.route('/accounts/reverse_transaction/<transaction_id>', methods=['POST'])
def reverse_transaction(transaction_id):
    """Reverse a transaction by creating an opposite transaction"""
    try:
        data = request.get_json()
        reason = data.get('reason', '').strip()
        
        if not reason:
            return jsonify({'success': False, 'error': 'Reason for reversal is required'})
        
        # Get the original transaction
        transaction = accounts_collection.find_one({'_id': ObjectId(transaction_id)})
        
        if not transaction:
            return jsonify({'success': False, 'error': 'Transaction not found'})
        
        # Check if transaction can be reversed
        if transaction.get('is_reversed', False) or transaction.get('original_transaction_id'):
            return jsonify({'success': False, 'error': 'Transaction has already been reversed or adjusted'})
        
        # Determine reversal amount
        reversal_amount = transaction['debit'] if transaction['type'] == 'Billing' else transaction['credit']
        
        # Get current balance before reversal
        current_balance = get_student_balance(str(transaction['student_id']))
        
        # Generate reversal transaction code
        reversal_code = generate_reversal_code()
        
        # Create reversal transaction
        reversal_data = {
            'transaction_code': reversal_code,
            'student_id': transaction['student_id'],
            'type': 'Clearing' if transaction['type'] == 'Billing' else 'Billing',
            'description': f"REVERSAL: {transaction.get('description', '')} - {reason}",
            'debit': reversal_amount if transaction['type'] == 'Clearing' else 0,
            'credit': reversal_amount if transaction['type'] == 'Billing' else 0,
            'balance_after': current_balance + (-reversal_amount if transaction['type'] == 'Billing' else reversal_amount),
            'created_at': datetime.utcnow(),
            'created_by': session.get('user_id', 'system'),
            'is_reversal': True,
            'reversal_reason': reason,
            'original_transaction_id': ObjectId(transaction_id),
            'reversal_of': transaction.get('transaction_code', '')
        }
        
        # Insert reversal transaction
        result = accounts_collection.insert_one(reversal_data)
        
        # Mark original transaction as reversed
        accounts_collection.update_one(
            {'_id': ObjectId(transaction_id)},
            {'$set': {
                'is_reversed': True,
                'reversal_code': reversal_code,
                'reversal_reason': reason,
                'reversed_at': datetime.utcnow(),
                'reversed_by': session.get('user_id', 'system')
            }}
        )
        
        # Recalculate balances
        recalculate_student_balance(str(transaction['student_id']))
        
        return jsonify({
            'success': True,
            'message': f'Transaction reversed successfully with code: {reversal_code}',
            'reversal_code': reversal_code
        })
    
    except Exception as e:
        print(f"Error reversing transaction: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@modify_bp.route('/accounts/withdraw_transaction/<transaction_id>', methods=['POST'])
def withdraw_transaction(transaction_id):
    """Withdraw/delete a transaction (only for recently created transactions)"""
    try:
        data = request.get_json()
        reason = data.get('reason', '').strip()
        
        if not reason:
            return jsonify({'success': False, 'error': 'Reason for withdrawal is required'})
        
        # Get the transaction
        transaction = accounts_collection.find_one({'_id': ObjectId(transaction_id)})
        
        if not transaction:
            return jsonify({'success': False, 'error': 'Transaction not found'})
        
        # Check if transaction can be withdrawn (within 24 hours)
        transaction_time = transaction.get('created_at')
        if not transaction_time:
            return jsonify({'success': False, 'error': 'Invalid transaction timestamp'})
        
        time_diff = datetime.utcnow() - transaction_time
        if time_diff.total_seconds() > 24 * 60 * 60:  # 24 hours
            return jsonify({'success': False, 'error': 'Transaction is too old to withdraw. Use reversal instead.'})
        
        # Check if transaction has already been modified
        if transaction.get('is_reversed', False) or transaction.get('original_transaction_id'):
            return jsonify({'success': False, 'error': 'Cannot withdraw a modified transaction'})
        
        # Mark transaction as withdrawn
        accounts_collection.update_one(
            {'_id': ObjectId(transaction_id)},
            {'$set': {
                'is_withdrawn': True,
                'withdrawal_reason': reason,
                'withdrawn_at': datetime.utcnow(),
                'withdrawn_by': session.get('user_id', 'system'),
                'status': 'withdrawn'
            }}
        )
        
        # Recalculate balances
        recalculate_student_balance(str(transaction['student_id']))
        
        return jsonify({
            'success': True,
            'message': 'Transaction withdrawn successfully'
        })
    
    except Exception as e:
        print(f"Error withdrawing transaction: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@modify_bp.route('/accounts/create_adjustment', methods=['POST'])
def create_adjustment():
    """Create an adjustment transaction (credit or debit memo)"""
    try:
        data = request.get_json()
        student_id = data.get('student_id')
        adjustment_type = data.get('adjustment_type')  # 'credit_memo' or 'debit_memo'
        amount = float(data.get('amount', 0))
        description = data.get('description', '').strip()
        reason = data.get('reason', '').strip()
        
        # Validate input
        if not student_id:
            return jsonify({'success': False, 'error': 'Student ID is required'})
        
        if not adjustment_type or adjustment_type not in ['credit_memo', 'debit_memo']:
            return jsonify({'success': False, 'error': 'Invalid adjustment type'})
        
        if amount <= 0:
            return jsonify({'success': False, 'error': 'Amount must be greater than 0'})
        
        if not description:
            return jsonify({'success': False, 'error': 'Description is required'})
        
        if not reason:
            return jsonify({'success': False, 'error': 'Reason for adjustment is required'})
        
        # Check if student exists
        student = students_collection.find_one({'_id': ObjectId(student_id)})
        if not student:
            return jsonify({'success': False, 'error': 'Student not found'})
        
        # Get current balance
        current_balance = get_student_balance(student_id)
        
        # Generate adjustment code
        adjustment_code = f"ADJ{''.join(random.choices(string.ascii_uppercase + string.digits, k=7))}"
        
        # Determine transaction type based on adjustment type
        if adjustment_type == 'credit_memo':
            # Credit memo reduces balance (like a payment/refund)
            transaction_type = 'Clearing'
            debit = 0
            credit = amount
            new_balance = current_balance - amount
        else:  # debit_memo
            # Debit memo increases balance (like an additional charge)
            transaction_type = 'Billing'
            debit = amount
            credit = 0
            new_balance = current_balance + amount
        
        # Create adjustment transaction
        adjustment_data = {
            'transaction_code': adjustment_code,
            'student_id': ObjectId(student_id),
            'type': transaction_type,
            'description': f"ADJUSTMENT: {description}",
            'debit': debit,
            'credit': credit,
            'balance_after': new_balance,
            'created_at': datetime.utcnow(),
            'created_by': session.get('user_id', 'system'),
            'is_adjustment': True,
            'adjustment_type': adjustment_type,
            'adjustment_reason': reason,
            'original_description': description
        }
        
        # Insert adjustment transaction
        result = accounts_collection.insert_one(adjustment_data)
        
        return jsonify({
            'success': True,
            'message': f'Adjustment created successfully with code: {adjustment_code}',
            'adjustment_code': adjustment_code
        })
    
    except Exception as e:
        print(f"Error creating adjustment: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@modify_bp.route('/accounts/transaction_audit_log/<transaction_id>')
def transaction_audit_log(transaction_id):
    """Get audit log for a transaction"""
    try:
        # Get the transaction
        transaction = accounts_collection.find_one({'_id': ObjectId(transaction_id)})
        
        if not transaction:
            return jsonify({'success': False, 'error': 'Transaction not found'})
        
        # Get all related transactions (reversals, adjustments, etc.)
        related_transactions = list(accounts_collection.find({
            '$or': [
                {'original_transaction_id': ObjectId(transaction_id)},
                {'_id': transaction.get('original_transaction_id')} if transaction.get('original_transaction_id') else {}
            ]
        }).sort('created_at', 1))
        
        # Prepare audit log
        audit_log = []
        
        # Add original transaction
        audit_log.append({
            'timestamp': transaction.get('created_at').isoformat() if isinstance(transaction.get('created_at'), datetime) else str(transaction.get('created_at', '')),
            'action': 'CREATED',
            'transaction_code': transaction.get('transaction_code', ''),
            'type': transaction.get('type', ''),
            'description': transaction.get('description', ''),
            'amount': transaction.get('debit') or transaction.get('credit'),
            'user': transaction.get('created_by', 'system'),
            'notes': 'Original transaction'
        })
        
        # Add edit history if exists
        if transaction.get('is_edited') and transaction.get('edit_history'):
            edit_history = transaction['edit_history']
            audit_log.append({
                'timestamp': edit_history.get('edited_at').isoformat() if isinstance(edit_history.get('edited_at'), datetime) else str(edit_history.get('edited_at', '')),
                'action': 'EDITED',
                'transaction_code': transaction.get('transaction_code', ''),
                'type': 'EDIT',
                'description': f"Edited from '{edit_history.get('old_description', '')}' to '{transaction.get('description', '')}'",
                'amount': f"{edit_history.get('old_amount', 0)} → {edit_history.get('new_amount', 0)}",
                'user': edit_history.get('edited_by', 'system'),
                'notes': 'Transaction details updated'
            })
        
        # Add reversal if exists
        if transaction.get('is_reversed'):
            audit_log.append({
                'timestamp': transaction.get('reversed_at').isoformat() if isinstance(transaction.get('reversed_at'), datetime) else str(transaction.get('reversed_at', '')),
                'action': 'REVERSED',
                'transaction_code': transaction.get('reversal_code', ''),
                'type': 'REVERSAL',
                'description': f"Reversal: {transaction.get('reversal_reason', '')}",
                'amount': f"Reversed {transaction.get('debit') or transaction.get('credit')}",
                'user': transaction.get('reversed_by', 'system'),
                'notes': f"Original: {transaction.get('transaction_code', '')}"
            })
        
        # Add withdrawal if exists
        if transaction.get('is_withdrawn'):
            audit_log.append({
                'timestamp': transaction.get('withdrawn_at').isoformat() if isinstance(transaction.get('withdrawn_at'), datetime) else str(transaction.get('withdrawn_at', '')),
                'action': 'WITHDRAWN',
                'transaction_code': transaction.get('transaction_code', ''),
                'type': 'WITHDRAWAL',
                'description': f"Withdrawn: {transaction.get('withdrawal_reason', '')}",
                'amount': f"Withdrawn {transaction.get('debit') or transaction.get('credit')}",
                'user': transaction.get('withdrawn_by', 'system'),
                'notes': 'Transaction withdrawn'
            })
        
        # Add related transactions
        for related in related_transactions:
            if related.get('is_reversal'):
                action = 'REVERSAL_CREATED'
                notes = f"Reversal of {transaction.get('transaction_code', '')}"
            elif related.get('is_adjustment'):
                action = 'ADJUSTMENT_CREATED'
                notes = f"Adjustment: {related.get('adjustment_reason', '')}"
            else:
                action = 'RELATED_TRANSACTION'
                notes = 'Related transaction'
            
            audit_log.append({
                'timestamp': related.get('created_at').isoformat() if isinstance(related.get('created_at'), datetime) else str(related.get('created_at', '')),
                'action': action,
                'transaction_code': str(related.get('transaction_code', '')),
                'type': related.get('type', ''),
                'description': str(related.get('description', '')),
                'amount': related.get('debit') or related.get('credit'),
                'user': related.get('created_by', 'system'),
                'notes': notes
            })
        
        # Sort by timestamp
        audit_log.sort(key=lambda x: x['timestamp'], reverse=True)
        
        return jsonify({'success': True, 'audit_log': audit_log})
    
    except Exception as e:
        print(f"Error getting audit log: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

# Helper functions (you'll need to import these or define them)
def get_student_balance(student_id):
    """Calculate current balance for a student"""
    try:
        transactions = list(accounts_collection.find({
            'student_id': ObjectId(student_id),
            'status': {'$ne': 'withdrawn'}
        }).sort('created_at', 1))
        
        balance = 0
        for transaction in transactions:
            if transaction['type'] == 'Billing':
                balance += transaction.get('debit', 0)
            else:  # Clearing
                balance -= transaction.get('credit', 0)
        
        return balance
    except Exception as e:
        print(f"Error calculating balance: {str(e)}")
        return 0

def recalculate_student_balance(student_id):
    """Recalculate and update all balances for a student"""
    try:
        transactions = list(accounts_collection.find({
            'student_id': ObjectId(student_id),
            'status': {'$ne': 'withdrawn'}
        }).sort('created_at', 1))
        
        balance = 0
        for transaction in transactions:
            if transaction['type'] == 'Billing':
                balance += transaction.get('debit', 0)
            else:  # Clearing
                balance -= transaction.get('credit', 0)
            
            # Update the balance_after field
            accounts_collection.update_one(
                {'_id': transaction['_id']},
                {'$set': {'balance_after': balance}}
            )
        
        return balance
    except Exception as e:
        print(f"Error recalculating balance: {str(e)}")
        return 0
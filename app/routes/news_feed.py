from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, session
from app import news_collection, users_collection
from bson import ObjectId
from datetime import datetime
import os
from werkzeug.utils import secure_filename
import uuid

bp = Blueprint('news_feed', __name__)

# Allowed extensions for file uploads
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'doc', 'docx', 'txt'}
UPLOAD_FOLDER = 'app/static/uploads/news'

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_user_identifier():
    """Get a unique identifier for the current user (session-based)"""
    # Initialize session if not exists
    if 'user_identifier' not in session:
        session['user_identifier'] = str(uuid.uuid4())
    return session['user_identifier']

@bp.route('/Updates')
@bp.route('/')
def news_dashboard():
    """News dashboard showing all updates"""
    news_updates = list(news_collection.find({'status': 'published'}).sort('created_at', -1))
    user_identifier = get_user_identifier()
    
    # Enhance news with like counts and user info
    for news in news_updates:
        news['id'] = str(news['_id'])
        news['like_count'] = len(news.get('likes', []))
        news['user_has_liked'] = user_identifier in news.get('likes', [])
        
        # Get author info if available
        if news.get('author_id'):
            author = users_collection.find_one({'_id': ObjectId(news['author_id'])})
            if author:
                news['author_name'] = f"{author.get('f_name', '')} {author.get('l_name', '')}".strip()
            else:
                news['author_name'] = 'Administrator'
        else:
            news['author_name'] = 'Administrator'
    
    return render_template('news/news_dashboard.html', news_updates=news_updates)

@bp.route('/news/create', methods=['GET', 'POST'])
def create_news():
    """Create new news update"""
    if request.method == 'POST':
        try:
            title = request.form['title']
            content = request.form['content']
            summary = request.form.get('summary', '')
            category = request.form.get('category', 'general')
            is_featured = request.form.get('is_featured') == 'on'
            status = request.form.get('status', 'published')
            
            # Handle file uploads
            background_image = None
            document_file = None
            
            if 'background_image' in request.files:
                file = request.files['background_image']
                if file and file.filename != '' and allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    unique_filename = f"{uuid.uuid4()}_{filename}"
                    file_path = os.path.join(UPLOAD_FOLDER, 'images', unique_filename)
                    os.makedirs(os.path.dirname(file_path), exist_ok=True)
                    file.save(file_path)
                    background_image = unique_filename
            
            if 'document_file' in request.files:
                file = request.files['document_file']
                if file and file.filename != '' and allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    unique_filename = f"{uuid.uuid4()}_{filename}"
                    file_path = os.path.join(UPLOAD_FOLDER, 'documents', unique_filename)
                    os.makedirs(os.path.dirname(file_path), exist_ok=True)
                    file.save(file_path)
                    document_file = {
                        'filename': filename,
                        'unique_filename': unique_filename,
                        'original_name': filename
                    }
            
            news_data = {
                'title': title,
                'content': content,
                'summary': summary,
                'category': category,
                'background_image': background_image,
                'document_file': document_file,
                'is_featured': is_featured,
                'status': status,
                'likes': [],
                'views': 0,
                'created_at': datetime.utcnow(),
                'updated_at': datetime.utcnow(),
                'author_id': None
            }
            
            result = news_collection.insert_one(news_data)
            
            if status == 'published':
                flash('News published successfully!', 'success')
            else:
                flash('News saved as draft successfully!', 'success')
                
            return redirect(url_for('news_feed.news_dashboard'))
            
        except Exception as e:
            flash(f'Error creating news: {str(e)}', 'error')
    
    return render_template('news/create_news.html')

@bp.route('/news/drafts')
def news_drafts():
    """View all drafted news"""
    drafts = list(news_collection.find({'status': 'draft'}).sort('created_at', -1))
    
    for draft in drafts:
        draft['id'] = str(draft['_id'])
        # Get author info if available
        if draft.get('author_id'):
            author = users_collection.find_one({'_id': ObjectId(draft['author_id'])})
            if author:
                draft['author_name'] = f"{author.get('f_name', '')} {author.get('l_name', '')}".strip()
            else:
                draft['author_name'] = 'Administrator'
        else:
            draft['author_name'] = 'Administrator'
    
    return render_template('news/news_drafts.html', drafts=drafts)

@bp.route('/news/publish/<news_id>')
def publish_news(news_id):
    """Publish a drafted news article"""
    try:
        result = news_collection.update_one(
            {'_id': ObjectId(news_id), 'status': 'draft'},
            {'$set': {
                'status': 'published',
                'published_at': datetime.utcnow(),
                'updated_at': datetime.utcnow()
            }}
        )
        
        if result.modified_count:
            flash('News published successfully!', 'success')
        else:
            flash('News not found or already published!', 'error')
            
    except Exception as e:
        flash(f'Error publishing news: {str(e)}', 'error')
    
    return redirect(url_for('news_feed.news_drafts'))

@bp.route('/news/edit/<news_id>', methods=['GET', 'POST'])
def edit_news(news_id):
    """Edit news article"""
    try:
        news = news_collection.find_one({'_id': ObjectId(news_id)})
        if not news:
            flash('News article not found!', 'error')
            return redirect(url_for('news_feed.news_dashboard'))
        
        if request.method == 'POST':
            try:
                title = request.form['title']
                content = request.form['content']
                summary = request.form.get('summary', '')
                category = request.form.get('category', 'general')
                is_featured = request.form.get('is_featured') == 'on'
                status = request.form.get('status', 'published')
                
                # Handle file uploads
                background_image = news.get('background_image')
                document_file = news.get('document_file')
                
                if 'background_image' in request.files:
                    file = request.files['background_image']
                    if file and file.filename != '' and allowed_file(file.filename):
                        filename = secure_filename(file.filename)
                        unique_filename = f"{uuid.uuid4()}_{filename}"
                        file_path = os.path.join(UPLOAD_FOLDER, 'images', unique_filename)
                        os.makedirs(os.path.dirname(file_path), exist_ok=True)
                        file.save(file_path)
                        background_image = unique_filename
                
                if 'document_file' in request.files:
                    file = request.files['document_file']
                    if file and file.filename != '' and allowed_file(file.filename):
                        filename = secure_filename(file.filename)
                        unique_filename = f"{uuid.uuid4()}_{filename}"
                        file_path = os.path.join(UPLOAD_FOLDER, 'documents', unique_filename)
                        os.makedirs(os.path.dirname(file_path), exist_ok=True)
                        file.save(file_path)
                        document_file = {
                            'filename': filename,
                            'unique_filename': unique_filename,
                            'original_name': filename
                        }
                
                update_data = {
                    'title': title,
                    'content': content,
                    'summary': summary,
                    'category': category,
                    'background_image': background_image,
                    'document_file': document_file,
                    'is_featured': is_featured,
                    'status': status,
                    'updated_at': datetime.utcnow()
                }
                
                # If publishing for the first time, set published_at
                if news['status'] == 'draft' and status == 'published':
                    update_data['published_at'] = datetime.utcnow()
                
                news_collection.update_one(
                    {'_id': ObjectId(news_id)},
                    {'$set': update_data}
                )
                
                if status == 'published':
                    flash('News updated and published successfully!', 'success')
                    return redirect(url_for('news_feed.news_dashboard'))
                else:
                    flash('News updated and saved as draft!', 'success')
                    return redirect(url_for('news_feed.news_drafts'))
                    
            except Exception as e:
                flash(f'Error updating news: {str(e)}', 'error')
        
        return render_template('news/edit_news.html', news=news)
        
    except Exception as e:
        flash('Invalid news ID!', 'error')
        return redirect(url_for('news_feed.news_dashboard'))

@bp.route('/news/delete/<news_id>')
def delete_news(news_id):
    """Delete news article"""
    try:
        result = news_collection.delete_one({'_id': ObjectId(news_id)})
        if result.deleted_count:
            flash('News deleted successfully!', 'success')
        else:
            flash('News not found!', 'error')
            
    except Exception as e:
        flash(f'Error deleting news: {str(e)}', 'error')
    
    return redirect(url_for('news_feed.news_drafts'))

@bp.route('/news/<news_id>')
def news_detail(news_id):
    """View full news article - only for published news"""
    try:
        news = news_collection.find_one({'_id': ObjectId(news_id), 'status': 'published'})
        if not news:
            flash('News article not found or not published!', 'error')
            return redirect(url_for('news_feed.news_dashboard'))
        
        # Increment view count
        news_collection.update_one(
            {'_id': ObjectId(news_id)},
            {'$inc': {'views': 1}}
        )
        
        user_identifier = get_user_identifier()
        news['id'] = str(news['_id'])
        news['like_count'] = len(news.get('likes', []))
        news['user_has_liked'] = user_identifier in news.get('likes', [])
        
        # Get author info
        if news.get('author_id'):
            author = users_collection.find_one({'_id': ObjectId(news['author_id'])})
            if author:
                news['author_name'] = f"{author.get('f_name', '')} {author.get('l_name', '')}".strip()
                news['author_role'] = author.get('role', 'Staff')
            else:
                news['author_name'] = 'Administrator'
                news['author_role'] = 'Staff'
        else:
            news['author_name'] = 'Administrator'
            news['author_role'] = 'Staff'
        
        # Get related news (same category)
        related_news = list(news_collection.find({
            '_id': {'$ne': ObjectId(news_id)},
            'category': news.get('category', 'general'),
            'status': 'published'
        }).limit(3))
        
        for related in related_news:
            related['id'] = str(related['_id'])
            related['like_count'] = len(related.get('likes', []))
            related['user_has_liked'] = user_identifier in related.get('likes', [])
        
        return render_template('news/news_detail.html', 
                             news=news, 
                             related_news=related_news)
        
    except Exception as e:
        flash('Invalid news ID!', 'error')
        return redirect(url_for('news_feed.news_dashboard'))

@bp.route('/news/like/<news_id>', methods=['POST'])
def like_news(news_id):
    """Like/unlike a news article"""
    try:
        user_identifier = get_user_identifier()
        print(f"User identifier: {user_identifier}")  # Debug print
        
        # Validate news_id
        if not ObjectId.is_valid(news_id):
            return jsonify({'success': False, 'error': 'Invalid news ID'})
        
        news = news_collection.find_one({'_id': ObjectId(news_id)})
        
        if not news:
            return jsonify({'success': False, 'error': 'News not found'})
        
        likes = news.get('likes', [])
        
        if user_identifier in likes:
            # Unlike
            likes.remove(user_identifier)
            action = 'unliked'
        else:
            # Like
            likes.append(user_identifier)
            action = 'liked'
        
        # Update the news article with new likes
        result = news_collection.update_one(
            {'_id': ObjectId(news_id)},
            {'$set': {'likes': likes}}
        )
        
        print(f"Update result: {result.modified_count} documents modified")  # Debug print
        
        return jsonify({
            'success': True,
            'action': action,
            'like_count': len(likes),
            'user_has_liked': action == 'liked'
        })
        
    except Exception as e:
        print(f"Error in like_news: {str(e)}")  # Debug print
        return jsonify({'success': False, 'error': str(e)})

@bp.route('/news/category/<category>')
def news_by_category(category):
    """Get news by category"""
    news_updates = list(news_collection.find({
        'category': category,
        'status': 'published'
    }).sort('created_at', -1))
    
    user_identifier = get_user_identifier()
    
    for news in news_updates:
        news['id'] = str(news['_id'])
        news['like_count'] = len(news.get('likes', []))
        news['user_has_liked'] = user_identifier in news.get('likes', [])
    
    return render_template('news/news_dashboard.html', 
                         news_updates=news_updates,
                         selected_category=category)

@bp.route('/news/featured')
def featured_news():
    """Get featured news"""
    news_updates = list(news_collection.find({
        'is_featured': True,
        'status': 'published'
    }).sort('created_at', -1))
    
    user_identifier = get_user_identifier()
    
    for news in news_updates:
        news['id'] = str(news['_id'])
        news['like_count'] = len(news.get('likes', []))
        news['user_has_liked'] = user_identifier in news.get('likes', [])
    
    return render_template('news/news_dashboard.html', 
                         news_updates=news_updates,
                         featured=True)
from flask import Blueprint, render_template

bp = Blueprint('contact', __name__)
@bp.route('/Contact-us')
def contact():
	return render_template ('contact_us.html')
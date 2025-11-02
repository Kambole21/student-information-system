from flask import Blueprint, url_for, redirect, session, render_template
bp = Blueprint('home', __name__)

@bp.route('/Home Page')
@bp.route('/')
def home():
	return render_template('home.html')
from flask import Blueprint, url_for, redirect, session, render_template
bp = Blueprint('home', __name__)

@bp.route('/Home Page')
def home():
	return render_template('home.html')
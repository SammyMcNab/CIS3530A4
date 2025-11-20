from flask import Blueprint, render_template

main = Blueprint('main', __name__)

@main.route('/')
def home():
    return render_template('home.html')

@main.route('/login')
def login():
    return render_template('login.html')

@main.route('/create_account')
def create_account():
    return render_template('create_account.html')
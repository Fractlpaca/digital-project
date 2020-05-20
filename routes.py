"""
This python file contains all the app routes for the web app.
Author: Joseph Grace
Created 20/05/2020
"""
from flask import Flask, request, url_for, redirect, render_template, flash, session

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/dashboard")
@login_required
def dashboard():
    return "Current user: {}".format(current_user.username)

@app.route("/register", methods=["GET", "POST"])
def register():
    print("Register", request.form, flush=True)
    if request.form:
        print("Form recieved", flush=True)
        username = request.form.get("username")
        if not Users.query.filter_by(username=username).first() is None:
            print("Error 1", flush=True)
        else:
            password_plaintext = request.form.get("password")
            password_hash = bcrypt.hash(password_plaintext, rounds=BCRYPT_ROUNDS)
            new_user = Users(username=request.form.get("username"),
                             password_hash=password_hash)
            db.session.add(new_user)
            db.session.commit()
            print("Added new user:",new_user, flush=True)
            login_user(new_user)
            return redirect(url_for("dashboard"))
    return render_template("register.html")

@app.route("/login", methods = ["GET", "POST"])
def login():
    logout_user()
    if request.form:
        username = request.form.get("username")
        user = Users.query.filter_by(username=username).first()
        password_plaintext = request.form.get("password")
        if Users.query.filter_by(username=username).first() is None:
            print("Error 2", flush=True)
        else:
            if bcrypt.verify(password_plaintext,user.password_hash):
                login_user(user)
                return redirect(url_for("dashboard"))
            else:
                print("Error 3", flush=True)
                #Error 2 and 3 must be presented as the same error for security reasons.
    return render_template("login.html")    

@app.route("/logout")
def logout():
    print("Logged out user", current_user, flush=True)
    logout_user()
    return redirect("/")
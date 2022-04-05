from ast import arg
import datetime
from datetime import datetime, date, timedelta, time
# import imp
from random import randint
import os
from re import S
from xmlrpc.client import NOT_WELLFORMED_ERROR
from flask  import Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_file
import pyrebase
import secrets
from functools import wraps
from flask_cors import CORS
import pandas as pd
from collections import OrderedDict
import pytz
from typing import List
# from pyngrok import ngrok

# Open a HTTP tunnel on the default port 80
# <NgrokTunnel: "http://<public_sub>.ngrok.io" -> "http://localhost:80">
# http_tunnel = ngrok.connect()
# Open a SSH tunnel
# <NgrokTunnel: "tcp://0.tcp.ngrok.io:12345" -> "localhost:22">
# ssh_tunnel = ngrok.connect(22, "tcp")

app = Flask(__name__)
app.secret_key = "sgdfsgfsgfdgfgdgfgfdgsdf"
app.permanent_session_lifetime = timedelta(minutes=120)

CORS(app)

IST = pytz.timezone('Asia/Kolkata')

#Connecting Database to app 
firebaseConfig = {
  "apiKey": "AIzaSyCGuEitG3Xd0czAG2wzVXONANGrocCfMws",
  "authDomain": "words-and-sips.firebaseapp.com",
  "databaseURL": "https://words-and-sips-default-rtdb.asia-southeast1.firebasedatabase.app",
  "projectId": "words-and-sips",
  "storageBucket": "words-and-sips.appspot.com",
  "messagingSenderId": "636972441572",
  "appId": "1:636972441572:web:8a62641e6b9664c3d071f1",
  "measurementId": "G-64L58BNDME",
}

firebase = pyrebase.initialize_app(firebaseConfig)
db = firebase.database()


# Check if user logged in
def is_admin(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if 'logged_in' in session:
            if session['type'] == 'admin':
                return f(*args, **kwargs)
        else:
            flash('Please Login First', 'secondary')
            return redirect(url_for('login'))
    return wrap


# Check if user logged in
def is_logged_in(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if 'logged_in' in session:
            return f(*args, **kwargs)
        else:
            flash('Please Login First', 'secondary')
            return redirect(url_for('login'))
    return wrap


@app.route('/') 
def index():
    if "flag" in session:
        if session["flag"] == 1:
            session["order_id"] = 0
            return render_template("index.html")
        else:
            message = "Can't log out"
            # # print(message)
            return redirect(url_for("menu"))
    else:
        return render_template("index.html")

@app.route('/checkout') 
def checkout():
    cart = []
    total = 0
    if session['phone'] != 0:
        cart_dict = session["cart"]["products"]
        
        # # # print(session["order_id"])
        for product_id in list(cart_dict.keys()):
            pro = db.child("menu").child(product_id).get().val()
            cart.append({
                "product_id": product_id,
                "name": pro.get("name"),
                "quantity": int(cart_dict[product_id]),
                "amount": int(pro.get("price")) * int(cart_dict[product_id]),
                "category": pro.get("category")
            })
            total += int(pro.get("price")) * int(cart_dict[product_id])
        return render_template("checkout.html", cart=cart, total=total)
    else:
        flash("Your session has expired", "danger")
        return render_template("checkout.html", cart=cart, total=total)
    



@app.route('/remove_from_cart/<string:product_id>')
def remove_from_cart(product_id):
    product = db.child("menu").child(product_id).get().val()
    price = product["price"]
    session["cart"]["cart_total"] -= int(price) * int(session["cart"]["products"][product_id])
    del session["cart"]["products"][product_id]
    flash("Item deleted from cart!", "info")
    return redirect(url_for("checkout"))


@app.route('/confirm_order', methods=["POST", "GET"])
def confirm_order():
    if session["type"] == "admin":
        return render_template("admin_order.html")

    else:
        cart_dict = session["cart"]["products"]
        cart = []
        users = db.child("users").order_by_child("type").equal_to("tab").get().val()
        orders = db.child("orders").order_by_child("start_time").get().val()

        order_date = datetime.now(IST)
        order_date = order_date.strftime("%d/%m/%Y %I:%M %p")

        for product_id in list(cart_dict.keys()):        
            order_id_min = randint(1, 99999)
            pro = db.child("menu").child(product_id).get().val()
            amount = int(pro.get("price")) * int(cart_dict[product_id])
            cart.append({
                "order_id": order_id_min,
                "order_time": order_date,
                "product_id": product_id,
                "print": 0,
                "name": pro.get("name"),
                "quantity": int(cart_dict[product_id]),
                "amount": amount,
                "category": pro.get("category"),
            })

        if session["order_id"] != 0:
            order_id = session["order_id"]  
            orders = db.child("orders").order_by_child("start_time").get().val()
            for i in orders.keys():
                if orders[i]["order_no"] == session["order_id"] and orders[i]["name"] == session["name"]:
                    curr = i

            curr_order = db.child("orders").child(curr).get().val()
            for item in cart:
                curr_order["order"].append(item)
            db.child("orders").child(curr).child("order").set(curr_order["order"])
            total = 0
            ci_flag = 0
            ci_total = 0
            for item in curr_order["order"]:
                if "amount" in item:
                    if "Cigarette" in item["category"]:
                        ci_flag = 1
                        ci_total = item["amount"]
                    total += item["amount"]
            total = total - ci_total
            session_charge = session["quantity"] * 100
            if total < session_charge:
                total = session_charge
            total += ci_total
            db.child("orders").child(curr).child("total").set(total)

        else:     
            total = session["service_charge"]
            if session["cart"]["cart_total"] > session["service_charge"]:
                total += session["cart"]["cart_total"] - session["service_charge"]

            for u in users.keys():
                for i in orders.keys():
                    if users[u]["phone"] == orders[i]["phone"]:
                        order = db.child("orders").child(i).child("order").get().val()
                        order.append(cart)
                        db.child("orders").child(i).child("order").set(order)
                        db.child("orders").child(i).child("total").set(total)

            if session["type"] == "tab":
                if users[u]["type"] == "tab" and users[u]["phone"] == session["phone"]:
                    total_total1 = db.child("users").child(u).child("total_total").get().val()
                    total_total = total_total1 + total
                    userdata = db.child("users").child(u).get().val()
                    userdata.update({"total_total": total_total})
                    try:
                        db.child("users").child(u).set(userdata)
                    except Exception as e:
                        print(e)

            # else:
                # data = {
                #     "name": session["name"],
                #     "order_no": session["order_id"],
                #     "order": cart,
                #     "total": total,
                #     'location': session["location"],
                #     "start_time": session["start_time"],
                #     "status": "OPEN",
                #     "table": session["table"],
                #     "type": session["type"]
                # }
                # data.update({"quantity": session["quantity"]})
        
            # res = db.child("orders").push(data)
            # print(res)

        flash("Order placed", "success")
        # session["order_id"] = order_id
        session["flag"] = 1
            
        return redirect(url_for("total_total"))

@app.route('/total_total')
def total_total():
    # # print("HI_TOTAL TOTAL")
    cart_dict = session["cart"]["products"]
    date = session["start_time"].split(" ")[0]
    # print(date)
    # print(type(session["start_time"]))
    date = datetime.strptime(date, "%d/%m/%Y")
    orders = db.child("orders").order_by_child("type").equal_to("tab").get().val()
    users = db.child("users").order_by_child("type").equal_to("tab").get().val()

    # print("CART_DICT: ", cart_dict)

    for product_id in list(cart_dict.keys()):
        pro = db.child("menu").child(product_id).get().val() 
        kflag, cflag, pflag = 0, 0, 0
        if db.child("sales").child(date).shallow().get().val():
            result = db.child("sales").child(date).get().val()
            if pro.get("category") in result.keys():
                result1 = db.child("sales").child(date).child(pro.get("category")).get().val()
                if pro.get("name") in result1.keys():
                    prod = db.child("sales").child(date).child(pro.get("category")).child(pro.get("name")).get().val()
                    prod = prod + int(cart_dict[product_id])
                    db.child("sales").child(date).child(pro.get("category")).child(pro.get("name")).set(prod)
                else:
                    pflag = 1
            else:
                cflag = 1
        else:
            kflag = 1

        if kflag == 1 or cflag==1 or pflag ==1:
            db.child("sales").child(date).child(pro.get("category")).child(pro.get("name")).set(int(cart_dict[product_id]))


    session["cart"] = {"products": {}, "cart_total": 0}
    session["service_charge"] = 0
    if session["type"] == "admin":
        session["phone"] = 11111111
        session["name"] = 'admin'
        return redirect(url_for('dashboard'))
    else:
        return redirect(url_for("menu"))

@app.route('/add_product/<string:order_id>', methods=["POST"])
def add_product(order_id):
    if request.method == 'POST':
        amt = request.form['cigsamt']
        # # print(amt)
        if not amt:
            amt = int(1)
        amt = int(amt)
    all_order = dict(db.child("orders").child(order_id).get().val())
    orders = all_order["order"] 
    now = datetime.now(IST)
    now = now.strftime("%d/%m/%Y %I:%M %p")
    order_id_min = randint(1, 99999)
    menu = db.child('menu').order_by_child('name').equal_to('Cigarette').get().key()

    pro = {
        "name": "Cigarettes",
        "amount": amt * 20,
        "quantity": amt,
        "order_time": now,
        "order_id": order_id_min,
        "print": 1
    }
    for order in orders:
        if order.get("name") == "Cigarettes":
            order["quantity"] += amt
            order["amount"] += amt*20
            all_order["total"] += amt*20

            break
    else:
        orders.append(pro)
        all_order["total"] += amt*20
    # # print(orders)
    res = db.child("orders").child(order_id).set(all_order)

    flash("Product addedd successfully", "success")
    return redirect(url_for("dashboard"))

@app.route("/update_quantity/<product_id>/<quantity>")
def update_product_quantity(product_id, quantity):
    if "cart" in session:
        # # print("OLD CART:", session["cart"])
        product_dict = session["cart"]["products"]
        product_dict[product_id] = quantity
        cart_total = 0
        for product_id, quantity in product_dict.items():
            product = db.child("menu").child(product_id).get().val()
            price = product["price"]
            cart_total += int(price) * int(quantity)
        session["cart"]["cart_total"] = cart_total
        # # print("NEW CART:", session["cart"])
        session["cart"] = {"products": product_dict, "cart_total": cart_total}
        flash("Quantity updated!", "info")
    return redirect(url_for("checkout"))


@app.route('/checkin', methods = ['GET','POST'])
def checkin():
    if request.method == 'POST':
        name = request.form['name']
        phone = request.form['phone']
        location = request.form['location']
        table = request.form['table']
        quantity = int(request.form['quantity'])
        start_time = request.form['start_time']
        session.permanent = True
        # # print(start_time)
        now = datetime.now(IST)
        now = now.strftime("%d/%m/%Y %I:%M %p")
        data = {
            "name": name,
            "phone": phone,
            "type":'customer',
            "location": location,
            "table": table,
            "quantity": quantity,
            "start_time": now
        }
        results = db.child("users").push(data)
        order_id = randint(1, 99999)  
        session["order_id"] = order_id
        session["flag"] = 0
        session["name"] = name
        session["phone"] = phone
        session['location'] = location
        session['table'] = table
        session["cart"] = {"products": {}, "cart_total":0}
        session["quantity"] = quantity
        session["start_time"] = now
        session["type"] = "customer"
        session["service_charge"] = 100 * quantity

        now = datetime.now(IST)
        now = now.strftime("%d/%m/%Y %I:%M %p")
        cart = []
        cart.append({
            "entry_fee": session["service_charge"],
            "order_time": now
        })  

        data = {
            "name": session["name"],
            "phone": session["phone"],
            "order_no": session["order_id"],
            "order": cart,
            "total": session["service_charge"],
            'location': session["location"],
            "start_time": now,
            "status": "OPEN",
            "table": session["table"],
            "type": session["type"]
        }
        data.update({"quantity": session["quantity"]})

        db.child("orders").push(data)
        
        return redirect(url_for('menu'))


@app.route('/manage_tabs', methods=["GET", "POST"])
@is_logged_in
def manage_tabs():
    orders = db.child("orders").order_by_child("type").equal_to("tab").get().val()

    users = db.child("users").order_by_child("type").equal_to("tab").get().val()

    if users:
        all_users = set()
        for order in orders:
            all_users.add(orders[order]["phone"])

        customers = {}
        for phone in all_users:
            for order in orders:
                if orders[order]["phone"] == phone:
                    customers[phone] = orders[order]["name"]

        totals = {}
        for phone in all_users:
            for user in users.keys():
                # # # print(user)
                if users[user]["phone"] == phone:
                    totals[phone] = users[user]["total_total"]

        # # # print(totals)
        # for phone in all_users:
        #     userdata = db.child("users").child(u).get().val()

    
        return render_template("managetabs.html",users=users, orders=orders, customers=customers, totals=totals)

    else:
        return render_template("managetabs.html")


@app.route('/change_total/<customer>', methods=["POST"])
def change_total(customer):
    orders = db.child("orders").order_by_child("type").equal_to("tab").get().val()

    phones = set()
    for order in orders:
        phones.add(orders[order]["phone"])
    
    customers = {}
    for phone in phones:
        for order in orders:
            if orders[order]["phone"] == phone:
                customers[phone] = orders[order]["name"]

    # # # print(customer)
    data = request.form.get("dep")
    # # # print(data)
    users = db.child("users").order_by_child("type").equal_to("tab").get().val()

    for u in users.keys():
        if users[u]["phone"] == customer:
            customer_id = u
    
    # # # print(customer_id)
    
    tot = db.child("users").child(customer_id).child("total_total").get().val()
    # # # print(tot)
    total_total = tot-data

    db.child("users").child(customer_id).update({"total_total": total_total})
    # userdata.update({"total_total": total_total})
    # db.child("users").child(customer_id).set(userdata)


    return render_template("managetabs.html", users=users, orders=orders, customers=customers)


@app.route('/menu')
def menu():
    menu  = db.child("menu").get().val()
    categories = set([menu[item]["category"] for item in menu])
    return render_template("menu.html", menu=menu, categories=categories)


@app.route('/manage_menu', methods=['GET', 'POST'])
def manage_menu():
    if request.method == "POST":
        category = request.form.get("category")
        item_name = request.form.get("item_name")
        active_status = bool(request.form.get("active_status"))
        price = int(request.form.get("price"))
        data = {"active": active_status,
        "name": item_name,
        "category": category,
        "price": price}
        res = db.child("menu").push(data)
        flash("Product successfully added!", "success")
   

    menu  = db.child("menu").get().val()
    return render_template("manage_menu.html", menu = menu)

@app.route("/delete_menu/<id>")
def delete_menu(id):
    # # # print(id)
    res = db.child("menu").child(id).remove()
    flash("Deleted successfully", "success")
    return jsonify({
        "success": True
    })


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == "POST":
        name = request.form.get("name")
        phone = request.form.get("phone")
        password = request.form.get("password")
        location = request.form['location']
        table = request.form['table']
        quantity = int(request.form['quantity'])
        start_time = request.form['start_time']
        try:
            user = db.child("users").order_by_child("phone").equal_to(phone).get().val()
        except:
            flash("User not found :(", "danger") 

        if user:
            session.permanent = True
            u = list(dict(user).values())[0]
        # # # print(u["phone"])
        # # # print(u["password"])
            if phone == u["phone"] and password == u["password"]:
                order_id = randint(1, 99999)  
                session["order_id"] = order_id
                session["flag"] = 0
                session["logged_in"] = True
                session["phone"] = phone
                session['type'] = 'tab'
                session["name"] = u["name"]
                # # print(u)
                # # print('password matched')
                # data = {
                #     "type":'customer',
                #     "location": location,
                #     "table": table,
                #     "quantity": quantity,
                #     "start_time": start_time
                # }
                results = db.child("users").order_by_child("phone").equal_to(session["phone"]).get().val()
                # session["id"] = results[0]["name"]
                session['location'] = location
                session['table'] = table
                session["cart"] = {"products": {}, "cart_total":0}
                session["quantity"] = quantity
                session["start_time"] = start_time
                session["service_charge"] = 100 * quantity

                string = session['start_time']
                if '-' in string:
                    # # # print(string)
                    str = string.replace('-', '/')
                session["start_time"] = string
                now = datetime.now(IST)
                now = now.strftime("%d/%m/%Y %I:%M %p")
                cart = []
                cart.append({
                    "entry_fee": session["service_charge"],
                    "order_time": now
                })  

                data = {
                    "name": session["name"],
                    "phone": session["phone"],
                    "order_no": session["order_id"],
                    "order": cart,
                    "total": session["service_charge"],
                    'location': session["location"],
                    "start_time": now,
                    "status": "OPEN",
                    "table": session["table"],
                    "type": session["type"]
                }
                data.update({"quantity": session["quantity"]})

                db.child("orders").push(data)
                return redirect(url_for('menu'))
            else:
                flash("Couldn't login! Try Again :(", "danger")
        else:
            flash("User not found :(", "danger")  

    return render_template("login.html")

# @app.route('/tab_checkin', methods=['GET', 'POST'])
# def tab_checkin():
#     if request.method == "POST":
#         location = request.form['location']
#         table = request.form['table']
#         quantity = int(request.form['quantity'])
#         start_time = request.form['start_time']
#         data = {
#             "type":'customer',
#             "location": location,
#             "table": table,
#             "quantity": quantity,
#             "start_time": start_time
#         }
#         results = db.child("users").order_by_child("name").equal_to(session["name"]).push(data)
#         session["id"] = results["name"]
#         session['location'] = location
#         session['table'] = table
#         session["cart"] = {"products": {}, "cart_total":0}
#         session["quantity"] = quantity
#         session["start_time"] = start_time
#         session["service_charge"] = 100 * quantity
#         return redirect(url_for('menu'))


#     return render_template("tab_checkin.html")

@app.route('/admin_login', methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        admin = db.child("admin").get().val()

        if email == admin["email"] and password == admin["password"]:
            session["new_order"] = {"order_user": ' ', "data": []}
            session["logged_in"] = True
            session["email"] = email
            session['type'] = 'admin'
            session["phone"] = 11111111

            # # # print('password matched')
            return redirect(url_for('dashboard'))
    
    return render_template("admin_login.html")


def stream_handler(message):
    print(message["event"]) # put
    print(type(message['path']))
    print(message["path"])
    if message["path"] != "/":
        session["new_order"]["order_user"] = message["path"].split("/")[-1]


@app.route('/admin/dashboard', methods=['GET', 'POST'])
@is_admin
def dashboard():
    orders1 = db.child("orders").order_by_child("status").equal_to("OPEN").get().val()
    if orders1:
        for order in orders1:
            string = orders1[order]['start_time']
            if '-' in string:
                strg = string.replace('-', '/')
                string = strg

            orders1[order]['start_time'] = datetime.strptime(string, '%d/%m/%Y %I:%M %p')
        
        orders = OrderedDict(sorted(orders1.items(), key=lambda kv: datetime.strptime(kv[1]['order'][-1]['order_time'], '%d/%m/%Y %I:%M %p'), reverse=True))

    session_time = time(2,0,0)
    now = datetime.now(IST).time()

    return render_template("dashboard.html", orders=orders, session_time=session_time, now=now)


@app.route('/checkout_order/<string:order_id>', methods=['GET', 'POST'])
def checkout_order(order_id):
    order = db.child("orders").child(order_id).update({"status": "CLOSED"})
    return redirect(url_for("dashboard"))


@app.route('/order_history')
def order_history():
    orders = db.child("orders").order_by_child("status").equal_to("CLOSED").get().val()
    new_orders = {}
    total = 0
    if orders:
        for id in orders.keys():
            if orders[id]["type"] != "tab":
                new_orders[id] = orders[id]
                total += orders[id]["total"]

    return render_template("order_history.html", orders=new_orders, total=total)
    
@app.route('/delete_users')
def delete_users():
    users = db.child("users").get().val()
    if users:
        for id in users.keys():
            db.child(f"users/{id}").remove() if users[id]["type"]=='customer' else None
        flash("deleted", "success")
    else:
        flash("No users", "info")
    return redirect(url_for("order_history"))

@app.route('/delete_orders')
def delete_orders():
    orders = db.child("orders").get().val()
    if orders:
        for id in orders.keys():
            db.child(f"orders/{id}").remove() if orders[id]["type"]!='tab' and orders[id]["status"] == "CLOSED" else None
        flash("deleted", "success")
    else:
        flash("No orders", "info")
    return redirect(url_for("order_history"))

@app.route('/view_sales', methods=["GET", "POST"])
def view_sales():
    sales = db.child("sales").get().val()
    if request.method == "POST":
        date = request.form.get("date")
        sale = db.child("sales").child(date).get().val()

        return render_template("sales.html", sales = sales, sale = sale, date= date)
    else:
        return render_template("sales.html", sales = sales)

@app.route('/delete_order/<string:id>/')
@app.route('/delete_order/<string:id>/<string:item_id>')
def delete_order(id, item_id='None'):
    users = db.child("users").get().val()
    orders = db.child("orders").get().val()
    value = 0
    flag = 0

    for u in users.keys():
        if users[u]["phone"] == orders[id]["phone"]:
            flag = 1
            user = u
        
    if flag == 1:
        db.child("users").child(user).update({"total_total": 0})

    if item_id != 'None':
        order = db.child("orders").child(id).child('order').get().val()
        total = db.child("orders").child(id).child('total').get().val()
        # # print(item_id)
        for o in order:
            if 'entry_fee' in o:
                entry_fee = o["entry_fee"]
            if 'order_id' in o:
                if str(o["order_id"]) == item_id:
                    # # print(o)
                    if total > entry_fee:
                        if total - o["amount"] > entry_fee:
                            total -= o["amount"]
                        else:
                            total = entry_fee
                    order.remove(o)

        db.child("orders").child(id).child('order').set(order)
        db.child("orders").child(id).child('total').set(total)
        return redirect(url_for("dashboard"))

    else:
        if orders[id]["type"] == "tab":
            for u in users.keys():
                if users[u]["phone"] == orders[id]["phone"]:
                    total = db.child("users").child(u).child("total_total").get().val()
                    userdata = db.child("users").child(u).get().val()
                    # # print("USERATA: :" + str(userdata))
                    value = total - orders[id]["total"]

                if value > 0:
                    userdata.update({"total_total": value})
                    try:
                        # # print(userdata)
                        db.child("users").child(u).update({"total_total": value})
                    except Exception as e:
                        print(e)

            db.child("orders").child(id).remove()
            return redirect(url_for("manage_tabs"))

        else:
            db.child("orders").child(id).remove()
            return redirect(url_for("order_history"))
    

@app.route('/edit_total/<string:customer>', methods=["POST", "GET"])
def edit_total(customer):
    users = db.child("users").order_by_child("type").equal_to("tab").get().val()
    val = request.form.get("val")
    # # print(customer)
    if request.form.get("plus"):
        for u in users.keys():
            if users[u]["phone"] == customer:
                total = db.child("users").child(u).child("total_total").get().val()
                userdata = db.child("users").child(u).get().val()
                # # print(userdata)
                value = total + int(val)
                userdata.update({"total_total": value})
                try:
                    db.child("users").child(u).set(userdata)
                except Exception as e:
                    print(e)
        
    if request.form.get("minus"):
        for u in users.keys():
            if users[u]["phone"] == customer:
                total = db.child("users").child(u).child("total_total").get().val()
                userdata = db.child("users").child(u).get().val()
                # # print(userdata)
                value = total - int(val)
                userdata.update({"total_total": value})
                try:
                    db.child("users").child(u).set(userdata)
                except Exception as e:
                    print(e)

    return redirect(url_for("manage_tabs"))

@app.route('/add_member', methods=["POST"])
def add_member():
    name = request.form.get("name")
    phone = request.form.get("phone")
    password = request.form.get("password")
    res = db.child("users").push({
        "name": name,
        "phone": phone,
        "password": password,
        "type": "tab",
        "total_total": 0
    })
    flash("Added successfully", "success")
    return redirect(url_for("manage_tabs"))

@app.route('/to_csv')
def to_csv():
    orders = db.child("orders").order_by_child("status").equal_to("CLOSED").get().val()
    df = pd.DataFrame(orders)
    df=df.T
    df = df.drop(['location', 'order', 'table', 'quantity', 'status'], axis = 1)
    df = df.iloc[:, 0:]
    # # print(df)
    df.to_csv("data.csv")
    return send_file("data.csv", as_attachment=True)

@app.route('/admin/logout/')
@is_logged_in
def logout():
    if 'logged_in' in session:
        session.clear()
        return redirect(url_for('login'))
    else:
        flash('You are not Logged in','secondary')
        return redirect(url_for('login'))


@app.route('/add_to_cart/<string:product_id>')
def add_to_cart(product_id):
    item  = db.child("menu").child(product_id).get().val()
    # if "cigarette" in item.values():
    if "cart" in session:
        product_dict = session["cart"]["products"]
        if product_id in product_dict:
            # add number
            product_dict[product_id] += 1
        else:
            # add key value
            product_dict[product_id] = 1
        total_price = int(session["cart"]["cart_total"])
        total_price += int(item["price"])
        session["cart"] = {"products": product_dict, "cart_total": total_price}
    else:
        session["cart"] = {
            "products": {product_id: 1},
            "cart_total": int(item["price"]),
        }
    flash("Added product to cart", "success")
    return redirect(url_for("menu"))

@app.route('/admin/add_order', methods=["GET", "POST"])
@is_admin
def add_order():
    session["service_charge"] = 0
    session["cart"] = {"products": {}, "cart_total": 0}
    menu  = db.child("menu").get().val()
    categories = set([menu[item]["category"] for item in menu])
    return render_template("menu.html", menu=menu, categories=categories)

@app.route('/add_new_order', methods=["GET", "POST"])
# @is_admin
def add_new_order():
    name = request.form.get("name")
    phone = request.form.get("phone")
    # # print(name + " " + phone)
    session["name"] = name
    session["phone"] = phone

    cart_dict = session["cart"]["products"]
    cart = []
    
    order_id_min = randint(1, 99999)
    order_date = datetime.now(IST)
    order_date = order_date.strftime("%d/%m/%Y %I:%M %p")

    for product_id in list(cart_dict.keys()):
        pro = db.child("menu").child(product_id).get().val()
        amount = int(pro.get("price")) * int(cart_dict[product_id])
        cart.append({
            "order_id": order_id_min,
            "order_time": order_date,
            "product_id": product_id,
            "print": 0,
            "name": pro.get("name"),
            "quantity": int(cart_dict[product_id]),
            "amount": amount,
            "category": pro.get("category"),
        })   

    # # time = datetime.now(IST)
    # # # print(session["start_time"])
    # sesh_time = session["start_time"].strftime("%d/%m/%Y %I:%M %p")
    # session["start_time"] = sesh_time

    now = datetime.now(IST)
    now = now.strftime("%d/%m/%Y %I:%M %p")

    order_id = randint(1, 99999)
    cart.append({
        "entry_fee": session["service_charge"],
        "order_time":now

    })
    total = session["service_charge"]
    if session["cart"]["cart_total"] > session["service_charge"]:
        total += session["cart"]["cart_total"] - session["service_charge"]

    start_time = datetime.now(IST)
    
    dt_string = start_time.strftime("%d/%m/%Y %I:%M %p")
    session["start_time"] = dt_string
    data1 = {
        "name": name,
        "phone": phone,
        "order_no": order_id,
        "order": cart,
        "total": total,
        'location': "None",
        "start_time": dt_string,
        "status": "OPEN",
        "table": "None",
        "type": session["type"]
    }
    data1.update({"quantity": 0})
    # # # print(data1)
    res = db.child("orders").push(data1)
    # session["order_id"] = order_id
    # # # print(order_id)
    # # # print(res)
    flash("Order placed", "success")

    return redirect(url_for("total_total"))

@app.route('/print_order/<string:id>/<int:item_id>')
def print_order(id, item_id):
    orders = db.child('orders').get().val()
    all_order = orders[id]['order']
    for i in all_order:
        if 'order_id' in i:
            if i['order_id'] == item_id:
                details = orders[id]
                order = i

    item = db.child("orders").child(id).child("order").order_by_child("order_id").equal_to(item_id).get().val()
    for i in item.keys():
        item[i]["print"] = 1
    
    db.child("orders").child(id).child("order").order_by_child("order_id").equal_to(item_id).update(item)

    return render_template("print_order.html", order = order, details = details)
    
if __name__ == '__main__':
    app.run(debug=True, port=7001)

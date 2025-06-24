import random
import psycopg2
from datetime import datetime
import re
import requests
import json
from flask import Flask, render_template, request, redirect, url_for, session
from decimal import Decimal
from flask import session


# Initialize flask application
app = Flask(__name__)
app.secret_key = 'supersecret123'

# PostgreSQL connection 
connection = {
    'dbname': 'coffee_shop_480', 
    'user': 'sanatopia',
    'host': '127.0.0.1',  
    'password': 'Sana123456',  
    'port': 5432
}

# Open PostgreSQL connection
def get_db():
    return psycopg2.connect(**connection)

# The purpose of the function is to authenticate a user by checking if the provided email and password exist in the employee table of the database.
# The function receives two input parameters: 'email' and 'password', both expected to be strings representing the user's login credentials.
# The function connects to the database, executes a SQL query to search for a matching employee record,fetches the results, and closes the connection.
# The function returns the first matching row as a tuple if authentication is successful; otherwise, it returns None.
def authenticate_user(email, password):
    ## Connect to the database
    conn = get_db()
    ### Create a cursor to perform database operations
    cur = conn.cursor()
    cur.execute("SELECT * FROM employee WHERE email = %s AND password = %s", (email, password))
    rows = cur.fetchall()
    conn.close() ## Close the database connection
    #return the first matching record if any; otherwise, return None
    return rows[0] if rows else None

# The purpose of the function is to serve the home page of the web application.
# the function does not receive any parameters 
# The function checks if the 'user' key is not present in the session; if so, it clears the entire session.
# The function then renders and returns the 'home.html' template to the client.
@app.route('/')
def home():
    ## Check if 'user' is not in the session data
    if 'user' not in session:
        session.clear() ## Clear the session if no user is logged in
    return render_template('home.html') ## Render and return the home page

# The purpose of the function is to serve the login page of the web application.
# The function does not receive any parameters 
# The function simply renders the 'login.html' template so that the user can input their login credentials.
# The function returns the rendered login page to the client.
@app.route('/login', methods=['GET'])
def login():
    return render_template('login.html')## Render and return the login page

# The purpose of the function is to handle the login form submission
# The function does not receive parameters directly it processes a POST request containing 'email' and 'password' fields from the submitted form data.
# The function queries the database for the provided email, verifies the password, and redirects the user to their dashboard.
# If authentication fails, it re-renders the login page with an error message.
@app.route('/handle_login', methods=['POST'])
def handle_login():
    ## Retrieve email and password from the submitted form
    email = request.form['email']
    password = request.form['password']

    ## Connect to the database
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT ssn, name, password FROM employee WHERE email = %s", (email,))
    user = cur.fetchone()
    cur.close() ## Close the cursor and the database connectio
    conn.close()

    if user and user[2] == password:
        ssn = user[0]
        name = user[1]
        session['user'] = email
        session['user_id'] = ssn
        session['name'] = name

         ## Retrieve the user's roles from the databas
        roles = get_user_roles(ssn)
         ## Assign the first role if available; otherwise, default to 'employee'
        if roles:
            role = roles[0]
        else:
            role = 'employee'
         ## Store the user's role in the session
        session['role'] = role

        return redirect(url_for('dashboard', user_id=ssn, role=role))  
    else:
        return render_template('login.html', message='Invalid credentials')

# The purpose of the function is to log out the currently authenticated user by clearing their session data.
# The function does not receive any parameters directly
# The function clears all data stored in the session to effectively log out the user.
# The function then redirects the user to the login page.    
@app.route('/logout', methods=['POST'])
def logout():
    session.clear()## Clear all session data to log the user out
    return redirect(url_for('login'))


# The purpose of the function is to display the dashboard page for a logged-in user, showing their name and available roles.
# The function receives two input parameters from the URL: user_id and role.
# The function retrieves all roles associated with the user from the database, as well as the user's name.
# The function returns the 'dashboard.html' template, passing the user's name, current role, and list of roles.
@app.route('/dashboard/<user_id>/<role>')
def dashboard(user_id, role):
     ## Retrieve all roles associated with the user from the database
    roles = get_user_roles(user_id)

    ## Connect to the database
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT name FROM employee WHERE ssn = %s", (user_id,))
    name_row = cur.fetchone()
    ## Close the database connection
    conn.close()

    name = name_row[0] if name_row else "User"  

    #return the dashboard page with the user's name, role, and list of roles
    return render_template('dashboard.html', roles=roles, role=role, name=name)

# The purpose of the function is to retrieve the roles 'manager' or 'barista' associated with a user based on their SSN.
# The function receives one input parameter, 'ssn'
# The function queries the database to check if the user exists in the 'manager' and 'barista' tables.
# The function returns a list of roles assigned to the user.
def get_user_roles(ssn):
    conn = get_db()## Connect to the database
    cur = conn.cursor()
    ## Initialize an empty list to store user roles
    roles = []

    ## Check if the user is a manager by querying the manager table
    cur.execute("SELECT * FROM manager WHERE ssn = %s", (ssn,))
    if cur.fetchone():
        ## If a matching record is found, add 'manager' to the roles list
        roles.append("manager")
    cur.execute("SELECT * FROM barista WHERE ssn = %s", (ssn,))
    if cur.fetchone():
        roles.append("barista")
    conn.close()## Close the database connection

    ## Return the list of roles associated with the user
    return roles

@app.route('/manager')
def manager_menu():
    return render_template('manager_menu.html')


# The purpose of the function is to display the barista menu page, allowing authenticated baristas to access their specific options.
# The function does not receive any parameters 
# The function checks if 'user_id' and 'role' are present in the session; if not, it redirects the user to the home page.
@app.route('/barista')
def barista_menu():
    ## Check if the user is authenticated and has a role set in the session
    if 'user_id' not in session or 'role' not in session:
        return redirect(url_for('home'))
     ## Render and return the barista menu page, passing the user's ID and role
    return render_template('barista_menu.html', user_id=session['user_id'], role=session['role'])


# The purpose of the function is to allow the addition of a new employee into the 'employee' table of the database.
# The function handles both GET and POST requests to the '/add_employee' route.
# On a GET request, it simply renders the 'add_employee.html' form page.
# On a POST request, it retrieves form data for the new employee, attempts to insert the employee into the database, and returns the form page again with a success or error message based on the result.
# The function returns the rendered HTML template with an optional message.

@app.route('/add_employee', methods=['GET', 'POST'])
def add_new_employee():
     ## Retrieve form fields for the new employee
    if request.method == 'POST':
        ssn = request.form['ssn']
        name = request.form['name']
        email = request.form['email']
        salary = request.form['salary']
        password = request.form['password']
        roles = request.form.getlist('roles')  

        conn = get_db()
        cur = conn.cursor()
        try:
             ## Execute an SQL INSERT statement to add the new employee to the database
            cur.execute("""
                INSERT INTO employee (ssn, name, email, salary, password)
                VALUES (%s, %s, %s, %s, %s)
            """, (ssn, name, email, salary, password))

            if 'manager' in roles:
                cur.execute("INSERT INTO manager (ssn, ownership_percent) VALUES (%s, %s)", (ssn, 0))  

            if 'barista' in roles:
                cur.execute("INSERT INTO barista (ssn) VALUES (%s)", (ssn,))

            conn.commit()
             ## Set a success message to display to the user
            message = "Employee added successfully with role(s): " + ", ".join(roles)

        except psycopg2.Error as e: ## If there is a database error, set an error message to display
            conn.rollback()
            message = f"Error: {e}"
        finally:
            cur.close()
            conn.close()

        return render_template('add_employee.html', message=message)

    return render_template('add_employee.html')

# The purpose of the function is to allow an admin or authorized user to delete an employee from the system, including removal from the 'barista', 'manager', and 'employee' tables.
# The function handles both GET and POST requests to the '/delete_employee' route.
# On a POST request, it deletes the employee with the specified SSN from all relevant tables and commits the transaction.
# On a GET request, it retrieves a list of all current employees to display on the deletion form.
# The function returns either the deletion form page with a list of employees or redirects back after deletion.
@app.route('/delete_employee', methods=['GET', 'POST'])
def delete_employee():
    ## Connect to the database
    conn = get_db()
    cur = conn.cursor()

    if request.method == 'POST':
        ## Get the SSN of the employee to delete from the form
        ssn_to_delete = request.form['ssn']

        try:
            ## Delete the employee from the barista table if present
            cur.execute("DELETE FROM barista WHERE ssn = %s", (ssn_to_delete,))
            ## Delete the employee from the manager table if present
            cur.execute("DELETE FROM manager WHERE ssn = %s", (ssn_to_delete,))
            ## Delete the employee from the employee table
            cur.execute("DELETE FROM employee WHERE ssn = %s", (ssn_to_delete,))
            conn.commit()
        except Exception as e:
            conn.rollback()
            return f"Error deleting employee: {str(e)}" ## Return an error message if deletion fails

        return redirect(url_for('delete_employee'))

    cur.execute("SELECT ssn, name FROM employee")
    employees = cur.fetchall()
    cur.close() ## Close database connection
    conn.close()

    return render_template('delete_employee.html', employees=employees)


# The purpose of the function is to allow a user to create a new drink order by selecting from the available menu items.
# The function handles both GET and POST requests to the '/create_order' route.
# On a GET request, it retrieves the menu from the database, formats the data, and displays the order form.
# On a POST request, it captures the selected drink and quantity, then redirects to an order summary page.
# The function returns either the rendered order form or redirects to the summary page depending on the request method.
@app.route('/create_order', methods=['GET', 'POST'])
def create_order():
    conn = get_db()## Connect to the database
    cur = conn.cursor()
    ## Retrieve the menu items: name, price, and temperature flag
    cur.execute("SELECT name, price, is_hot FROM menuitem")
    menu = cur.fetchall()
    conn.close() ## Close the database connection

    menu_data = [
        {"name": row[0], "price": row[1], "temp": "hot" if row[2] else "cold"}
        for row in menu
    ]

    if request.method == 'POST':
        ## Retrieve drink name and quantity from the form
        drink_name = request.form['drink_name']
        quantity = int(request.form['quantity'])
        return redirect(url_for('order_summary', drink_name=drink_name, quantity=quantity))

     ## Render and return the order form with the available menu data
    return render_template('order.html', menu=menu_data)


# The purpose of the function is to display an order summary, calculate the total cost including any applicable discounts,and allow the user to confirm the order by choosing a payment method.
# The function retrieves the price of the selected drink, calculates the total cost, applies a discount if applicable, and either displays the summary or redirects to the order success page upon confirmation.
@app.route('/order_summary', methods=['GET', 'POST'])
def order_summary():
    drink_name = request.args.get('drink_name')
    quantity = int(request.args.get('quantity'))

    ## Connect to the database and fetch the price of the selected drink
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT price FROM menuitem WHERE name = %s", (drink_name,))
    price_row = cur.fetchone()
    conn.close()

    if not price_row:
        return "Drink not found", 404

    ## Extract the price and calculate the total cost
    price = price_row[0]
    total = price * quantity  

    ## Initialize discount to zero
    discount = 0
     ## Apply a 15% discount if the drink is a "latte" and quantity is 2 or more
    if drink_name.lower() == "latte" and quantity >= 2:
        discount = total * Decimal('0.15')
        total -= discount

    if request.method == 'POST':
        payment_method = request.form['payment_method']
        return redirect(url_for('order_success', drink_name=drink_name, quantity=quantity, payment_method=payment_method))

    ## Render and return the order summary page with calculated totals and discount
    return render_template('order_summary.html', 
                       drink_name=drink_name, 
                       quantity=quantity, 
                       total=total,
                       discount=discount)


# The purpose of the function is to finalize an order, update the accounting ledger with the new balance,and display a success page including the drink preparation steps.
# The function calculates the total price with any applicable discount, updates the accounting balance,
# retrieves the preparation steps for the ordered drink, and renders the success page with all relevant details.
@app.route('/order_success')
def order_success():
    ## Retrieve order details from query parameters
    drink_name = request.args.get('drink_name')
    quantity = int(request.args.get('quantity'))
    payment_method = request.args.get('payment_method')

    conn = get_db()
    cur = conn.cursor()

    ## Retrieve the unit price of the ordered drink
    cur.execute("SELECT price FROM menuitem WHERE name = %s", (drink_name,))
    price = cur.fetchone()[0]

     ## Calculate total price and apply discount if applicable
    total_price = price * quantity
    discount = 0
    if drink_name.lower() == "latte" and quantity >= 2:
        discount = total_price * Decimal('0.15')
        total_price -= discount

    ## Retrieve the most recent balance from the accounting ledger
    cur.execute("SELECT balance FROM accountingentry ORDER BY timestamp DESC LIMIT 1")
    result = cur.fetchone()
    current_balance = float(result[0]) if result else 0

    ## Compute new balance after adding the order's total price
    new_balance = current_balance + float(total_price)

    
    cur.execute("""
        INSERT INTO accountingentry (timestamp, balance)
        VALUES (%s, %s)
    """, (datetime.now(), new_balance))
    conn.commit()

    ## Retrieve the recipe steps for the ordered drink, ordered by step number
    cur.execute("""
        SELECT step_number, step_name FROM recipe
        WHERE menu_item_name = %s
        ORDER BY step_number
    """, (drink_name,))
    steps = cur.fetchall()

    ## Close the database connection
    conn.close()

     ## Render and return the order success page with order details, updated balance, and recipe steps
    return render_template('order_success.html',
                           drink_name=drink_name,
                           quantity=quantity,
                           total_price=total_price,
                           discount=discount,
                           payment_method=payment_method,
                           new_balance=new_balance,
                           steps=steps)


# The purpose of the function is to allow updating the salary of an existing employee based on their email address.
# On a POST request, it attempts to update the employee's salary in the database and shows a success or error message.
# On a GET request or after an update, it retrieves all employees and their current salary information to display in the form.
# The function returns the rendered 'update_employee.html' template, including the list of employees and an optional message.   
@app.route('/update_employee', methods=['GET', 'POST'])
def update_employee():
    ## Connect to the database
    conn = get_db()
    cur = conn.cursor()
    ## Initialize message for feedback to the user
    message = None

    if request.method == 'POST':
        ## Retrieve the email and new salary from the form
        email = request.form['email']
        new_salary = request.form['new_salary']
        try:
            new_salary = float(new_salary) ## Convert new salary to float and update the employee's record
            cur.execute("UPDATE employee SET salary = %s WHERE email = %s", (new_salary, email))
            conn.commit()
            message = "Salary updated successfully."
        except Exception as e:
            ## Roll back changes and store error message if update fails
            message = f"Error: {str(e)}"
            conn.rollback()

    ## Retrieve updated list of employees with their name, email, and salary
    cur.execute("SELECT name, email, salary FROM employee")
    employees = cur.fetchall()
    employees = [(name, email, float(salary)) for (name, email, salary) in employees]  
    
    conn.close()## Close the database connection
    #return the update employee page with the employee list and status message
    return render_template('update_employee.html', employees=employees, message=message)


# The purpose of the function is to display the full menu to users, including item details like size, type, price, and temperature.
# It queries the 'menuitem' table in the database to retrieve all available menu items and formats the results for display.
# The function returns the rendered view_menu.html template with the list of formatted menu items.
@app.route('/view_menu')
def view_menu():
    ## Connect to the database
    conn = get_db()
    cur = conn.cursor()
    ## Query the database for all menu items with their attributes
    cur.execute("SELECT name, size_oz, type, price, is_hot FROM menuitem")  
    menu = cur.fetchall()
    ## Format the raw menu data into a list of dictionaries for easier rendering
    menu_data = [
        {
            "name": row[0],
            "size": row[1],
            "type": row[2],
            "price": row[3],
            "temp": "hot" if row[4] else "cold"
        } for row in menu
    ]
    conn.close()
    #return the view_menu page with the formatted menu data
    return render_template('view_menu.html', menu=menu_data)


# The purpose of the function is to allow an admin or authorized user to add a new drink item to the menu.
# On a POST request, it retrieves form data, inserts the new item into the 'menuitem' table, and displays a success or error message.
# On a GET request, it simply renders the form for adding a new menu item.
# The function returns the rendered add_menu_item.html template along with any status message.
@app.route('/add_menu_item', methods=['GET', 'POST'])
def add_menu_item():
    ## Initialize the message to provide feedback to the user
    message = ""
    if request.method == 'POST':
        ## Retrieve new menu item details from the form
        name = request.form['name']
        size = request.form['size']
        drink_type = request.form['type']
        price = request.form['price']
        ## Determine if the drink is cold based on form input
        temp = request.form['temp'].lower() == 'cold'

        conn = get_db()
        cur = conn.cursor()
        try:
            ## Execute an SQL INSERT statement to add the new menu item
            cur.execute("""
                INSERT INTO menuitem (name, size, type, price, is_cold)
                VALUES (%s, %s, %s, %s, %s)
            """, (name, size, drink_type, price, temp))
            conn.commit()
            message = "Menu item added successfully."
        except psycopg2.Error as e:
            message = f"Error: {e}"
        conn.close()
    #return the add menu item page with a feedback message
    return render_template('add_menu_item.html', message=message)

# The purpose of the function is to display the top 5 best-selling menu items by quantity and the top 5 highest revenue-generating menu items.
# It queries the database to calculate both the most popular items by quantity sold and the highest revenue items by total sales amount.
# The function returns the rendered top_k_combined.html template with both rankings.
@app.route('/top_k_combined')
def top_k_combined():
    conn = get_db()
    cur = conn.cursor()

    ## Query to retrieve the top 5 menu items by total quantity sold
    cur.execute("""
        SELECT menu_item_name, SUM(quantity) AS total_sold
        FROM lineitem
        GROUP BY menu_item_name
        ORDER BY total_sold DESC
        LIMIT 5;
    """)
    popular = cur.fetchall()

    ## Query to retrieve the top 5 menu items by total revenue generated
    cur.execute("""
        SELECT li.menu_item_name, SUM(li.quantity * m.price) AS total_revenue
        FROM lineitem li
        JOIN menuitem m ON li.menu_item_name = m.name
        GROUP BY li.menu_item_name
        ORDER BY total_revenue DESC
        LIMIT 5;
    """)
    revenue = cur.fetchall()

    conn.close()
    #return the top_k_combined page with popular items and revenue data
    return render_template('top_k_combined.html', popular=popular, revenue=revenue)


# The purpose of the function is to display all available promotions from the database, including their pricing, time frames, and applicable days.
# It retrieves all promotion records, formats the data for easier display, and returns the rendered 'promotion.html' template with the promotion details.
@app.route('/promotion')
def promotion():
    conn = get_db()
    cur = conn.cursor()

    ## Query to retrieve all promotion details
    cur.execute("""
        SELECT promo_id, promo_price, start_time, end_time, day_of_week
        FROM promotion
    """)
    promos = cur.fetchall()

    ## Format the raw promotion data into a structured list of dictionaries
    formatted = [
        {
            "name": f"Promo #{row[0]}",
            "price": row[1],
            "start": row[2],
            "end": row[3],
            "day": row[4]
        } for row in promos
    ]
    conn.close()
    #return the promotion page with formatted promotion data
    return render_template('promotion.html', promotions=formatted)

@app.route('/analytics')
def analytics():
    return render_template('analytics.html')



# The purpose of the function is to allow an admin or authorized user to refill existing inventory items or add new items into the inventory system.
# On a POST request, it processes the refill by either updating the stock quantity of an existing item or inserting a new item into the inventory table.
# On a GET request or after a refill, it retrieves and displays the full list of inventory items.
# The function returns the rendered 'inventory.html' template with the inventory list and any feedback message.
@app.route('/refill_inventory', methods=['GET', 'POST'])
def refill_inventory():
    conn = get_db()
    cur = conn.cursor()

    ## Initialize a message for user feedback
    message = ""

    if request.method == 'POST':
        ## Retrieve and clean the item name from the form
        item_name = request.form['item_name'].strip().lower()
        try:
            ## Attempt to parse the quantity to a float
            quantity = float(request.form['quantity'])
        except ValueError:
            ## If parsing fails, set quantity to an invalid number to trigger error handling
            quantity = -1  

        ## Check for valid positive quantity
        if quantity <= 0:
            message = "Quantity must be a positive number!"
        else:
            ## Check if the item already exists in the inventory
            cur.execute("SELECT * FROM inventoryitem WHERE name = %s", (item_name,))
            item = cur.fetchone()

            if item:
                ## If item exists, update its stock quantity
                cur.execute("""
                    UPDATE inventoryitem
                    SET in_stock = in_stock + %s
                    WHERE name = %s
                """, (quantity, item_name))
                conn.commit()
                message = f"Successfully added {quantity} more units to {item_name}!"
            else:
                 ## If item does not exist, insert it as a new inventory item
                unit = "unit"
                price_per_unit = 1.00

                
                cur.execute("""
                    INSERT INTO inventoryitem (name, unit, price_per_unit, in_stock)
                    VALUES (%s, %s, %s, %s)
                """, (item_name, unit, price_per_unit, quantity))
                conn.commit()
                message = f"New item '{item_name}' added with {quantity} units!"

    ## Retrieve the updated inventory list to display
    cur.execute("SELECT name, unit, price_per_unit, in_stock FROM inventoryitem ORDER BY name ASC")
    inventory = cur.fetchall()

    conn.close()

    #return the inventory page with the inventory list and status message
    return render_template('inventory.html', inventory=inventory, message=message)


# The purpose of the function is to display the full accounting report, showing the historical balance changes over time.
# It retrieves all accounting entries timestamp and balance from the database in chronological order, also calculates the total balance based on the most recent entry.
# The function returns the rendered accounting.html template with the accounting history and total balance.
@app.route('/view_accounting_report')
def view_accounting_report():
    conn = get_db()
    cur = conn.cursor()

    ## Query to retrieve all accounting entries ordered by timestamp
    cur.execute("SELECT timestamp, balance FROM accountingentry ORDER BY timestamp ASC")
    entries = cur.fetchall()
    ## Close the database connection
    conn.close()

    ## Calculate the total balance based on the most recent entry
    total_balance = entries[-1][1] if entries else 0  

    #return the accounting report page with the entry history and total balance
    return render_template('accounting.html', history=entries, total_balance=total_balance)


# The purpose of the function is to send a text prompt to a locally running Ollama LLM  and retrieve the generated response.
# The function receives a single input parameter, 'prompt', which is a string containing the question or command to send to the model.
# The function sends a POST request to the local Ollama API, extracts the generated response from the returned JSON, and returns the response as a cleaned-up string.
def ask_ollama(prompt):
    """Send a prompt to local Ollama LLM and get the response."""

    ## Define the URL of the local Ollama API endpoint
    url = "http://localhost:11434/api/generate"

    ## Prepare the payload with the model name, prompt, and stream setting
    payload = {
        "model": "llama3",  
        "prompt": prompt,
        "stream": False
    }

    ## Send a POST request to the Ollama API with the given payload
    response = requests.post(url, json=payload)
    ## Parse the JSON response returned by the server
    data = response.json()

    #return the generated text from the response
    return data.get('response', '').strip()

OLLAMA_API_URL = "http://localhost:11434/api/generate"

# The purpose of the function is to send a prompt to a local Ollama LLM server and retrieve the generated response.
# The function receives a single input parameter, 'prompt', which is the user's text prompt to send to the model.
# The function sends a POST request to the server, parses the first line of the raw response as JSON,
# and returns the generated text response. If parsing fails, it returns an error message.
def ask_ollama(prompt):
    """Send a prompt to the local Ollama server and get the response."""
    url = "http://localhost:11434/api/generate"

    ## Define the request payload with the model name and prompt
    payload = {
        "model": "llama3",
        "prompt": prompt,
        "stream": False
    }
    ## Send a POST request to the Ollama server with the payload
    response = requests.post(url, json=payload)
    try:
        raw_text = response.text
        first_json = json.loads(raw_text.splitlines()[0])
        ## Extract and return the generated response text
        return first_json.get("response", "Sorry, no response from LLM.")
    except Exception as e:
        ## Return an error message if parsing fails
        return f"Error parsing LLM response: {e}"


# The purpose of the function is to interact with a local LLM to generate drink facts and personalized upsell recommendations based on user input.
# The function handles both GET and POST requests to the '/llm_suggestions' route.
# On a POST request, it processes the user's drink name and/or order details, sends prompts to the LLM for suggestions, and stores the responses.
# The function returns the rendered 'llm_suggestions.html' template with any generated facts and recommendations.
@app.route('/llm_suggestions', methods=['GET', 'POST'])
def llm_suggestions():

    ## Initialize variables to hold LLM-generated content
    drink_facts = None
    order_recommendations = None

    if request.method == 'POST':
        ## Retrieve the drink name and order details from the form
        drink_name = request.form.get('drink_name')
        order_details = request.form.get('order_details')

        ## If a drink name is provided, ask the LLM for a historical fact and preparation info
        if drink_name:
            prompt = f"Give an interesting historical fact and preparation info about the drink called {drink_name}."
            drink_facts = ask_ollama(prompt)

        ## If order details are provided, ask the LLM for upsell recommendations
        if order_details:
            prompt = f"Given the order: {order_details}, suggest additional coffee shop items the customer might enjoy."
            order_recommendations = ask_ollama(prompt)

    #return the LLM suggestions page with generated facts and recommendations
    return render_template('llm_suggestions.html', drink_facts=drink_facts, order_recommendations=order_recommendations)

if __name__ == '__main__':
    app.run(debug=True)

import psycopg2
from datetime import datetime 
import requests
from decimal import Decimal


connection = { 'dbname': 'coffee_shop_480',
'user': 'postgres',
'host': '127.0.0.1',
'password': '123456',
'port': 5433 }

# open connection
conn = psycopg2.connect(**connection)
print(conn)
print("CONNECTED TO DATABASE")


# log in a user using email and password
def login(email, password):
    cur = conn.cursor()
    # run query
    cur.execute(f"SELECT * FROM employee WHERE email = '{email}' AND password = '{password}'")
    # get all results into a list of tuples
    rows = cur.fetchall()  
    if rows != []:
        return rows[0]
    
# log out helper
def safe_input(prompt):
    user_input = input(prompt).strip().lower()
    if user_input == "logout":
        print("Logging out...")
        exit(0)
    return user_input

# talk to the LLM
def ask_llm(prompt):
    response = requests.post(
        "http://localhost:11434/api/generate",
        json={
            "model": "llama3",
            "prompt": prompt,
            "stream": False  # stream = True gives partial outputs but we want full
        }
    )
    if response.ok:
        return response.json()["response"]
    else:
        return "LLM Error!!"


# look if a user is a manager or barista or both
def get_user_roles(ssn):
    cur = conn.cursor()
    roles = []
    cur.execute("SELECT * FROM manager WHERE ssn = %s", (ssn,))
    if cur.fetchone():
        roles.append("manager")
    cur.execute("SELECT * FROM barista WHERE ssn = %s", (ssn,))
    if cur.fetchone():
        roles.append("barista")
    return roles

# menu options for managers
def manager_menu():
    print("\n--- Manager Menu ---")
    print("1. Add New Employee")
    print("2. Delete Employee")
    print("3. Update Employee Salary")
    print("4. Refill Inventory")
    print("5. View Accounting Report")
    print("6. View Top K Popular Drinks")
    print("7. View Top-K Revenue Drinks")
    print("0. Logout")

# menu options for baristas
def barista_menu():
    print("\n--- Barista Menu ---")
    print("1. Create Order")
    print("0. Logout")

# add new employee into the database
def add_new_employee():
    cur = conn.cursor()
    print("\n--- Add New Employee ---")
    ssn = input("SSN (format: XXX-XX-XXXX): ")
    name = input("Full Name: ")
    email = input("Email: ")
    salary = input("Salary: ")
    password = input("Password: ")

    try:
        cur.execute("""
            INSERT INTO employee (ssn, name, email, salary, password)
            VALUES (%s, %s, %s, %s, %s)
        """, (ssn, name, email, salary, password))
    except psycopg2.Error as e:
        print("Error inserting into employee table:", e)
        conn.rollback()
        return

    role_input = input("Is this person a manager? (y/n): ").lower()
    if role_input == 'y':
        percent = input("Ownership % (1-100): ")
        try:
            cur.execute("INSERT INTO manager (ssn, ownership_percent) VALUES (%s, %s)", (ssn, percent))
        except psycopg2.Error as e:
            print("Error inserting into manager table:", e)

    role_input = input("Is this person a barista? (y/n): ").lower()
    if role_input == 'y':
        try:
            cur.execute("INSERT INTO barista (ssn) VALUES (%s)", (ssn,))
        except psycopg2.Error as e:
            print(" Error inserting into barista table:", e)

    conn.commit()
    print("Employee ADDED successfully.")

# delete employee from database
def delete_employee():
    cur = conn.cursor()
    print("\n--- Delete Employee ---")
    ssn = input("Enter the SSN of the employee to delete: ")

    # check if employee exists
    cur.execute("SELECT name FROM employee WHERE ssn = %s", (ssn,))
    result = cur.fetchone()

    if not result:
        print("Employee NOT found.")
        return

    confirm = input(f"Are you sure you want to delete {result[0]}? (y/n): ").lower()
    if confirm != 'y':
        print("Deletion cancelled.")
        return

    try:
        # remove schedule if barista
        cur.execute("DELETE FROM schedule WHERE ssn = %s", (ssn,))
        
        # remove from barista table
        cur.execute("DELETE FROM barista WHERE ssn = %s", (ssn,))
        
        # remove from manager table
        cur.execute("DELETE FROM manager WHERE ssn = %s", (ssn,))
        
        # remove from employee table
        cur.execute("DELETE FROM employee WHERE ssn = %s", (ssn,))
        
        conn.commit()
        print("Employee deleted successfully.")
    except psycopg2.Error as e:
        print("Error deleting employee:", e)
        conn.rollback()

# update employees salary
def update_salary():
    cur = conn.cursor()
    print("\n--- Update Employee Salary ---")
    email = input("Enter the employee's email: ")

    # look up employee by email
    cur.execute("SELECT ssn, name, salary FROM employee WHERE email = %s", (email,))
    result = cur.fetchone()

    if not result:
        print("Employee not found.")
        return

    ssn, name, current_salary = result
    print(f"Current salary of {name} ({ssn}): ${current_salary}")

    try:
        new_salary = float(input("Enter the new salary amount: "))
    except ValueError:
        print("Invalid input. Salary must be a number.")
        return

    try:
        cur.execute("UPDATE employee SET salary = %s WHERE ssn = %s", (new_salary, ssn))
        conn.commit()
        print(f"Salary updated successfully to ${new_salary:.2f}")
    except psycopg2.Error as e:
        print("Error updating salary:", e)
        conn.rollback()

# refill inventory 
def refill_inventory():
    cur = conn.cursor()
    print("\n--- Refill Inventory ---")

    # available inventory items
    cur.execute("SELECT name, in_stock, unit, price_per_unit FROM inventoryitem")
    items = cur.fetchall()

    if not items:
        print("No inventory items found.")
        return

    print("\nCurrent Inventory:")
    for item in items:
        print(f"- {item[0]}: {item[1]} {item[2]} @ ${item[3]:.2f} per {item[2]}")

    # which item to refill
    item_name = input("\nEnter the name of the item to refill: ").strip()

    cur.execute("SELECT in_stock, price_per_unit FROM inventoryitem WHERE name = %s", (item_name,))
    item = cur.fetchone()

    if not item:
        print("Item not found.")
        return

    current_stock, price_per_unit = item

    # how much to add
    try:
        quantity_to_add = float(input(f"How many units of '{item_name}' do you want to add?: "))
    except ValueError:
        print("Invalid input. Quantity must be a number.")
        return

    total_cost = total_cost = quantity_to_add * float(price_per_unit)


    # latest account balance
    cur.execute("SELECT balance FROM accountingentry ORDER BY timestamp DESC LIMIT 1")
    result = cur.fetchone()

    if result:
        current_balance = result[0]
    else:
        print("There's NO accounting records found! Using $0 as starting balance.")
        current_balance = 0

    new_balance = float(current_balance) - total_cost


    try:
        # update inventory & insert new accounting record
        cur.execute("UPDATE inventoryitem SET in_stock = in_stock + %s WHERE name = %s", (quantity_to_add, item_name))
        cur.execute("INSERT INTO accountingentry (timestamp, balance) VALUES (%s, %s)", (datetime.now(), new_balance))
        conn.commit()
        print(f"Added {quantity_to_add} units of '{item_name}' to inventory.")
        print(f"${total_cost:.2f} deducted. New account balance: ${new_balance:.2f}")
    except psycopg2.Error as e:
        print("Error during refill:", e)
        conn.rollback()

# show all accounting balance entries over time
def view_accounting_report():
    cur = conn.cursor()
    print("\n--- Accounting Report ---")

    cur.execute("SELECT timestamp, balance FROM accountingentry ORDER BY timestamp ASC")
    entries = cur.fetchall()

    if not entries:
        print("No accounting entries found.")
        return

    for timestamp, balance in entries:
        print(f"{timestamp.strftime('%Y-%m-%d %H:%M:%S')} → Balance: ${balance:.2f}")


# barista function for creating new drink order
def create_order():
    cur = conn.cursor()
    print("\n--- Create New Order ---")

    # available drinks
    cur.execute("SELECT name, price, size_oz, is_hot  FROM menuitem")
    menu_items = cur.fetchall()

    if not menu_items:
        print("No menu items available.")
        return

    print("\nAvailable Drinks:")
    for item in menu_items:
        print(f"- {item[0]} (${item[1]:.2f}) | Ounces: {item[2]} | Is the drink hot?: {item[3]}")

    order = {}  # dictionary to hold drink info

    while True:
        drink = input("\nEnter the name of the drink to add (or type 'done' to finish): ").strip()

        if drink.lower() == 'done':
            break

        # validate drink name
        cur.execute("SELECT price FROM menuitem WHERE name = %s", (drink,))
        price_check = cur.fetchone()
        if not price_check:
            print("That drink is not on the menu.")
            continue

        try:
            quantity = int(input("Enter quantity: "))
            if quantity <= 0:
                raise ValueError
        except ValueError:
            print("Quantity must be a positive number.")
            continue

        if drink in order:
            order[drink] += quantity
        else:
            order[drink] = quantity

        print(f"Added {quantity} x {drink} to order.")



    if not order:
        print("No items in order. Cancelling.")
        return

    # ingredient available BEFORE order summary
    cur.execute("SELECT name, in_stock FROM inventoryitem")
    inventory = {row[0]: row[1] for row in cur.fetchall()}

    for drink, qty in order.items():
        cur.execute("SELECT ingredients FROM recipe WHERE menu_item_name = %s", (drink,))
        recipe_rows = cur.fetchall()
        for row in recipe_rows:
            for ingredient in row[0]:
                if ingredient not in inventory:
                    print(f"Missing ingredient in inventory: {ingredient}")
                    return
                if inventory[ingredient] < qty:
                    print(f"Not enough {ingredient} in stock. Needed: {qty}, Available: {inventory[ingredient]}")
                    return

    # proceed w/ order summary
    print("\n Order Summary:")
    total = 0
    for drink, qty in order.items():
        cur.execute("SELECT price FROM menuitem WHERE name = %s", (drink,))
        price = cur.fetchone()[0]
        subtotal = price * qty
        total += subtotal
        print(f"- {drink} x {qty} = ${subtotal:.2f}")

    print(f"Total: ${total:.2f}")


    # 2+ lattes for 15% off promo
    if order.get("latte", 0) >= 2:
        discount = total * Decimal("0.15")
        total -= discount
        print(f"\nPromo applied: 15% off entire order for buying 2+ lattes! You saved ${discount:.2f}")

    process_order(order, total)


# helper to actually process & save the order into database
def process_order(order, total_price):
    cur = conn.cursor()

    # promo  stuff
    cur.execute("SELECT promo_id, start_time, end_time, day_of_week, promo_price FROM promotion")
    promos = cur.fetchall()

    now = datetime.now()
    current_time = now.time()
    current_day = now.strftime("%A")  # 'Monday' or any day of the week

    for promo_id, start_time, end_time, day_of_week, promo_price in promos:
        # if day does not match
        if day_of_week != 'All' and day_of_week.lower() != current_day.lower():
            continue

        # normal & overnight time ranges
        if start_time < end_time:
            if not (start_time <= current_time <= end_time):
                continue
        else:
            # overnight promo 9PM to 1AM
            if not (current_time >= start_time or current_time <= end_time):
                continue

        # look if items are in order
        cur.execute("SELECT menu_item_name FROM appliesto WHERE promo_id = %s", (promo_id,))
        required_items = [row[0] for row in cur.fetchall()]

        if all(item in order and order[item] >= 1 for item in required_items):
            print(f"\n🎉 Promotion applied: {required_items} for ${promo_price:.2f}")
            total_price = float(promo_price)
            break  # only use one promo at a time

    # payment method
    print("\nChoose payment method:")
    print("1. Cash")
    print("2. Credit Card")
    print("3. App")
    method_map = {"1": "cash", "2": "credit card", "3": "app"}
    method_choice = input("Enter choice: ")

    if method_choice not in method_map:
        print("Invalid choice.")
        return

    payment_method = method_map[method_choice]
    timestamp = datetime.now()

    try:
        # insert order into orderrecord
        cur.execute("""
            INSERT INTO orderrecord (order_time, payment_method, total_price)
            VALUES (%s, %s, %s)
        """, (timestamp, payment_method, total_price))

        # insert each drink into lineitem
        for drink, qty in order.items():
            cur.execute("""
                INSERT INTO lineitem (order_time, menu_item_name, quantity)
                VALUES (%s, %s, %s)
            """, (timestamp, drink, qty))

            # deduct ingredients based on recipe
            cur.execute("""
                SELECT ingredients FROM recipe
                WHERE menu_item_name = %s
            """, (drink,))
            recipe_rows = cur.fetchall()

            if not recipe_rows:
                print(f"No recipe found for {drink}. Skipping ingredient deduction.")
                continue

            for row in recipe_rows:
                ingredient_list = row[0]  # postgres array

            for ingredient in ingredient_list:
                # check current stock
                cur.execute("SELECT in_stock FROM inventoryitem WHERE name = %s", (ingredient,))
                result = cur.fetchone()

                if not result:
                    print(f"Ingredient {ingredient} not found in inventory.")
                    conn.rollback()
                    return

                in_stock = result[0]
                if in_stock < qty:
                    print(f"Not enough {ingredient} in stock. Needed: {qty}, Available: {in_stock}")
                    conn.rollback()
                    return

                # safe to deduct
                cur.execute("""
                    UPDATE inventoryitem
                    SET in_stock = in_stock - %s
                    WHERE name = %s
                """, (qty, ingredient))


        # update accounting balance
        cur.execute("SELECT balance FROM accountingentry ORDER BY timestamp DESC LIMIT 1")
        result = cur.fetchone()
        current_balance = float(result[0]) if result else 0
        new_balance = current_balance + float(total_price)

        cur.execute("""
            INSERT INTO accountingentry (timestamp, balance)
            VALUES (%s, %s)
        """, (timestamp, new_balance))

        conn.commit()

        print("\nOrder placed successfully!")
        print(f"Total: ${total_price:.2f}")
        print(f"New balance: ${new_balance:.2f}")


        #  instructions
        print("\nInstructions:")
        for drink, qty in order.items():
            print(f"\n- {qty}x {drink}:")
            cur.execute("""
                SELECT step_number, step_name FROM recipe
                WHERE menu_item_name = %s
                ORDER BY step_number
            """, (drink,))
            steps = cur.fetchall()
            for step in steps:
                print(f"  {step[0]}. {step[1]}")

    except psycopg2.Error as e:
        print("Error placing order:", e)
        conn.rollback()

# show top K drinks that made the most money
def top_k_revenue_drinks():
    cur = conn.cursor()
    print("\n--- Top-K Revenue Drinks ---")

    try:
        k_input = safe_input("Enter how many top-selling drinks to show (k or 'logout'): ")
        if not k_input.isdigit():
            print("Invalid input. Please enter a number.")
            return
        k = int(k_input)

        if k <= 0:
            print("Please enter a number greater than 0.")
            return
    except ValueError:
        print("Invalid input. Please enter a number.")
        return

    cur.execute("""
        SELECT li.menu_item_name, SUM(li.quantity * m.price) AS total_revenue
        FROM lineitem li
        JOIN menuitem m ON li.menu_item_name = m.name
        GROUP BY li.menu_item_name
        ORDER BY total_revenue DESC
        LIMIT %s;
    """, (k,))

    results = cur.fetchall()

    if not results:
        print("No revenue data found.")
        return

    print(f"\n Top {k} Revenue-Generating Drinks:")
    for i, (name, revenue) in enumerate(results, start=1):
        print(f"{i}. {name} — ${revenue:.2f}")


# show top K drinks that sold the most (most popular)
def top_k_popular_drinks():
    cur = conn.cursor()
    print("\n--- Top-K Most Popular Drinks ---")
    
    try:
        k = int(input("Enter how many top-selling drinks to show (k): "))
        if k <= 0:
            print("Please enter a number greater than 0.")
            return
    except ValueError:
        print("Invalid input. Please enter a number.")
        return

    cur.execute("""
        SELECT menu_item_name, SUM(quantity) AS total_sold
        FROM lineitem
        GROUP BY menu_item_name
        ORDER BY total_sold DESC
        LIMIT %s;
    """, (k,))

    results = cur.fetchall()

    if not results:
        print("No sales found!")
        return

    print(f"\n Top {k} Most Popular Drinks:")
    for i, (name, total) in enumerate(results, start=1):
        print(f"{i}. {name} — {total} sold")



if __name__ == '__main__':

    print("Welcome to 480 Coffee")
    email = input("Please Enter Your Email: ")
    password = input("Please Enter Your Password: ")
    result = login(email,password)
    
    while not result:
        print("Login Unsuccessful")
        email = input("Please Enter Your Email: ")
        password = input("Please Enter Your Password: ")
        result = login(email,password)

    print(f"Logged in as: '{result[1]}'")
    ssn = result[0]
    roles = get_user_roles(ssn)
    print("DEBUG: Roles list is:", roles)
    print(f"Your Role(s): {', '.join(roles)}")

while True:
    if len(roles) == 1:
        selected_role = roles[0]
    else:
        print("\nWhich role would you like to use?")
        if "manager" in roles:
            print("1. Manager")
        if "barista" in roles:
            print("2. Barista")
        print("0. Logout")

    

    choice = safe_input("Enter your role (or type 'logout'): ")

    if choice == "0":
        print("Logging out...")
        break
    elif (choice == "1" or choice.lower() == "manager") and "manager" in roles:
        selected_role = "manager"
    elif (choice == "2" or choice.lower() == "barista") and "barista" in roles:
        selected_role = "barista"

    else:
        print("Invalid role choice.")
        continue


    if selected_role == "manager":
        while True:
            manager_menu()
            choice = safe_input("Enter an option (or 0 to go back, or type 'logout'): ")
            if choice == "0":
                break
            elif choice == "1":
                add_new_employee()
            elif choice == "2":
                delete_employee()
            elif choice == "3":
                update_salary()
            elif choice == "4":
                refill_inventory()
            elif choice == "5":
                view_accounting_report()
            elif choice == "6":
                top_k_popular_drinks()
            elif choice == "7":
                top_k_revenue_drinks()
            else:
                print("Invalid option for manager.")

    elif selected_role == "barista":
        while True:
            barista_menu()
            choice = safe_input("Enter an option (or 0 to go back, or type 'logout'): ")
            if choice == "0":
                break
            elif choice == "1":
                create_order()
            else:
                print("Invalid option for barista.")

# llm using ollama
if __name__ == "__main__":
    print("Testing LLM connection...\n")
    result = ask_llm("Tell me something fun about cold brew coffee.")
    print("LLM Response:\n", result)

from flask import Flask, render_template, request, session, redirect, url_for
import datetime
from dateutil.relativedelta import relativedelta
import pymysql.cursors
import hashlib

app = Flask(__name__)

conn = pymysql.connect(host='localhost',user='root',password='',db='ticket_reservation_system',cursorclass=pymysql.cursors.DictCursor)

def getAirports(conn):
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM airport")
    return cursor.fetchall()

def getAirlines(conn):
    cursor = conn.cursor()
    cursor.execute("SELECT airline_name FROM airline")
    return cursor.fetchall()

def getUniqueAirplanesForAirline(conn, airline):
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM airplane WHERE airline_name=%s", airline)
    return cursor.fetchall()

def getAirplanesForAirline(conn, airline):
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM airplane natural left outer join maintenance WHERE airline_name=%s", airline)
    return cursor.fetchall()

def getFlightsForAirline(conn, airline):
    cursor = conn.cursor()
    query = "SELECT airplane_id, airline_name, T1.flight_num, T1.airport_city as depart_city, depart_date, depart_time, T2.airport_city as arrival_city, arrival_date, arrival_time, base_price, status FROM (SELECT airplane_id, airline_name, flight_num, airport_city, depart_date, depart_time, base_price, status FROM flight, airport WHERE depart_from = airport_code) as T1, (SELECT flight_num, airport_city, arrival_date, arrival_time FROM flight, airport where arrive_at = airport_code) as T2 WHERE T1.flight_num = T2.flight_num and airline_name = %s and T1.depart_date > CAST(CURRENT_DATE() as Date) ORDER BY depart_date"
    cursor.execute(query, airline)
    return cursor.fetchall()


def getAirlineFromStaff(conn, username):
    cursor = conn.cursor()
    query = 'SELECT * FROM airline_staff WHERE username=%s'
    cursor.execute(query, (username))

    staffData = cursor.fetchone()
    if staffData: return staffData['airline_name']
    else: return ""

def getCustomers(conn, airline):
    cursor = conn.cursor()
    query = 'SELECT first_name, last_name, email, emails FROM customer NATURAL JOIN (SELECT cust_email as email, Count(cust_email) as emails FROM ticket WHERE airline_name = %s GROUP BY cust_email) as emails ORDER BY emails DESC'
    cursor.execute(query, airline)
    return cursor.fetchall()

def moreFlightInfo(conn, airline, flight_num):
    cursor = conn.cursor()
    query = 'SELECT airplane_id, depart_date, depart_time FROM flight WHERE airline_name = %s and flight_num = %s'
    cursor.execute(query, (airline, flight_num))

    flight_info = cursor.fetchone()
    return flight_info['airplane_id'], flight_info['depart_date'], flight_info['depart_time']

def flightInfoForReview(conn, ticket_id):
    cursor = conn.cursor()
    query = 'SELECT airline_name, airplane_id, flight_num, depart_date, depart_time FROM ticket WHERE ticket_id=%s'
    cursor.execute(query, ticket_id)

    flight_info = cursor.fetchone()
    return flight_info['airline_name'], flight_info['airplane_id'], flight_info['flight_num'], flight_info['depart_date'], flight_info['depart_time']


#home page
@app.route('/')
def root():
    cursor = conn.cursor()
    query = """
    SELECT airline_name, T1.flight_num, T1.airport_city as depart_city, depart_date, depart_time, T2.airport_city as arrival_city, arrival_date, arrival_time, base_price, status
    FROM (SELECT airline_name, flight_num, airport_city, depart_date, depart_time, base_price, status FROM flight, airport WHERE depart_from = airport_code) as T1,
         (SELECT flight_num, airport_city, arrival_date, arrival_time FROM flight, airport where arrive_at = airport_code) as T2
    WHERE T1.flight_num = T2.flight_num and T1.depart_date >= CAST(CURRENT_DATE() as Date) ORDER BY depart_date """

    cursor.execute(query)
    flights = cursor.fetchall()
    return render_template("home.html", airlines = getAirlines(conn),airports = getAirports(conn), flights = flights, search=True)


#home page checking for status
@app.route('/checkStatus', methods=['GET', 'POST'])
def checkStatus():
    cursor = conn.cursor()

    airline_name = request.form['airline_name']
    flight_id = str(request.form['flight_id'])
    arrival_date = str(request.form['arrival_date'])
    depart_date = str(request.form['departure_date'])

    query = """
    SELECT airline_name, T1.flight_num, T1.airport_city as depart_city, T1.depart_date, T1.depart_time, T2.airport_city as arrival_city, T2.arrival_date, T2.arrival_time, T1.base_price, T1.status
    FROM
        (SELECT airline_name, flight_num, airport_city, depart_date, depart_time, base_price, status
         FROM flight
         JOIN airport ON depart_from = airport_code) AS T1
    JOIN
        (SELECT flight_num, airport_city, arrival_date, arrival_time
         FROM flight
         JOIN airport ON arrive_at = airport_code) AS T2 ON T1.flight_num = T2.flight_num
    WHERE T1.airline_name = %s AND T1.flight_num = %s AND T1.depart_date = %s AND T2.arrival_date = %s
    """

    cursor.execute(query, (airline_name, flight_id, depart_date, arrival_date))
    result = cursor.fetchone()

    return render_template("home.html", result=result, search=False)

#home page search flights
@app.route('/searchFlights', methods=['GET', 'POST'])
def searchFlight():
    cursor = conn.cursor()

    depart_from = request.form['departure_airport']
    arrive_to = request.form['arrival_airport']
    depart_date = str(request.form['departure_date'])
    return_date = str(request.form['return_date'])

    query = """
    SELECT airline_name, T1.flight_num, T1.airport_city as depart_city, depart_date, depart_time, T2.airport_city as arrival_city, arrival_date, arrival_time, base_price, status
    FROM (SELECT airline_name, flight_num, airport_city, depart_date, depart_time, base_price, status FROM flight, airport WHERE depart_from = airport_code) as T1,
         (SELECT flight_num, airport_city, arrival_date, arrival_time FROM flight, airport where arrive_at = airport_code) as T2
    WHERE T1.flight_num = T2.flight_num and T1.airport_city = %s and T2.airport_city = %s and depart_date = %s"""

    cursor.execute(query, (depart_from, arrive_to, depart_date))
    depart_flights = cursor.fetchall()

    if return_date:
        query = """
        SELECT airline_name, T1.flight_num, T1.airport_city as depart_city, depart_date, depart_time, T2.airport_city as arrival_city, arrival_date, arrival_time, base_price, status
        FROM (SELECT airline_name, flight_num, airport_city, depart_date, depart_time, base_price, status FROM flight, airport WHERE depart_from = airport_code) as T1,
             (SELECT flight_num, airport_city, arrival_date, arrival_time FROM flight, airport where arrive_at = airport_code) as T2
        WHERE T1.flight_num = T2.flight_num and T1.airport_city = %s and T2.airport_city = %s and depart_date = %s"""

        cursor.execute(query, (arrive_to, depart_from, return_date))
        return_flights = cursor.fetchall()
        return render_template("home.html", airlines = getAirlines(conn), airports=getAirports(conn),flights=depart_flights, rflights = return_flights, search=False)
    else:
        return render_template("home.html", airlines = getAirlines(conn),
                               airports=getAirports(conn), flights=depart_flights, search=False)


#login page
@app.route('/login')
def login():
    return render_template("/login.html")

@app.route('/register')
def register():
    return render_template("register.html")

@app.route('/logout')
def logout():
    session.pop('username')
    return redirect('/login')

# staff loign
@app.route('/staffLoginAuth', methods=['GET', 'POST'])
def loginStaff():
    username = request.form['username']
    password = request.form['password']
    hashed_password = hashlib.md5(password.encode()).hexdigest()

    cursor = conn.cursor()
    query = "SELECT * FROM airline_staff WHERE username = %s and password = %s"
    cursor.execute(query, (username, password))

    data = cursor.fetchone()
    if (data):
        session['username'] = username
        return redirect(url_for("staffHome"))
    else:
        return render_template("login.html", error = "Invalid Login")

@app.route('/getStaffReg')
def getStaffReg():
    return render_template("/register/staff.html", airlines=getAirlines(conn))

@app.route('/staffRegistration', methods=['GET', 'POST'])
def staffReg():
    cursor = conn.cursor()
    username = request.form['username']

    query = "SELECT * FROM airline_staff WHERE username = %s"
    cursor.execute(query, username)
    data = cursor.fetchone()
    if data is not None:
        return render_template("/login/staffReg.html", error="Account already associated with username, please login", airlines=getAirlines(conn))

    password = request.form['password']
    hashed_password = hashlib.md5(password.encode()).hexdigest()

    airline = request.form['airline_name']
    email = request.form['email']
    f_name = request.form['first_name']
    l_name = request.form['last_name']
    phone = str(request.form['phone_number'])
    dob = str(request.form['dob'])

    query = "insert into airline_staff values (%s, %s, %s, %s, %s, %s)"
    cursor.execute(query, (username, airline, password, f_name, l_name, dob))
    query = "insert into email values (%s, %s, %s)"
    cursor.execute(query, (username, airline, email))
    query = "insert into staff_phone_number values (%s, %s, %s)"
    cursor.execute(query, (username, airline, phone))

    conn.commit()
    return redirect(url_for("login"))

@app.route('/staffHome')
def staffHome():
    username = session['username']

    cursor = conn.cursor()
    query = 'SELECT * FROM airline_staff WHERE username=%s'
    cursor.execute(query, (username))

    staffData = cursor.fetchone()

    flights = getFlightsForAirline(conn, getAirlineFromStaff(conn, username))

    return render_template('/staff/staff_home.html', username=username, data=staffData, flights=flights, airports=getAirports(conn), search=True)

@app.route('/staffSearchFlights', methods=['GET', 'POST'])
def staffSearchFlight():
    cursor = conn.cursor()

    username = session['username']

    start_date = request.form['start']
    end_date = request.form['end']
    depart = request.form['departure_airport']
    arrival = request.form['arrival_airport']

    query = """
    SELECT airline_name, T1.flight_num, T1.airport_city as depart_city, depart_date, depart_time, T2.airport_city as arrival_city, arrival_date, arrival_time, base_price, status
    FROM (SELECT airline_name, flight_num, airport_city, depart_date, depart_time, base_price, status FROM flight, airport WHERE depart_from = airport_code) as T1,
         (SELECT flight_num, airport_city, arrival_date, arrival_time FROM flight, airport where arrive_at = airport_code) as T2
    WHERE T1.flight_num = T2.flight_num and airline_name = %s and T1.depart_date >= %s and T1.depart_date <= %s and T1.airport_city = %s and T2.airport_city = %s ORDER BY depart_date"""

    cursor.execute(query, (getAirlineFromStaff(conn, username), start_date, end_date, depart, arrival))
    flights = cursor.fetchall()

    return render_template('/staff/staff_home.html', flights=flights, airports=getAirports(conn), search=False)

@app.route('/getCustomersFromFlight', methods=['GET', 'POST'])
def getCustomersFromFlight():
    flight = request.form['flight_num']

    cursor = conn.cursor()

    query = "SELECT * FROM ticket natural left outer join review WHERE flight_num = %s"
    cursor.execute(query, flight)
    data = cursor.fetchall()

    query = "SELECT avg(rating) as avg FROM ticket natural left outer join review WHERE flight_num = %s"
    cursor.execute(query, int(flight))
    avgRating = cursor.fetchone()

    return render_template('/staff/flightReview.html', flight=flight, data=data, avgRating=avgRating)

@app.route('/flightManager')
def flightManager():
    username = session['username']
    airline = getAirlineFromStaff(conn, username)
    airplanes = getAirplanesForAirline(conn, airline)
    flights = getFlightsForAirline(conn, airline)
    airports = getAirports(conn)

    return render_template('/staff/flightManager.html', airplanes=airplanes, flights=flights, airports=airports)

@app.route('/flightStatusPage')
def flightStatusPage():
    airline = getAirlineFromStaff(conn, session['username'])
    flights = getFlightsForAirline(conn, airline)
    return render_template('/staff/flightManagerPages/changeFlightStatus.html', flights=flights)

@app.route('/changeStatus', methods=['GET', 'POST'])
def changeStatus():
    cursor = conn.cursor()
    flight_id = request.form['flight_id']
    status = request.form['status']

    query = "UPDATE flight SET status = %s WHERE flight_num = %s"
    cursor.execute(query, (status, flight_id))
    conn.commit()

    return redirect(url_for("flightManager"))

@app.route('/addFlightPage')
def addFlightPage():
    airline = getAirlineFromStaff(conn, session['username'])
    airports = getAirports(conn)
    airplanes = getUniqueAirplanesForAirline(conn, airline)
    return render_template('/staff/flightManagerPages/addFlight.html', airports=airports, airplanes=airplanes)

@app.route('/addFlight', methods=['GET', 'POST'])
def addFlight():
    cursor = conn.cursor()

    airline = getAirlineFromStaff(conn, session['username'])
    airplane_id = request.form['airplane_id']
    flight_id = request.form['flight_id']
    price = request.form['price']
    depart_airport = request.form['depart_airport']
    depart_date = request.form['depart_date']
    depart_time = request.form['depart_time']
    arrival_airport = request.form['arrival_airport']
    arrival_date = request.form['arrival_date']
    arrival_time = request.form['arrival_time']

    query = "select * from maintenance where airline_name = %s and airplane_id = %s"
    cursor.execute(query, (airline, airplane_id))
    maintenances = cursor.fetchall()

    depart_datetime = datetime.datetime.combine(
        datetime.date(int(depart_date[0:4]), int(depart_date[5:7]), int(depart_date[8:])),
        datetime.time(int(depart_time[0:2]), int(depart_time[3:])))
    arrive_datetime = datetime.datetime.combine(
        datetime.date(int(arrival_date[0:4]), int(arrival_date[5:7]), int(arrival_date[8:])),
        datetime.time(int(arrival_time[0:2]), int(arrival_time[3:])))

    if maintenances:
        for maintenance in maintenances:
            start_time = str(maintenance['start_time'])
            end_time = str(maintenance['end_time'])
            start_datetime = datetime.datetime.combine(maintenance['start_date'], datetime.time(int(start_time[0:2]), int(start_time[3:5])))
            end_datetime = datetime.datetime.combine(maintenance['end_date'], datetime.time(int(end_time[0:2]), int(end_time[3:5])))

            print(start_datetime, end_datetime, depart_datetime, arrive_datetime)
            print(max(start_datetime, depart_datetime))
            print(min(end_datetime, arrive_datetime))
            overlap = max(start_datetime, depart_datetime) <= min(end_datetime, arrive_datetime)
            print(overlap)

            if overlap:
                return render_template('/staff/flightManagerPages/addFlight.html', error="Maintenance Scheduled During Flight",
                                airports=getAirports(conn), airplanes=getAirplanesForAirline(conn, airline))


    query = "insert into flight values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,%s)"
    cursor.execute(query, (airline, airplane_id, flight_id, depart_airport, depart_date, depart_time,
                           arrival_airport, arrival_date, arrival_time, price, "ontime",0))
    conn.commit()

    return redirect(url_for("flightManager"))

@app.route('/addAirportPage')
def addAirportPage():
    return render_template('/staff/flightManagerPages/addAirport.html')

@app.route('/addAirport', methods=['GET', 'POST'])
def addAirport():
    cursor = conn.cursor()
    airport_code = request.form['code']

    query = "SELECT airport_code FROM airport WHERE airport_code=%s"
    cursor.execute(query, airport_code)
    exist = cursor.fetchone()

    if exist:
        return render_template('/staff/flightManagerPages/addAirport.html', error="Airport Code Already Used")

    name = request.form['name']
    city = request.form['city']
    country = request.form['country']
    num_terminals = request.form['num_terminals']
    airport_type = request.form['airport_type']

    query = "insert into airport values (%s, %s, %s, %s, %s, %s)"
    cursor.execute(query, (airport_code, name, city, country, num_terminals, airport_type))
    conn.commit()

    return redirect(url_for("flightManager"))

@app.route('/addAirplanePage')
def addAirplanePage():
    return render_template('/staff/flightManagerPages/addAirplane.html')

@app.route('/addAirplane', methods=['GET', 'POST'])
def addAirplane():
    cursor = conn.cursor()
    airplane_id = request.form['id']

    query = "SELECT airplane_id FROM airplane WHERE airplane_id=%s"
    cursor.execute(query, airplane_id)
    exist = cursor.fetchone()

    if exist:
        return render_template('/staff/flightManagerPages/addAirplane.html', error="Airplane ID Already Used")

    airline = getAirlineFromStaff(conn, session['username'])
    num_seats = request.form['num_seats']
    manufacturer = request.form['manufacturer']
    model_num = request.form['model_num']
    manufact_date = request.form['manufact_date']

    query = "insert into airplane values (%s, %s, %s, %s, %s, %s)"
    cursor.execute(query, (airline, airplane_id, num_seats, manufacturer, model_num, manufact_date))
    conn.commit()

    return redirect(url_for("flightManager"))


@app.route('/scheduleMaintenancePage')
def scheduleMaintanencePage():
    airline = getAirlineFromStaff(conn, session['username'])
    airplanes = getAirplanesForAirline(conn, airline)
    return render_template('/staff/flightManagerPages/scheduleMaintenance.html', airplanes=airplanes)

@app.route('/scheduleMaintenance', methods=['GET', 'POST'])
def scheduleMaintanence():
    cursor = conn.cursor()
    airline = getAirlineFromStaff(conn, session['username'])

    airplane_id = request.form['airplane_id']
    start_date = request.form['start_date']
    start_time = request.form['start_time']
    end_date = request.form['end_date']
    end_time = request.form['end_time']

    start_datetime = datetime.datetime.combine(
        datetime.date(int(start_date[0:4]), int(start_date[5:7]), int(start_date[8:])),
        datetime.time(int(start_time[0:2]), int(start_time[3:])))
    end_datetime = datetime.datetime.combine(
        datetime.date(int(end_date[0:4]), int(end_date[5:7]), int(end_date[8:])),
        datetime.time(int(end_time[0:2]), int(end_time[3:])))

    query = "select * from flight where airline_name=%s and airplane_id=%s"
    cursor.execute(query, (airline, airplane_id))
    flights = cursor.fetchall()

    if flights:
        for flight in flights:
            depart_time = str(flight['depart_time'])
            arrival_time = str(flight['arrival_time'])
            depart_datetime = datetime.datetime.combine(flight['depart_date'], datetime.time(int(depart_time[0:2]), int(depart_time[3:5])))
            arrive_datetime = datetime.datetime.combine(flight['arrival_date'], datetime.time(int(arrival_time[0:2]), int(arrival_time[3:5])))

            overlap = max(start_datetime, depart_datetime) <= min(end_datetime, arrive_datetime)
            print(overlap)

            if overlap:
                return render_template('/staff/flightManagerPages/scheduleMaintenance.html', airplanes=getAirplanesForAirline(conn, airline),
                                        error="Maintenance Scheduled During Flight")

    query = "insert into maintenance values (%s, %s, %s, %s, %s, %s)"
    cursor.execute(query, (airline, airplane_id, start_date, start_time, end_date, end_time))
    conn.commit()

    return redirect(url_for("flightManager"))

@app.route('/revenue')
def revenue():
    cursor = conn.cursor()
    username = session['username']
    airline = getAirlineFromStaff(conn, username)
    customers = getCustomers(conn, airline)

    today = datetime.date.today()
    last_month = today - relativedelta(months=1)
    last_year = today - relativedelta(years=1)

    query = "select SUM(cost) as month from ticket where airline_name = %s and purchase_date <= %s and purchase_date >= %s"
    cursor.execute(query, (airline, today, last_month))
    month_profit = cursor.fetchone()

    query = "select SUM(cost) as year from ticket where airline_name = %s and purchase_date <= %s and purchase_date >= %s"
    cursor.execute(query, (airline, today, last_year))
    year_profit = cursor.fetchone()

    return render_template('/staff/revenue.html', customers=customers, month_profit=month_profit, year_profit=year_profit)

@app.route('/frequentCustomers')
def frequent_customers():
    cursor = conn.cursor()

    query = '''SELECT first_name, last_name, email, COUNT(ticket_id) as ticket_count
    FROM customer
    JOIN ticket ON customer.email = ticket.cust_email
    WHERE ticket.purchase_date >= CURDATE() - INTERVAL 1 YEAR
    GROUP BY customer.email
    ORDER BY ticket_count DESC'''


    cursor.execute(query)
    customers = cursor.fetchall()
    return render_template("/staff/frequentCustomers.html", customers=customers)



@app.route('/getFlightsFromCustomer', methods=['GET', 'POST'])
def getFlightsFromCustomer():
    cursor = conn.cursor()
    cust_email = request.form['cust_email']

    query = "SELECT flight_num, COUNT(flight_num) as num_tickets FROM ticket WHERE cust_email=%s GROUP BY flight_num"
    cursor.execute(query, (cust_email))
    flights = cursor.fetchall()

    return render_template('/staff/customerFlights.html', flights=flights, cust_email=cust_email)

# CUSTOMER PAGE AND FUNCTIONALITY
@app.route('/custLoginAuth', methods=['GET', 'POST'])
def loginCustomer():
    username = request.form['username']
    password = request.form['password']

    hashed_password = hashlib.md5(password.encode()).hexdigest()

    cursor = conn.cursor()
    query = "SELECT * FROM customer WHERE email = %s and password = %s"
    cursor.execute(query, (username, password))

    data = cursor.fetchone()

    if (data):
        session['username'] = username
        return redirect(url_for("custHome"))
    else:
        return render_template("login.html", error = "Invalid Login")

@app.route('/getCustReg')
def getCustReg():
    return render_template("/register/customer.html")

@app.route('/customerRegistration', methods=['GET', 'POST'])
def customerRegistration():
    cursor = conn.cursor()
    email = request.form['email']

    query = "SELECT * FROM customer WHERE email = %s"
    cursor.execute(query, email)
    data = cursor.fetchone()

    if data is not None:
        return render_template("login.html", error="Account already exsits, try login")

    password = request.form['password']
    hashed_password = hashlib.md5(password.encode()).hexdigest()

    f_name = request.form['first_name']
    l_name = request.form['last_name']
    phone = str(request.form['phone_number'])
    dob = str(request.form['dob'])

    b_num = request.form['building_num']
    street = request.form['street']
    a_num = request.form['apartment_num']
    city = request.form['city']
    state = request.form['state']
    zip = request.form['zip_code']

    p_num = request.form['passport_num']
    p_exp = str(request.form['passport_exp'])
    p_country = request.form['passport_country']

    query = "insert into Customer values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
    cursor.execute(query, (email, password, f_name, l_name, b_num, street, a_num,
          city, state, zip, p_num, p_exp, p_country, dob))
    query = "insert into Phone_Number values (%s, %s)"
    cursor.execute(query, (email, phone))
    conn.commit()

    return redirect(url_for("login"))

@app.route('/custHome')
def custHome():
    username = session['username']
    today = datetime.date.today()
    cursor = conn.cursor()

    query = "SELECT * FROM Customer WHERE email=%s"
    cursor.execute(query, (username))
    data = cursor.fetchone()

    query = """
    SELECT * FROM (SELECT T1.flight_num, T1.airport_city as depart_city, depart_date, depart_time, T2.airport_city as arrival_city, arrival_date, arrival_time, base_price, status
    FROM (SELECT flight_num, airport_city, depart_date, depart_time, base_price, status FROM flight, airport WHERE depart_from = airport_code) as T1,
         (SELECT flight_num, airport_city, arrival_date, arrival_time FROM flight, airport where arrive_at = airport_code) as T2
         WHERE T1.flight_num = T2.flight_num) as flights

         natural join

         (SELECT distinct flight_num, ticket_id FROM ticket WHERE cust_email=%s and depart_date >= %s) as tickets"""

    cursor.execute(query, (username, today))
    future_flights = cursor.fetchall()

    query = """
    SELECT * FROM (SELECT T1.flight_num, T1.airport_city as depart_city, depart_date, depart_time, T2.airport_city as arrival_city, arrival_date, arrival_time, base_price, status
    FROM (SELECT flight_num, airport_city, depart_date, depart_time, base_price, status FROM flight, airport WHERE depart_from = airport_code) as T1,
         (SELECT flight_num, airport_city, arrival_date, arrival_time FROM flight, airport where arrive_at = airport_code) as T2 WHERE T1.flight_num = T2.flight_num) as flights

         natural join

         (SELECT distinct flight_num, ticket_id FROM ticket WHERE cust_email=%s and depart_date < %s) as tickets"""

    cursor.execute(query, (username, today))
    past_flights = cursor.fetchall()

    return render_template('/customer/customer_home.html', data=data, next_day=datetime.datetime.date((datetime.datetime.today() + relativedelta(days=1))), future_flights=future_flights, past_flights=past_flights)

@app.route('/getFlights')
def getFlights():
    cursor = conn.cursor()

    query = """
    SELECT airline_name, flight_num, depart_city, depart_date, depart_time, arrival_city, arrival_date, arrival_time,
        IF (num_seats * 0.8 <= numTickets, base_price * 1.25, base_price) as price
    FROM

    (SELECT airline_name, airplane_id, flight_num, depart_city, depart_date, depart_time, arrival_city, arrival_date, arrival_time, base_price, status, num_seats
    FROM
        (SELECT airline_name, airplane_id, T1.flight_num, T1.airport_city as depart_city, depart_date, depart_time, T2.airport_city as arrival_city, arrival_date, arrival_time, base_price, status
        FROM
            (SELECT airline_name, airplane_id, flight_num, airport_city, depart_date, depart_time, base_price, status
            FROM flight, airport WHERE depart_from = airport_code) as T1,
            (SELECT flight_num, airport_city, arrival_date, arrival_time
            FROM flight, airport where arrive_at = airport_code) as T2
        WHERE T1.flight_num = T2.flight_num and T1.depart_date >= CAST(CURRENT_DATE() as Date)) as flights natural join airplane) as flights2

    natural left outer join

    (SELECT flight_num, COUNT(flight_num) as numTickets
    FROM ticket
    GROUP BY flight_num) as tickets

    WHERE numTickets < num_seats or numTickets is NULL
    ORDER BY depart_date
    """

    cursor.execute(query)
    flights = cursor.fetchall()
    return render_template('/customer/tickets.html', today=datetime.date.today(), airlines = getAirlines(conn),
                           airports=getAirports(conn), flights=flights, search=True)

@app.route('/searchFlightsCust', methods=['GET', 'POST'])
def searchFlightsCust():
    cursor = conn.cursor()

    depart_from = request.form['departure_airport']
    arrive_to = request.form['arrival_airport']
    depart_date = str(request.form['departure_date'])
    return_date = str(request.form['return_date'])

    query = """
    SELECT airline_name, flight_num, depart_city, depart_date, depart_time, arrival_city, arrival_date, arrival_time,
        IF (num_seats * 0.8 <= numTickets, base_price * 1.25, base_price) as price
    FROM

    (SELECT airline_name, airplane_id, flight_num, depart_city, depart_date, depart_time, arrival_city, arrival_date, arrival_time, base_price, status, num_seats
    FROM
        (SELECT airline_name, airplane_id, T1.flight_num, T1.airport_city as depart_city, depart_date, depart_time, T2.airport_city as arrival_city, arrival_date, arrival_time, base_price, status
        FROM
            (SELECT airline_name, airplane_id, flight_num, airport_city, depart_date, depart_time, base_price, status
            FROM flight, airport WHERE depart_from = airport_code) as T1,
            (SELECT flight_num, airport_city, arrival_date, arrival_time
            FROM flight, airport where arrive_at = airport_code) as T2
        WHERE T1.flight_num = T2.flight_num and T1.airport_city = %s and T2.airport_city = %s and T1.depart_date = %s ORDER BY depart_date) as flights natural join airplane) as flights2

    natural left outer join

    (SELECT flight_num, COUNT(flight_num) as numTickets
    FROM ticket
    GROUP BY flight_num) as tickets

    WHERE numTickets < num_seats or numTickets is NULL
    """

    cursor.execute(query, (depart_from, arrive_to, depart_date))
    flights = cursor.fetchall()

    if not return_date:
        return render_template('/customer/tickets.html', today=datetime.date.today(), airlines = getAirlines(conn),
                           airports=getAirports(conn), flights=flights, search=False)
    else:
        return render_template('/customer/tickets.html', today=datetime.date.today(), airlines = getAirlines(conn),
                           airports=getAirports(conn), flights=flights, search=False, depart_from=depart_from, arrive_to=arrive_to, return_date=return_date)

@app.route('/purchaseTwoWay', methods=['GET', 'POST'])
def purchaseTwoWay():
    cursor = conn.cursor()

    first_flight = request.form['first_flight']
    first_flight_airline = request.form['first_flight_airline']
    first_cost = request.form['first_cost']
    depart_from = request.form['departure_airport']
    arrive_to = request.form['arrival_airport']
    depart_date = str(request.form['departure_date'])

    query = """
    SELECT airline_name, flight_num, depart_city, depart_date, depart_time, arrival_city, arrival_date, arrival_time,
        IF (num_seats * 0.8 <= numTickets, base_price * 1.25, base_price) as price
    FROM

    (SELECT airline_name, airplane_id, flight_num, depart_city, depart_date, depart_time, arrival_city, arrival_date, arrival_time, base_price, status, num_seats
    FROM
        (SELECT airline_name, airplane_id, T1.flight_num, T1.airport_city as depart_city, depart_date, depart_time, T2.airport_city as arrival_city, arrival_date, arrival_time, base_price, status
        FROM
            (SELECT airline_name, airplane_id, flight_num, airport_city, depart_date, depart_time, base_price, status
            FROM flight, airport WHERE depart_from = airport_code) as T1,
            (SELECT flight_num, airport_city, arrival_date, arrival_time
            FROM flight, airport where arrive_at = airport_code) as T2
        WHERE T1.flight_num = T2.flight_num and T1.airport_city = %s and T2.airport_city = %s and T1.depart_date = %s ORDER BY depart_date) as flights natural join airplane) as flights2

    natural left outer join

    (SELECT flight_num, COUNT(flight_num) as numTickets
    FROM ticket
    GROUP BY flight_num) as tickets

    WHERE numTickets < num_seats or numTickets is NULL
    """

    cursor.execute(query, (depart_from, arrive_to, depart_date))
    flights = cursor.fetchall()

    return render_template('/customer/tickets.html', today=datetime.date.today(), airlines = getAirlines(conn),
                           airports=getAirports(conn), flights=flights, first_flight = first_flight,
                           first_flight_airline=first_flight_airline, first_cost = first_cost, search=False)

@app.route('/purchaseOneWay', methods=['GET', 'POST'])
def purchaseOneWay():
    cursor = conn.cursor()
    first_flight_num = request.form['first_flight']
    if first_flight_num == "-1" : twoTickets = False
    else: twoTickets = True

    query = "SELECT MAX(ticket_id) as maxTicket FROM ticket"
    cursor.execute(query)
    tickets = cursor.fetchone()

    if tickets: numTickets = tickets['maxTicket']
    else: numTickets = 0

    return render_template('/customer/purchase.html', twoTickets=twoTickets, flight_info=request.form,
                           ticketOne = numTickets + 1, ticketTwo = numTickets + 2)

@app.route('/purchaseTickets', methods=['GET', 'POST'])
def purchaseTickets():
    email = session['username']
    cursor = conn.cursor()

    first_name = request.form['first_name']
    last_name = request.form['last_name']
    date_of_birth = request.form['date_of_birth']

    card_number = request.form['card_number']
    card_name = request.form['card_name']
    card_type = request.form['card_type']
    expiration = request.form['expiration']

    first_flight = request.form['first_flight']
    ticketOne = request.form['ticketOne']
    ticketTwo = request.form['ticketTwo']

    query = "insert into ticket values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"

    if first_flight != '-1':
        first_flight_airline = request.form['first_flight_airline']
        first_cost = request.form['first_cost']
        airplane_id, depart_date, depart_time = moreFlightInfo(conn, first_flight_airline, first_flight)

        cursor.execute(query, (first_flight_airline, airplane_id, first_flight, ticketOne, depart_date, depart_time,
                               card_type, card_number, card_name, expiration, first_name,
                               last_name, email, date_of_birth, datetime.date.today(), datetime.datetime.now().time(), first_cost))
        conn.commit()

    flight_num = request.form['flight_num']
    airline = request.form['airline']
    cost = request.form['cost']
    airplane_id, depart_date, depart_time = moreFlightInfo(conn, airline, flight_num)

    if first_flight != '-1':
        cursor.execute(query, (airline, airplane_id, flight_num, ticketTwo, depart_date, depart_time,
                               card_type, card_number, card_name, expiration, first_name,
                               last_name, email, date_of_birth, datetime.date.today(), datetime.datetime.now().time(), cost))
    else:
        cursor.execute(query, (airline, airplane_id, flight_num, ticketOne, depart_date, depart_time,
                               card_type, card_number, card_name, expiration, first_name,
                               last_name, email, date_of_birth, datetime.date.today(), datetime.datetime.now().time(), cost))

    conn.commit()
    return redirect(url_for("custHome"))

@app.route('/cancelFlight', methods=['GET', 'POST'])
def cancelFlight():
    cursor = conn.cursor()

    ticket_id = request.form['ticket_id']
    query = "delete from ticket where ticket_id = %s"
    cursor.execute(query, ticket_id)
    conn.commit()

    return redirect(url_for("custHome"))

@app.route('/getReviewPage', methods=['GET', 'POST'])
def getReviewPage():
    cursor = conn.cursor()
    ticket_id = request.form['ticket_id']

    query = "SELECT rating, comments FROM review WHERE ticket_id = %s"
    cursor.execute(query, ticket_id)
    review = cursor.fetchone()

    return render_template("/customer/review.html", ticket_id=ticket_id, review=review)

@app.route('/reviewFlight', methods=['GET', 'POST'])
def reviewFlight():
    cursor = conn.cursor()
    ticket_id = request.form['ticket_id']

    query = "SELECT rating, comments FROM review WHERE ticket_id = %s"
    cursor.execute(query, ticket_id)
    review = cursor.fetchone()

    rating = request.form['rating']
    comments = request.form['comments']

    if review:
        query = "update review set rating=%s, comments=%s where ticket_id = %s"
        cursor.execute(query, (rating, comments, ticket_id))
        conn.commit()
    else:
        email = session['username']
        airline_name, airplane_id, flight_num, depart_date, depart_time = flightInfoForReview(conn, ticket_id)

        query = "insert into review values (%s, %s, %s, %s, %s, %s, %s, %s, %s)"
        cursor.execute(query, (airline_name, airplane_id, flight_num, rating, depart_date, depart_time, comments, email, ticket_id))
        conn.commit()

    return redirect(url_for("custHome"))

MONTHS = {1: "January", 2: "Febuary", 3: "March", 4: "April", 5: "May", 6: "June",
               7: "July", 8: "August", 9: "Sepetember", 10: "October", 11: "November", 12: "December"}

@app.route('/getSpending')
def getSpending():
    cursor = conn.cursor()
    email = session['username']

    query = "SELECT cost, purchase_date FROM ticket WHERE cust_email=%s ORDER BY purchase_date DESC"
    cursor.execute(query, email)
    purchases = cursor.fetchall()

    today = datetime.datetime.today()
    last_year = datetime.datetime.date(today - relativedelta(years=1))
    six_month_date = datetime.datetime.date(today - relativedelta(months=6))
    purchase_months = []
    purchase_amounts = {}

    if purchases:
        total = 0

        six_month = (today - relativedelta(months=5)).month

        for _ in range(6):
            purchase_months.append(MONTHS[six_month])
            purchase_amounts[six_month] = 0
            six_month += 1
            if six_month == 13:
                six_month = 1

        for purchase in purchases:
            if purchase['purchase_date'] >= last_year:
                total += purchase['cost']
            if purchase['purchase_date'] >= six_month_date and purchase['purchase_date'].month in purchase_amounts:
                purchase_amounts[purchase['purchase_date'].month] += purchase['cost']
    else:
        total = 0

    return render_template('/customer/spending.html', total=total,
                           purchase_months = purchase_months, purchase_amounts=list(purchase_amounts.values()),
                           start_range=last_year, end_range=datetime.datetime.date(today), search=True)

@app.route('/getSpendingRange', methods=['GET', 'POST'])
def getSpendingRange(): # unable to span multiple years
    cursor = conn.cursor()
    email = session['username']

    query = "SELECT cost, purchase_date FROM ticket WHERE cust_email=%s ORDER BY purchase_date DESC"
    cursor.execute(query, email)
    purchases = cursor.fetchall()

    start_range = datetime.datetime.strptime(request.form['start_range'], '%Y-%m-%d')
    end_range = datetime.datetime.strptime(request.form['end_range'], '%Y-%m-%d')

    start_range = datetime.datetime.date(start_range)
    end_range = datetime.datetime.date(end_range)

    start_month = start_range.month
    date_range = relativedelta(end_range, start_range).months + 1

    purchase_months = []
    purchase_amounts = {}

    if purchases:
        total = 0
        for _ in range(date_range):
            purchase_months.append(MONTHS[start_month])
            purchase_amounts[start_month] = 0
            start_month += 1
            if start_month == 13:
                start_month = 1

        for purchase in purchases:
            print(purchase['purchase_date'])
            if start_range <= purchase['purchase_date'] <= end_range:
                total += purchase['cost']
            if start_range <= purchase['purchase_date'] <= end_range and purchase['purchase_date'].month in purchase_amounts:
                purchase_amounts[purchase['purchase_date'].month] += purchase['cost']
    else:
        total = 0

    return render_template('/customer/spending.html', total=total,
                           purchase_months=purchase_months, purchase_amounts=list(purchase_amounts.values()),
                           start_range=start_range, end_range=end_range, search=False)

app.secret_key = 'derek the goat'
if __name__ == "__main__":
    app.run('127.0.0.1', 4000, debug=True)

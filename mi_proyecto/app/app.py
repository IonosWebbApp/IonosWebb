from flask import Flask, render_template, request, redirect, url_for, send_file, flash
import os
from werkzeug.utils import secure_filename
import pandas as pd
import zipfile
import io
from datetime import datetime
import plotly.express as px
import numpy as np
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from users import db, User, UploadedFile

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
app.config['UPLOAD_FOLDER'] = 'uploads/'
app.config['STATIC_FOLDER'] = 'static/'
ALLOWED_EXTENSIONS = {'csv'}

db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Crear carpetas si no existen
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])
if not os.path.exists(app.config['STATIC_FOLDER']):
    os.makedirs(app.config['STATIC_FOLDER'])

# Funciones de ayuda
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def format_currency(value):
    if value is None:
        return ""
    if value < 0:
        return "({:,.2f})".format(abs(value))
    return "{:,.2f}".format(value)

app.jinja_env.filters['format_currency'] = format_currency

def absolute_value(value):
    return abs(value)

app.jinja_env.filters['abs'] = absolute_value

# Ruta para la página principal
@app.route('/')
def index():
    return render_template('index.html')

# Ruta para el registro de usuarios
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        existing_user = User.query.filter_by(username=username).first()
        if existing_user is None:
            user = User(username=username)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            flash('User successfully registered.')
            return redirect(url_for('login'))
        else:
            flash('User already exists.')
    return render_template('register.html')

# Ruta para el login de usuarios
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            flash('Logged in successfully.')
            return redirect(url_for('index'))
        else:
            flash('Invalid username or password.')
    return render_template('login.html')

# Ruta para el logout de usuarios
@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out successfully.')
    return redirect(url_for('login'))

# Ruta para la administración de usuarios
@app.route('/admin')
@login_required
def admin():
    if current_user.role != 'admin':
        flash('Access denied.')
        return redirect(url_for('index'))
    users = User.query.all()
    return render_template('admin.html', users=users)

# Ruta para eliminar usuarios
@app.route('/delete_user/<int:user_id>', methods=['POST'])
@login_required
def delete_user(user_id):
    if current_user.role != 'admin':
        flash('Access denied.')
        return redirect(url_for('index'))
    user = User.query.get(user_id)
    if user:
        db.session.delete(user)
        db.session.commit()
        flash('User deleted successfully.')
    else:
        flash('User not found.')
    return redirect(url_for('admin'))

# Ruta para ver los archivos subidos
@app.route('/admin_files')
@login_required
def admin_files():
    if current_user.role != 'admin':
        flash('Access denied.')
        return redirect(url_for('index'))
    files = UploadedFile.query.all()
    return render_template('admin_files.html', files=files)

# Función para procesar el archivo CSV
def process_csv(file_path):
    try:
        data = pd.read_csv(file_path)
        data = data.replace({np.nan: None})
    except Exception as e:
        return None, str(e), 0, 0, {}, {}, {}, {}, {}, [], {}, {}, {}

    dates = []
    num_equity_actions = 0
    num_equity_options = 0
    symbol_counts = {}
    symbol_total_stock = {}
    symbol_total_income = {}
    symbol_total_sum = {}
    symbol_dividends = {}
    symbol_dates = {}
    underlying_symbol_dates = {}
    
    for column in data.columns:
        if data[column].dtype == 'object':
            try:
                date_column = pd.to_datetime(data[column], errors='coerce')
                date_column = date_column.dropna()
                if not date_column.empty:
                    sorted_dates = sorted(date_column)
                    first_date = sorted_dates[0]
                    last_date = sorted_dates[-1]
                    total_days = (last_date - first_date).days
                    if total_days < 0:
                        total_days = abs(total_days)
                    dates.append(first_date)
                    dates.append(last_date)
                    dates.append(total_days)
            except ValueError:
                pass
                
    if 'Sub Type' in data.columns and 'Symbol' in data.columns and 'Value' in data.columns:
        dividends_data = data[data['Sub Type'] == 'Dividend']
        for _, row in dividends_data.iterrows():
            symbol = row['Symbol']
            value = float(row['Value']) if row['Value'] is not None else 0.0
            if symbol in symbol_dividends:
                symbol_dividends[symbol] += value
            else:
                symbol_dividends[symbol] = value

    if 'Instrument Type' in data.columns:
        equity_data = data[(data['Instrument Type'] == 'Equity') & (pd.to_datetime(data['Date']) >= dates[0]) & (pd.to_datetime(data['Date']) <= dates[1])]
        num_equity_actions = equity_data.shape[0]
        equity_option_data = data[(data['Instrument Type'] == 'Equity Option') & (pd.to_datetime(data['Date']) >= dates[0]) & (pd.to_datetime(data['Date']) <= dates[1])]
        num_equity_options = equity_option_data.shape[0]
        for _, row in equity_data.iterrows():
            symbol = row['Symbol']
            date = row['Date']
            try:
                quantity = float(row['Quantity']) if row['Quantity'] is not None else 0.0
                average_price = float(row['Average Price']) if row['Average Price'] is not None else 0.0
                income = quantity * average_price
                if symbol in symbol_counts:
                    symbol_counts[symbol] += 1
                    if symbol in symbol_total_stock:
                        symbol_total_stock[symbol] += quantity
                    else:
                        symbol_total_stock[symbol] = quantity
                    if symbol in symbol_total_income:
                        symbol_total_income[symbol] += income
                    else:
                        symbol_total_income[symbol] = income
                    symbol_total_sum[symbol] += (quantity + income)
                else:
                    symbol_counts[symbol] = 1
                    symbol_total_stock[symbol] = quantity
                    symbol_total_income[symbol] = income
                    symbol_total_sum[symbol] = quantity + income
                if symbol not in symbol_dates:
                    symbol_dates[symbol] = date
            except ValueError:
                pass

    for symbol in symbol_counts:
        buy_to_open = data.loc[(data['Symbol'] == symbol) & (data['Sub Type'] == 'Buy to Open'), 'Quantity'].sum()
        sell_to_close = data.loc[(data['Symbol'] == symbol) & (data['Sub Type'] == 'Sell to Close'), 'Quantity'].sum()
        symbol_total_stock[symbol] = buy_to_open - sell_to_close
    
    total_income_sum = sum(symbol_total_income.values())
    total_dividends_sum = sum(symbol_dividends.values())
    
    underlying_symbols = data['Underlying Symbol'].dropna().unique().tolist()
    underlying_symbol_counts = data['Underlying Symbol'].value_counts().to_dict()
    
    data['Value'] = pd.to_numeric(data['Value'], errors='coerce').fillna(0)
    underlying_symbol_values = {symbol: data.loc[(data['Underlying Symbol'] == symbol) & (data['Value'] != 0), 'Value'].sum() for symbol in underlying_symbols}
    
    data['Quantity'] = pd.to_numeric(data['Quantity'], errors='coerce').fillna(0)
    underlying_symbol_quantities = {symbol: int(data.loc[(data['Underlying Symbol'] == symbol) & (data['Quantity'] != 0), 'Quantity'].sum()) for symbol in underlying_symbols}
    
    underlying_symbol_global_values = {symbol: underlying_symbol_values[symbol] + underlying_symbol_quantities[symbol] for symbol in underlying_symbols}
    
    total_dollar_values = {}
    for symbol in underlying_symbols:
        mask = (data['Underlying Symbol'] == symbol) & (data['Instrument Type'] != 'Equity')
        total_dollar_values[symbol] = data.loc[mask, 'Value'].sum()
        if symbol not in underlying_symbol_dates:
            underlying_symbol_dates[symbol] = data.loc[mask, 'Date'].iloc[0]

    total_value_sum = sum(value for value in underlying_symbol_values.values() if value != 0)
    total_quantity_sum = sum(quantity for quantity in underlying_symbol_quantities.values() if quantity != 0)

    total_global_value_sum = sum(underlying_symbol_global_values.values())
    total_total_dollar_sum = sum(total_dollar_values.values())
    
    total_deposits = data.loc[data['Sub Type'] == 'Deposit', 'Value'].sum()

    acciones_en_proceso = -sum([symbol_total_income[symbol] for symbol in symbol_total_stock if symbol_total_stock[symbol] != 0])

    total_dividends = sum(symbol_dividends.values())

    pl_acciones = sum([symbol_total_income[symbol] for symbol in symbol_total_stock if symbol_total_stock[symbol] == 0])

    pl_values = {}
    for symbol in underlying_symbols:
        mask = (data['Root Symbol'] == symbol) & (data['Root Symbol'] != 0)
        pl_values[symbol] = (data.loc[mask, 'Value'] * data.loc[mask, 'Quantity']).sum()
    
    total_pl_2_sum = sum(pl_values.values())

    total_opciones_en_proceso = sum(total_dollar_values.values())

    total_pl_opciones = sum(pl_values.values())

    efectivo = acciones_en_proceso + total_dividends + pl_acciones + total_opciones_en_proceso + total_pl_opciones - total_deposits

    resumen_financiero = {
        "Acciones en Proceso": abs(acciones_en_proceso),
        "Total Dividendos": abs(total_dividends),
        "P/L Acciones": abs(pl_acciones),
        "Opciones En Proceso": abs(total_opciones_en_proceso),
        "P/L Opciones": abs(total_pl_opciones),
        "Efectivo": abs(efectivo)
    }

    pie_chart_path_resumen = os.path.join(app.config['STATIC_FOLDER'], 'resumen_financiero_pie_chart.html')
    create_pie_chart(resumen_financiero, pie_chart_path_resumen, title="Resumen Financiero")
    
    return data, dates, num_equity_actions, num_equity_options, symbol_counts, symbol_total_stock, symbol_total_income, symbol_total_sum, symbol_dividends, total_income_sum, total_dividends_sum, symbol_dates, underlying_symbols, underlying_symbol_counts, underlying_symbol_values, underlying_symbol_quantities, underlying_symbol_global_values, total_value_sum, total_quantity_sum, total_dollar_values, total_global_value_sum, total_total_dollar_sum, total_deposits, acciones_en_proceso, total_dividends, pl_acciones, pl_values, total_pl_2_sum, total_opciones_en_proceso, total_pl_opciones, efectivo, underlying_symbol_dates

def create_pie_chart(data, output_path, title=""):
    labels = list(data.keys())
    sizes = [abs(value) for value in data.values()]
    num_colors = len(labels)
    colors = ['rgba({0},{0},{0},0.6)'.format(int(255 * (i / num_colors))) for i in range(num_colors)]
    
    fig = px.pie(values=sizes, names=labels, title=title, hole=0.3)
    fig.update_traces(marker=dict(colors=colors), textinfo='percent+label', pull=[0.1 if v == max(sizes) else 0 for v in sizes])
    fig.write_html(output_path)

def get_equity_symbols(data):
    if 'Symbol' in data.columns and 'Instrument Type' in data.columns:
        equity_symbols = data[data['Instrument Type'] == 'Equity']['Symbol'].unique().tolist()
        return equity_symbols
    return []

# Ruta para la subida de archivos
@app.route('/upload', methods=['POST'])
@login_required
def upload_file():
    if 'file' not in request.files:
        return redirect(request.url)
    file = request.files['file']
    if file.filename == '':
        return redirect(request.url)
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        
        # Guardar registro del archivo subido
        uploaded_file = UploadedFile(filename=filename, user_id=current_user.id, upload_date=datetime.utcnow())
        db.session.add(uploaded_file)
        db.session.commit()
        
        return redirect(url_for('uploaded_file', filename=filename))
    return redirect(request.url)

# Ruta para mostrar los resultados del archivo subido
@app.route('/uploads/<filename>')
@login_required
def uploaded_file(filename):
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    data, dates, num_equity_actions, num_equity_options, symbol_counts, symbol_total_stock, symbol_total_income, symbol_total_sum, symbol_dividends, total_income_sum, total_dividends_sum, symbol_dates, underlying_symbols, underlying_symbol_counts, underlying_symbol_values, underlying_symbol_quantities, underlying_symbol_global_values, total_value_sum, total_quantity_sum, total_dollar_values, total_global_value_sum, total_total_dollar_sum, total_deposits, acciones_en_proceso, total_dividends, pl_acciones, pl_values, total_pl_2_sum, total_opciones_en_proceso, total_pl_opciones, efectivo, underlying_symbol_dates = process_csv(file_path)
    if data is None:
        return f"Error processing file: {dates}"
    equity_symbols = get_equity_symbols(data)
    for i in range(2):
        dates[i] = dates[i].strftime('%Y-%m-%d')
    
    pie_chart_path = os.path.join(app.config['STATIC_FOLDER'], 'dividends_pie_chart.html')
    create_pie_chart(symbol_dividends, pie_chart_path, title="Distribution of Dividends by Symbol")

    return render_template('uploaded.html', filename=filename, dates=dates, num_equity_actions=num_equity_actions, num_equity_options=num_equity_options, symbol_counts=symbol_counts, symbol_total_stock=symbol_total_stock, symbol_total_income=symbol_total_income, symbol_total_sum=symbol_total_sum, equity_symbols=equity_symbols, symbol_dividends=symbol_dividends, pie_chart_url=url_for('static', filename='dividends_pie_chart.html'), total_income_sum=total_income_sum, total_dividends_sum=total_dividends_sum, symbol_dates=symbol_dates, underlying_symbols=underlying_symbols, underlying_symbol_counts=underlying_symbol_counts, underlying_symbol_values=underlying_symbol_values, underlying_symbol_quantities=underlying_symbol_quantities, underlying_symbol_global_values=underlying_symbol_global_values, total_value_sum=total_value_sum, total_quantity_sum=total_quantity_sum, total_dollar_values=total_dollar_values, total_global_value_sum=total_global_value_sum, total_total_dollar_sum=total_total_dollar_sum, total_deposits=total_deposits, acciones_en_proceso=acciones_en_proceso, total_dividends=total_dividends, pl_acciones=pl_acciones, pl_values=pl_values, total_pl_2_sum=total_pl_2_sum, total_opciones_en_proceso=total_opciones_en_proceso, total_pl_opciones=total_pl_opciones, efectivo=efectivo, pie_chart_url_resumen=url_for('static', filename='resumen_financiero_pie_chart.html'), underlying_symbol_dates=underlying_symbol_dates)

# Ruta para la descarga de archivos
@app.route('/download/<filename>')
@login_required
def download_csv(filename):
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    return send_file(file_path, as_attachment=True, download_name=filename)

if __name__ == "__main__":
    with app.app_context():
        db.create_all()

        # Crear usuario administrador por defecto si no existe
        admin_username = 'admin'
        admin_password = 'adminpassword'
        existing_admin = User.query.filter_by(username=admin_username).first()
        if existing_admin is None:
            admin_user = User(username=admin_username, role='admin')
            admin_user.set_password(admin_password)
            db.session.add(admin_user)
            db.session.commit()

    app.run(debug=True)

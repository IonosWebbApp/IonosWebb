# app.py

from flask import Flask, render_template, request, redirect, url_for, send_file
import os
from werkzeug.utils import secure_filename
import pandas as pd
import zipfile
import io
from datetime import datetime

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads/'
ALLOWED_EXTENSIONS = {'csv'}

# Crear carpetas si no existen
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])
if not os.path.exists('static'):
    os.makedirs('static')

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def process_csv(file_path):
    try:
        data = pd.read_csv(file_path)
    except Exception as e:
        return None, str(e), 0, 0, {}, {}, {}, {}, {}

    dates = []
    num_equity_actions = 0
    num_equity_options = 0
    symbol_counts = {}
    symbol_total_stock = {}
    symbol_total_income = {}
    symbol_total_sum = {}
    symbol_dividends = {}
    
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
                        total_days = abs(total_days)  # Tomar el valor absoluto si es negativo
                    dates.append(first_date)  # Añadir la primera fecha
                    dates.append(last_date)  # Añadir la última fecha
                    dates.append(total_days)  # Añadir el total de días transcurridos
            except ValueError:
                pass
                
    # Filtrar y sumar los valores de la columna "Value" que son "Dividend" por símbolo
    if 'Sub Type' in data.columns and 'Symbol' in data.columns and 'Value' in data.columns:
        dividends_data = data[data['Sub Type'] == 'Dividend']
        for _, row in dividends_data.iterrows():
            symbol = row['Symbol']
            value = float(row['Value'])
            if symbol in symbol_dividends:
                symbol_dividends[symbol] += value
            else:
                symbol_dividends[symbol] = value

    # Calcular el número de acciones del tipo "Equity" entre las fechas de "First Date" y "Last Date"
    if 'Instrument Type' in data.columns:
        equity_data = data[(data['Instrument Type'] == 'Equity') & (pd.to_datetime(data['Date']) >= dates[0]) & (pd.to_datetime(data['Date']) <= dates[1])]
        num_equity_actions = equity_data.shape[0]
        # Calcular el número de operaciones del tipo "Equity Option" entre las fechas de "First Date" y "Last Date"
        equity_option_data = data[(data['Instrument Type'] == 'Equity Option') & (pd.to_datetime(data['Date']) >= dates[0]) & (pd.to_datetime(data['Date']) <= dates[1])]
        num_equity_options = equity_option_data.shape[0]
        # Calcular el conteo de símbolos, el total de stock, los ingresos totales y la suma total para acciones de tipo "Equity"
        for _, row in equity_data.iterrows():
            symbol = row['Symbol']
            try:
                quantity = float(row['Quantity'])
                average_price = float(row['Average Price'])
                income = quantity * average_price
                if symbol in symbol_counts:
                    symbol_counts[symbol] += 1
                    symbol_total_stock[symbol] += quantity
                    symbol_total_income[symbol] += income
                    symbol_total_sum[symbol] += (quantity + income)
                else:
                    symbol_counts[symbol] = 1
                    symbol_total_stock[symbol] = quantity
                    symbol_total_income[symbol] = income
                    symbol_total_sum[symbol] = quantity + income
            except ValueError:
                pass
    return data, dates, num_equity_actions, num_equity_options, symbol_counts, symbol_total_stock, symbol_total_income, symbol_total_sum, symbol_dividends

def get_equity_symbols(data):
    if 'Symbol' in data.columns and 'Instrument Type' in data.columns:
        equity_symbols = data[data['Instrument Type'] == 'Equity']['Symbol'].unique().tolist()
        return equity_symbols
    return []

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
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
        return redirect(url_for('uploaded_file', filename=filename))
    return redirect(request.url)

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    data, dates, num_equity_actions, num_equity_options, symbol_counts, symbol_total_stock, symbol_total_income, symbol_total_sum, symbol_dividends = process_csv(file_path)
    if data is None:
        return f"Error processing file: {dates}"  # 'dates' contains the error message in este caso
    equity_symbols = get_equity_symbols(data)
    # Formatear las fechas en el formato deseado
    for i in range(2):
        dates[i] = dates[i].strftime('%Y-%m-%d')
    return render_template('uploaded.html', filename=filename, dates=dates, num_equity_actions=num_equity_actions, num_equity_options=num_equity_options, symbol_counts=symbol_counts, symbol_total_stock=symbol_total_stock, symbol_total_income=symbol_total_income, symbol_total_sum=symbol_total_sum, equity_symbols=equity_symbols, symbol_dividends=symbol_dividends)

@app.route('/download/<filename>')
def download_csv(filename):
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    return send_file(file_path, as_attachment=True, download_name=filename)

if __name__ == "__main__":
    app.run(debug=True)

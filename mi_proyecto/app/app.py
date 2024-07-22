from flask import Flask, render_template, request, redirect, url_for, send_file
import os
from werkzeug.utils import secure_filename
import pandas as pd
import zipfile
import io
from datetime import datetime
import plotly.express as px
import numpy as np

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads/'
app.config['STATIC_FOLDER'] = 'static/'
ALLOWED_EXTENSIONS = {'csv'}

# Crear carpetas si no existen
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])
if not os.path.exists(app.config['STATIC_FOLDER']):
    os.makedirs(app.config['STATIC_FOLDER'])

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def format_currency(value):
    """Formatea un valor numérico como moneda o cantidad."""
    if value is None:
        return ""
    if value < 0:
        return "({:,.2f})".format(abs(value))
    return "{:,.2f}".format(value)

app.jinja_env.filters['format_currency'] = format_currency

def absolute_value(value):
    """Devuelve el valor absoluto."""
    return abs(value)

app.jinja_env.filters['abs'] = absolute_value

def process_csv(file_path):
    try:
        data = pd.read_csv(file_path)
        data = data.replace({np.nan: None})  # Reemplazar los valores "nan" por None
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
            value = float(row['Value']) if row['Value'] is not None else 0.0  # No convertir a valor absoluto aquí
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
                quantity = float(row['Quantity']) if row['Quantity'] is not None else 0.0
                average_price = float(row['Average Price']) if row['Average Price'] is not None else 0.0
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
    
    total_income_sum = sum(symbol_total_income.values())
    total_dividends_sum = sum(symbol_dividends.values())
    
    # Obtener los valores únicos de la columna "Underlying Symbol" y sus recuentos
    underlying_symbols = data['Underlying Symbol'].dropna().unique().tolist()
    underlying_symbol_counts = data['Underlying Symbol'].value_counts().to_dict()
    
    # Calcular la suma de "Value" para cada "Underlying Symbol" considerando solo valores diferentes de cero
    data['Value'] = pd.to_numeric(data['Value'], errors='coerce').fillna(0)
    underlying_symbol_values = {symbol: data.loc[(data['Underlying Symbol'] == symbol) & (data['Value'] != 0), 'Value'].sum() for symbol in underlying_symbols}
    
    # Calcular la suma de "Quantity" para cada "Underlying Symbol" considerando solo valores diferentes de cero
    data['Quantity'] = pd.to_numeric(data['Quantity'], errors='coerce').fillna(0)
    underlying_symbol_quantities = {symbol: int(data.loc[(data['Underlying Symbol'] == symbol) & (data['Quantity'] != 0), 'Quantity'].sum()) for symbol in underlying_symbols}
    
    # Calcular la suma de "Valor Global" como la suma de "Valor Total" y "Cantidad Total"
    underlying_symbol_global_values = {symbol: underlying_symbol_values[symbol] + underlying_symbol_quantities[symbol] for symbol in underlying_symbols}
    
    # Calcular "Total $" para cada "Underlying Symbol" donde "Instrument Type" es diferente de "Equity"
    total_dollar_values = {symbol: data.loc[(data['Underlying Symbol'] == symbol) & (data['Instrument Type'] != 'Equity'), 'Value'].sum() for symbol in underlying_symbols}
    
    # Calcular la suma total de "Valor Total" y "Cantidad Total" considerando solo valores diferentes de cero
    total_value_sum = sum(value for value in underlying_symbol_values.values() if value != 0)
    total_quantity_sum = sum(quantity for quantity in underlying_symbol_quantities.values() if quantity != 0)

    # Calcular la suma total de "Valor Global" y "Total $"
    total_global_value_sum = sum(underlying_symbol_global_values.values())
    total_total_dollar_sum = sum(total_dollar_values.values())
    
    return data, dates, num_equity_actions, num_equity_options, symbol_counts, symbol_total_stock, symbol_total_income, symbol_total_sum, symbol_dividends, total_income_sum, total_dividends_sum, underlying_symbols, underlying_symbol_counts, underlying_symbol_values, underlying_symbol_quantities, underlying_symbol_global_values, total_value_sum, total_quantity_sum, total_dollar_values, total_global_value_sum, total_total_dollar_sum

def create_pie_chart(symbol_dividends, output_path):
    labels = list(symbol_dividends.keys())
    values = list(symbol_dividends.values())
    
    df = pd.DataFrame({
        'Símbolo': labels,
        'Dividendos': values
    })
    
    fig = px.pie(df, names='Símbolo', values='Dividendos', title='Distribución de Dividendos por Símbolo')
    fig.update_traces(textinfo='label+percent', marker=dict(colors=['#CCCCCC', '#B0B0B0', '#999999', '#808080', '#666666', '#4C4C4C', '#333333']))
    fig.update_layout(title_font_color='#333333', legend_title_font_color='#333333')
    fig.write_html(output_path)

def create_bar_chart(symbol_total_income, output_path):
    labels = list(symbol_total_income.keys())
    values = list(symbol_total_income.values())
    
    df = pd.DataFrame({
        'Símbolo': labels,
        'Total Income': values
    })
    
    fig = px.bar(df, x='Símbolo', y='Total Income', title='Total Income by Symbol', color='Total Income', color_continuous_scale='gray')
    fig.update_layout(xaxis_title='Símbolo', yaxis_title='Total Income', xaxis_title_font_color='#333333', yaxis_title_font_color='#333333')
    fig.write_html(output_path)

def create_total_dollar_area_chart(total_dollar_values, output_path):
    labels = list(total_dollar_values.keys())
    values = list(total_dollar_values.values())
    
    df = pd.DataFrame({
        'Símbolo': labels,
        'Total $': values
    })
    
    fig = px.area(df, x='Símbolo', y='Total $', title='Total $ por Símbolo', color_discrete_sequence=['#CCCCCC'])
    fig.update_layout(xaxis_title='Símbolo', yaxis_title='Total $', xaxis_title_font_color='#333333', yaxis_title_font_color='#333333')
    fig.write_html(output_path)

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
        
        data, dates, num_equity_actions, num_equity_options, symbol_counts, symbol_total_stock, symbol_total_income, symbol_total_sum, symbol_dividends, total_income_sum, total_dividends_sum, underlying_symbols, underlying_symbol_counts, underlying_symbol_values, underlying_symbol_quantities, underlying_symbol_global_values, total_value_sum, total_quantity_sum, total_dollar_values, total_global_value_sum, total_total_dollar_sum = process_csv(file_path)
        
        if data is None:
            return f"Error processing file: {dates}"
        
        # Crear el gráfico de pastel de distribución de dividendos por símbolo
        pie_chart_path = os.path.join(app.config['STATIC_FOLDER'], 'pie_chart.html')
        create_pie_chart(symbol_dividends, pie_chart_path)
        
        # Crear el gráfico de barras de ingresos totales por símbolo
        bar_chart_path = os.path.join(app.config['STATIC_FOLDER'], 'bar_chart.html')
        create_bar_chart(symbol_total_income, bar_chart_path)
        
        # Crear el gráfico de área de Total $ por símbolo
        total_dollar_area_chart_path = os.path.join(app.config['STATIC_FOLDER'], 'total_dollar_area_chart.html')
        create_total_dollar_area_chart(total_dollar_values, total_dollar_area_chart_path)
        
        return render_template('uploaded.html', 
                               filename=filename, 
                               dates=dates, 
                               num_equity_actions=num_equity_actions, 
                               num_equity_options=num_equity_options,
                               symbol_counts=symbol_counts,
                               symbol_total_stock=symbol_total_stock,
                               symbol_total_income=symbol_total_income,
                               symbol_total_sum=symbol_total_sum,
                               symbol_dividends=symbol_dividends,
                               total_income_sum=total_income_sum,
                               total_dividends_sum=total_dividends_sum,
                               pie_chart_url=url_for('static', filename='pie_chart.html'),
                               bar_chart_url=url_for('static', filename='bar_chart.html'),
                               total_dollar_area_chart_url=url_for('static', filename='total_dollar_area_chart.html'),
                               underlying_symbols=underlying_symbols,
                               underlying_symbol_counts=underlying_symbol_counts,
                               underlying_symbol_values=underlying_symbol_values,
                               underlying_symbol_quantities=underlying_symbol_quantities,
                               underlying_symbol_global_values=underlying_symbol_global_values,
                               total_value_sum=total_value_sum,
                               total_quantity_sum=total_quantity_sum,
                               total_dollar_values=total_dollar_values,
                               total_global_value_sum=total_global_value_sum,
                               total_total_dollar_sum=total_total_dollar_sum)
    return redirect(request.url)

@app.route('/download/<filename>')
def download_csv(filename):
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if os.path.exists(file_path):
        return send_file(file_path, as_attachment=True)
    return "File not found", 404

if __name__ == '__main__':
    app.run(debug=True)
from flask import Flask, render_template, request, redirect, url_for, send_file
import os
from werkzeug.utils import secure_filename
import pandas as pd
import plotly.graph_objs as go
import zipfile
import io

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads/'
app.config['GRAPH_FOLDER'] = 'static/'
ALLOWED_EXTENSIONS = {'csv'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

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
        data, descriptions = process_csv(file_path)
        generate_graphs(data, filename, descriptions)
        return redirect(url_for('uploaded_file', filename=filename))
    return redirect(request.url)

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    graph_files = []
    descriptions = []
    base_filename = 'graph_' + filename[:-4]
    for file in os.listdir(app.config['GRAPH_FOLDER']):
        if file.startswith(base_filename):
            graph_files.append(url_for('static', filename=file))
            column_name = file.split('_')[-1][:-5]
            descriptions.append(f"Histogram of the column '{column_name}' showing the distribution of values.")
    return render_template('uploaded.html', filename=filename, graph_files=graph_files, descriptions=descriptions)

@app.route('/download/<filename>')
def download_graphs(filename):
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w') as zf:
        for file in os.listdir(app.config['GRAPH_FOLDER']):
            if file.startswith('graph_' + filename[:-4]):
                zf.write(os.path.join(app.config['GRAPH_FOLDER'], file), file)
    zip_buffer.seek(0)
    return send_file(zip_buffer, as_attachment=True, download_name=f"graphs_{filename[:-4]}.zip")

def process_csv(file_path):
    data = pd.read_csv(file_path)
    descriptions = {column: f"Histogram of the column '{column}' showing the distribution of values." for column in data.columns}
    return data, descriptions

def generate_graphs(data, filename, descriptions):
    generated_graphs = set()  # Conjunto para almacenar las columnas ya representadas en un gráfico

    for column in data.columns:
        # Verificar si los datos de la columna ya se han representado en otro gráfico
        if tuple(data[column].to_list()) in generated_graphs:
            continue

        # Si no se ha representado antes, generar el gráfico y agregar la columna al conjunto de datos generados
        trace = go.Histogram(x=data[column], name=column)
        layout = go.Layout(title=f'Histogram of {column}', xaxis=dict(title='Value'), yaxis=dict(title='Frequency'))
        fig = go.Figure(data=[trace], layout=layout)
        fig.write_html(os.path.join(app.config['GRAPH_FOLDER'], f"graph_{filename[:-4]}_{column}.html"))

        generated_graphs.add(tuple(data[column].to_list()))  # Agregar la lista de datos al conjunto de datos generados

if __name__ == "__main__":
    app.run(debug=True)

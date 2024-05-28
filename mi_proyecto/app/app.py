from flask import Flask, render_template, request, redirect, url_for
import os
from werkzeug.utils import secure_filename
import pandas as pd
import plotly.graph_objs as go

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads/'
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
        data = process_csv(file_path)
        generate_graph(data, filename)
        return redirect(url_for('uploaded_file', filename=filename))
    return redirect(request.url)

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    graph_files = []
    for file in os.listdir('static'):
        if file.startswith('graph_' + filename[:-4]):
            graph_files.append(url_for('static', filename=file))
    return render_template('uploaded.html', filename=filename, graph_files=graph_files)

def process_csv(file_path):
    data = pd.read_csv(file_path)
    return data

def generate_graph(data, filename):
    for column in data.columns:
        trace = go.Histogram(x=data[column], name=column)
        layout = go.Layout(title=f'Histograma de {column}', xaxis=dict(title='Valor'), yaxis=dict(title='Frecuencia'))
        fig = go.Figure(data=[trace], layout=layout)
        fig.write_html(f"static/graph_{filename[:-4]}_{column}.html")  # Guardar el gráfico como HTML

if __name__ == "__main__":
    app.run(debug=True)

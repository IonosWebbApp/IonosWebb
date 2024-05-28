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
    graph_url = url_for('static', filename='graph_' + filename[:-4] + '.html')
    return render_template('uploaded.html', filename=filename, graph_url=graph_url)

def process_csv(file_path):
    data = pd.read_csv(file_path)
    # Aquí podrías realizar más procesamiento de datos si es necesario
    return data

def generate_graph(data, filename):
    plot_data = []
    for column in data.columns:
        trace = go.Histogram(x=data[column], name=column)
        plot_data.append(trace)
    
    layout = go.Layout(title='Histograma', xaxis=dict(title='Valor'), yaxis=dict(title='Frecuencia'))
    fig = go.Figure(data=plot_data, layout=layout)
    fig.write_html("static/graph_" + filename[:-4] + ".html")  # Guardar el gráfico como HTML

if __name__ == "__main__":
    app.run(debug=True)

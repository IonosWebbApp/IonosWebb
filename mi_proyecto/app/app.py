from flask import Flask, render_template, request, redirect, url_for
import os
from werkzeug.utils import secure_filename
import pandas as pd
import matplotlib.pyplot as plt

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads/'
ALLOWED_EXTENSIONS = {'csv'}

# Helper function to check allowed file extensions
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Home route
@app.route('/')
def index():
    return render_template('index.html')

# Route for file upload
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
        # Process CSV and generate graph
        data = process_csv(file_path)
        generate_graph(data)
        return redirect(url_for('uploaded_file', filename=filename))
    return redirect(request.url)

# Route to display the uploaded file and generated graph
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return render_template('uploaded.html', filename=filename)

# Function to process CSV
def process_csv(file_path):
    data = pd.read_csv(file_path)
    # Perform data analysis here
    return data

# Function to generate graph
def generate_graph(data):
    plt.figure()
    data.plot(kind='bar')
    plt.savefig('static/graph.png')

if __name__ == "__main__":
    app.run(debug=True)

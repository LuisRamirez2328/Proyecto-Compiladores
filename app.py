from flask import Flask, render_template
import subprocess
import sys

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/run_qt')
def run_qt():
    # Ejecuta el archivo de la aplicación PyQt
    subprocess.Popen([sys.executable, 'qt_app.py'])
    return "Aplicación PyQt ejecutándose"

if __name__ == '__main__':
    app.run(debug=True)

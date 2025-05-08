from flask import Flask, render_template, request, send_file, jsonify
import pandas as pd
from fpdf import FPDF
import os
import joblib
import requests
from werkzeug.utils import secure_filename

# CONFIGURACIÓN
UPLOAD_FOLDER = 'uploads'
EXCEL_FILE = 'listado de categorias.xlsx'
MODELO_FILE = 'modelo_dano_entrenado.pkl'
ID_DRIVE_MODELO = '1AaBbCcDdEeFf1234567890'  # ← Reemplaza con el ID real de Google Drive

# Crear carpeta de uploads si no existe
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# INICIALIZAR FLASK
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# FUNCIÓN: Descargar modelo desde Google Drive si no existe
def descargar_modelo_drive(id_archivo, destino):
    if not os.path.exists(destino):
        print(f"Descargando {destino} desde Google Drive...")
        url = f"https://drive.google.com/uc?export=download&id={id_archivo}"
        r = requests.get(url)
        with open(destino, "wb") as f:
            f.write(r.content)
        print("✅ Descarga completada.")
    else:
        print(f"{destino} ya existe.")

# DESCARGA AUTOMÁTICA DEL MODELO
descargar_modelo_drive(ID_DRIVE_MODELO, MODELO_FILE)
modelo = joblib.load(MODELO_FILE)

# FUNCIONES DEL PROYECTO
def cargar_categorias():
    df = pd.read_excel(EXCEL_FILE, engine="openpyxl")
    return df["Categoria"].dropna().drop_duplicates().tolist()

def cargar_subcategorias(categoria):
    df = pd.read_excel(EXCEL_FILE, engine="openpyxl")
    return df[df["Categoria"] == categoria]["revestimiento"].dropna().drop_duplicates().tolist()

def predecir_valor(categoria, subcategoria, ubicacion, area):
    df = pd.DataFrame([{
        "categoria": categoria,
        "subcategoria": subcategoria,
        "ubicacion": ubicacion,
        "material": subcategoria,
        "area": area
    }])
    return round(modelo.predict(df)[0], 2)

# RUTA RAÍZ - evita página en blanco
@app.route('/')
def index():
    return "<h1>🚀 App desplegada correctamente en Render</h1><p>Formulario disponible en /formulario (si lo activas).</p>"

# CATEGORÍAS Y SUBCATEGORÍAS
@app.route('/obtener_categorias', methods=['GET'])
def obtener_categorias():
    return jsonify(cargar_categorias())

@app.route('/obtener_subcategorias', methods=['GET'])
def obtener_subcategorias():
    categoria = request.args.get('categoria')
    return jsonify(cargar_subcategorias(categoria))

# GENERACIÓN DE PDF
@app.route('/generar_pdf', methods=['POST'])
def generar_pdf():
    direccion = request.form.get("direccion")
    afectado = request.form.get("afectado")
    fecha = request.form.get("fecha")
    nro_caso = request.form.get("nro_caso")
    descripcion = request.form.get("descripcion")
    categorias = request.form.getlist("categoria[]")
    subcategorias = request.form.getlist("subcategoria[]")
    ubicaciones = request.form.getlist("ubicacion[]")
    cantidades = [float(c) for c in request.form.getlist("cantidad[]")]

    valores_estimados = []
    total_estimado = 0
    imagenes_por_dano = []

    for i in range(len(categorias)):
        valor = predecir_valor(categorias[i], subcategorias[i], ubicaciones[i], cantidades[i])
        valores_estimados.append(valor)
        total_estimado += valor
        imagenes = request.files.getlist(f"imagen_{i}[]")
        imagenes_por_dano.append(imagenes)

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(200, 10, "ACTA DE INSPECCIÓN", ln=True, align="C")
    pdf.set_font("Arial", "", 12)
    pdf.ln(8)
    pdf.cell(200, 10, f"N° Caso: {nro_caso}", ln=True)
    pdf.cell(200, 10, f"Fecha: {fecha}", ln=True)
    pdf.cell(200, 10, f"Dirección: {direccion}", ln=True)
    pdf.cell(200, 10, f"Nombre del Afectado: {afectado}", ln=True)
    pdf.ln(5)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, "Descripción de los Hechos:", ln=True)
    pdf.set_font("Arial", "", 12)
    pdf.multi_cell(0, 10, descripcion)
    pdf.ln(5)

    for i in range(len(categorias)):
        pdf.add_page()
        pdf.set_font("Arial", "B", 14)
        pdf.cell(0, 10, f"Daño #{i+1}", ln=True)
        pdf.set_font("Arial", "B", 12)
        pdf.cell(50, 10, "Categoría:", ln=False)
        pdf.set_font("Arial", "", 12)
        pdf.cell(0, 10, categorias[i], ln=True)
        pdf.set_font("Arial", "B", 12)
        pdf.cell(50, 10, "Revestimiento:", ln=False)
        pdf.set_font("Arial", "", 12)
        pdf.cell(0, 10, subcategorias[i], ln=True)
        pdf.set_font("Arial", "B", 12)
        pdf.cell(50, 10, "Ubicación:", ln=False)
        pdf.set_font("Arial", "", 12)
        pdf.cell(0, 10, ubicaciones[i], ln=True)
        pdf.set_font("Arial", "B", 12)
        pdf.cell(50, 10, "Área:", ln=False)
        pdf.set_font("Arial", "", 12)
        pdf.cell(0, 10, f"{cantidades[i]} m²", ln=True)
        pdf.set_font("Arial", "B", 12)
        pdf.cell(50, 10, "Valor Estimado:", ln=False)
        pdf.set_font("Arial", "", 12)
        pdf.cell(0, 10, f"{valores_estimados[i]} UF", ln=True)
        pdf.ln(5)

        fotos = imagenes_por_dano[i]
        for idx, imagen in enumerate(fotos):
            if imagen.filename:
                imagen_path = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(f"{i}_{idx}_{imagen.filename}"))
                imagen.save(imagen_path)
                try:
                    x = 10 + (idx % 2) * 100
                    y = pdf.get_y()
                    pdf.image(imagen_path, x=x, y=y, w=60, h=60)
                    if idx % 2 == 1:
                        pdf.ln(65)
                except:
                    continue
        if len(fotos) % 2 == 1:
            pdf.ln(65)

    pdf.add_page()
    pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 10, "Resumen de Daños", ln=True, align="C")
    pdf.set_font("Arial", "B", 10)
    pdf.cell(40, 8, "Categoría", 1)
    pdf.cell(40, 8, "Revestimiento", 1)
    pdf.cell(40, 8, "Ubicación", 1)
    pdf.cell(30, 8, "Área", 1)
    pdf.cell(40, 8, "Valor Estimado", 1)
    pdf.ln()

    pdf.set_font("Arial", "", 10)
    for i in range(len(categorias)):
        pdf.cell(40, 8, categorias[i], 1)
        pdf.cell(40, 8, subcategorias[i], 1)
        pdf.cell(40, 8, ubicaciones[i], 1)
        pdf.cell(30, 8, f"{cantidades[i]} m²", 1)
        pdf.cell(40, 8, f"{valores_estimados[i]} UF", 1)
        pdf.ln()

    pdf.set_font("Arial", "B", 12)
    pdf.cell(150, 10, "TOTAL ESTIMADO:", 1)
    pdf.cell(40, 10, f"{total_estimado:.2f} UF", 1)

    pdf_path = "inspeccion.pdf"
    pdf.output(pdf_path)
    return send_file(pdf_path, as_attachment=True)

# NO ES NECESARIO EN RENDER, PERO ÚTIL LOCALMENTE
if __name__ == '__main__':
    app.run(debug=True)

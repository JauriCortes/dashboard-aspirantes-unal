import sqlite3
import pandas as pd
from flask import Flask, render_template, request
from transformers import pipeline

app = Flask(__name__)

# --- Cargar estadísticas del hito 2 ---
df = pd.read_csv('aspirantes_unal.csv')
df = df[(df['ptotal'] > 100) & (df['ins_sede_nombre'] != 'Universidad') & (df['edad'] > 0)]

total_aspirantes = len(df)
total_admitidos = len(df[df['admitido'] == 'Sí'])
tasa_general = round(total_admitidos / total_aspirantes * 100, 1)

asp_periodo = pd.read_csv('stats_aspirantes_periodo.csv')
tasa_sede = pd.read_csv('stats_tasa_sede.csv', index_col=0)
puntaje_periodo = pd.read_csv('stats_puntaje_periodo.csv')
nacionalidades = pd.read_csv('stats_nacionalidades.csv', index_col=0)

# --- Modelos de IA ---
print('Cargando modelos de IA...')
clasificador = pipeline('sentiment-analysis',
                        model='pysentimiento/robertuito-sentiment-analysis')
ner = pipeline('ner', model='dslim/bert-base-NER',
               aggregation_strategy='first')
print('Modelos cargados.')

# --- SQLite para comentarios ---
def inicializar_db():
    conn = sqlite3.connect('dashboard.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS comentarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        texto TEXT,
        sentimiento TEXT,
        score REAL,
        entidades TEXT
    )''')
    conn.commit()
    conn.close()

inicializar_db()

def guardar_comentario(texto, sentimiento, score, entidades):
    conn = sqlite3.connect('dashboard.db')
    cursor = conn.cursor()
    cursor.execute('INSERT INTO comentarios (texto, sentimiento, score, entidades) VALUES (?, ?, ?, ?)',
                   (texto, sentimiento, score, entidades))
    conn.commit()
    conn.close()

def obtener_resumen():
    conn = sqlite3.connect('dashboard.db')
    cursor = conn.cursor()
    cursor.execute('SELECT sentimiento, COUNT(*) FROM comentarios GROUP BY sentimiento')
    resumen = dict(cursor.fetchall())
    cursor.execute('SELECT COUNT(*) FROM comentarios')
    total = cursor.fetchone()[0]
    conn.close()
    return total, resumen

def obtener_ultimo():
    conn = sqlite3.connect('dashboard.db')
    cursor = conn.cursor()
    cursor.execute('SELECT texto, sentimiento, score, entidades FROM comentarios ORDER BY id DESC LIMIT 1')
    ultimo = cursor.fetchone()
    conn.close()
    return ultimo

# --- Ruta principal ---
@app.route('/', methods=['GET', 'POST'])
def index():
    resultado = None

    if request.method == 'POST':
        texto = request.form.get('comentario', '').strip()
        if texto:
            sent = clasificador(texto)[0]
            entidades = ner(texto)
            ent_texto = ', '.join([f"{e['word']} ({e['entity_group']})" for e in entidades]) or 'Ninguna'

            guardar_comentario(texto, sent['label'], round(sent['score'], 4), ent_texto)

            resultado = {
                'texto': texto,
                'sentimiento': sent['label'],
                'score': round(sent['score'], 4),
                'entidades': ent_texto
            }

    total, resumen = obtener_resumen()

    return render_template('index.html',
                           total_aspirantes=total_aspirantes,
                           total_admitidos=total_admitidos,
                           tasa_general=tasa_general,
                           asp_periodo=asp_periodo.to_html(classes='tabla', index=False),
                           tasa_sede=tasa_sede.to_html(classes='tabla'),
                           puntaje_periodo=puntaje_periodo.to_html(classes='tabla', index=False),
                           nacionalidades=nacionalidades.to_html(classes='tabla'),
                           resultado=resultado,
                           total_comentarios=total,
                           resumen=resumen)

if __name__ == '__main__':
    app.run(debug=True)
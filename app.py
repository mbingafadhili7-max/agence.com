import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask import send_from_directory
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'votre_cle_secrete_ici'  # À changer en production
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024  # 2MB max

# Extensions autorisées pour les images
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    """Vérifie si le fichier a une extension autorisée"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def init_db():
    """Initialise la base de données avec les tables nécessaires"""
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    
    # Table des utilisateurs (admin)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        )
    ''')
    
    # Table des réservations
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reservations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom TEXT NOT NULL,
            email TEXT NOT NULL,
            telephone TEXT NOT NULL,
            destination TEXT NOT NULL,
            classe TEXT NOT NULL,
            date TEXT NOT NULL,
            statut TEXT DEFAULT 'en_attente',
            date_creation TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Table des commentaires
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS commentaires (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom TEXT NOT NULL,
            message TEXT NOT NULL,
            date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            approuve INTEGER DEFAULT 0
        )
    ''')
    
    # Table des destinations
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS destinations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titre TEXT NOT NULL,
            description TEXT NOT NULL,
            prix REAL NOT NULL,
            image_url TEXT
        )
    ''')
    
    # Table des images d'accueil
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS images_accueil (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT NOT NULL,
            ordre INTEGER DEFAULT 0
        )
    ''')
    
    # Table des textes
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS textes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            identifiant TEXT UNIQUE NOT NULL,
            contenu TEXT NOT NULL
        )
    ''')
    
    # Vérifier si l'admin existe
    cursor.execute('SELECT * FROM users WHERE username = ?', ('admin',))
    if not cursor.fetchone():
        # Créer l'admin par défaut
        password_hash = generate_password_hash('admin123')
        cursor.execute('INSERT INTO users (username, password_hash) VALUES (?, ?)', 
                      ('admin', password_hash))
    
    # Vérifier si les textes par défaut existent
    textes_par_defaut = [
        ('presentation', 'Bienvenue sur notre agence de voyage ! Nous vous proposons les meilleures destinations à des prix compétitifs.'),
        ('contact', 'Contactez-nous au 01 23 45 67 89 ou par email à contact@agence-voyage.com'),
        ('footer', '© 2023 Agence de Voyage. Tous droits réservés.')
    ]
    
    for identifiant, contenu in textes_par_defaut:
        cursor.execute('SELECT * FROM textes WHERE identifiant = ?', (identifiant,))
        if not cursor.fetchone():
            cursor.execute('INSERT INTO textes (identifiant, contenu) VALUES (?, ?)', 
                          (identifiant, contenu))
    
    # Vérifier si des destinations existent
    cursor.execute('SELECT COUNT(*) FROM destinations')
    if cursor.fetchone()[0] == 0:
        destinations_par_defaut = [
            ('Paris, France', 'La ville lumière avec sa tour Eiffel et ses monuments historiques.', 799.99, 'paris.jpg'),
            ('Tokyo, Japon', 'Mélange unique de tradition et de modernité.', 1299.99, 'tokyo.jpg'),
            ('New York, USA', 'La ville qui ne dort jamais.', 1099.99, 'newyork.jpg'),
            ('Bali, Indonésie', 'Plages paradisiaques et culture riche.', 899.99, 'bali.jpg')
        ]
        
        for titre, description, prix, image in destinations_par_defaut:
            cursor.execute('INSERT INTO destinations (titre, description, prix, image_url) VALUES (?, ?, ?, ?)',
                          (titre, description, prix, image))
    
    conn.commit()
    conn.close()

def get_db_connection():
    """Établit une connexion à la base de données"""
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

# Initialiser la base de données
init_db()

# ============================================
# ROUTES PUBLIQUES (UTILISATEURS)
# ============================================

@app.route('/')
def index():
    """Page d'accueil"""
    conn = get_db_connection()
    
    # Récupérer les images d'accueil
    images = conn.execute('SELECT * FROM images_accueil ORDER BY ordre').fetchall()
    
    # Récupérer les textes
    presentation = conn.execute('SELECT contenu FROM textes WHERE identifiant = ?', 
                               ('presentation',)).fetchone()
    contact = conn.execute('SELECT contenu FROM textes WHERE identifiant = ?', 
                          ('contact',)).fetchone()
    footer = conn.execute('SELECT contenu FROM textes WHERE identifiant = ?', 
                         ('footer',)).fetchone()
    
    # Récupérer les dernières destinations
    destinations = conn.execute('SELECT * FROM destinations LIMIT 3').fetchall()
    
    # Récupérer les commentaires approuvés
    commentaires = conn.execute('''
        SELECT * FROM commentaires 
        WHERE approuve = 1 
        ORDER BY date DESC 
        LIMIT 3
    ''').fetchall()
    
    conn.close()
    
    return render_template('index.html', 
                         images=images,
                         presentation=presentation['contenu'] if presentation else '',
                         contact=contact['contenu'] if contact else '',
                         footer=footer['contenu'] if footer else '',
                         destinations=destinations,
                         commentaires=commentaires)

@app.route('/reservation', methods=['GET', 'POST'])
def reservation():
    """Page de réservation"""
    if request.method == 'POST':
        # Récupérer les données du formulaire
        nom = request.form['nom'].strip()
        email = request.form['email'].strip()
        telephone = request.form['telephone'].strip()
        destination = request.form['destination'].strip()
        classe = request.form['classe']
        date = request.form['date']
        
        # Validation basique
        if not nom or not email or not telephone or not destination or not date:
            flash('Tous les champs sont obligatoires', 'error')
            return redirect(url_for('reservation'))
        
        # Enregistrer dans la base de données
        conn = get_db_connection()
        conn.execute('''
            INSERT INTO reservations (nom, email, telephone, destination, classe, date)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (nom, email, telephone, destination, classe, date))
        conn.commit()
        conn.close()
        
        flash('Votre réservation a été enregistrée avec succès !', 'success')
        return redirect(url_for('reservation'))
    
    # Récupérer les destinations pour le formulaire
    conn = get_db_connection()
    destinations = conn.execute('SELECT titre FROM destinations').fetchall()
    conn.close()
    
    return render_template('reservation.html', destinations=destinations)

@app.route('/commentaires', methods=['GET', 'POST'])
def commentaires():
    """Page des commentaires"""
    if request.method == 'POST':
        # Récupérer les données du formulaire
        nom = request.form['nom'].strip()
        message = request.form['message'].strip()
        
        # Validation
        if not nom or not message:
            flash('Le nom et le message sont obligatoires', 'error')
            return redirect(url_for('commentaires'))
        
        if len(message) > 500:
            flash('Le message ne doit pas dépasser 500 caractères', 'error')
            return redirect(url_for('commentaires'))
        
        # Enregistrer dans la base de données
        conn = get_db_connection()
        conn.execute('INSERT INTO commentaires (nom, message) VALUES (?, ?)', 
                    (nom, message))
        conn.commit()
        conn.close()
        
        flash('Votre commentaire a été soumis et sera publié après modération.', 'success')
        return redirect(url_for('commentaires'))
    
    # Récupérer les commentaires approuvés
    conn = get_db_connection()
    commentaires_list = conn.execute('''
        SELECT * FROM commentaires 
        WHERE approuve = 1 
        ORDER BY date DESC
    ''').fetchall()
    conn.close()
    
    return render_template('commentaires.html', commentaires=commentaires_list)

@app.route('/destinations')
def destinations():
    """Page des destinations"""
    conn = get_db_connection()
    destinations_list = conn.execute('SELECT * FROM destinations ORDER BY titre').fetchall()
    conn.close()
    
    return render_template('destinations.html', destinations=destinations_list)

@app.route('/tarifs')
def tarifs():
    """Page des tarifs"""
    conn = get_db_connection()
    tarifs_list = conn.execute('SELECT * FROM destinations ORDER BY prix').fetchall()
    conn.close()
    
    return render_template('tarifs.html', destinations=tarifs_list)

# ============================================
# ROUTES ADMINISTRATEUR
# ============================================

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    """Connexion administrateur"""
    # Si l'admin est déjà connecté
    if session.get('admin_logged_in'):
        return redirect(url_for('admin_dashboard'))
    
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password'].strip()
        
        # Vérifier les identifiants
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        conn.close()
        
        if user and check_password_hash(user['password_hash'], password):
            session['admin_logged_in'] = True
            session['admin_username'] = username
            flash('Connexion réussie !', 'success')
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Identifiants incorrects', 'error')
    
    return render_template('admin_login.html')

@app.route('/admin/logout')
def admin_logout():
    """Déconnexion administrateur"""
    session.pop('admin_logged_in', None)
    session.pop('admin_username', None)
    flash('Vous avez été déconnecté', 'info')
    return redirect(url_for('admin_login'))

@app.route('/admin/dashboard')
def admin_dashboard():
    """Tableau de bord administrateur"""
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    
    conn = get_db_connection()
    
    # Statistiques
    total_reservations = conn.execute('SELECT COUNT(*) FROM reservations').fetchone()[0]
    reservations_en_attente = conn.execute('SELECT COUNT(*) FROM reservations WHERE statut = ?', 
                                          ('en_attente',)).fetchone()[0]
    total_commentaires = conn.execute('SELECT COUNT(*) FROM commentaires').fetchone()[0]
    commentaires_en_attente = conn.execute('SELECT COUNT(*) FROM commentaires WHERE approuve = ?', 
                                          (0,)).fetchone()[0]
    total_destinations = conn.execute('SELECT COUNT(*) FROM destinations').fetchone()[0]
    
    # Dernières réservations
    dernieres_reservations = conn.execute('''
        SELECT * FROM reservations 
        ORDER BY date_creation DESC 
        LIMIT 5
    ''').fetchall()
    
    # Derniers commentaires
    derniers_commentaires = conn.execute('''
        SELECT * FROM commentaires 
        ORDER BY date DESC 
        LIMIT 5
    ''').fetchall()
    
    conn.close()
    
    return render_template('admin_dashboard.html',
                         total_reservations=total_reservations,
                         reservations_en_attente=reservations_en_attente,
                         total_commentaires=total_commentaires,
                         commentaires_en_attente=commentaires_en_attente,
                         total_destinations=total_destinations,
                         dernieres_reservations=dernieres_reservations,
                         derniers_commentaires=derniers_commentaires)

@app.route('/admin/reservations')
def admin_reservations():
    """Gestion des réservations"""
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    
    statut = request.args.get('statut', 'tous')
    
    conn = get_db_connection()
    
    if statut == 'tous':
        reservations = conn.execute('''
            SELECT * FROM reservations 
            ORDER BY date_creation DESC
        ''').fetchall()
    else:
        reservations = conn.execute('''
            SELECT * FROM reservations 
            WHERE statut = ? 
            ORDER BY date_creation DESC
        ''', (statut,)).fetchall()
    
    conn.close()
    
    return render_template('admin_reservations.html', 
                         reservations=reservations, 
                         statut=statut)

@app.route('/admin/reservation/<int:id>/approuver')
def approuver_reservation(id):
    """Approuver une réservation"""
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    
    conn = get_db_connection()
    conn.execute('UPDATE reservations SET statut = ? WHERE id = ?', 
                ('approuvee', id))
    conn.commit()
    conn.close()
    
    flash('Réservation approuvée avec succès', 'success')
    return redirect(url_for('admin_reservations'))

@app.route('/admin/reservation/<int:id>/supprimer')
def supprimer_reservation(id):
    """Supprimer une réservation"""
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    
    conn = get_db_connection()
    conn.execute('DELETE FROM reservations WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    
    flash('Réservation supprimée avec succès', 'success')
    return redirect(url_for('admin_reservations'))

@app.route('/admin/commentaires')
def admin_commentaires():
    """Gestion des commentaires"""
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    
    statut = request.args.get('statut', 'tous')
    
    conn = get_db_connection()
    
    if statut == 'tous':
        commentaires = conn.execute('''
            SELECT * FROM commentaires 
            ORDER BY date DESC
        ''').fetchall()
    elif statut == 'en_attente':
        commentaires = conn.execute('''
            SELECT * FROM commentaires 
            WHERE approuve = 0 
            ORDER BY date DESC
        ''').fetchall()
    else:  # approuves
        commentaires = conn.execute('''
            SELECT * FROM commentaires 
            WHERE approuve = 1 
            ORDER BY date DESC
        ''').fetchall()
    
    conn.close()
    
    return render_template('admin_commentaires.html', 
                         commentaires=commentaires, 
                         statut=statut)

@app.route('/admin/commentaire/<int:id>/approuver')
def approuver_commentaire(id):
    """Approuver un commentaire"""
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    
    conn = get_db_connection()
    conn.execute('UPDATE commentaires SET approuve = 1 WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    
    flash('Commentaire approuvé avec succès', 'success')
    return redirect(url_for('admin_commentaires'))

@app.route('/admin/commentaire/<int:id>/supprimer')
def supprimer_commentaire(id):
    """Supprimer un commentaire"""
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    
    conn = get_db_connection()
    conn.execute('DELETE FROM commentaires WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    
    flash('Commentaire supprimé avec succès', 'success')
    return redirect(url_for('admin_commentaires'))

@app.route('/admin/destinations')
def admin_destinations():
    """Gestion des destinations"""
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    
    conn = get_db_connection()
    destinations = conn.execute('SELECT * FROM destinations ORDER BY titre').fetchall()
    conn.close()
    
    return render_template('admin_destinations.html', destinations=destinations)

@app.route('/admin/destination/ajouter', methods=['GET', 'POST'])
def ajouter_destination():
    """Ajouter une destination"""
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    
    if request.method == 'POST':
        titre = request.form['titre'].strip()
        description = request.form['description'].strip()
        prix = request.form['prix'].strip()
        
        # Validation
        if not titre or not description or not prix:
            flash('Tous les champs sont obligatoires', 'error')
            return redirect(url_for('ajouter_destination'))
        
        try:
            prix = float(prix)
        except ValueError:
            flash('Le prix doit être un nombre valide', 'error')
            return redirect(url_for('ajouter_destination'))
        
        # Gestion de l'image
        image_url = None
        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename != '' and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                # Créer le dossier s'il n'existe pas
                os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'destinations'), exist_ok=True)
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'destinations', filename)
                file.save(filepath)
                image_url = f'uploads/destinations/{filename}'
        
        # Enregistrer dans la base de données
        conn = get_db_connection()
        conn.execute('''
            INSERT INTO destinations (titre, description, prix, image_url)
            VALUES (?, ?, ?, ?)
        ''', (titre, description, prix, image_url))
        conn.commit()
        conn.close()
        
        flash('Destination ajoutée avec succès', 'success')
        return redirect(url_for('admin_destinations'))
    
    return render_template('admin_destinations.html', ajouter=True)

@app.route('/admin/destination/<int:id>/modifier', methods=['GET', 'POST'])
def modifier_destination(id):
    """Modifier une destination"""
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    
    conn = get_db_connection()
    
    if request.method == 'POST':
        titre = request.form['titre'].strip()
        description = request.form['description'].strip()
        prix = request.form['prix'].strip()
        
        # Validation
        if not titre or not description or not prix:
            flash('Tous les champs sont obligatoires', 'error')
            return redirect(url_for('modifier_destination', id=id))
        
        try:
            prix = float(prix)
        except ValueError:
            flash('Le prix doit être un nombre valide', 'error')
            return redirect(url_for('modifier_destination', id=id))
        
        # Gestion de l'image
        image_url = request.form['image_url_actuelle']
        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename != '' and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                # Créer le dossier s'il n'existe pas
                os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'destinations'), exist_ok=True)
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'destinations', filename)
                file.save(filepath)
                image_url = f'uploads/destinations/{filename}'
        
        # Mettre à jour dans la base de données
        conn.execute('''
            UPDATE destinations 
            SET titre = ?, description = ?, prix = ?, image_url = ?
            WHERE id = ?
        ''', (titre, description, prix, image_url, id))
        conn.commit()
        conn.close()
        
        flash('Destination modifiée avec succès', 'success')
        return redirect(url_for('admin_destinations'))
    
    # Récupérer la destination
    destination = conn.execute('SELECT * FROM destinations WHERE id = ?', (id,)).fetchone()
    conn.close()
    
    if not destination:
        flash('Destination non trouvée', 'error')
        return redirect(url_for('admin_destinations'))
    
    return render_template('admin_destinations.html', modifier=True, destination=destination)

@app.route('/admin/destination/<int:id>/supprimer')
def supprimer_destination(id):
    """Supprimer une destination"""
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    
    conn = get_db_connection()
    
    # Vérifier si des réservations existent pour cette destination
    reservations = conn.execute('SELECT COUNT(*) FROM reservations WHERE destination LIKE ?', 
                               (f'%{conn.execute("SELECT titre FROM destinations WHERE id = ?", (id,)).fetchone()[0]}%',)).fetchone()[0]
    
    if reservations > 0:
        flash('Impossible de supprimer cette destination car des réservations y sont associées', 'error')
        conn.close()
        return redirect(url_for('admin_destinations'))
    
    conn.execute('DELETE FROM destinations WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    
    flash('Destination supprimée avec succès', 'success')
    return redirect(url_for('admin_destinations'))

@app.route('/admin/parametres', methods=['GET', 'POST'])
def admin_parametres():
    """Gérer les paramètres du site"""
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    
    conn = get_db_connection()
    
    if request.method == 'POST':
        # Mettre à jour les textes
        presentation = request.form['presentation'].strip()
        contact = request.form['contact'].strip()
        footer = request.form['footer'].strip()
        
        conn.execute('UPDATE textes SET contenu = ? WHERE identifiant = ?', 
                    (presentation, 'presentation'))
        conn.execute('UPDATE textes SET contenu = ? WHERE identifiant = ?', 
                    (contact, 'contact'))
        conn.execute('UPDATE textes SET contenu = ? WHERE identifiant = ?', 
                    (footer, 'footer'))
        
        # Gérer les images d'accueil
        if 'images_accueil' in request.files:
            files = request.files.getlist('images_accueil')
            for file in files:
                if file and file.filename != '' and allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    # Créer le dossier s'il n'existe pas
                    os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'accueil'), exist_ok=True)
                    filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'accueil', filename)
                    file.save(filepath)
                    
                    # Ajouter à la base de données
                    conn.execute('INSERT INTO images_accueil (url) VALUES (?)', 
                                (f'uploads/accueil/{filename}',))
        
        conn.commit()
        flash('Paramètres mis à jour avec succès', 'success')
    
    # Récupérer les données actuelles
    presentation = conn.execute('SELECT contenu FROM textes WHERE identifiant = ?', 
                               ('presentation',)).fetchone()
    contact = conn.execute('SELECT contenu FROM textes WHERE identifiant = ?', 
                          ('contact',)).fetchone()
    footer = conn.execute('SELECT contenu FROM textes WHERE identifiant = ?', 
                         ('footer',)).fetchone()
    
    images_accueil = conn.execute('SELECT * FROM images_accueil ORDER BY ordre').fetchall()
    
    conn.close()
    
    return render_template('admin_dashboard.html', 
                         parametres=True,
                         presentation=presentation['contenu'] if presentation else '',
                         contact=contact['contenu'] if contact else '',
                         footer=footer['contenu'] if footer else '',
                         images_accueil=images_accueil)

@app.route('/admin/image/<int:id>/supprimer')
def supprimer_image_accueil(id):
    """Supprimer une image d'accueil"""
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    
    conn = get_db_connection()
    conn.execute('DELETE FROM images_accueil WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    
    flash('Image supprimée avec succès', 'success')
    return redirect(url_for('admin_parametres'))

# ============================================
# ROUTES UTILITAIRES
# ============================================

@app.route('/uploads/<path:filename>')
def serve_upload(filename):
    """Servir les fichiers uploadés"""
    return send_from_directory('static', filename)

if __name__ == '__main__':
    # Créer les dossiers d'uploads s'ils n'existent pas
    os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'destinations'), exist_ok=True)
    os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'accueil'), exist_ok=True)
    
    app.run(debug=True)
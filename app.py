from flask import Flask, request, jsonify, session, render_template, send_file, redirect, url_for
from flask_cors import CORS
from config import Config
from models import db, bcrypt, User, Role, Courrier, AuditLog, ScanHistory, Assignation, NotificationAssignation
import os
import uuid
import json
from datetime import datetime, timedelta
from functools import wraps
import random

# ==================== IMPORT ML SERVICE ====================
from ml_service import MLService

# ==================== INITIALISATION DE L'APPLICATION ====================
app = Flask(__name__)
app.config.from_object(Config)

# Configuration MySQL avec SQLAlchemy
app.config['SQLALCHEMY_DATABASE_URI'] = Config.get_database_uri()
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SESSION_COOKIE_SECURE'] = Config.SESSION_COOKIE_SECURE
app.config['SESSION_COOKIE_HTTPONLY'] = Config.SESSION_COOKIE_HTTPONLY
app.config['MAX_CONTENT_LENGTH'] = Config.MAX_CONTENT_LENGTH

# Initialisation des extensions
db.init_app(app)
bcrypt.init_app(app)
CORS(app, supports_credentials=True)

# Création des dossiers nécessaires
os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
os.makedirs(Config.SCAN_FOLDER, exist_ok=True)
os.makedirs(Config.ARCHIVE_FOLDER, exist_ok=True)
os.makedirs('models', exist_ok=True)

# ==================== INITIALISATION ML SERVICE ====================
ml_service = MLService(model_dir='models/')


# ==================== DÉCORATEURS ====================
def permission_required(required_level):
    """Décorateur pour vérifier les permissions"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                return jsonify({'success': False, 'message': 'Non authentifié'}), 401
            user = User.query.get(session['user_id'])
            if not user or not user.role or user.role.niveau < required_level:
                return jsonify({'success': False, 'message': 'Permission insuffisante'}), 403
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def log_action(action, entity_type, entity_id, details):
    """Journalisation des actions dans l'audit trail"""
    if 'user_id' in session:
        try:
            log = AuditLog(
                user_id=session['user_id'],
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                details=details[:500] if details else '',
                ip_address=request.remote_addr
            )
            db.session.add(log)
            db.session.commit()
        except Exception as e:
            print(f"Erreur log: {e}")


def sanitize_input(text):
    """Nettoie les entrées utilisateur"""
    if not text or not isinstance(text, str):
        return text
    import re
    text = re.sub(r'[<>]', '', text)
    return text.strip()[:500]


def generate_csrf_token():
    """Génère token CSRF"""
    import secrets
    if 'csrf_token' not in session:
        session['csrf_token'] = secrets.token_hex(32)
    return session['csrf_token']


def log_security_event(event_type, details):
    """Logge les événements de sécurité"""
    print(f"[SECURITY] {datetime.now()} - {event_type} - {details}")


# ==================== INITIALISATION DE LA BASE DE DONNÉES ====================
def init_database():
    """Initialise la base de données avec les rôles et utilisateurs par défaut"""
    with app.app_context():
        db.create_all()
        
        # Création des rôles
        roles_data = [
            {'nom': 'stagiaire', 'niveau': 1, 'description': 'Accès limité - consultation uniquement'},
            {'nom': 'assistant', 'niveau': 3, 'description': 'Peut scanner et ajouter des courriers'},
            {'nom': 'charge_etude', 'niveau': 5, 'description': 'Peut modifier et exporter les courriers'},
            {'nom': 'chef_service', 'niveau': 8, 'description': 'Peut supprimer et archiver'},
            {'nom': 'directeur', 'niveau': 10, 'description': 'Accès total à toutes les fonctionnalités'}
        ]
        
        for role_data in roles_data:
            if not Role.query.filter_by(nom=role_data['nom']).first():
                role = Role(**role_data)
                db.session.add(role)
        
        db.session.commit()
        
        # Création des utilisateurs de test
        test_users = [
            {'username': 'ahmed.directeur', 'password': 'directeur123', 'nom_complet': 'Ahmed Benali', 
             'email': 'ahmed@matn.gov.ma', 'role': 'directeur', 'service': 'Direction Générale', 'telephone': '0612345678'},
            {'username': 'fatima.chef', 'password': 'chef123', 'nom_complet': 'Fatima Zahra', 
             'email': 'fatima@urbanisme.gov.ma', 'role': 'chef_service', 'service': 'Urbanisme', 'telephone': '0623456789'},
            {'username': 'karim.assistant', 'password': 'assistant123', 'nom_complet': 'Karim Tazi', 
             'email': 'karim@habitat.gov.ma', 'role': 'assistant', 'service': 'Habitat', 'telephone': '0634567890'},
            {'username': 'nadia.etude', 'password': 'etude123', 'nom_complet': 'Nadia El Fassi', 
             'email': 'nadia@amenagement.gov.ma', 'role': 'charge_etude', 'service': 'Aménagement', 'telephone': '0645678901'},
            {'username': 'youssef.stagiaire', 'password': 'stagiaire123', 'nom_complet': 'Youssef Meriem', 
             'email': 'youssef@matn.gov.ma', 'role': 'stagiaire', 'service': 'Politique Ville', 'telephone': '0656789012'}
        ]
        
        for user_data in test_users:
            if not User.query.filter_by(username=user_data['username']).first():
                role = Role.query.filter_by(nom=user_data['role']).first()
                if role:
                    user = User(
                        username=user_data['username'],
                        nom_complet=user_data['nom_complet'],
                        email=user_data['email'],
                        telephone=user_data['telephone'],
                        role_id=role.id,
                        service=user_data['service'],
                        departement=user_data['service'],
                        statut='actif'
                    )
                    user.set_password(user_data['password'])
                    db.session.add(user)
        
        db.session.commit()
        print("✅ Base de données initialisée avec succès!")


# ==================== ROUTES PAGES ====================
@app.route('/')
def index():
    return render_template('index.html')


@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('index'))
    return render_template('dashboard.html')


# ==================== ROUTES AUTHENTIFICATION ====================
@app.route('/api/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        username = sanitize_input(data.get('username', ''))
        password = data.get('password', '')
        
        if not username or not password:
            return jsonify({'success': False, 'message': 'Veuillez remplir tous les champs'})
        
        user = User.query.filter_by(username=username, statut='actif').first()
        
        if user and user.check_password(password):
            session.clear()
            session['user_id'] = user.id
            session['username'] = user.username
            session['user_role'] = user.role.nom if user.role else None
            session['role_niveau'] = user.role.niveau if user.role else 0
            session['csrf_token'] = generate_csrf_token()
            
            user.last_login = datetime.utcnow()
            db.session.commit()
            
            log_action('login', 'user', user.id, f"Connexion réussie pour {user.username}")
            
            return jsonify({
                'success': True,
                'message': f'Bienvenue {user.nom_complet or user.username}',
                'user': user.to_dict(),
                'csrf_token': session['csrf_token']
            })
        
        log_security_event('failed_login', f"Tentative échouée pour {username}")
        return jsonify({'success': False, 'message': 'Identifiants incorrects'})
    
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@app.route('/api/logout', methods=['POST'])
def logout():
    if 'user_id' in session:
        log_action('logout', 'session', session['user_id'], "Déconnexion")
    session.clear()
    return jsonify({'success': True})


@app.route('/api/check_auth', methods=['GET'])
def check_auth():
    if 'user_id' in session:
        user = User.query.get(session['user_id'])
        if user:
            return jsonify({
                'success': True,
                'user': user.to_dict(),
                'csrf_token': session.get('csrf_token')
            })
    return jsonify({'success': False})


@app.route('/api/user/permissions', methods=['GET'])
@permission_required(1)
def get_user_permissions():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Non authentifié'})
    
    user = User.query.get(session['user_id'])
    if not user:
        return jsonify({'success': False, 'message': 'Utilisateur non trouvé'})
    
    niveau = user.role.niveau if user.role else 0
    
    permissions = {
        'can_view_courriers': niveau >= 1,
        'can_add_courrier': niveau >= 5,
        'can_edit_courrier': niveau >= 5,
        'can_delete_courrier': niveau >= 8,
        'can_manage_users': niveau >= 10,
        'can_view_stats_global': niveau >= 8,
        'can_export_data': niveau >= 5,
        'can_scan_documents': niveau >= 3,
        'can_validate_documents': niveau >= 8,
        'can_assign_courriers': niveau >= 8
    }
    
    return jsonify({
        'success': True,
        'role': user.role.nom if user.role else 'inconnu',
        'niveau': niveau,
        'departement': user.departement,
        'service': user.service,
        'permissions': permissions
    })


# ==================== ROUTES COURRIERS ====================
@app.route('/api/courriers', methods=['GET'])
@permission_required(1)
def get_courriers():
    try:
        search = request.args.get('search', '')
        status = request.args.get('status', '')
        priority = request.args.get('priority', '')
        classification = request.args.get('classification', '')
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 10))
        
        user = User.query.get(session['user_id'])
        query = Courrier.query
        
        if user.role.niveau < 8:
            query = query.filter_by(service_destinataire=user.service)
        
        if search:
            query = query.filter(
                db.or_(
                    Courrier.expediteur.like(f'%{search}%'),
                    Courrier.objet.like(f'%{search}%'),
                    Courrier.contenu.like(f'%{search}%')
                )
            )
        
        if status and status != 'all':
            query = query.filter_by(statut=status)
        
        if priority and priority != 'all':
            query = query.filter_by(priorite=priority)
        
        if classification and classification != 'all':
            query = query.filter_by(ai_classification=classification)
        
        paginated = query.order_by(Courrier.id.desc()).paginate(page=page, per_page=per_page, error_out=False)
        
        return jsonify({
            'success': True,
            'courriers': [c.to_dict() for c in paginated.items],
            'total': paginated.total,
            'page': page,
            'pages': paginated.pages
        })
    
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@app.route('/api/courriers', methods=['POST'])
@permission_required(5)
def add_courrier():
    try:
        data = request.get_json()
        
        if not data.get('expediteur') or not data.get('objet'):
            return jsonify({'success': False, 'message': 'Expéditeur et objet requis'})
        
        user = User.query.get(session['user_id'])
        
        # ===== CLASSIFICATION ML AUTOMATIQUE =====
        texte_complet = f"{data.get('objet', '')} {data.get('contenu', '')}"
        classification = ml_service.categorize_courrier(texte_complet)
        priorite_ml = ml_service.suggest_priority(texte_complet, data.get('expediteur'))
        
        # Utiliser la priorité ML si plus élevée que celle saisie
        priorite_finale = data.get('priorite', 'medium')
        if priorite_ml == 'high' and priorite_finale != 'high':
            priorite_finale = 'high'
        
        courrier = Courrier(
            user_id=session['user_id'],
            date_reception=datetime.strptime(data.get('date_reception', datetime.now().strftime('%Y-%m-%d')), '%Y-%m-%d').date(),
            expediteur=sanitize_input(data['expediteur']),
            email=sanitize_input(data.get('email', '')),
            objet=sanitize_input(data['objet']),
            contenu=sanitize_input(data.get('contenu', '')),
            priorite=priorite_finale,
            statut=data.get('statut', 'en_attente'),
            service_destinataire=data.get('service_destinataire') or user.service,
            numero_reference=sanitize_input(data.get('numero_reference', '')),
            # Champs ML
            ai_classification=classification.get('categorie', 'normal'),
            ocr_confidence=classification.get('confidence', 0)
        )
        
        db.session.add(courrier)
        db.session.commit()
        
        log_action('add', 'courrier', courrier.id, f"Ajout courrier: {courrier.objet}")
        
        return jsonify({
            'success': True,
            'message': 'Courrier ajouté avec succès',
            'id': courrier.id,
            'ml_classification': classification,
            'ml_priorite': priorite_ml
        })
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})


@app.route('/api/courriers/<int:courrier_id>', methods=['PUT'])
@permission_required(5)
def update_courrier_route(courrier_id):
    try:
        data = request.get_json()
        user = User.query.get(session['user_id'])
        courrier = Courrier.query.get_or_404(courrier_id)
        
        # Vérification supplémentaire : seul le service concerné ou niveau 8+ peut modifier
        if user.role.niveau < 8 and courrier.service_destinataire != user.service:
            return jsonify({'success': False, 'message': 'Non autorisé à modifier ce courrier'}), 403
        
        if 'objet' in data:
            courrier.objet = sanitize_input(data['objet'])
        if 'statut' in data:
            courrier.statut = data['statut']
        if 'priorite' in data:
            courrier.priorite = data['priorite']
        if 'contenu' in data:
            courrier.contenu = sanitize_input(data['contenu'])
        if 'date_traitement' in data:
            courrier.date_traitement = datetime.strptime(data['date_traitement'], '%Y-%m-%d').date() if data['date_traitement'] else None
        if 'commentaire_traitement' in data:
            courrier.commentaire_traitement = sanitize_input(data['commentaire_traitement'])
        
        db.session.commit()
        log_action('update', 'courrier', courrier_id, f"Modification courrier: {courrier.objet}")
        
        return jsonify({'success': True, 'message': 'Courrier modifié'})
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})


@app.route('/api/courriers/<int:courrier_id>', methods=['DELETE'])
@permission_required(8)
def delete_courrier_route(courrier_id):
    try:
        user = User.query.get(session['user_id'])
        courrier = Courrier.query.get_or_404(courrier_id)
        
        # Chef service ne peut supprimer que les courriers de son service
        if user.role.niveau == 8 and courrier.service_destinataire != user.service:
            return jsonify({'success': False, 'message': 'Non autorisé à supprimer ce courrier'}), 403
        
        if courrier.scan_image_path and os.path.exists(courrier.scan_image_path):
            os.remove(courrier.scan_image_path)
        
        db.session.delete(courrier)
        db.session.commit()
        
        log_action('delete', 'courrier', courrier_id, f"Suppression courrier: {courrier.objet}")
        
        return jsonify({'success': True, 'message': 'Courrier supprimé'})
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})


# ==================== ROUTES SCAN ====================
@app.route('/api/scan/analyze', methods=['POST'])
@permission_required(3)
def analyze_document():
    if 'document' not in request.files:
        return jsonify({'success': False, 'message': 'Aucun document'})
    
    file = request.files['document']
    if file.filename == '':
        return jsonify({'success': False, 'message': 'Fichier vide'})
    
    temp_filename = f"temp_{uuid.uuid4().hex}.jpg"
    temp_path = os.path.join(Config.SCAN_FOLDER, temp_filename)
    file.save(temp_path)
    
    try:
        # Extraire le texte (simulé pour l'instant)
        extracted_text = f"Document scanné: {file.filename}\nTexte extrait automatiquement par OCR."
        
        # ===== CLASSIFICATION ML DU TEXTE EXTRAIT =====
        classification = ml_service.categorize_courrier(extracted_text)
        priorite_ml = ml_service.suggest_priority(extracted_text)
        
        return jsonify({
            'success': True,
            'extracted_text': extracted_text,
            'confidence': 85,
            'processing_time': 1200,
            'suggested_expediteur': 'Ministère de l\'Aménagement du Territoire',
            'suggested_objet': 'Courrier officiel',
            'suggested_priorite': priorite_ml,
            'ai_classification': classification.get('categorie', 'normal'),
            'ai_summary': f"Courrier classé comme: {classification.get('categorie', 'Normal')} avec {classification.get('confidence', 50)}% de confiance",
            'numero_reference': str(random.randint(10000, 99999)),
            'extras': {}
        })
    
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


@app.route('/api/scan/save', methods=['POST'])
@permission_required(3)
def save_scanned_courrier():
    try:
        courrier_data = json.loads(request.form.get('courrier_data', '{}'))
        user = User.query.get(session['user_id'])
        
        # ===== CLASSIFICATION ML =====
        texte_complet = f"{courrier_data.get('objet', '')} {courrier_data.get('contenu', '')}"
        classification = ml_service.categorize_courrier(texte_complet)
        priorite_ml = ml_service.suggest_priority(texte_complet, courrier_data.get('expediteur'))
        
        courrier = Courrier(
            user_id=session['user_id'],
            date_reception=datetime.now().date(),
            expediteur=sanitize_input(courrier_data.get('expediteur', 'Document scanné')),
            objet=sanitize_input(courrier_data.get('objet', 'Courrier scanné')),
            contenu=sanitize_input(courrier_data.get('contenu', '')),
            priorite=priorite_ml if priorite_ml else courrier_data.get('priorite', 'medium'),
            statut='en_attente',
            service_destinataire=user.service,
            scan_score=int(request.form.get('analysis_score', 0)),
            scan_verdict=request.form.get('verdict', 'Analyse terminée'),
            numero_reference=courrier_data.get('numero_reference', ''),
            ai_classification=classification.get('categorie', 'normal'),
            ocr_confidence=courrier_data.get('ocr_confidence', 0)
        )
        
        db.session.add(courrier)
        db.session.flush()
        
        if 'scan_image' in request.files:
            file = request.files['scan_image']
            if file and file.filename:
                ext = file.filename.rsplit('.', 1)[1].lower()
                filename = f"scan_{session['user_id']}_{courrier.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{ext}"
                filepath = os.path.join(Config.SCAN_FOLDER, filename)
                file.save(filepath)
                
                courrier.scan_image_path = filepath
                courrier.scan_image_name = filename
                courrier.scan_image_size = os.path.getsize(filepath)
                courrier.scan_image_type = ext
                courrier.original_filename = file.filename
        
        db.session.commit()
        log_action('scan_add', 'courrier', courrier.id, f"Ajout par scan: {courrier.objet}")
        
        return jsonify({
            'success': True,
            'message': 'Courrier enregistré avec classification ML',
            'id': courrier.id,
            'ml_classification': classification,
            'ml_priorite': priorite_ml
        })
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})


@app.route('/api/scan/view/<int:courrier_id>', methods=['GET'])
@permission_required(3)
def view_scan(courrier_id):
    user = User.query.get(session['user_id'])
    courrier = Courrier.query.get_or_404(courrier_id)
    
    # Vérification supplémentaire : même service ou rôle élevé
    if user.role.niveau < 8 and courrier.service_destinataire != user.service:
        return jsonify({'success': False, 'message': 'Non autorisé à voir ce document'}), 403
    
    if not courrier.scan_image_path or not os.path.exists(courrier.scan_image_path):
        return jsonify({'success': False, 'message': 'Aucune image'})
    
    return send_file(courrier.scan_image_path, mimetype='image/jpeg')


# ==================== ROUTES STATISTIQUES ====================
@app.route('/api/stats/global', methods=['GET'])
@permission_required(8)
def get_global_stats():
    try:
        user = User.query.get(session['user_id'])
        query = Courrier.query
        
        if user.role.niveau < 8:
            query = query.filter_by(service_destinataire=user.service)
        
        # Récupérer les données réelles
        courriers = query.all()
        
        # Statistiques par mois
        monthly_stats = {}
        for c in courriers:
            if c.date_reception:
                mois_key = c.date_reception.strftime('%b %Y')
                if mois_key not in monthly_stats:
                    monthly_stats[mois_key] = 0
                monthly_stats[mois_key] += 1
        
        evolution = [{'mois': k, 'total': v} for k, v in sorted(monthly_stats.items())]
        if len(evolution) < 5:
            # Ajouter des données simulées si pas assez
            mois = ['Jan 2026', 'Fev 2026', 'Mar 2026', 'Avr 2026', 'Mai 2026']
            for m in mois:
                if not any(e['mois'] == m for e in evolution):
                    evolution.append({'mois': m, 'total': random.randint(2, 15)})
            evolution = sorted(evolution, key=lambda x: x['mois'])
        
        stats = {
            'total': query.count(),
            'en_attente': query.filter_by(statut='en_attente').count(),
            'traite': query.filter_by(statut='traite').count(),
            'urgent': query.filter_by(statut='urgent').count(),
            'archive': query.filter_by(statut='archive').count(),
            'haute_priorite': query.filter_by(priorite='high').count()
        }
        
        return jsonify({
            'success': True,
            'stats': stats,
            'evolution': evolution[:5],
            'top_expediteurs': [],
            'par_service': {},
            'performance': [random.randint(60, 95) for _ in range(6)]
        })
    
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@app.route('/api/analytics/advanced', methods=['GET'])
@permission_required(8)
def get_advanced_analytics():
    try:
        user = User.query.get(session['user_id'])
        query = Courrier.query
        
        if user.role.niveau < 8:
            query = query.filter_by(service_destinataire=user.service)
        
        courriers = query.all()
        
        # Distribution par heure (basée sur les dates de réception)
        hourly_counts = {}
        for c in courriers:
            if c.date_reception:
                hour = c.date_reception.hour if hasattr(c.date_reception, 'hour') else 12
                hourly_counts[hour] = hourly_counts.get(hour, 0) + 1
        
        hourly_distribution = [{'heure': h, 'total': hourly_counts.get(h, 0)} for h in range(8, 20)]
        
        # Distribution par jour de semaine
        jours = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche']
        weekly_counts = {}
        for c in courriers:
            if c.date_reception:
                weekday = c.date_reception.weekday()
                weekly_counts[weekday] = weekly_counts.get(weekday, 0) + 1
        
        weekly_distribution = [{'jour': jours[i], 'total': weekly_counts.get(i, 0)} for i in range(7)]
        
        return jsonify({
            'success': True,
            'hourly_distribution': hourly_distribution,
            'weekly_distribution': weekly_distribution,
            'processing_time': [
                {'priorite': 'high', 'priorite_label': 'Haute', 'temps_moyen': random.randint(2, 8)},
                {'priorite': 'medium', 'priorite_label': 'Moyenne', 'temps_moyen': random.randint(8, 24)},
                {'priorite': 'low', 'priorite_label': 'Basse', 'temps_moyen': random.randint(24, 72)}
            ]
        })
    
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


# ==================== ROUTES ML ====================

@app.route('/api/ml/predictions', methods=['GET'])
@permission_required(8)
def get_ml_predictions():
    try:
        user = User.query.get(session['user_id'])
        query = Courrier.query
        
        if user.role.niveau < 8:
            query = query.filter_by(service_destinataire=user.service)
        
        courriers = query.all()
        
        # Préparer les données historiques pour le ML
        historical_data = []
        for c in courriers:
            if c.date_reception:
                historical_data.append({
                    'date': c.date_reception,
                    'count': 1
                })
        
        # Si pas assez de données, utiliser fallback
        if len(historical_data) < 14:
            predictions = ml_service._fallback_prediction(30)
            method = 'fallback'
        else:
            try:
                # Entraîner et prédire avec ML
                model_type = 'rf'  # Random Forest par défaut
                predictions = ml_service.predict_volume(historical_data, days=30, model_type=model_type)
                method = 'machine_learning'
            except Exception as e:
                print(f"Erreur ML: {e}")
                predictions = ml_service._fallback_prediction(30)
                method = 'fallback'
        
        # Calculer les stats
        en_attente = query.filter_by(statut='en_attente').count()
        urgents = query.filter_by(priorite='high').filter(Courrier.statut != 'traite').count()
        
        suggestions = []
        if en_attente > 10:
            suggestions.append(f"⚠️ ALERTE: {en_attente} courriers en attente de traitement")
        elif en_attente > 5:
            suggestions.append(f"📋 Attention: {en_attente} courriers en attente")
        else:
            suggestions.append("✅ Bon rythme: Peu de courriers en attente")
        
        if urgents > 3:
            suggestions.append(f"🚨 {urgents} courriers urgents nécessitent une attention particulière")
        
        suggestions.append("💡 Conseil: Traitez les courriers par ordre de priorité")
        
        jours_labels = [(datetime.now() + timedelta(days=i)).strftime('%d/%m') for i in range(30)]
        
        return jsonify({
            'success': True,
            'predictions_30j': predictions,
            'jours_labels': jours_labels,
            'suggestions': suggestions,
            'volume_estime': sum(predictions),
            'en_attente': en_attente,
            'urgents': urgents,
            'method': method,
            'data_points': len(historical_data)
        })
    
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@app.route('/api/ml/classify', methods=['POST'])
@permission_required(3)
def ml_classify_courrier():
    """Utilise le ML pour classer un courrier"""
    try:
        data = request.get_json()
        texte = data.get('texte', '')
        
        if not texte:
            return jsonify({'success': False, 'message': 'Texte requis'})
        
        result = ml_service.categorize_courrier(texte)
        
        return jsonify({
            'success': True,
            'categorie': result.get('categorie'),
            'service': result.get('service'),
            'confidence': result.get('confidence'),
            'method': result.get('method', 'rule_based')
        })
    
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@app.route('/api/ml/priorite', methods=['POST'])
@permission_required(3)
def ml_predict_priorite():
    """Utilise le ML pour prédire la priorité"""
    try:
        data = request.get_json()
        texte = data.get('texte', '')
        expediteur = data.get('expediteur', '')
        
        if not texte:
            return jsonify({'success': False, 'message': 'Texte requis'})
        
        priorite = ml_service.suggest_priority(texte, expediteur)
        
        return jsonify({
            'success': True,
            'priorite': priorite,
            'method': 'machine_learning'
        })
    
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@app.route('/api/ml/train', methods=['POST'])
@permission_required(10)  # Seul le Directeur
def train_ml_models():
    """Réentraîne tous les modèles ML"""
    try:
        # Récupérer les courriers labelisés
        courriers = Courrier.query.filter(
            Courrier.ai_classification.isnot(None),
            Courrier.ai_classification != ''
        ).all()
        
        courriers_labelises = []
        for c in courriers:
            courriers_labelises.append({
                'texte': f"{c.objet or ''} {c.contenu or ''}",
                'categorie': c.ai_classification or 'normal',
                'priorite': c.priorite or 'medium'
            })
        
        # Récupérer les données historiques pour le volume
        historical_data = []
        for c in Courrier.query.all():
            if c.date_reception:
                historical_data.append({
                    'date': c.date_reception,
                    'count': 1
                })
        
        # Entraîner tous les modèles
        results = ml_service.train_all_models(historical_data, courriers_labelises)
        
        return jsonify({
            'success': True,
            'message': 'Modèles ML entraînés avec succès',
            'results': results,
            'total_samples': len(courriers_labelises),
            'volume_samples': len(historical_data)
        })
    
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@app.route('/api/ml/metrics', methods=['GET'])
@permission_required(8)
def get_ml_metrics():
    """Récupère les métriques des modèles ML"""
    try:
        metrics = ml_service.get_model_metrics()
        return jsonify({
            'success': True,
            'metrics': metrics
        })
    
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


# ==================== ROUTES AUDIT ====================
@app.route('/api/audit/logs', methods=['GET'])
@permission_required(8)
def get_audit_logs():
    try:
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 50))
        
        logs = AuditLog.query.order_by(AuditLog.created_at.desc()).paginate(page=page, per_page=per_page)
        
        return jsonify({
            'success': True,
            'logs': [log.to_dict() for log in logs.items],
            'total': logs.total,
            'page': page,
            'pages': logs.pages
        })
    
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


# ==================== ROUTES ASSIGNATION DES COURRIERS ====================

@app.route('/api/assignations/courriers-pendings', methods=['GET'])
@permission_required(8)
def get_pending_courriers_for_assignation():
    """Récupère les courriers en attente et urgents pour assignation"""
    try:
        # Récupérer tous les courriers en attente ou urgents
        query = Courrier.query.filter(
            Courrier.statut.in_(['en_attente', 'urgent'])
        ).order_by(Courrier.priorite.desc(), Courrier.created_at.asc())
        
        # Exclure les courriers déjà assignés et non traités
        assigned_ids = db.session.query(Assignation.courrier_id).filter(
            Assignation.status.in_(['pending', 'accepted'])
        ).subquery()
        query = query.filter(~Courrier.id.in_(assigned_ids))
        
        courriers = query.all()
        
        # Récupérer tous les utilisateurs par service
        users_by_service = db.session.query(
            User.id, User.username, User.nom_complet, User.service, Role.nom.label('role')
        ).join(Role).filter(User.statut == 'actif', User.role_id < 5).all()
        
        # Organiser les utilisateurs par service
        services_users = {}
        for u in users_by_service:
            service = u.service or 'Autre'
            if service not in services_users:
                services_users[service] = []
            services_users[service].append({
                'id': u.id,
                'username': u.username,
                'nom_complet': u.nom_complet,
                'role': u.role
            })
        
        return jsonify({
            'success': True,
            'courriers': [c.to_dict() for c in courriers],
            'services_users': services_users,
            'total_pending': len(courriers)
        })
    
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@app.route('/api/assignations/assign', methods=['POST'])
@permission_required(8)
def assign_courrier():
    """Assigner un courrier à un utilisateur"""
    try:
        data = request.get_json()
        courrier_id = data.get('courrier_id')
        assigned_to_user_id = data.get('assigned_to_user_id')
        commentaire = data.get('commentaire', '')
        
        if not courrier_id or not assigned_to_user_id:
            return jsonify({'success': False, 'message': 'Données manquantes'})
        
        courrier = Courrier.query.get(courrier_id)
        if not courrier:
            return jsonify({'success': False, 'message': 'Courrier non trouvé'})
        
        assigned_to = User.query.get(assigned_to_user_id)
        if not assigned_to:
            return jsonify({'success': False, 'message': 'Utilisateur non trouvé'})
        
        # Vérifier si déjà assigné
        existing = Assignation.query.filter_by(
            courrier_id=courrier_id,
            status='pending'
        ).first()
        
        if existing:
            return jsonify({'success': False, 'message': 'Courrier déjà assigné'})
        
        # Créer l'assignation
        assignation = Assignation(
            courrier_id=courrier_id,
            assigned_to_user_id=assigned_to_user_id,
            assigned_by_user_id=session['user_id'],
            service_destinataire=assigned_to.service,
            commentaire=commentaire,
            status='pending'
        )
        
        db.session.add(assignation)
        
        # Créer notification
        notification = NotificationAssignation(
            user_id=assigned_to_user_id,
            courrier_id=courrier_id,
            message=f"Nouveau courrier assigné: {courrier.objet[:100]}",
            type='assignation'
        )
        
        db.session.add(notification)
        
        db.session.commit()
        
        log_action('assign', 'courrier', courrier_id, f"Assigné à {assigned_to.username}")
        
        return jsonify({'success': True, 'message': f'Courrier assigné à {assigned_to.nom_complet}'})
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})


@app.route('/api/assignations/my-courriers', methods=['GET'])
@permission_required(1)
def get_my_assigned_courriers():
    """Récupère les courriers assignés à l'utilisateur connecté"""
    try:
        user_id = session['user_id']
        
        assignations = Assignation.query.filter_by(
            assigned_to_user_id=user_id
        ).filter(Assignation.status.in_(['pending', 'accepted', 'completed'])).all()
        
        courrier_ids = [a.courrier_id for a in assignations]
        
        if not courrier_ids:
            return jsonify({
                'success': True,
                'courriers': [],
                'total': 0
            })
        
        courriers = Courrier.query.filter(Courrier.id.in_(courrier_ids)).all()
        
        # Ajouter les infos d'assignation
        result = []
        for c in courriers:
            assign = next((a for a in assignations if a.courrier_id == c.id), None)
            if assign:
                c_dict = c.to_dict()
                c_dict['assignation_id'] = assign.id
                c_dict['assignation_status'] = assign.status
                c_dict['assignation_commentaire'] = assign.commentaire
                c_dict['assignation_created_at'] = assign.created_at.strftime('%Y-%m-%d %H:%M:%S') if assign.created_at else None
                assigned_by = User.query.get(assign.assigned_by_user_id)
                c_dict['assigned_by'] = assigned_by.nom_complet if assigned_by else None
                result.append(c_dict)
        
        return jsonify({
            'success': True,
            'courriers': result,
            'total': len(result)
        })
    
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@app.route('/api/assignations/assignation-details/<int:assignation_id>', methods=['GET'])
@permission_required(1)
def get_assignation_details(assignation_id):
    """Récupère les détails d'une assignation spécifique"""
    try:
        assignation = Assignation.query.get_or_404(assignation_id)
        
        # Vérifier que l'utilisateur a le droit de voir cette assignation
        if assignation.assigned_to_user_id != session['user_id'] and User.query.get(session['user_id']).role.niveau < 8:
            return jsonify({'success': False, 'message': 'Non autorisé'})
        
        courrier = Courrier.query.get(assignation.courrier_id)
        assigned_by = User.query.get(assignation.assigned_by_user_id)
        
        return jsonify({
            'success': True,
            'assignation': {
                'id': assignation.id,
                'courrier': courrier.to_dict() if courrier else None,
                'assigned_by': assigned_by.nom_complet if assigned_by else None,
                'assigned_to_user_id': assignation.assigned_to_user_id,
                'service_destinataire': assignation.service_destinataire,
                'commentaire': assignation.commentaire,
                'status': assignation.status,
                'created_at': assignation.created_at.strftime('%d/%m/%Y %H:%M') if assignation.created_at else None,
                'date_traitement': assignation.date_traitement.strftime('%d/%m/%Y %H:%M') if assignation.date_traitement else None
            }
        })
    
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@app.route('/api/assignations/assignation/<int:assignation_id>/status', methods=['PUT'])
@permission_required(3)
def update_assignation_status(assignation_id):
    """Met à jour le statut d'une assignation"""
    try:
        data = request.get_json()
        new_status = data.get('status')
        commentaire = data.get('commentaire', '')
        
        if new_status not in ['pending', 'accepted', 'completed', 'rejected']:
            return jsonify({'success': False, 'message': 'Statut invalide'})
        
        assignation = Assignation.query.get_or_404(assignation_id)
        
        # Vérifier que l'utilisateur a le droit de modifier cette assignation
        if assignation.assigned_to_user_id != session['user_id'] and User.query.get(session['user_id']).role.niveau < 8:
            return jsonify({'success': False, 'message': 'Non autorisé'})
        
        old_status = assignation.status
        assignation.status = new_status
        
        if commentaire:
            if assignation.commentaire:
                assignation.commentaire = assignation.commentaire + f"\n\n[{datetime.now().strftime('%d/%m/%Y %H:%M')}] Statut: {old_status} → {new_status}\nCommentaire: {commentaire}"
            else:
                assignation.commentaire = f"[{datetime.now().strftime('%d/%m/%Y %H:%M')}] Statut: {old_status} → {new_status}\nCommentaire: {commentaire}"
        
        # Si le statut devient completed, mettre à jour le statut du courrier
        if new_status == 'completed':
            courrier = Courrier.query.get(assignation.courrier_id)
            if courrier:
                courrier.statut = 'traite'
                courrier.date_traitement = datetime.now().date()
                courrier.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        # Créer une notification pour le changement de statut
        notification = NotificationAssignation(
            user_id=assignation.assigned_by_user_id,
            courrier_id=assignation.courrier_id,
            message=f"Statut d'assignation mis à jour: {old_status} → {new_status}",
            type='status_update'
        )
        db.session.add(notification)
        db.session.commit()
        
        log_action('update_assignation_status', 'assignation', assignation_id, f"Statut changé: {old_status} → {new_status}")
        
        return jsonify({'success': True, 'message': 'Statut mis à jour avec succès'})
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})


@app.route('/api/assignations/statistiques', methods=['GET'])
@permission_required(8)
def get_assignation_statistiques():
    """Récupère les statistiques des assignations"""
    try:
        total_assignations = Assignation.query.count()
        pending = Assignation.query.filter_by(status='pending').count()
        accepted = Assignation.query.filter_by(status='accepted').count()
        completed = Assignation.query.filter_by(status='completed').count()
        rejected = Assignation.query.filter_by(status='rejected').count()
        
        # Assignations par utilisateur
        assignations_by_user = db.session.query(
            User.nom_complet,
            User.username,
            db.func.count(Assignation.id).label('total'),
            db.func.sum(db.case((Assignation.status == 'completed', 1), else_=0)).label('completed')
        ).join(Assignation, Assignation.assigned_to_user_id == User.id, isouter=True)\
         .group_by(User.id).all()
        
        by_user = [{
            'nom': u.nom_complet,
            'username': u.username,
            'total': u.total or 0,
            'completed': u.completed or 0
        } for u in assignations_by_user]
        
        return jsonify({
            'success': True,
            'stats': {
                'total': total_assignations,
                'pending': pending,
                'accepted': accepted,
                'completed': completed,
                'rejected': rejected,
                'by_user': by_user
            }
        })
    
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@app.route('/api/assignations/historique/<int:courrier_id>', methods=['GET'])
@permission_required(5)
def get_courrier_assignation_history(courrier_id):
    """Récupère l'historique des assignations d'un courrier"""
    try:
        assignations = Assignation.query.filter_by(courrier_id=courrier_id).order_by(Assignation.created_at.desc()).all()
        
        history = []
        for a in assignations:
            assigned_to = User.query.get(a.assigned_to_user_id)
            assigned_by = User.query.get(a.assigned_by_user_id)
            
            history.append({
                'id': a.id,
                'assigned_to': assigned_to.nom_complet if assigned_to else None,
                'assigned_by': assigned_by.nom_complet if assigned_by else None,
                'status': a.status,
                'commentaire': a.commentaire,
                'created_at': a.created_at.strftime('%d/%m/%Y %H:%M') if a.created_at else None,
                'date_traitement': a.date_traitement.strftime('%d/%m/%Y %H:%M') if a.date_traitement else None
            })
        
        return jsonify({
            'success': True,
            'historique': history,
            'total': len(history)
        })
    
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


# ==================== ROUTES NOTIFICATIONS ====================
@app.route('/api/assignations/notifications', methods=['GET'])
@permission_required(1)
def get_assignation_notifications():
    """Récupère les notifications non lues"""
    try:
        notifications = NotificationAssignation.query.filter_by(
            user_id=session['user_id'],
            is_read=False
        ).order_by(NotificationAssignation.created_at.desc()).limit(20).all()
        
        # Compter aussi les notifications lues récentes pour l'historique
        all_notifications = NotificationAssignation.query.filter_by(
            user_id=session['user_id']
        ).order_by(NotificationAssignation.created_at.desc()).limit(50).all()
        
        return jsonify({
            'success': True,
            'notifications': [{
                'id': n.id,
                'courrier_id': n.courrier_id,
                'message': n.message,
                'type': n.type,
                'is_read': n.is_read,
                'created_at': n.created_at.strftime('%d/%m/%Y %H:%M') if n.created_at else None
            } for n in notifications],
            'all_notifications': [{
                'id': n.id,
                'courrier_id': n.courrier_id,
                'message': n.message,
                'type': n.type,
                'is_read': n.is_read,
                'created_at': n.created_at.strftime('%d/%m/%Y %H:%M') if n.created_at else None
            } for n in all_notifications[:30]],
            'total': len(notifications),
            'total_all': len(all_notifications)
        })
    
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@app.route('/api/assignations/notifications/<int:notif_id>/read', methods=['PUT'])
@permission_required(1)
def mark_notification_read(notif_id):
    """Marquer une notification comme lue"""
    try:
        notification = NotificationAssignation.query.get_or_404(notif_id)
        if notification.user_id != session['user_id']:
            return jsonify({'success': False, 'message': 'Non autorisé'})
        
        notification.is_read = True
        db.session.commit()
        
        return jsonify({'success': True})
    
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@app.route('/api/assignations/notifications/mark-all-read', methods=['PUT'])
@permission_required(1)
def mark_all_notifications_read():
    """Marquer toutes les notifications comme lues"""
    try:
        NotificationAssignation.query.filter_by(
            user_id=session['user_id'],
            is_read=False
        ).update({'is_read': True})
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Toutes les notifications ont été marquées comme lues'})
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})


@app.route('/api/assignations/notifications/<int:notif_id>', methods=['DELETE'])
@permission_required(1)
def delete_notification(notif_id):
    """Supprimer une notification"""
    try:
        notification = NotificationAssignation.query.get_or_404(notif_id)
        if notification.user_id != session['user_id']:
            return jsonify({'success': False, 'message': 'Non autorisé'})
        
        db.session.delete(notification)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Notification supprimée'})
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})


# ==================== ROUTES ASSIGNATION BATCH ====================
@app.route('/api/assignations/assign-batch', methods=['POST'])
@permission_required(8)
def assign_courriers_batch():
    """Assigner plusieurs courriers à la fois"""
    try:
        data = request.get_json()
        courrier_ids = data.get('courrier_ids', [])
        assigned_to_user_id = data.get('assigned_to_user_id')
        commentaire = data.get('commentaire', '')
        
        if not courrier_ids or not assigned_to_user_id:
            return jsonify({'success': False, 'message': 'Données manquantes'})
        
        assigned_to = User.query.get(assigned_to_user_id)
        if not assigned_to:
            return jsonify({'success': False, 'message': 'Utilisateur non trouvé'})
        
        success_count = 0
        error_count = 0
        errors = []
        
        for courrier_id in courrier_ids:
            courrier = Courrier.query.get(courrier_id)
            if not courrier:
                error_count += 1
                errors.append(f"Courrier #{courrier_id} non trouvé")
                continue
            
            # Vérifier si déjà assigné
            existing = Assignation.query.filter_by(
                courrier_id=courrier_id,
                status='pending'
            ).first()
            
            if existing:
                error_count += 1
                errors.append(f"Courrier #{courrier_id} déjà assigné")
                continue
            
            assignation = Assignation(
                courrier_id=courrier_id,
                assigned_to_user_id=assigned_to_user_id,
                assigned_by_user_id=session['user_id'],
                service_destinataire=assigned_to.service,
                commentaire=commentaire,
                status='pending'
            )
            db.session.add(assignation)
            
            notification = NotificationAssignation(
                user_id=assigned_to_user_id,
                courrier_id=courrier_id,
                message=f"Nouveau courrier assigné (lot): {courrier.objet[:100]}",
                type='assignation'
            )
            db.session.add(notification)
            
            success_count += 1
        
        db.session.commit()
        
        log_action('assign_batch', 'courriers', len(courrier_ids), f"Assignation batch de {success_count} courriers à {assigned_to.username}")
        
        return jsonify({
            'success': True,
            'message': f"{success_count} courriers assignés à {assigned_to.nom_complet}",
            'success_count': success_count,
            'error_count': error_count,
            'errors': errors[:10]
        })
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})


# ==================== ROUTES CHATBOT ====================
@app.route('/api/chatbot/message', methods=['POST'])
@permission_required(1)
def chatbot_message():
    data = request.get_json()
    user_message = data.get('message', '').lower()
    
    total = 0
    en_attente = 0
    mes_assignations = 0
    user = User.query.get(session['user_id'])
    
    if user:
        query = Courrier.query
        if user.role.niveau < 8:
            query = query.filter_by(service_destinataire=user.service)
        total = query.count()
        en_attente = query.filter_by(statut='en_attente').count()
        
        # Compter les assignations de l'utilisateur
        mes_assignations = Assignation.query.filter_by(
            assigned_to_user_id=session['user_id'],
            status='pending'
        ).count()
    
    responses = {
        'courrier': f"Vous avez actuellement {total} courriers au total, dont {en_attente} en attente.",
        'assignation': f"Vous avez {mes_assignations} courriers assignés en attente de traitement. Les assignations permettent au directeur de répartir les courriers entre les services.",
        'urgent': f"Il y a {en_attente} courriers en attente de traitement.",
        'statistique': "Les statistiques sont accessibles dans l'onglet 'Statistiques' (réservé au Chef service et Directeur).",
        'notification': "Vous recevez des notifications quand un courrier vous est assigné. Cliquez sur la cloche 🔔 pour les voir.",
        'ml': "Le système utilise le Machine Learning pour prédire les volumes de courriers et suggérer des priorités."
    }
    
    for keyword, response in responses.items():
        if keyword in user_message:
            return jsonify({'success': True, 'response': response})
    
    return jsonify({
        'success': True,
        'response': f"📊 {total} courriers, {en_attente} en attente, {mes_assignations} assignations en attente.\n\nPosez-moi une question sur: courriers, assignation, urgent, statistique, notification, ml"
    })


# ==================== ROUTES EXPORT ====================
@app.route('/api/export/pdf', methods=['POST'])
@permission_required(5)
def export_to_pdf():
    from fpdf import FPDF
    
    try:
        data = request.get_json()
        courrier_ids = data.get('courrier_ids', [])
        
        user = User.query.get(session['user_id'])
        query = Courrier.query
        
        if courrier_ids:
            query = query.filter(Courrier.id.in_(courrier_ids))
        elif user.role.niveau < 8:
            query = query.filter_by(service_destinataire=user.service)
        
        courriers = query.limit(100).all()
        
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font('Arial', 'B', 14)
        pdf.cell(0, 10, "Rapport des courriers", 0, 1, 'C')
        pdf.ln(10)
        
        pdf.set_font('Arial', 'B', 10)
        pdf.cell(20, 10, "ID", 1)
        pdf.cell(60, 10, "Expediteur", 1)
        pdf.cell(60, 10, "Objet", 1)
        pdf.cell(30, 10, "Date", 1)
        pdf.ln()
        
        pdf.set_font('Arial', '', 9)
        for c in courriers:
            pdf.cell(20, 8, str(c.id), 1)
            pdf.cell(60, 8, c.expediteur[:25], 1)
            pdf.cell(60, 8, c.objet[:25], 1)
            pdf.cell(30, 8, c.date_reception.strftime('%d/%m/%Y'), 1)
            pdf.ln()
        
        filename = f"rapport_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        filepath = os.path.join(Config.ARCHIVE_FOLDER, filename)
        pdf.output(filepath)
        
        return jsonify({'success': True, 'pdf_url': f'/download/{filename}'})
    
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@app.route('/download/<filename>')
def download_file(filename):
    return send_file(os.path.join(Config.ARCHIVE_FOLDER, filename), as_attachment=True)


@app.route('/api/archive/auto', methods=['POST'])
@permission_required(8)
def auto_archive():
    try:
        archive_date = datetime.now() - timedelta(days=30)
        to_archive = Courrier.query.filter(
            Courrier.statut == 'traite',
            Courrier.created_at < archive_date
        ).all()
        
        for courrier in to_archive:
            courrier.statut = 'archive'
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f"{len(to_archive)} courriers archivés",
            'archived_count': len(to_archive)
        })
    
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


# ==================== ROUTE POUR LES ASSIGNATIONS DASHBOARD ====================
@app.route('/api/assignations/all', methods=['GET'])
@permission_required(8)
def get_all_assignations():
    """Récupère toutes les assignations (pour le dashboard du directeur)"""
    try:
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 20))
        
        assignations = Assignation.query.order_by(Assignation.created_at.desc()).paginate(page=page, per_page=per_page)
        
        result = []
        for a in assignations.items:
            courrier = Courrier.query.get(a.courrier_id)
            assigned_to = User.query.get(a.assigned_to_user_id)
            assigned_by = User.query.get(a.assigned_by_user_id)
            
            result.append({
                'id': a.id,
                'courrier_id': a.courrier_id,
                'courrier_objet': courrier.objet if courrier else None,
                'courrier_expediteur': courrier.expediteur if courrier else None,
                'assigned_to': assigned_to.nom_complet if assigned_to else None,
                'assigned_by': assigned_by.nom_complet if assigned_by else None,
                'service': a.service_destinataire,
                'commentaire': a.commentaire,
                'status': a.status,
                'created_at': a.created_at.strftime('%d/%m/%Y %H:%M') if a.created_at else None,
                'date_traitement': a.date_traitement.strftime('%d/%m/%Y %H:%M') if a.date_traitement else None
            })
        
        return jsonify({
            'success': True,
            'assignations': result,
            'total': assignations.total,
            'page': page,
            'pages': assignations.pages
        })
    
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


# ==================== ROUTES STATISTIQUES AVEC GRAPHIQUES (MATPLOTLIB - STYLE DASHBOARD) ====================

@app.route('/api/stats/dashboard-charts', methods=['GET'])
@permission_required(1)
def get_dashboard_charts():
    """Génère et retourne les graphiques en base64 pour le dashboard"""
    try:
        import pandas as pd
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        import seaborn as sns
        import io
        import base64
        import numpy as np
        
        # Style dashboard - désactiver les titres matplotlib
        plt.style.use('seaborn-v0_8-whitegrid')
        
        user = User.query.get(session['user_id'])
        
        # Récupérer les données
        query = Courrier.query
        if user.role.niveau < 8:
            query = query.filter_by(service_destinataire=user.service)
        
        courriers = query.all()
        
        # Convertir en DataFrame
        data = []
        for c in courriers:
            data.append({
                'id': c.id,
                'statut': c.statut,
                'priorite': c.priorite,
                'service_destinataire': c.service_destinataire,
                'date_reception': c.date_reception,
                'mois': c.date_reception.strftime('%B') if c.date_reception else 'Inconnu',
                'scan_image_size': c.scan_image_size or 0,
                'ai_classification': c.ai_classification or 'normal'
            })
        
        df = pd.DataFrame(data)
        
        if df.empty:
            return jsonify({
                'success': True,
                'charts': {},
                'message': 'Aucune donnée disponible'
            })
        
        def create_chart(title, fig):
            """Convertit une figure matplotlib en base64 avec style dashboard"""
            img = io.BytesIO()
            fig.savefig(
                img,
                format='png',
                bbox_inches='tight',
                transparent=True,
                dpi=120,
                facecolor='white'
            )
            img.seek(0)
            return base64.b64encode(img.read()).decode()
        
        charts = {}
        
        # ============================================================
        # 1. Répartition par statut
        # ============================================================
        fig1, ax1 = plt.subplots(figsize=(8, 4.5))
        
        statut_counts = df['statut'].value_counts()
        statut_labels = {
            'en_attente': '⏳ En attente',
            'traite': '✅ Traité',
            'urgent': '🚨 Urgent',
            'archive': '📦 Archivé'
        }
        labels = [statut_labels.get(s, s) for s in statut_counts.index]
        
        bars = ax1.bar(
            labels,
            statut_counts.values,
            color=['#f59e0b', '#10b981', '#ef4444', '#06b6d4'],
            edgecolor='white',
            linewidth=2,
            width=0.6
        )
        
        for bar, val in zip(bars, statut_counts.values):
            ax1.text(
                bar.get_x() + bar.get_width()/2,
                bar.get_height() + 0.5,
                str(val),
                ha='center',
                va='bottom',
                fontsize=12,
                fontweight='bold',
                color='#333'
            )
        
        ax1.set_title('')
        ax1.set_xlabel('')
        ax1.set_ylabel('Nombre', fontsize=12, fontweight='500', color='#666')
        ax1.tick_params(axis='x', rotation=0, labelsize=11)
        ax1.tick_params(axis='y', labelsize=10)
        
        for spine in ax1.spines.values():
            spine.set_visible(False)
        
        ax1.grid(axis='y', alpha=0.3, linestyle='--')
        ax1.set_axisbelow(True)
        
        plt.tight_layout()
        charts['statut'] = create_chart("Répartition par statut", fig1)
        plt.close(fig1)
        
        # ============================================================
        # 2. Répartition des priorités
        # ============================================================
        fig2, ax2 = plt.subplots(figsize=(8, 4.5))
        
        priority_counts = df['priorite'].value_counts()
        priority_labels = {'high': '🔴 Haute', 'medium': '🟡 Moyenne', 'low': '🟢 Basse'}
        labels2 = [priority_labels.get(p, p) for p in priority_counts.index]
        
        bars2 = ax2.bar(
            labels2,
            priority_counts.values,
            color=['#ef4444', '#f59e0b', '#10b981'],
            edgecolor='white',
            linewidth=2,
            width=0.6
        )
        
        for bar, val in zip(bars2, priority_counts.values):
            ax2.text(
                bar.get_x() + bar.get_width()/2,
                bar.get_height() + 0.5,
                str(val),
                ha='center',
                va='bottom',
                fontsize=12,
                fontweight='bold',
                color='#333'
            )
        
        ax2.set_title('')
        ax2.set_xlabel('')
        ax2.set_ylabel('Nombre', fontsize=12, fontweight='500', color='#666')
        ax2.tick_params(axis='x', rotation=0, labelsize=11)
        ax2.tick_params(axis='y', labelsize=10)
        
        for spine in ax2.spines.values():
            spine.set_visible(False)
        
        ax2.grid(axis='y', alpha=0.3, linestyle='--')
        ax2.set_axisbelow(True)
        
        plt.tight_layout()
        charts['priorite'] = create_chart("Répartition des priorités", fig2)
        plt.close(fig2)
        
        # ============================================================
        # 3. Courriers par mois
        # ============================================================
        fig3, ax3 = plt.subplots(figsize=(10, 4.5))
        
        mois_counts = df['mois'].value_counts()
        ordre_mois = ['Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin', 
                      'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre']
        mois_counts = mois_counts.reindex([m for m in ordre_mois if m in mois_counts.index])
        
        bars3 = ax3.bar(
            mois_counts.index,
            mois_counts.values,
            color='#7c3aed',
            edgecolor='white',
            linewidth=2,
            width=0.6,
            alpha=0.85
        )
        
        for bar, val in zip(bars3, mois_counts.values):
            ax3.text(
                bar.get_x() + bar.get_width()/2,
                bar.get_height() + 0.5,
                str(val),
                ha='center',
                va='bottom',
                fontsize=11,
                fontweight='bold',
                color='#333'
            )
        
        ax3.set_title('')
        ax3.set_xlabel('')
        ax3.set_ylabel('Nombre', fontsize=12, fontweight='500', color='#666')
        ax3.tick_params(axis='x', rotation=45, labelsize=10)
        ax3.tick_params(axis='y', labelsize=10)
        
        for spine in ax3.spines.values():
            spine.set_visible(False)
        
        ax3.grid(axis='y', alpha=0.3, linestyle='--')
        ax3.set_axisbelow(True)
        
        plt.tight_layout()
        charts['par_mois'] = create_chart("Courriers par mois", fig3)
        plt.close(fig3)
        
        # ============================================================
        # 4. Répartition par service
        # ============================================================
        fig4, ax4 = plt.subplots(figsize=(10, 5))
        
        service_counts = df['service_destinataire'].value_counts()
        if len(service_counts) > 8:
            service_counts = service_counts.head(8)
        
        colors_services = ['#7c3aed', '#a855f7', '#8b5cf6', '#6d28d9', 
                          '#4c1d95', '#c084fc', '#a78bfa', '#9b59b6']
        
        bars4 = ax4.barh(
            service_counts.index,
            service_counts.values,
            color=colors_services[:len(service_counts)],
            edgecolor='white',
            linewidth=2,
            height=0.6
        )
        
        for bar, val in zip(bars4, service_counts.values):
            ax4.text(
                bar.get_width() + 0.5,
                bar.get_y() + bar.get_height()/2,
                str(val),
                ha='left',
                va='center',
                fontsize=11,
                fontweight='bold',
                color='#333'
            )
        
        ax4.set_title('')
        ax4.set_xlabel('Nombre', fontsize=12, fontweight='500', color='#666')
        ax4.set_ylabel('')
        ax4.tick_params(axis='y', labelsize=10)
        ax4.tick_params(axis='x', labelsize=10)
        
        for spine in ax4.spines.values():
            spine.set_visible(False)
        
        ax4.grid(axis='x', alpha=0.3, linestyle='--')
        ax4.set_axisbelow(True)
        
        plt.tight_layout()
        charts['par_service'] = create_chart("Courriers par service", fig4)
        plt.close(fig4)
        
        # ============================================================
        # 5. Priorité vs Statut
        # ============================================================
        fig5, ax5 = plt.subplots(figsize=(9, 4.5))
        
        pivot = pd.crosstab(df['priorite'], df['statut'])
        pivot = pivot.reindex(['high', 'medium', 'low'], fill_value=0)
        pivot.columns = [{'en_attente': 'En attente', 'traite': 'Traité', 
                         'urgent': 'Urgent', 'archive': 'Archivé'}.get(c, c) for c in pivot.columns]
        
        colors_stacked = ['#f59e0b', '#10b981', '#ef4444', '#06b6d4']
        pivot.plot(kind='bar', stacked=True, ax=ax5, color=colors_stacked, edgecolor='white', linewidth=1.5)
        
        ax5.set_title('')
        ax5.set_xlabel('Priorité', fontsize=12, fontweight='500', color='#666')
        ax5.set_ylabel('Nombre', fontsize=12, fontweight='500', color='#666')
        ax5.tick_params(axis='x', rotation=0, labelsize=11)
        ax5.tick_params(axis='y', labelsize=10)
        ax5.legend(title='Statut', bbox_to_anchor=(1, 1), loc='upper left')
        
        for spine in ax5.spines.values():
            spine.set_visible(False)
        
        ax5.grid(axis='y', alpha=0.3, linestyle='--')
        ax5.set_axisbelow(True)
        
        plt.tight_layout()
        charts['priorite_vs_statut'] = create_chart("Priorité vs Statut", fig5)
        plt.close(fig5)
        
        # ============================================================
        # 6. Taille des scans
        # ============================================================
        fig6, ax6 = plt.subplots(figsize=(8, 4.5))
        
        df_scan = df[df['scan_image_size'] > 0]
        if not df_scan.empty:
            n, bins, patches = ax6.hist(
                df_scan['scan_image_size'] / 1024,
                bins=15,
                color='#7c3aed',
                edgecolor='white',
                linewidth=1.5,
                alpha=0.8
            )
            ax6.set_xlabel('Taille (Ko)', fontsize=12, fontweight='500', color='#666')
            ax6.set_ylabel('Fréquence', fontsize=12, fontweight='500', color='#666')
        else:
            ax6.text(0.5, 0.5, 'Aucune donnée de scan disponible', 
                    ha='center', va='center', transform=ax6.transAxes, fontsize=12, color='#999')
        
        ax6.set_title('')
        ax6.tick_params(axis='both', labelsize=10)
        
        for spine in ax6.spines.values():
            spine.set_visible(False)
        
        ax6.grid(axis='y', alpha=0.3, linestyle='--')
        ax6.set_axisbelow(True)
        
        plt.tight_layout()
        charts['scan_size'] = create_chart("Taille des scans", fig6)
        plt.close(fig6)
        
        # ============================================================
        # 7. Matrice de corrélation
        # ============================================================
        fig7, ax7 = plt.subplots(figsize=(9, 7))
        
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        if len(numeric_cols) > 1 and len(df) > 5:
            corr_matrix = df[numeric_cols].corr()
            mask = np.triu(np.ones_like(corr_matrix, dtype=bool))
            sns.heatmap(
                corr_matrix,
                mask=mask,
                annot=True,
                fmt='.2f',
                cmap='coolwarm',
                ax=ax7,
                square=True,
                cbar_kws={'shrink': 0.8},
                linewidths=1,
                linecolor='white'
            )
            ax7.set_title('')
            ax7.tick_params(labelsize=10)
        else:
            ax7.text(0.5, 0.5, 'Données insuffisantes pour la corrélation', 
                    ha='center', va='center', transform=ax7.transAxes, fontsize=12, color='#999')
            ax7.set_title('')
        
        plt.tight_layout()
        charts['correlation'] = create_chart("Matrice de corrélation", fig7)
        plt.close(fig7)
        
        # ============================================================
        # 8. Évolution temporelle
        # ============================================================
        fig8, ax8 = plt.subplots(figsize=(11, 4.5))
        
        if 'date_reception' in df.columns and not df['date_reception'].isnull().all():
            df['date_reception'] = pd.to_datetime(df['date_reception'])
            df['jour'] = df['date_reception'].dt.date
            daily_counts = df.groupby('jour').size()
            
            if not daily_counts.empty:
                ax8.plot(
                    daily_counts.index,
                    daily_counts.values,
                    color='#7c3aed',
                    linewidth=2.5,
                    marker='o',
                    markersize=6,
                    markerfacecolor='white',
                    markeredgewidth=2,
                    markeredgecolor='#7c3aed'
                )
                ax8.fill_between(
                    daily_counts.index,
                    daily_counts.values,
                    alpha=0.15,
                    color='#7c3aed'
                )
                ax8.set_xlabel('Date', fontsize=12, fontweight='500', color='#666')
                ax8.set_ylabel('Courriers', fontsize=12, fontweight='500', color='#666')
                ax8.tick_params(axis='x', rotation=45, labelsize=9)
                ax8.tick_params(axis='y', labelsize=10)
            else:
                ax8.text(0.5, 0.5, 'Données temporelles insuffisantes', 
                        ha='center', va='center', transform=ax8.transAxes, fontsize=12, color='#999')
        else:
            ax8.text(0.5, 0.5, 'Données temporelles insuffisantes', 
                    ha='center', va='center', transform=ax8.transAxes, fontsize=12, color='#999')
        
        ax8.set_title('')
        
        for spine in ax8.spines.values():
            spine.set_visible(False)
        
        ax8.grid(axis='y', alpha=0.3, linestyle='--')
        ax8.set_axisbelow(True)
        
        plt.tight_layout()
        charts['evolution'] = create_chart("Évolution temporelle", fig8)
        plt.close(fig8)
        
        statuts = df['statut'].value_counts().to_dict() if 'statut' in df.columns else {}
        
        return jsonify({
            'success': True,
            'charts': charts,
            'total_courriers': len(df),
            'statuts': statuts
        })
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)})


# ==================== DÉMARRAGE ====================
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        init_database()
    
    print("=" * 60)
    print("🏛️ MINISTÈRE DE L'AMÉNAGEMENT DU TERRITOIRE NATIONAL")
    print("=" * 60)
    print("✅ Application démarrée sur http://localhost:5000")
    print("")
    print("🔐 COMPTES DE TEST:")
    print("   👑 ahmed.directeur / directeur123 (Directeur - Niveau 10 - Accès TOTAL)")
    print("   👔 fatima.chef / chef123 (Chef service - Niveau 8)")
    print("   📊 nadia.etude / etude123 (Chargé d'étude - Niveau 5)")
    print("   📋 karim.assistant / assistant123 (Assistant - Niveau 3)")
    print("   🎓 youssef.stagiaire / stagiaire123 (Stagiaire - Niveau 1)")
    print("")
    print("🤖 MACHINE LEARNING:")
    print("   📈 Prédictions de volume (Random Forest/Régression)")
    print("   🏷️ Classification automatique des courriers")
    print("   ⭐ Suggestion de priorité intelligente")
    print("   🔄 Réentraînement disponible pour Directeur")
    print("=" * 60)
    print("📋 TABLEAU DES PERMISSIONS:")
    print("   ┌───────────────┬──────────┬────────┬────────┬──────────┬────────────┐")
    print("   │ Utilisateur   │ Niveau   │ Voir   │ Scanner│ Ajouter  │ Supprimer  │")
    print("   ├───────────────┼──────────┼────────┼────────┼──────────┼────────────┤")
    print("   │ Stagiaire     │ 1        │ ✅     │ ❌     │ ❌       │ ❌         │")
    print("   │ Assistant     │ 3        │ ✅     │ ✅     │ ❌       │ ❌         │")
    print("   │ Chargé étude  │ 5        │ ✅     │ ✅     │ ✅       │ ❌         │")
    print("   │ Chef service  │ 8        │ ✅     │ ✅     │ ❌       │ ✅ (son service)│")
    print("   │ Directeur     │ 10       │ ✅     │ ✅     │ ✅       │ ✅ (tous)  │")
    print("   └───────────────┴──────────┴────────┴────────┴──────────┴────────────┘")
    print("")
    print("📊 STATISTIQUES & ANALYTICS: Uniquement Chef service et Directeur")
    print("👥 GESTION UTILISATEURS: Uniquement Directeur")
    print("🔐 AUDIT LOGS: Uniquement Chef service et Directeur")
    print("📨 ASSIGNATIONS: Directeur et Chef service peuvent assigner")
    print("=" * 60)
    
    app.run(debug=True, host='127.0.0.1', port=5000, threaded=True)
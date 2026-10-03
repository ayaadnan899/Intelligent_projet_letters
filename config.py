import os
# Importation de la bibliothèque os pour gérer les variables d'environnement et les chemins
from dotenv import load_dotenv
# Importation de load_dotenv pour charger les variables depuis le fichier .env
# Chargement des variables de configuration présentes dans le fichier .env
load_dotenv()

# Classe contenant toute la configuration de l'application
# Elle centralise les paramètres de sécurité, base de données, fichiers, OCR et Machine Lea
class Config:
    """Configuration centralisée de l'application"""
    
    # ==================== SECURITE ====================
    # Clé secrète utilisée par Flask pour sécuriser les sessions et les cookies
    SECRET_KEY = os.environ.get('SECRET_KEY', 'ta_cle_super_secrete_pour_production_2026')
    # Nombre de tours utilisés pour le chiffrement des mots de passe avec Bcrypt
    BCRYPT_ROUNDS = 12
    
    # ==================== BASE DE DONNEES ====================
    # Adresse du serveur MySQL
    DB_HOST = os.environ.get('DB_HOST', '127.0.0.1')
    # Nom d'utilisateur utilisé pour accéder à la base de données
    DB_USER = os.environ.get('DB_USER', 'root')
    # Mot de passe de connexion à la base de données
    DB_PASSWORD = os.environ.get('DB_PASSWORD', '')
    # Nom de la base de données utilisée par l'application
    DB_NAME = os.environ.get('DB_NAME', 'courriers_db')
    # Port de connexion du serveur MySQL
    DB_PORT = int(os.environ.get('DB_PORT', 3306))
    
    # ==================== EMAIL ====================
    # Serveur SMTP utilisé pour l'envoi des emails
    EMAIL_SERVER = os.environ.get('EMAIL_SERVER', 'smtp.gmail.com')
    # Port du serveur email
    EMAIL_PORT = int(os.environ.get('EMAIL_PORT', 587))
    # Adresse email de l'expéditeur
    EMAIL_USER = os.environ.get('EMAIL_USER', '')
    # Mot de passe du compte email
    EMAIL_PASSWORD = os.environ.get('EMAIL_PASSWORD', '')
    # Adresse email de l'administration
    ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL', 'admin@matn.gov.ma')
    # Activation ou désactivation du service email
    USE_EMAIL = os.environ.get('USE_EMAIL', 'False').lower() == 'true'
    
    # ==================== UPLOADS ====================
    # Dossier principal où seront stockés les fichiers uploadés
    UPLOAD_FOLDER = 'uploads'
    # Dossier contenant les documents scannés
    SCAN_FOLDER = 'scans'
    # Dossier utilisé pour l'archivage des courriers
    ARCHIVE_FOLDER = 'archives'
    # Taille maximale autorisée pour un fichier (16 Mo)
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
    # Extensions des fichiers autorisés dans l'application
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf'}
    # Types MIME autorisés pour vérifier la sécurité des fichiers
    ALLOWED_MIME_TYPES = {'image/jpeg', 'image/png', 'image/gif', 'application/pdf'}
    
    # ==================== SESSION ====================
    # Active ou désactive l'utilisation de cookies sécurisés HTTPS
    # False en développement, True en production
    SESSION_COOKIE_SECURE = False 
    # Empêche l'accès aux cookies depuis JavaScript
    # Protection contre certaines attaques XSS 
    SESSION_COOKIE_HTTPONLY = True
    # Protection contre les attaques CSRF
    SESSION_COOKIE_SAMESITE = 'Lax'
    # Durée de validité d'une session utilisateur (8 heures)
    PERMANENT_SESSION_LIFETIME = 28800  # 8 heures
    
    # ==================== TESSERACT OCR ====================
    # Chemin vers l'installation de Tesseract OCR
    # Utilisé pour extraire automatiquement le texte des documents scannés
    TESSERACT_CMD = os.environ.get('TESSERACT_CMD', r'C:\Program Files\Tesseract-OCR\tesseract.exe')
    # Langues utilisées par le moteur OCR
    # Français et anglais
    TESSERACT_LANGUAGES = ['fra', 'eng']
    
    # ==================== ML & ANALYTICS ====================
    # Nombre de jours utilisés pour effectuer les prévisions ML
    ML_PREDICTION_DAYS = 30
    # Nombre de jours historiques utilisés pour analyser les données
    ML_HISTORY_DAYS = 90
    # Seuil utilisé pour détecter les valeurs anormales
    ANOMALY_THRESHOLD = 2.0  # Écart-type pour détection d'anomalies
    
    # ==================== PAGINATION ====================
    # Nombre d'éléments affichés par page
    DEFAULT_PAGE_SIZE = 20
    # Nombre maximum d'éléments affichables par page
    MAX_PAGE_SIZE = 100
    
    # ==================== CACHE (Redis) ====================
    # Adresse du serveur Redis pour le système de cache
    REDIS_URL = os.environ.get('REDIS_URL', None)
    # Durée par défaut de conservation des données en cache
    CACHE_DEFAULT_TIMEOUT = 300  # 5 minutes
    # Fonction permettant de générer l'URL de connexion à MySQL
    @classmethod
    def get_database_uri(cls):
        """Retourne l'URI de connexion à la base de données"""
        return f"mysql+pymysql://{cls.DB_USER}:{cls.DB_PASSWORD}@{cls.DB_HOST}:{cls.DB_PORT}/{cls.DB_NAME}?charset=utf8mb4"
    
    # Fonction permettant de vérifier si l'extension d'un fichier est autorisée
    @classmethod
    def is_allowed_file(cls, filename):
        """Vérifie si l'extension du fichier est autorisée"""
        return '.' in filename and filename.rsplit('.', 1)[1].lower() in cls.ALLOWED_EXTENSIONS
    # Fonction permettant de vérifier le type MIME réel du fichier
    @classmethod
    def is_allowed_mime(cls, mime_type):
        """Vérifie si le type MIME est autorisé"""
        return mime_type in cls.ALLOWED_MIME_TYPES
import re
import bleach
import secrets
from functools import wraps
from flask import request, jsonify, session
from datetime import datetime
import hashlib
import hmac

# Liste blanche des tags HTML autorisés
ALLOWED_HTML_TAGS = ['b', 'strong', 'i', 'em', 'p', 'br', 'span', 'div', 'ul', 'li', 'ol']
ALLOWED_HTML_ATTRIBUTES = {'*': ['class', 'id'], 'a': ['href', 'title']}


def sanitize_input(text):
    """
    Nettoie les entrées utilisateur pour éviter XSS
    """
    if not text or not isinstance(text, str):
        return text
    
    # Nettoyage avec bleach
    text = bleach.clean(text, tags=ALLOWED_HTML_TAGS, attributes=ALLOWED_HTML_ATTRIBUTES)
    
    # Suppression des caractères dangereux
    text = re.sub(r'[<>]', '', text)
    
    # Trim
    text = text.strip()
    
    # Limiter la longueur (protection contre DoS)
    if len(text) > 10000:
        text = text[:10000]
    
    return text


def validate_email(email):
    """
    Valide le format d'un email
    """
    if not email:
        return True  # Email optionnel
    
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def validate_phone(phone):
    """
    Valide un numéro de téléphone marocain
    Formats acceptés: 06XXXXXXXX, 05XXXXXXXX, 07XXXXXXXX
    """
    if not phone:
        return True
    
    pattern = r'^(05|06|07)[0-9]{8}$'
    return bool(re.match(pattern, phone))


def validate_reference(ref):
    """
    Valide un numéro de référence
    """
    if not ref:
        return True
    
    # Format: lettres/chiffres/tirets, 5-20 caractères
    pattern = r'^[A-Z0-9\-]{5,20}$'
    return bool(re.match(pattern, ref.upper()))


def generate_csrf_token():
    """
    Génère un token CSRF
    """
    if 'csrf_token' not in session:
        session['csrf_token'] = secrets.token_hex(32)
    return session['csrf_token']


def require_csrf_token(f):
    """
    Décorateur pour vérifier le token CSRF
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Skip CSRF pour les requêtes GET et HEAD
        if request.method in ['GET', 'HEAD', 'OPTIONS']:
            return f(*args, **kwargs)
        
        token = request.headers.get('X-CSRFToken') or request.form.get('csrf_token')
        
        if not token or token != session.get('csrf_token'):
            log_security_event('csrf_failure', f"Token CSRF invalide depuis {request.remote_addr}")
            return jsonify({'success': False, 'message': 'Token CSRF invalide'}), 403
        
        return f(*args, **kwargs)
    return decorated_function


def log_security_event(event_type, details):
    """
    Logge les événements de sécurité
    """
    # Implémentation simple - pourrait être étendue avec la base de données
    print(f"[SECURITY] {datetime.now().isoformat()} - {event_type} - {details}")


def hash_data(data):
    """
    Hachage de données sensibles
    """
    if not data:
        return None
    return hashlib.sha256(data.encode()).hexdigest()


def verify_hmac(data, signature, secret_key):
    """
    Vérifie une signature HMAC
    """
    expected = hmac.new(secret_key.encode(), data.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def generate_password_reset_token(user_id):
    """
    Génère un token de réinitialisation de mot de passe
    """
    timestamp = str(int(datetime.utcnow().timestamp()))
    data = f"{user_id}:{timestamp}"
    signature = hmac.new(b'reset_secret_key', data.encode(), hashlib.sha256).hexdigest()
    return f"{data}:{signature}"


def verify_password_reset_token(token):
    """
    Vérifie un token de réinitialisation
    """
    try:
        parts = token.split(':')
        if len(parts) != 3:
            return None
        
        user_id = parts[0]
        timestamp = parts[1]
        signature = parts[2]
        
        data = f"{user_id}:{timestamp}"
        expected = hmac.new(b'reset_secret_key', data.encode(), hashlib.sha256).hexdigest()
        
        if not hmac.compare_digest(expected, signature):
            return None
        
        # Vérifier expiration (24h)
        token_time = int(timestamp)
        current_time = int(datetime.utcnow().timestamp())
        
        if current_time - token_time > 86400:
            return None
        
        return int(user_id)
    
    except Exception:
        return None


def rate_limit_key():
    """
    Clé pour le rate limiting basée sur IP ou utilisateur
    """
    if 'user_id' in session:
        return f"user_{session['user_id']}"
    return request.remote_addr
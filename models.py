from flask_sqlalchemy import SQLAlchemy 
# Importation de SQLAlchemy pour créer les modèles de base de données
# Importation de Bcrypt pour le chiffrement des mots de passe
from flask_bcrypt import Bcrypt
# Importation de datetime pour gérer les dates automatiquement
from datetime import datetime

# Création de l'objet database qui sera utilisé dans toute l'application
db = SQLAlchemy()
# Création de l'objet de chiffrement des mots de passe
bcrypt = Bcrypt()

# MODELE ROLE
# Gestion des rôles et des niveaux d'autorisation
class Role(db.Model):
    __tablename__ = 'roles'
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(50), unique=True, nullable=False)
    niveau = db.Column(db.Integer, default=1)
    description = db.Column(db.String(200))
    # Pas de colonne created_at pour compatibilité
    
    def to_dict(self):
        return {
            'id': self.id,
            'nom': self.nom,
            'niveau': self.niveau,
            'description': self.description
        }


class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)

    nom_complet = db.Column(db.String(100))
    email = db.Column(db.String(100))
    telephone = db.Column(db.String(20))
    departement = db.Column(db.String(50))
    service = db.Column(db.String(50))
    statut = db.Column(db.String(20), default='actif')

    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'))

    role = db.relationship('Role', backref='users')

    def set_password(self, password):
        self.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')

    def check_password(self, password):
        return bcrypt.check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'nom_complet': self.nom_complet,
            'email': self.email,
            'service': self.service
        }

class Courrier(db.Model):
    __tablename__ = 'courriers'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    numero_reference = db.Column(db.String(50), index=True)
    date_reception = db.Column(db.Date, nullable=False)
    expediteur = db.Column(db.String(200), nullable=False, index=True)
    email = db.Column(db.String(100))
    objet = db.Column(db.String(500), nullable=False, index=True)
    contenu = db.Column(db.Text)
    priorite = db.Column(db.Enum('low', 'medium', 'high'), default='medium')
    
    ai_classification = db.Column(db.String(100), nullable=True)
    ocr_confidence = db.Column(db.Float, default=0)
    
    statut = db.Column(db.Enum('en_attente', 'traite', 'urgent', 'archive'), default='en_attente')
    service_destinataire = db.Column(db.String(50), index=True)
    scan_image_path = db.Column(db.String(500))
    scan_image_name = db.Column(db.String(255))
    scan_image_size = db.Column(db.Integer)
    scan_image_type = db.Column(db.String(10))
    original_filename = db.Column(db.String(255))
    scan_score = db.Column(db.Integer, default=0)
    scan_verdict = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    createur = db.relationship('User', backref='courriers_list')
    
    def to_dict(self):
        return {
            'id': self.id,
            'numero_reference': self.numero_reference,
            'date_reception': self.date_reception.strftime('%Y-%m-%d') if self.date_reception else None,
            'expediteur': self.expediteur,
            'email': self.email,
            'objet': self.objet,
            'contenu': self.contenu,
            'priorite': self.priorite,
            'statut': self.statut,
            'service_destinataire': self.service_destinataire,
            'scan_image_path': self.scan_image_path,
            'scan_image_name': self.scan_image_name,
            'scan_score': self.scan_score,
            'scan_verdict': self.scan_verdict,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'createur_nom': self.createur.nom_complet if self.createur else None
        }


class AuditLog(db.Model):
    __tablename__ = 'audit_logs'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    action = db.Column(db.String(50), nullable=False)
    entity_type = db.Column(db.String(50))
    entity_id = db.Column(db.Integer)
    details = db.Column(db.Text)
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    user = db.relationship('User', backref='audit_logs_list')
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'action': self.action,
            'entity_type': self.entity_type,
            'entity_id': self.entity_id,
            'details': self.details,
            'ip_address': self.ip_address,
            'created_at': self.created_at.strftime('%d/%m/%Y %H:%M:%S') if self.created_at else None
        }


class ScanHistory(db.Model):
    __tablename__ = 'scan_history'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    filename = db.Column(db.String(255))
    extracted_text = db.Column(db.Text)
    confidence_score = db.Column(db.Integer)
    processing_time_ms = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    user = db.relationship('User', backref='scan_history_list')

class Assignation(db.Model):
    """Modèle des assignations de courriers"""
    __tablename__ = 'assignations'
    
    id = db.Column(db.Integer, primary_key=True)
    courrier_id = db.Column(db.Integer, db.ForeignKey('courriers.id'), nullable=False)
    assigned_to_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    assigned_by_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    service_destinataire = db.Column(db.String(50))
    status = db.Column(db.Enum('pending', 'accepted', 'rejected', 'completed'), default='pending')
    commentaire = db.Column(db.Text)
    date_assignation = db.Column(db.DateTime, default=datetime.utcnow)
    date_traitement = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relations
    courrier = db.relationship('Courrier', backref='assignations', foreign_keys=[courrier_id])
    assigned_to = db.relationship('User', foreign_keys=[assigned_to_user_id], backref='assignations_recues')
    assigned_by = db.relationship('User', foreign_keys=[assigned_by_user_id], backref='assignations_envoyees')
    
    def to_dict(self):
        return {
            'id': self.id,
            'courrier_id': self.courrier_id,
            'assigned_to_user_id': self.assigned_to_user_id,
            'assigned_to_name': self.assigned_to.nom_complet if self.assigned_to else None,
            'assigned_by_name': self.assigned_by.nom_complet if self.assigned_by else None,
            'status': self.status,
            'commentaire': self.commentaire,
            'date_assignation': self.date_assignation.strftime('%d/%m/%Y %H:%M') if self.date_assignation else None,
            'date_traitement': self.date_traitement.strftime('%d/%m/%Y %H:%M') if self.date_traitement else None
        }


class NotificationAssignation(db.Model):
    """Modèle des notifications d'assignation"""
    __tablename__ = 'notifications_assignation'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    courrier_id = db.Column(db.Integer, db.ForeignKey('courriers.id'), nullable=False)
    message = db.Column(db.Text)
    type = db.Column(db.String(50), default='assignation')
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relations
    user = db.relationship('User', foreign_keys=[user_id], backref='notifications_assignation')
    courrier = db.relationship('Courrier', foreign_keys=[courrier_id], backref='notifications_assignation')
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'courrier_id': self.courrier_id,
            'message': self.message,
            'type': self.type,
            'is_read': self.is_read,
            'created_at': self.created_at.strftime('%d/%m/%Y %H:%M') if self.created_at else None
        }
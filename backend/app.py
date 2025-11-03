import os
import logging
from flask import Flask, render_template, request, jsonify
from werkzeug.utils import secure_filename
from datetime import datetime
from telegram import Bot
from telegram.request import HTTPXRequest
import asyncio

# Configuration de l'application
app = Flask(__name__)
app.secret_key = 'votre_cle_secrete_ici'

# Configuration Telegram - À REMPLACER AVEC VOS VRAIES CLÉS
TELEGRAM_BOT_TOKEN = 'votre_bot_token_ici'
TELEGRAM_CHAT_ID = 'votre_chat_id_ici'

# Configuration des uploads
UPLOAD_FOLDERS = {
    'releves_notes': 'uploads/releves_notes',
    'autres_certifications': 'uploads/certifications',
    'passeport_cni': 'uploads/documents_identite'
}

ALLOWED_EXTENSIONS = {'pdf', 'jpg', 'jpeg', 'png', 'doc', 'docx'}

# Création des dossiers d'upload
for folder in UPLOAD_FOLDERS.values():
    os.makedirs(folder, exist_ok=True)

app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

async def send_telegram_message(message):
    """Envoyer un message à Telegram"""
    try:
        request = HTTPXRequest()
        bot = Bot(token=TELEGRAM_BOT_TOKEN, request=request)
        await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message, parse_mode='HTML')
        return True
    except Exception as e:
        logging.error(f"Erreur Telegram: {e}")
        return False

async def send_telegram_document(document_path, caption=""):
    """Envoyer un document à Telegram"""
    try:
        request = HTTPXRequest()
        bot = Bot(token=TELEGRAM_BOT_TOKEN, request=request)
        with open(document_path, 'rb') as doc:
            await bot.send_document(chat_id=TELEGRAM_CHAT_ID, document=doc, caption=caption)
        return True
    except Exception as e:
        logging.error(f"Erreur envoi document Telegram: {e}")
        return False

def save_uploaded_file(file, folder_type):
    """Sauvegarder un fichier uploadé"""
    if file and file.filename != '' and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_")
        unique_filename = timestamp + filename
        
        upload_folder = UPLOAD_FOLDERS[folder_type]
        file_path = os.path.join(upload_folder, unique_filename)
        file.save(file_path)
        return file_path
    return None

def format_form_data(form_data, files_info):
    """Formatter les données du formulaire pour Telegram"""
    message = f"""
📋 <b>NOUVELLE CANDIDATURE REÇUE</b>
⏰ {datetime.now().strftime("%d/%m/%Y %H:%M:%S")}

👤 <b>INFORMATIONS PERSONNELLES</b>
├ Nom: {form_data.get('nom', 'N/A')}
├ Prénom: {form_data.get('prenom', 'N/A')}
├ Téléphone: {form_data.get('telephone', 'N/A')}
├ Email: {form_data.get('email', 'N/A')}
├ Pays: {form_data.get('pays', 'N/A')}
├ Ville: {form_data.get('ville', 'N/A')}
├ Quartier: {form_data.get('quartier', 'N/A')}
├ Père: {form_data.get('nomPere', 'N/A')}
├ Mère: {form_data.get('nomMere', 'N/A')}
└ Statut: {form_data.get('statut', 'N/A')}

🚨 <b>CONTACT D'URGENCE</b>
├ Nom: {form_data.get('urgenceNom', 'N/A')}
├ Prénom: {form_data.get('urgencePrenom', 'N/A')}
├ Téléphone: {form_data.get('urgenceTelephone', 'N/A')}
├ Email: {form_data.get('urgenceEmail', 'N/A')}
└ Lien: {form_data.get('urgenceLien', 'N/A')}

🎓 <b>INFORMATIONS ACADÉMIQUES</b>
├ Établissement Bac: {form_data.get('etablissementBac', 'N/A')}
├ Diplômes: 
{form_data.get('diplomes', 'N/A')}

📎 <b>FICHIERS JOINTS</b>
├ Relevés de notes: {files_info.get('releves_notes', 'Non fourni')}
├ Autres certifications: {files_info.get('autres_certifications', 'Non fourni')}
└ Pièce d'identité: {files_info.get('passeport_cni', 'Non fourni')}
"""
    return message



@app.route('/submit', methods=['POST'])
def submit_form():
    try:
        # Récupération des données du formulaire
        form_data = request.form.to_dict()
        
        # Traitement des fichiers
        files_info = {}
        file_paths = {}

        # Relevés de notes
        if 'relevesNotes' in request.files:
            file = request.files['relevesNotes']
            file_path = save_uploaded_file(file, 'releves_notes')
            if file_path:
                files_info['releves_notes'] = os.path.basename(file_path)
                file_paths['releves_notes'] = file_path

        # Autres certifications
        if 'autresCertifications' in request.files:
            file = request.files['autresCertifications']
            if file.filename != '':
                file_path = save_uploaded_file(file, 'autres_certifications')
                if file_path:
                    files_info['autres_certifications'] = os.path.basename(file_path)
                    file_paths['autres_certifications'] = file_path
            else:
                files_info['autres_certifications'] = 'Non fourni'

        # Passeport/CNI
        if 'passeportCNI' in request.files:
            file = request.files['passeportCNI']
            file_path = save_uploaded_file(file, 'passeport_cni')
            if file_path:
                files_info['passeport_cni'] = os.path.basename(file_path)
                file_paths['passeport_cni'] = file_path

        # Formatage du message pour Telegram
        telegram_message = format_form_data(form_data, files_info)

        # Envoi à Telegram
        async def send_all():
            # Envoi du message principal
            success = await send_telegram_message(telegram_message)
            
            # Envoi des fichiers
            for file_type, file_path in file_paths.items():
                caption = f"{file_type.replace('_', ' ').title()} - {form_data.get('prenom', '')} {form_data.get('nom', '')}"
                await send_telegram_document(file_path, caption)
            
            return success

        # Exécution asynchrone
        success = asyncio.run(send_all())

        if success:
            return jsonify({
                'success': True,
                'message': 'Formulaire soumis avec succès ! Vos informations ont été envoyées.'
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Erreur lors de l\'envoi. Veuillez réessayer.'
            }), 500

    except Exception as e:
        logging.error(f"Erreur lors du traitement du formulaire: {e}")
        return jsonify({
            'success': False,
            'message': 'Une erreur est survenue. Veuillez réessayer.'
        }), 500

if __name__ == '__main__':
    
    app.run(debug=True, host='0.0.0.0', port=5000)
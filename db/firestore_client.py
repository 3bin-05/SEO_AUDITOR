import os
import json
import logging
import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud.firestore_v1.base_query import FieldFilter

logger = logging.getLogger(__name__)

# Global firestore client reference
db = None

def init_firestore():
    """
    Initializes the Firebase Admin SDK using credentials from environment variables.
    Supports:
    1. Automatic detection of *firebase-adminsdk*.json files in the root folder.
    2. Filepath paths provided in the FIREBASE_CREDENTIALS_JSON variable.
    3. Inline JSON credentials strings.
    """
    global db
    if db is not None:
        return db
        
    creds_json = os.getenv("FIREBASE_CREDENTIALS_JSON")
    
    # 1. Automatic detection fallback if no env var is set
    if not creds_json:
        import glob
        json_files = glob.glob("*firebase-adminsdk*.json")
        if json_files:
            creds_json = json_files[0]
            logger.info(f"Auto-detected Firebase credentials file: {creds_json}")
            
    if not creds_json:
        logger.warning("FIREBASE_CREDENTIALS_JSON env var is missing and no service account files were detected; database operations are disabled.")
        return None
        
    try:
        # Check if Firebase App is already initialized
        if not firebase_admin._apps:
            # 2. Check if it points to an existing file
            if os.path.exists(creds_json):
                with open(creds_json, 'r') as f:
                    creds_dict = json.load(f)
                cred = credentials.Certificate(creds_dict)
            else:
                # 3. Parse as inline JSON string
                creds_dict = json.loads(creds_json)
                cred = credentials.Certificate(creds_dict)
                
            firebase_admin.initialize_app(cred)
            logger.info("Firebase Admin SDK initialized successfully.")
        db = firestore.client()
        return db
    except Exception as e:
        logger.error(f"Failed to initialize Firebase Admin SDK: {e}")
        return None

def save_scan(user_id: str, url: str, result_dict: dict, username: str = None) -> bool:
    """
    Saves a scan's score, grade, and breakdown to Firestore,
    and updates/creates the user's metadata and scan counter.
    """
    client = init_firestore()
    if client is None:
        logger.warning("Firestore client not available; scan was not saved.")
        return False
        
    try:
        user_id = str(user_id)
        
        # 1. Update user profile document (set first_seen, update username, increment scan count)
        user_ref = client.collection("users").document(user_id)
        user_snapshot = user_ref.get()
        
        if not user_snapshot.exists:
            user_ref.set({
                "first_seen": firestore.SERVER_TIMESTAMP,
                "username": username or "",
                "scan_count": 1
            })
        else:
            update_data = {"scan_count": firestore.Increment(1)}
            if username:
                update_data["username"] = username
            user_ref.update(update_data)
            
        # 2. Add scan result document
        scan_data = {
            "user_id": user_id,
            "url": url,
            "score": int(result_dict.get("score", 0)),
            "grade": result_dict.get("grade", "F"),
            "breakdown": result_dict.get("breakdown", []),
            "scanned_at": firestore.SERVER_TIMESTAMP
        }
        client.collection("scans").add(scan_data)
        logger.info(f"Scan for user {user_id} and URL {url} successfully saved to Firestore.")
        return True
    except Exception as e:
        logger.error(f"Failed to save scan to Firestore: {e}")
        return False

def get_history(user_id: str, limit: int = 5) -> list:
    """
    Retrieves the last N scans for a given user from Firestore,
    ordered by scanned_at descending.
    """
    client = init_firestore()
    if client is None:
        logger.warning("Firestore client not available; returning empty history.")
        return []
        
    try:
        user_id = str(user_id)
        scans_ref = client.collection("scans")
        query = scans_ref.where(filter=FieldFilter("user_id", "==", user_id))\
                         .order_by("scanned_at", direction=firestore.Query.DESCENDING)\
                         .limit(limit)
                         
        docs = query.stream()
        results = []
        for doc in docs:
            data = doc.to_dict()
            data["id"] = doc.id
            results.append(data)
        return results
    except Exception as e:
        logger.error(f"Failed to query scan history: {e}")
        return []

def get_last_scan(user_id: str) -> dict:
    """
    Retrieves the single most recent scan for a given user from Firestore.
    """
    client = init_firestore()
    if client is None:
        logger.warning("Firestore client not available; returning empty last scan.")
        return None
        
    try:
        user_id = str(user_id)
        scans_ref = client.collection("scans")
        query = scans_ref.where(filter=FieldFilter("user_id", "==", user_id))\
                         .order_by("scanned_at", direction=firestore.Query.DESCENDING)\
                         .limit(1)
                         
        docs = list(query.stream())
        if docs:
            data = docs[0].to_dict()
            data["id"] = docs[0].id
            return data
        return None
    except Exception as e:
        logger.error(f"Failed to query last scan: {e}")
        return None

def delete_history(user_id: str) -> bool:
    """
    Deletes all scan history documents for a user from Firestore
    and resets their user scan counter.
    """
    client = init_firestore()
    if client is None:
        logger.warning("Firestore client not available; unable to delete history.")
        return False
        
    try:
        user_id = str(user_id)
        scans_ref = client.collection("scans")
        query = scans_ref.where(filter=FieldFilter("user_id", "==", user_id))
        
        # Batch delete scans
        batch = client.batch()
        docs = query.stream()
        count = 0
        for doc in docs:
            batch.delete(doc.reference)
            count += 1
            if count >= 500:  # Firestore batch limits
                batch.commit()
                batch = client.batch()
                count = 0
        if count > 0:
            batch.commit()
            
        # Reset count in user profile document
        user_ref = client.collection("users").document(user_id)
        if user_ref.get().exists:
            user_ref.update({"scan_count": 0})
            
        logger.info(f"Scan history and counts for user {user_id} deleted successfully.")
        return True
    except Exception as e:
        logger.error(f"Failed to delete history: {e}")
        return False

"""
Decision log storage via Firebase Firestore.

Works in three modes, checked in this order, so the app runs correctly
at every stage of your setup:
  1. FIREBASE_CREDENTIALS_JSON env var set (production / Railway) —
     parses the JSON directly, no file needed.
  2. FIREBASE_CREDENTIALS_PATH env var points to a real local file
     (local development after you've downloaded your Firebase key).
  3. Neither present — falls back to an in-memory list so the whole app
     (including the Decision Log UI) still works before you've set up
     Firebase at all. You'll see a console warning, and logs won't
     persist across backend restarts, but nothing breaks.
"""

import os
import json
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

_firestore_client = None
_use_memory_fallback = False
_memory_log = []  # used only in fallback mode


def init_db():
    global _firestore_client, _use_memory_fallback

    firebase_enabled = os.getenv("FIREBASE_ENABLED", "false").lower() in ("1", "true", "yes", "on")
    creds_json = os.getenv("FIREBASE_CREDENTIALS_JSON")
    creds_path = os.getenv("FIREBASE_CREDENTIALS_PATH")

    if not firebase_enabled:
        _use_memory_fallback = True
        print("[database] Firebase disabled by FIREBASE_ENABLED; using in-memory decision log.")
        return

    try:
        if creds_json:
            import firebase_admin
            from firebase_admin import credentials, firestore

            if firebase_admin._apps:
                _firestore_client = firestore.client()
                return

            cred_dict = json.loads(creds_json)
            cred = credentials.Certificate(cred_dict)
            firebase_admin.initialize_app(cred)
            _firestore_client = firestore.client()
            print("[database] Firebase initialized from FIREBASE_CREDENTIALS_JSON.")
        elif creds_path and os.path.exists(creds_path):
            import firebase_admin
            from firebase_admin import credentials, firestore

            if firebase_admin._apps:
                _firestore_client = firestore.client()
                return

            cred = credentials.Certificate(creds_path)
            firebase_admin.initialize_app(cred)
            _firestore_client = firestore.client()
            print("[database] Firebase initialized from local credentials file.")
        else:
            _use_memory_fallback = True
            print("[database] WARNING: No Firebase credentials found. Using in-memory "
                  "decision log (won't persist across restarts). See "
                  "docs/MASTER_SETUP_CHECKLIST.md Phase 0 to set up Firebase.")
    except Exception as e:
        _use_memory_fallback = True
        print(f"[database] WARNING: Firebase init failed ({e}). Using in-memory fallback.")


def log_decision(sim_timestamp: str, conflict_type: str, trains_involved: list,
                  action_taken: str, reason: str, resolved_by: str):
    entry = {
        "sim_timestamp": sim_timestamp,
        "conflict_type": conflict_type,
        "trains_involved": trains_involved,
        "action_taken": action_taken,
        "reason": reason,
        "resolved_by": resolved_by,
        "created_at": datetime.utcnow().isoformat(),
    }

    if _use_memory_fallback or _firestore_client is None:
        _memory_log.insert(0, entry)
        del _memory_log[200:]  # cap in-memory size
        return

    try:
        _firestore_client.collection("decision_log").add(entry)
    except Exception as e:
        print(f"[database] Firestore write failed ({e}), falling back to memory for this entry.")
        _memory_log.insert(0, entry)
        del _memory_log[200:]


def get_logs(train_no: str = None, limit: int = 100) -> list:
    if _use_memory_fallback or _firestore_client is None:
        results = _memory_log
        if train_no:
            results = [e for e in results if train_no in e.get("trains_involved", [])]
        return results[:limit]

    try:
        query = _firestore_client.collection("decision_log").order_by(
            "created_at", direction="DESCENDING"
        ).limit(limit)
        if train_no:
            query = query.where("trains_involved", "array_contains", train_no)
        return [doc.to_dict() for doc in query.stream()]
    except Exception as e:
        print(f"[database] Firestore read failed ({e}), returning in-memory log instead.")
        return _memory_log[:limit]


init_db()

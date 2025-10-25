import firebase_admin
from firebase_admin import credentials, firestore
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Initialize Firebase Admin SDK
cred_path = os.getenv("FIREBASE_SERVICE_ACCOUNT_KEY_PATH")
cred = credentials.Certificate(cred_path)
firebase_admin.initialize_app(cred)

# Get a reference to the Firestore database
db = firestore.client()

# Define collection names
CLOTH_COLLECTION = "cloth_purchases"
INVENTORY_COLLECTION = "inventory"
SALES_COLLECTION = "sales"
PRODUCTION_COLLECTION = "production_tracking"
DESIGN_COLLECTION = "designs"
EXPENSES_COLLECTION = "expenses"

# irn_genrator.py
import requests
import json
from config_manager import load_config, get_api_credentials, IRP_SANDBOX_URL, IRP_PRODUCTION_URL # Import base URLs

CONFIG = load_config() # Load config which includes [IRP_API] section

# --- Determine Base URL based on Mode ---
IRP_MODE = CONFIG['IRP_API'].get('Mode', 'SANDBOX').upper() # Default to SANDBOX if missing
BASE_URL = IRP_SANDBOX_URL if IRP_MODE == 'SANDBOX' else IRP_PRODUCTION_URL

# --- Construct Full API Endpoints using [IRP_API] section ---
# Use the paths defined in config_manager defaults or config.ini
AUTH_PATH = CONFIG['IRP_API'].get('AuthPath', '/ewaybillapi/v1.04/auth') # Use default path if missing
GENERATE_PATH = CONFIG['IRP_API'].get('GeneratePath', '/ewaybillapi/v1.04/invoice') # Use default path if missing

IRP_AUTH_ENDPOINT = f"{BASE_URL}{AUTH_PATH}"
IRP_GENERATE_ENDPOINT = f"{BASE_URL}{GENERATE_PATH}"
# Add others if needed (Cancel, GetIrnDetails etc.)
# IRP_CANCEL_ENDPOINT = f"{BASE_URL}{CONFIG['IRP_API'].get('CancelPath', '/ewaybillapi/v1.04/invoice/cancel')}"
# IRP_GETIRN_ENDPOINT = f"{BASE_URL}{CONFIG['IRP_API'].get('GetIrnDetailsPath', '/ewaybillapi/v1.04/invoice/irn')}"
# IRP_GETGSTIN_ENDPOINT = f"{BASE_URL}{CONFIG['IRP_API'].get('GetGstinDetailsPath', '/ewaybillapi/v1.04/master/gstin')}"


# Placeholder for authentication token (This token is from the IRP, not the GSP itself unless GSP acts as pure proxy)
IRP_AUTH_TOKEN = None # Renamed for clarity
SEK = None # Session Encryption Key, often received with auth token

# --- Authentication Function (Now targeting IRP Auth) ---
def authenticate_irp():
    """
    Authenticates with the IRP Auth endpoint using credentials.
    Retrieves AuthToken and Session Encryption Key (SEK).
    """
    global IRP_AUTH_TOKEN, SEK
    username, password = get_api_credentials()
    user_gstin = CONFIG['IRP_API'].get('UserGstin') # Get the registered GSTIN

    if not username or not password:
        raise ValueError("IRP API credentials (Username/Password) not set in .env or keyring.")
    if not user_gstin:
        raise ValueError("User GSTIN not set in config (IRP_API section) or .env.")

    # --- Construct IRP Auth Request ---
    headers = {
        'Content-Type': 'application/json',
        'Gstin': user_gstin # User GSTIN often required in header for auth
    }
    payload = {
        "action": "AUTH",
        "username": username,
        "password": password
        # "forceRefreshAccessToken": "false" # Optional
    }
    print(f"Attempting IRP Authentication to: {IRP_AUTH_ENDPOINT}")
    print(f"Auth Headers (excluding sensitive): Gstin={user_gstin}")
    # print(f"Auth Payload: {json.dumps(payload)}") # Avoid logging password

    try:
        response = requests.post(IRP_AUTH_ENDPOINT, headers=headers, json=payload, timeout=30)
        print(f"Auth Response Status Code: {response.status_code}")
        # print(f"Auth Response Body: {response.text}") # Debug carefully

        response_data = response.json()

        if response.status_code == 200 and response_data.get("Status") == 1 and response_data.get("Data"):
            auth_data = response_data["Data"]
            IRP_AUTH_TOKEN = auth_data.get("AuthToken")
            SEK = auth_data.get("Sek") # Session Encryption Key
            expiry = auth_data.get("TokenExpiry") # Usually in minutes

            if not IRP_AUTH_TOKEN or not SEK:
                 raise ValueError("AuthToken or SEK missing in successful IRP auth response.")

            print(f"IRP Authentication Successful. Token expires in {expiry} minutes.")
            return True
        else:
            error_code = response_data.get("error", {}).get("error_cd", response_data.get("ErrorDetails", [{}])[0].get("ErrorCode", "N/A"))
            error_msg = response_data.get("error", {}).get("message", response_data.get("ErrorDetails", [{}])[0].get("ErrorMessage", "Unknown Error"))
            full_error = f"Code: {error_code}, Message: {error_msg}"
            print(f"IRP Authentication Failed: {full_error}")
            # print(f"Response Body: {response.text}") # Log full error details if needed
            raise ConnectionError(f"IRP Authentication Failed: {full_error}")

    except requests.exceptions.RequestException as e:
        print(f"IRP Authentication network error: {e}")
        raise ConnectionError(f"Network error during IRP authentication: {e}")
    except json.JSONDecodeError:
         print(f"Failed to decode IRP Auth JSON response. Status: {response.status_code}, Body:\n{response.text}")
         raise ValueError("Invalid JSON response from IRP Authentication.")
    except Exception as e:
        print(f"An unexpected error occurred during IRP authentication: {e}")
        raise


# --- format_invoice_json function remains the same ---
def format_invoice_json(invoice_tally_data):
    # ... (Keep your existing JSON formatting logic) ...
    # !!! ENSURE THIS MAPS CORRECTLY TO IRP SCHEMA v1.1 !!!
    # You MUST get all required details like Seller/Buyer GSTIN, addresses, HSN, rates etc.
    # from the Tally data ('raw_data' in tally_connector is a good place to start).
    print(f"Formatting JSON for Voucher: {invoice_tally_data.get('voucher_no', 'N/A')}")

    # --- Placeholder JSON structure ---
    # !!! THIS IS EXTREMELY SIMPLIFIED - REPLACE WITH ACTUAL IRP SCHEMA MAPPING !!!
    json_payload = {
        "Version": "1.1",
        "TranDtls": {
            "TaxSch": "GST",
            "SupTyp": "B2B" # Determine from Tally data (B2B, SEZWP, SEZOP, EXPWP, EXPOP, DEXP)
            # "RegRev": "N", # Default "N", set "Y" for reverse charge
            # "IgstOnIntra": "N" # Default "N", set "Y" if IGST applicable for intra-state for SEZ
        },
        "DocDtls": {
            "Typ": "INV", # Determine Type (INV, CRN, DBN) from Tally Voucher Type
            "No": str(invoice_tally_data.get('voucher_no', '')), # Ensure string
            "Dt": "25/10/2023" # !!! Needs proper date formatting DD/MM/YYYY from invoice_tally_data['date'] !!!
        },
        "SellerDtls": {
            "Gstin": CONFIG['IRP_API'].get('UserGstin'), # !!! USE CONFIGURED GSTIN !!!
            "LglNm": "SELLER_LEGAL_NAME_FROM_TALLY_COMPANY", # !!! Get from Tally Company object !!!
            "TrdNm": "SELLER_TRADE_NAME_IF_DIFFERENT",
            "Addr1": "SELLER_ADDR1", # !!! Get from Tally Company object !!!
            "Addr2": "SELLER_ADDR2", # Optional
            "Loc": "SELLER_LOCATION", # !!! Get from Tally Company object !!!
            "Pin": 560001, # !!! Get from Tally Company object (needs to be integer) !!!
            "Stcd": "29", # !!! Get State Code from Tally Company object !!!
            "Ph": "9999988888", # Optional
            "Em": "seller@example.com" # Optional
        },
         "BuyerDtls": {
            "Gstin": "BUYER_GSTIN_FROM_PARTY", # !!! Get from Tally Party Ledger !!!
            "LglNm": invoice_tally_data.get('party_name', ''), # !!! Get Legal Name from Party Ledger !!!
            "TrdNm": "BUYER_TRADE_NAME_IF_DIFFERENT",
            "Pos": "05", # !!! Place of Supply (State Code) - Determine from Tally Invoice !!! CRITICAL
            "Addr1": "BUYER_ADDR1", # !!! Get from Party Ledger !!!
            "Addr2": "BUYER_ADDR2", # Optional
            "Loc": "BUYER_LOCATION", # !!! Get from Party Ledger !!!
            "Pin": 110001, # !!! Get from Party Ledger (needs to be integer) !!!
            "Stcd": "07", # !!! Get State Code from Party Ledger !!!
            "Ph": "7777766666", # Optional
            "Em": "buyer@example.com" # Optional
        },
        # --- Item List - Requires iterating through voucher inventory/ledger entries ---
        "ItemList": [
            # ... (Your item details - GET THESE FROM TALLY RAW DATA) ...
             {
                "SlNo": "1", # Serial number string
                "PrdDesc": "Product A Description", # Optional
                "IsServc": "N", # "Y" for service, "N" for goods
                "HsnCd": "9983", # String - !!! GET FROM TALLY ITEM/LEDGER !!!
                "Qty": 10.0, # Optional, Numeric
                "Unit": "NOS", # Optional, Unit Code (PCS, NOS, KGS etc) - !!! GET FROM TALLY !!!
                "UnitPrice": 500.0, # Numeric
                "TotAmt": 5000.0, # UnitPrice * Qty (Numeric)
                "Discount": 0.0, # Optional, Numeric
                "PreTaxVal": 5000.0, # TotAmt - Discount (If applicable)
                "AssAmt": 5000.0, # Taxable Value (Numeric) = AssAmt in Tally
                "GstRt": 18.0, # Numeric (e.g., 18.0 for 18%) - !!! GET FROM TALLY !!!
                "IgstAmt": 900.0, # Numeric - !!! Calculate/Get from Tally !!!
                "CgstAmt": 0.0, # Numeric - !!! Calculate/Get from Tally !!!
                "SgstAmt": 0.0, # Numeric - !!! Calculate/Get from Tally !!!
                # ... other item fields ...
                "TotItemVal": 5900.0, # AssAmt + GstAmts + CesAmts + OthChrg (Numeric) - !!! Calculate/Get from Tally !!!
            },
        ],
         "ValDtls": {
             # ... (Your value details - GET/CALCULATE FROM TALLY) ...
            "AssVal": 5000.0, # Sum of AssAmt for all items - !!! Calculate/Get from Tally !!!
            "CgstVal": 0.0, # Sum of CgstAmt - !!! Calculate/Get from Tally !!!
            "SgstVal": 0.0, # Sum of SgstAmt - !!! Calculate/Get from Tally !!!
            "IgstVal": 900.0, # Sum of IgstAmt - !!! Calculate/Get from Tally !!!
            "CesVal": 0.0, # Sum of CesAmt + CesNonAdvlAmt - !!! Calculate/Get from Tally !!!
            "StCesVal": 0.0, # Sum of StateCesAmt + StateCesNonAdvlAmt - !!! Calculate/Get from Tally !!!
            "Discount": 0.0, # Optional, Total discount given at invoice level
            "OthChrg": 0.0, # Optional, Other charges at invoice level not included in item level
            "RndOffAmt": 0.0, # Optional, Numeric (+/-) - !!! Get from Tally !!!
            "TotInvVal": 5900.0, # Total Invoice Value = AssVal + All Taxes + Ces + OthChrg + RndOffAmt - Discount - !!! Must match Tally Amount !!!
            "TotInvValFc": 0.0 # Optional, For Export Invoices Only
        }
        # Add ShipDtls, DispDtls, ExpDtls, EwbDtls if applicable
    }
    # --- E-Invoice Payload Encryption (Standard IRP Requirement) ---
    # You need to encrypt the json_payload using the SEK from authentication
    # Usually AES-256-CBC encryption, base64 encoded.
    # This requires the 'cryptography' library. Implement this carefully!
    # encrypted_payload = encrypt_payload(json.dumps(json_payload), SEK) # Placeholder
    # final_data_to_send = json.dumps({"Data": encrypted_payload})

    # --- FOR NOW: Return unencrypted JSON string for structure testing ---
    # !!! REPLACE THIS WITH ENCRYPTED PAYLOAD LOGIC LATER !!!
    final_data_to_send = json.dumps({"Data": json.dumps(json_payload)}) # Simulating structure

    return final_data_to_send


def generate_irn(encrypted_json_payload_str): # Pass the { "Data": "encrypted..." } structure
    """Sends the formatted and encrypted JSON to the IRP Generate endpoint."""
    if not IRP_AUTH_TOKEN or not SEK: # Check for IRP token and SEK
        print("IRP Authentication token/SEK not available. Attempting authentication...")
        if not authenticate_irp(): # Use IRP auth function
            raise ConnectionError("IRP Authentication Failed. Cannot generate IRN.")

    username, _ = get_api_credentials() # Still needed for headers
    user_gstin = CONFIG['IRP_API'].get('UserGstin')

    # --- Construct IRP Request Headers ---
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'authtoken': IRP_AUTH_TOKEN, # Auth token from IRP
        'user_name': username,       # API Username
        'Gstin': user_gstin,         # Your registered GSTIN
        # 'Irn': '...' # Required for Cancel IRN, Get IRN Details etc. Not for Generate.
        # Add other headers if required by specific GSP/IRP implementation (e.g., Client ID/Secret if GSP proxies)
    }

    print(f"Sending IRN Request to: {IRP_GENERATE_ENDPOINT}")
    print(f"Request Headers (excluding sensitive): Gstin={user_gstin}, user_name={username}")
    # print(f"Payload (Structure check): {encrypted_json_payload_str[:100]}...") # Log only start of payload

    try:
        response = requests.post(
            IRP_GENERATE_ENDPOINT,
            headers=headers,
            data=encrypted_json_payload_str.encode('utf-8'), # Send the { "Data": "encrypted..." } JSON string
            timeout=60
        )

        print(f"API Response Status Code: {response.status_code}")
        # print(f"API Response Body:\n{response.text}") # DEBUG: Log raw response

        # --- Decrypt IRP Response (Standard IRP Requirement) ---
        # The response data is also usually encrypted with SEK.
        # encrypted_response_data = response.json().get("Data")
        # decrypted_response_text = decrypt_response(encrypted_response_data, SEK) # Placeholder
        # return decrypted_response_text # Return decrypted JSON string

        # --- FOR NOW: Return raw response text for structure testing ---
        # !!! REPLACE THIS WITH DECRYPTION LOGIC LATER !!!
        return response.text # Return the raw response text for parsing

    except requests.exceptions.RequestException as e:
        print(f"Error calling IRP API: {e}")
        return json.dumps({"Success": "false", "ErrorDetails": [{"ErrorCode": "NET_ERROR", "ErrorMessage": str(e)}]})
    except Exception as e:
        print(f"An unexpected error occurred during API call: {e}")
        return json.dumps({"Success": "false", "ErrorDetails": [{"ErrorCode": "PY_ERROR", "ErrorMessage": f"Unexpected Python error: {e}"}]})

# --- parse_response function remains mostly the same ---
# It now parses the decrypted JSON response from IRP
def parse_response(decrypted_api_response_text):
    """Parses the DECRYPTED JSON response from the IRP."""
    try:
        response_data = json.loads(decrypted_api_response_text)

        # Check for standard IRP success structure first
        if response_data.get("Status") == 1 and response_data.get("Data", {}).get("Irn"):
            irn_data = response_data["Data"]
            print("IRN Generation Successful.")
            return {
                "status": "Generated",
                "irn": irn_data.get("Irn"),
                "ack_no": str(irn_data.get("AckNo", "")), # Ensure string
                "ack_date": irn_data.get("AckDt"), # Format DD/MM/YYYY HH:MM:SS usually
                "qr_code": irn_data.get("SignedQRCode"),
                "error_msg": ""
            }
        # Check for standard IRP error structure
        elif response_data.get("Status") == 0 and response_data.get("ErrorDetails"):
            errors = response_data["ErrorDetails"]
            error_msg = "; ".join([f"Code {e.get('error_cd', e.get('ErrorCode', 'N/A'))}: {e.get('error_desc', e.get('ErrorMessage', 'Unknown'))}" for e in errors])
            print(f"IRN Generation Failed: {error_msg}")
            return {"status": "Failed", "error_msg": error_msg}
        # Handle other potential error formats
        elif response_data.get("error"): # Sometimes errors come under a single "error" key
             error_code = response_data["error"].get("error_cd", "UNKNOWN")
             error_message = response_data["error"].get("message", "Unknown API error.")
             full_error = f"Code {error_code}: {error_message}"
             print(f"IRN Generation Failed: {full_error}")
             return {"status": "Failed", "error_msg": full_error}
        # Handle unexpected structures
        else:
            full_error = f"Unexpected API response structure."
            if len(decrypted_api_response_text) < 500:
                full_error += f" | Raw (Decrypted): {decrypted_api_response_text}"
            else:
                 full_error += " | Raw (Decrypted) response too long."
            print(f"IRN Generation Failed: {full_error}")
            return {"status": "Failed", "error_msg": full_error}

    except json.JSONDecodeError:
        print(f"Error: Decrypted API response is not valid JSON.")
        err_detail = decrypted_api_response_text[:500]
        return {"status": "Failed", "error_msg": f"Invalid JSON response from API (Decrypted): {err_detail}..."}
    except Exception as e:
        print(f"Error parsing decrypted API response: {e}")
        return {"status": "Failed", "error_msg": f"Error parsing response: {e}"}


# --- IMPORTANT: Add Encryption/Decryption ---
# You will need the 'cryptography' library: pip install cryptography
# Add functions like encrypt_payload(payload_str, sek) and decrypt_response(encrypted_data, sek)
# using AES-256-CBC and Base64 encoding as per IRP specifications.
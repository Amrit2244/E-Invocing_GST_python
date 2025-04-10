# tally_connector.py (Updated with UTC date handling and user tracking)

import requests
import xml.etree.ElementTree as ET
import xmltodict
import xml.sax.saxutils as saxutils
from config_manager import load_config
import json
from datetime import datetime
import pytz

# Load Tally port from config
CONFIG = load_config()
TALLY_URL = f"http://localhost:{CONFIG.get('TALLY', 'Port', fallback='9000')}"
CURRENT_USER = "Amrit2244"  # Current user's login

def format_tally_date(date_str):
    """Convert UTC datetime string to Tally's expected format (DD-MM-YYYY)."""
    try:
        dt = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
        indian_tz = pytz.timezone('Asia/Kolkata')
        dt_indian = pytz.utc.localize(dt).astimezone(indian_tz)
        return dt_indian.strftime('%d-%m-%Y')
    except Exception as e:
        print(f"Date conversion error: {e}")
        return date_str

def check_tally_connection():
    """Basic connection check for Tally Prime."""
    try:
        simple_request = """<?xml version="1.0" encoding="UTF-8"?>
        <ENVELOPE>
            <HEADER>
                <VERSION>1</VERSION>
                <TALLYREQUEST>Export</TALLYREQUEST>
                <TYPE>Data</TYPE>
                <ID>CompanyInfo</ID>
            </HEADER>
        </ENVELOPE>
        """
        headers = {
            'Content-Type': 'text/xml;charset=utf-8',
            'Accept': '*/*'
        }
        
        print(f"Attempting to connect to Tally at: {TALLY_URL}")
        response = requests.post(
            TALLY_URL, 
            data=simple_request.encode('utf-8'), 
            headers=headers, 
            timeout=5,
            verify=False
        )
        
        return response.status_code == 200
        
    except Exception as e:
        print(f"Connection Error: {str(e)}")
        return False

def get_pending_invoices_xml(from_date, to_date):
    """
    Generate XML request for fetching detailed sales vouchers from Tally Prime.
    """
    xml_request = f"""<?xml version="1.0" encoding="UTF-8"?>
    <ENVELOPE>
        <HEADER>
            <VERSION>1</VERSION>
            <TALLYREQUEST>Export</TALLYREQUEST>
            <TYPE>Data</TYPE>
            <ID>Voucher Register</ID>
        </HEADER>
        <BODY>
            <DESC>
                <STATICVARIABLES>
                    <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
                    <SVCURRENTCOMPANY>$$CurrentCompany</SVCURRENTCOMPANY>
                    <SVFROMDATE>{from_date}</SVFROMDATE>
                    <SVTODATE>{to_date}</SVTODATE>
                    <VOUCHERTYPENAME>Sales</VOUCHERTYPENAME>
                    <EXPLODEFLAG>Yes</EXPLODEFLAG>
                    <SHOWBILLEXPLODE>Yes</SHOWBILLEXPLODE>
                </STATICVARIABLES>
                <REPORTNAME>Voucher Register</REPORTNAME>
            </DESC>
        </BODY>
    </ENVELOPE>
    """
    return xml_request

def fetch_pending_invoices(from_date, to_date):
    """
    Fetch and parse sales vouchers from Tally Prime with improved error handling.
    """
    global TALLY_URL
    if not check_tally_connection():
        raise ConnectionError(f"Tally is not running or not accessible at {TALLY_URL}")

    xml_payload = get_pending_invoices_xml(from_date, to_date)
    headers = {
        'Content-Type': 'text/xml;charset=utf-8',
        'Accept': '*/*'
    }

    try:
        print(f"\nFetching invoices from {from_date} to {to_date}")
        print(f"Request initiated by user: {CURRENT_USER}")
        print("\nRequest Headers:", headers)
        print("Request Payload:", xml_payload)
        
        response = requests.post(
            TALLY_URL, 
            data=xml_payload.encode('utf-8'), 
            headers=headers, 
            timeout=30,
            verify=False
        )
        
        print(f"\nResponse Status: {response.status_code}")
        print(f"Response Headers: {dict(response.headers)}")
        print(f"Response Content: {response.text[:1000]}")

        if response.status_code != 200:
            print(f"Error: Tally returned status code {response.status_code}")
            return []

        # Parse response
        try:
            data_dict = xmltodict.parse(response.text)
            print("\nParsed XML Structure:", json.dumps(data_dict, indent=2))
        except Exception as e:
            print(f"Error parsing XML: {e}")
            print("Raw response:", response.text)
            return []

        # Initialize empty list for invoices
        invoices = []
        
        try:
            # Check for error response
            if isinstance(data_dict, dict) and 'RESPONSE' in data_dict:
                error_msg = data_dict['RESPONSE']
                print(f"Tally returned an error: {error_msg}")
                return []

            # Navigate through the response structure
            envelope = data_dict.get('ENVELOPE', {})
            if not envelope:
                print("No ENVELOPE found in response")
                return []

            # Try different possible voucher data locations
            vouchers = []
            
            # Check BODY -> DATA structure
            if 'BODY' in envelope:
                body = envelope['BODY']
                if isinstance(body, dict) and 'DATA' in body:
                    data = body['DATA']
                    if 'TALLYMESSAGE' in data:
                        messages = data['TALLYMESSAGE']
                        if isinstance(messages, list):
                            vouchers.extend([msg.get('VOUCHER', {}) for msg in messages])
                        else:
                            voucher = messages.get('VOUCHER', {})
                            if voucher:
                                vouchers.append(voucher)

            # If no vouchers found in TALLYMESSAGE, try direct VOUCHER tag
            if not vouchers and 'VOUCHER' in envelope:
                if isinstance(envelope['VOUCHER'], list):
                    vouchers.extend(envelope['VOUCHER'])
                else:
                    vouchers.append(envelope['VOUCHER'])

            if not vouchers:
                print("\nNo voucher data found in response")
                print("Available keys in ENVELOPE:", envelope.keys())
                return []

            print(f"\nProcessing {len(vouchers)} vouchers...")
            
            for voucher in vouchers:
                try:
                    # Get ledger entries
                    ledger_entries = voucher.get('ALLLEDGERENTRIES.LIST', [])
                    if not isinstance(ledger_entries, list):
                        ledger_entries = [ledger_entries]

                    # Get party details from ledger entries
                    party_details = next((entry for entry in ledger_entries 
                                       if entry.get('ISDEEMEDPOSITIVE') == 'Yes'), {})

                    invoice = {
                        'master_id': voucher.get('MASTERID', ''),
                        'voucher_no': voucher.get('VOUCHERNUMBER', ''),
                        'date': voucher.get('DATE', ''),
                        'party_name': (
                            party_details.get('LEDGERNAME', '') or
                            voucher.get('PARTYLEDGERNAME', '') or 
                            voucher.get('PARTYNAME', '')
                        ),
                        'amount': party_details.get('AMOUNT', voucher.get('AMOUNT', '0')),
                        'narration': voucher.get('NARRATION', ''),
                        'reference': voucher.get('REFERENCE', ''),
                        'gstin': voucher.get('PARTYGSTIN', ''),
                        'state_name': voucher.get('STATENAME', ''),
                        'status': 'Pending',
                        'error': '',
                        'created_by': CURRENT_USER,
                        'created_at': datetime.now(pytz.UTC).strftime('%Y-%m-%d %H:%M:%S'),
                        'raw_data': voucher
                    }
                    
                    # Only add if we have essential data
                    if invoice['voucher_no'] and invoice['party_name']:
                        invoices.append(invoice)
                        print(f"Processed: {invoice['voucher_no']} - {invoice['party_name']}")
                        
                except Exception as e:
                    print(f"Error processing voucher: {e}")
                    continue
            
            print(f"\nSuccessfully processed {len(invoices)} invoices")
            
        except Exception as e:
            print(f"\nError processing response: {e}")
            print("Response structure:", json.dumps(data_dict, indent=2))
            return []

        return invoices

    except Exception as e:
        print(f"\nError during fetch: {e}")
        if 'response' in locals():
            print("Full Response Content:", response.text)
        return []

if __name__ == "__main__":
    print("Testing Tally connection...")
    if check_tally_connection():
        print("Successfully connected to Tally!")
        
        try:
            print("\nTesting invoice fetch...")
            from_date = "01-04-2025"
            to_date = "10-04-2025"
            
            print(f"Fetching invoices from {from_date} to {to_date}")
            print(f"Current UTC time: {datetime.now(pytz.UTC)}")
            print(f"User: {CURRENT_USER}")
            
            invoices = fetch_pending_invoices(from_date, to_date)
            print(f"\nFetched {len(invoices)} invoices")
            
            if invoices:
                print("\nFirst Invoice Details:")
                print(json.dumps(invoices[0], indent=2, default=str))
            else:
                print("\nNo invoices found for the specified date range")
            
        except Exception as e:
            print(f"Error testing invoice fetch: {e}")
    else:
        print("Failed to connect to Tally")
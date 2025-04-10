# tally_connector.py

import requests
import xmltodict
import json
from datetime import datetime
import pytz
from config_manager import load_config, get_current_user, get_current_time_utc

# Load configuration
CONFIG = load_config()
TALLY_URL = f"http://localhost:{CONFIG.get('TALLY', 'Port', fallback='9000')}"
CURRENT_USER = get_current_user()

def check_tally_connection():
    """Basic connection check for Tally Prime."""
    try:
        # Use a simple request to check if Tally is reachable
        simple_request = """<?xml version="1.0" encoding="UTF-8"?>
        <ENVELOPE>
            <HEADER>
                <VERSION>1</VERSION>
                <TALLYREQUEST>Export</TALLYREQUEST>
                <TYPE>Data</TYPE>
                <ID>List of Companies</ID>
            </HEADER>
        </ENVELOPE>
        """
        headers = {
            'Content-Type': 'text/xml;charset=utf-8',
            'Accept': '*/*'
        }

        print(f"Attempting to connect to Tally at: {TALLY_URL}")
        response = requests.post(TALLY_URL, data=simple_request.encode('utf-8'), headers=headers, timeout=5)

        print(f"Connection Response Status: {response.status_code}")
        print(f"Connection Response: {response.text[:500]}")

        return response.status_code == 200

    except Exception as e:
        print(f"Connection Error: {str(e)}")
        return False

def get_pending_invoices_xml(from_date, to_date):
    """
    Generate XML request for fetching sales vouchers from Tally Prime using predefined reports.
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
                    <SVFROMDATE>{from_date}</SVFROMDATE>
                    <SVTODATE>{to_date}</SVTODATE>
                    <VOUCHERTYPENAME>Sales</VOUCHERTYPENAME>
                    <EXPLODEFLAG>Yes</EXPLODEFLAG>
                </STATICVARIABLES>
            </DESC>
        </BODY>
    </ENVELOPE>
    """
    return xml_request

def parse_voucher_data(voucher):
    """
    Parse individual voucher data to extract required fields.
    """
    try:
        ledger_entries = voucher.get('ALLLEDGERENTRIES.LIST', [])
        if not isinstance(ledger_entries, list):
            ledger_entries = [ledger_entries]

        # Initialize tax components
        cgst_amount = 0
        sgst_amount = 0
        igst_amount = 0
        total_amount = 0

        # Process ledger entries for tax and total amounts
        for entry in ledger_entries:
            if isinstance(entry, dict):
                ledger_name = entry.get('LEDGERNAME', '').upper()
                amount = abs(float(entry.get('AMOUNT', '0').replace('-', '') or 0))

                if 'CGST' in ledger_name:
                    cgst_amount += amount
                elif 'SGST' in ledger_name:
                    sgst_amount += amount
                elif 'IGST' in ledger_name:
                    igst_amount += amount
                elif entry.get('ISPARTYLEDGER', 'No') == 'Yes':
                    total_amount = amount

        # Calculate taxable amount
        taxable_amount = total_amount - (cgst_amount + sgst_amount + igst_amount)

        return {
            'voucher_number': voucher.get('VOUCHERNUMBER', ''),
            'date': voucher.get('DATE', ''),
            'party_name': voucher.get('PARTYLEDGERNAME', ''),
            'party_gstin': voucher.get('PARTYGSTIN', ''),
            'destination': voucher.get('STATENAME', ''),
            'taxable_amount': taxable_amount,
            'cgst_amount': cgst_amount,
            'sgst_amount': sgst_amount,
            'igst_amount': igst_amount,
            'total_amount': total_amount,
            'status': 'Pending',
            'created_by': CURRENT_USER,
            'created_at': get_current_time_utc()
        }

    except Exception as e:
        print(f"Error parsing voucher: {e}")
        return None

def fetch_pending_invoices(from_date, to_date):
    """
    Fetch and parse sales vouchers from Tally Prime.
    """
    if not check_tally_connection():
        raise ConnectionError(f"Tally is not running or not accessible at {TALLY_URL}")

    xml_payload = get_pending_invoices_xml(from_date, to_date)
    headers = {'Content-Type': 'text/xml;charset=utf-8', 'Accept': '*/*'}

    try:
        print(f"Fetching invoices from {from_date} to {to_date}")
        print("Sending request to Tally...")
        response = requests.post(TALLY_URL, data=xml_payload.encode('utf-8'), headers=headers, timeout=30)

        print(f"Response Status: {response.status_code}")
        print(f"Response Content (first 500 chars): {response.text[:500]}")

        if response.status_code != 200:
            print(f"Error: Tally returned status code {response.status_code}")
            return []

        # Parse XML response
        data_dict = xmltodict.parse(response.text)
        envelope = data_dict.get('ENVELOPE', {})
        body_data = envelope.get('BODY', {}).get('DATA', {}).get('TALLYMESSAGE', [])

        if not isinstance(body_data, list):
            body_data = [body_data]

        invoices = []
        for entry in body_data:
            voucher = entry.get('VOUCHER', {})
            parsed_data = parse_voucher_data(voucher)
            if parsed_data:
                invoices.append(parsed_data)

        print(f"Successfully fetched {len(invoices)} invoices.")
        return invoices

    except Exception as e:
        print(f"Error during fetch: {e}")
        return []

def update_tally_voucher(voucher_master_id, irn_data):
    """Update voucher in Tally Prime with IRN details."""
    if not check_tally_connection():
        return False, "Tally is not connected"

    irn = irn_data.get('irn', '') or ''
    ack_no = irn_data.get('ack_no', '') or ''
    ack_date = irn_data.get('ack_date', '') or ''
    status = irn_data.get('status', '') or ''
    error_msg = irn_data.get('error_msg', '') or ''

    xml_request = f"""<?xml version="1.0" encoding="UTF-8"?>
    <ENVELOPE>
        <HEADER>
            <VERSION>1</VERSION>
            <TALLYREQUEST>Import</TALLYREQUEST>
            <TYPE>Data</TYPE>
            <ID>Vouchers</ID>
        </HEADER>
        <BODY>
            <DESC>
                <STATICVARIABLES>
                    <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
                    <IMPORTDUPS>@@DUPIGNORE</IMPORTDUPS>
                </STATICVARIABLES>
            </DESC>
            <DATA>
                <TALLYMESSAGE>
                    <VOUCHER REMOTEID="{voucher_master_id}" VCHTYPE="Sales" ACTION="Alter">
                        <MASTERID>{voucher_master_id}</MASTERID>
                        <ALTERID>{voucher_master_id}</ALTERID>
                        <ALLLEDGERENTRIES.LIST>
                            <EINVOICEDETAILS.LIST>
                                <IRN>{irn}</IRN>
                                <ACKNO>{ack_no}</ACKNO>
                                <ACKDT>{ack_date}</ACKDT>
                                <STATUS>{status}</STATUS>
                                <ERRORMSG>{error_msg[:500]}</ERRORMSG>
                            </EINVOICEDETAILS.LIST>
                        </ALLLEDGERENTRIES.LIST>
                        <UPDATEDBY>{CURRENT_USER}</UPDATEDBY>
                        <UPDATEDATE>{datetime.now(pytz.UTC).strftime('%Y%m%d')}</UPDATEDATE>
                    </VOUCHER>
                </TALLYMESSAGE>
            </DATA>
        </BODY>
    </ENVELOPE>
    """
    
    headers = {'Content-Type': 'text/xml;charset=utf-8', 'Accept': '*/*'}

    try:
        print(f"Updating voucher {voucher_master_id} in Tally...")
        response = requests.post(
            TALLY_URL, 
            data=xml_request.encode('utf-8'), 
            headers=headers,
            timeout=30,
            verify=False
        )
        
        if response.status_code == 200:
            if "<LINEERROR>" in response.text:
                error_msg = "Tally reported an error during update"
                print(f"Update Error: {error_msg}")
                return False, error_msg
            return True, "Update successful"
        else:
            return False, f"Update failed with status {response.status_code}"
            
    except Exception as e:
        error_msg = f"Update error: {str(e)}"
        print(error_msg)
        return False, error_msg

if __name__ == "__main__":
    print(f"Current Date and Time (UTC): {get_current_time_utc()}")
    print(f"Current User's Login: {CURRENT_USER}")

    if check_tally_connection():
        print("\nSuccessfully connected to Tally!")
        try:
            print("\nTesting invoice fetch...")
            from_date = "01-04-2025"
            to_date = "10-04-2025"
            invoices = fetch_pending_invoices(from_date, to_date)
            print(f"\nFetched {len(invoices)} invoices")
            if invoices:
                print("\nFirst Invoice Details:")
                print(json.dumps(invoices[0], indent=2))
        except Exception as e:
            print(f"\nError testing invoice fetch: {e}")
    else:
        print("\nFailed to connect to Tally.")
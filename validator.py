import re

def is_valid_gstin(gstin):
    """Basic validation for GSTIN format."""
    if not gstin: return False
    pattern = r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$"
    return bool(re.match(pattern, gstin))

def is_valid_hsn(hsn):
    """Basic validation for HSN format (numeric, certain length)."""
    if not hsn: return False
    pattern = r"^[0-9]{4,8}$" # 4, 6, or 8 digits usually
    return bool(re.match(pattern, hsn))

def is_valid_date_format(date_str):
     """Checks if date is DD/MM/YYYY."""
     if not date_str: return False
     pattern = r"^\d{2}/\d{2}/\d{4}$"
     return bool(re.match(pattern, date_str))

def validate_invoice_data_for_irn(invoice_json_dict):
    """
    Performs pre-validation checks before sending to IRP.
    Checks mandatory fields and basic formats in the *final JSON*.
    Returns True if valid, or a list of error strings if invalid.
    """
    errors = []
    # --- DocDtls ---
    doc = invoice_json_dict.get("DocDtls", {})
    if not doc.get("Typ") in ["INV", "CRN", "DBN"]: errors.append("Invalid DocDtls.Typ")
    if not doc.get("No"): errors.append("Missing DocDtls.No")
    if not is_valid_date_format(doc.get("Dt")): errors.append("Invalid DocDtls.Dt format (must be DD/MM/YYYY)")

    # --- SellerDtls ---
    seller = invoice_json_dict.get("SellerDtls", {})
    if not is_valid_gstin(seller.get("Gstin")): errors.append("Invalid SellerDtls.Gstin")
    if not seller.get("LglNm"): errors.append("Missing SellerDtls.LglNm")
    # Add more checks: Addr1, Loc, Pin, Stcd

    # --- BuyerDtls ---
    buyer = invoice_json_dict.get("BuyerDtls", {})
    if not is_valid_gstin(buyer.get("Gstin")): errors.append("Invalid BuyerDtls.Gstin")
    if not buyer.get("LglNm"): errors.append("Missing BuyerDtls.LglNm")
    if not buyer.get("Pos"): errors.append("Missing BuyerDtls.Pos (Place of Supply State Code)")
    # Add more checks: Addr1, Loc, Pin, Stcd

    # --- ItemList ---
    items = invoice_json_dict.get("ItemList", [])
    if not items: errors.append("ItemList cannot be empty")
    for idx, item in enumerate(items):
        if not item.get("SlNo"): errors.append(f"Item {idx+1}: Missing SlNo")
        if not item.get("IsServc") in ["Y", "N"]: errors.append(f"Item {idx+1}: Invalid IsServc")
        if not is_valid_hsn(item.get("HsnCd")): errors.append(f"Item {idx+1}: Invalid HsnCd")
        # Add checks for numeric types: UnitPrice, TotAmt, AssAmt, GstRt etc.
        if item.get("GstRt") is None: errors.append(f"Item {idx+1}: Missing GstRt")
        if item.get("TotItemVal") is None: errors.append(f"Item {idx+1}: Missing TotItemVal")

    # --- ValDtls ---
    vals = invoice_json_dict.get("ValDtls", {})
    if vals.get("AssVal") is None: errors.append("Missing ValDtls.AssVal")
    if vals.get("TotInvVal") is None: errors.append("Missing ValDtls.TotInvVal")
    # Add checks for consistency (e.g., Sum of item AssAmt == ValDtls.AssVal)

    # --- TranDtls ---
    tran = invoice_json_dict.get("TranDtls", {})
    if not tran.get("TaxSch") == "GST": errors.append("Invalid TranDtls.TaxSch")
    if not tran.get("SupTyp"): errors.append("Missing TranDtls.SupTyp")

    if errors:
        return errors
    else:
        return True
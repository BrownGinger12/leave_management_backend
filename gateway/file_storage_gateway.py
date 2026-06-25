# gateway/file_storage_gateway.py
import os  # used for path handling and filesystem operations
import time  # used to compute and check signed URL expiry timestamps
import hmac  # used to generate and verify signed URL signatures
import hashlib  # used as the hash algorithm for HMAC signatures
from werkzeug.utils import secure_filename  # sanitizes filenames before saving to disk
from dotenv import load_dotenv  # loads environment variables from .env

load_dotenv()  # ensure env vars are available even if this module is imported before app.py calls load_dotenv()

UPLOAD_DIR = os.path.join("uploads", "employee_photos")  # directory where employee photos are stored on the server
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}  # file extensions permitted for photo uploads
SIGNING_SECRET = os.getenv("PHOTO_SIGNING_SECRET", "dev-secret-change-me")  # secret key used to sign photo URLs
DEFAULT_EXPIRY_SECONDS = 600  # how long a signed photo URL stays valid (10 minutes)


def is_allowed_file(filename: str) -> bool:
    """
    Checks whether a filename has an allowed image extension.

    Parameters:
        filename (str): The original filename of the uploaded file.

    Returns:
        bool: True if the extension is allowed, False otherwise.
    """
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS  # check extension against allow-list


def save_file(file, filename: str) -> dict:
    """
    Saves an uploaded file to the upload directory on the server's local filesystem.

    Parameters:
        file (FileStorage): The uploaded file object from the request.
        filename (str): The filename to save the file as.

    Returns:
        dict: statusCode 200 with the saved file's relative path, or statusCode 500 on failure.
    """
    try:
        os.makedirs(UPLOAD_DIR, exist_ok=True)  # ensure the upload directory exists
        safe_name = secure_filename(filename)  # strip unsafe characters from the filename
        path = os.path.join(UPLOAD_DIR, safe_name)  # build the full filesystem path
        file.save(path)  # write the file to disk
        return {"statusCode": 200, "path": path.replace("\\", "/")}  # return normalized relative path
    except Exception as e:  # catch unexpected errors
        return {"statusCode": 500, "message": str(e)}  # return 500 with error detail


def delete_file(path: str) -> None:
    """
    Deletes a file from the server's local filesystem if it exists.

    Parameters:
        path (str): The relative path of the file to delete.

    Returns:
        None
    """
    if path and os.path.exists(path):  # only attempt deletion if the path is set and exists
        os.remove(path)  # remove the file from disk


def _build_signature(path: str, expires: int) -> str:
    """
    Computes the HMAC-SHA256 signature for a file path and expiry timestamp.

    Parameters:
        path (str): The relative file path being signed.
        expires (int): Unix timestamp after which the signature is no longer valid.

    Returns:
        str: The hex-encoded HMAC signature.
    """
    message = f"{path}:{expires}".encode()  # combine path and expiry into the signed message
    return hmac.new(SIGNING_SECRET.encode(), message, hashlib.sha256).hexdigest()  # compute the HMAC digest


def generate_signed_url(path: str, expires_in: int = DEFAULT_EXPIRY_SECONDS) -> str:
    """
    Builds a time-limited signed URL for a stored file so it can only be accessed
    with a valid, non-expired signature.

    Parameters:
        path (str): The relative file path (as stored in the database) to sign.
        expires_in (int): Number of seconds the signed URL remains valid.

    Returns:
        str: A relative URL of the form "/<path>?expires=<ts>&signature=<sig>".
    """
    expires = int(time.time()) + expires_in  # compute the expiry timestamp
    signature = _build_signature(path, expires)  # sign the path and expiry together
    return f"/{path}?expires={expires}&signature={signature}"  # build the final signed URL


def verify_signed_url(path: str, expires: str, signature: str) -> bool:
    """
    Verifies that a signed URL's signature is valid and has not expired.

    Parameters:
        path (str): The relative file path being requested.
        expires (str): The expiry timestamp from the request's query string.
        signature (str): The signature from the request's query string.

    Returns:
        bool: True if the signature is valid and not expired, False otherwise.
    """
    try:
        expires_int = int(expires)  # parse the expiry timestamp
    except (TypeError, ValueError):  # expires missing or not a valid integer
        return False  # reject malformed requests

    if time.time() > expires_int:  # check if the signed URL has expired
        return False  # reject expired requests

    expected_signature = _build_signature(path, expires_int)  # recompute the expected signature
    return hmac.compare_digest(expected_signature, signature or "")  # constant-time comparison to prevent timing attacks

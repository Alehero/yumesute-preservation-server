"""Stable, identifiable local CA selection. Never replace existing trust silently."""
import json
import secrets
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.x509.oid import NameOID
from mitmproxy.certs import CertStore


def prepare_ca(private: Path, explicit=None):
    settings = private / "certificate-store.json"
    saved = json.loads(settings.read_text()) if settings.exists() else {}
    selected = explicit or saved.get("ca_dir")
    directory = Path(selected).expanduser().resolve() if selected else (private / "mitmproxy").resolve()
    key_file = directory / "mitmproxy-ca.pem"
    if not key_file.exists():
        if selected or (directory.exists() and any(directory.iterdir())):
            raise ValueError("Selected CA store is missing mitmproxy-ca.pem; refusing to replace it.")
        CertStore.create_store(directory, "mitmproxy", 2048,
                               organization="Yumesute Local",
                               cn="Yumesute Local " + secrets.token_hex(4))
    # Ensure the downloadable certificate actually belongs to the signing key.
    pem = key_file.read_bytes()
    certificate = x509.load_pem_x509_certificate(pem)
    key = serialization.load_pem_private_key(pem, password=None)
    public = x509.load_pem_x509_certificate((directory / "mitmproxy-ca-cert.cer").read_bytes())
    def public_bytes(obj):
        return obj.public_key().public_bytes(serialization.Encoding.DER,
                                            serialization.PublicFormat.SubjectPublicKeyInfo)
    if public_bytes(key) != public_bytes(certificate) or public.fingerprint(hashes.SHA256()) != certificate.fingerprint(hashes.SHA256()):
        raise ValueError("CA signing key and downloadable certificate do not match.")
    name = certificate.subject.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value
    fingerprint = ":".join(f"{b:02X}" for b in certificate.fingerprint(hashes.SHA256()))
    if explicit:
        settings.write_text(json.dumps({"ca_dir": str(directory)}, indent=2) + "\n")
        settings.chmod(0o600)
    return directory, name, fingerprint

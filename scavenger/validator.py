from __future__ import annotations

import asyncio
import base64
import binascii
from collections import Counter
import hashlib
import json
import re
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Generic, TypeVar

import aiohttp
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, padding
from loguru import logger

from scavenger.models import ValidationResult

if TYPE_CHECKING:
    from scavenger.config import ScavengerSettings

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ROOT_GOOGLE_PEM_PATH = PROJECT_ROOT / "res/pem/google.pem"
ROOT_AOSP_EC_PEM_PATH = PROJECT_ROOT / "res/pem/aosp_ec.pem"
ROOT_AOSP_RSA_PEM_PATH = PROJECT_ROOT / "res/pem/aosp_rsa.pem"
ROOT_KNOX_PEM_PATH = PROJECT_ROOT / "res/pem/knox.pem"

_PEM_BEGIN = "-----BEGIN CERTIFICATE-----"
_PEM_END = "-----END CERTIFICATE-----"
_B64_LINE = re.compile(r"^[A-Za-z0-9+/=]+$")
_WS = re.compile(r"\s+")

T = TypeVar("T")


@dataclass
class RemoteCache(Generic[T]):
    fetched_at: float
    data: T
    etag: str | None
    last_modified: str | None


class KeyboxValidator:
    def __init__(self, settings: "ScavengerSettings"):
        self.settings = settings
        self._timeout = aiohttp.ClientTimeout(total=settings.request_timeout_seconds)
        self._banned_cache: RemoteCache[list[str]] | None = None
        self._revocation_cache: RemoteCache[dict] | None = None
        self._revocation_entries_fingerprint: str | None = None
        self._revocation_updated_since_last_check = False

        self._google_public_key = self._load_public_key(ROOT_GOOGLE_PEM_PATH)
        self._aosp_ec_public_key = self._load_public_key(ROOT_AOSP_EC_PEM_PATH)
        self._aosp_rsa_public_key = self._load_public_key(ROOT_AOSP_RSA_PEM_PATH)
        self._knox_public_key = self._load_public_key(ROOT_KNOX_PEM_PATH)

    def consume_revocation_update_flag(self) -> bool:
        if not self._revocation_updated_since_last_check:
            return False

        self._revocation_updated_since_last_check = False
        return True

    @staticmethod
    def _revocation_fingerprint(status_json: dict) -> str:
        entries = status_json.get("entries", {})
        canonical_entries = json.dumps(entries, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical_entries.encode("utf-8")).hexdigest()

    def _update_revocation_fingerprint(self, status_json: dict) -> None:
        new_fingerprint = self._revocation_fingerprint(status_json)
        old_fingerprint = self._revocation_entries_fingerprint
        if old_fingerprint is not None and new_fingerprint != old_fingerprint:
            self._revocation_updated_since_last_check = True
        self._revocation_entries_fingerprint = new_fingerprint

    def _load_public_key(self, file_path: Path):
        with open(file_path, "rb") as key_file:
            return serialization.load_pem_public_key(
                key_file.read(),
                backend=default_backend(),
            )

    @staticmethod
    def _compare_keys(public_key1, public_key2) -> bool:
        return public_key1.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ) == public_key2.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )

    @staticmethod
    def _not_valid_before(certificate: x509.Certificate) -> datetime:
        return certificate.not_valid_before_utc

    @staticmethod
    def _not_valid_after(certificate: x509.Certificate) -> datetime:
        return certificate.not_valid_after_utc

    async def validate(self, xml_payload: bytes) -> ValidationResult:
        reasons: list[str] = []

        if len(xml_payload) > self.settings.max_xml_size:
            return ValidationResult(is_valid=False, reasons=["File size is too large"])

        try:
            banned_serials = await self._fetch_banned_serials()
        except Exception as exc:
            logger.error("Failed to fetch banned serials: {}", exc)
            return ValidationResult(
                is_valid=False,
                reasons=["Failed to load the list of banned serial numbers."],
            )

        leaked_serials = self._load_leaked_serials()

        try:
            status_json = await self._load_revocation_status()
        except Exception as exc:
            logger.error("Failed to load revocation list: {}", exc)
            return ValidationResult(is_valid=False, reasons=["Failed to load revocation list."])

        try:
            root = ET.fromstring(xml_payload)
            pem_numbers = self._parse_number_of_certificates(root)
            max_pem_number = max(pem_numbers)
            if max_pem_number < 3:
                reasons.append(
                    "Insufficient certificates in the keychain. A minimum of 3 certificates is required."
                )
            pem_certificates = self._parse_certificates(root, max_pem_number)
        except Exception as exc:
            return ValidationResult(is_valid=False, reasons=[str(exc)])

        certificates: list[x509.Certificate] = []
        try:
            for pem_certificate in pem_certificates:
                certificate = x509.load_pem_x509_certificate(
                    pem_certificate.encode(),
                    default_backend(),
                )
                certificates.append(certificate)
        except Exception as exc:
            return ValidationResult(is_valid=False, reasons=[str(exc)])

        revoked_certificates: list[str] = []
        certificate_serials: list[str] = []

        nearest_expiration_date: datetime | None = None
        any_certificate_expired = False
        has_banned_serial = False
        has_leaked_serial = False

        entries = status_json.get("entries", {})

        for certificate in reversed(certificates):
            serial_number_string = hex(certificate.serial_number)[2:].lower()
            certificate_serials.append(serial_number_string)

            subject_serial_number = self._subject_serial_number(certificate)
            if subject_serial_number and subject_serial_number in banned_serials:
                has_banned_serial = True

            current_time = datetime.now(timezone.utc)
            not_valid_before = self._not_valid_before(certificate)
            not_valid_after = self._not_valid_after(certificate)

            if current_time > not_valid_after:
                any_certificate_expired = True

            if nearest_expiration_date is None or not_valid_after < nearest_expiration_date:
                nearest_expiration_date = not_valid_after

            if serial_number_string in banned_serials:
                has_banned_serial = True

            if serial_number_string in leaked_serials:
                has_leaked_serial = True

            status = entries.get(serial_number_string)
            if status is not None:
                revoked_certificates.append(serial_number_string)

        chain_is_valid = self._verify_certificate_chain(certificates)

        root_certificate = certificates[-1]
        root_public_key = root_certificate.public_key()
        certificate_type: str | None = None
        if self._compare_keys(root_public_key, self._google_public_key):
            certificate_type = "hardware"
        elif self._compare_keys(root_public_key, self._aosp_ec_public_key):
            certificate_type = "software"
        elif self._compare_keys(root_public_key, self._aosp_rsa_public_key):
            certificate_type = "software"
        elif self._compare_keys(root_public_key, self._knox_public_key):
            certificate_type = "knox"

        is_within_validity = all(
            self._not_valid_before(cert) <= datetime.now(timezone.utc) <= self._not_valid_after(cert)
            for cert in certificates
        )
        is_correct_root = certificate_type in {"hardware", "knox"}
        is_not_revoked = not revoked_certificates
        is_not_banned = not has_banned_serial
        is_not_leaked = not has_leaked_serial

        special_serial_violation = self._has_special_serial_violation(certificates)

        is_valid_keychain = (
            len(certificates) >= 3
            and is_within_validity
            and chain_is_valid
            and is_not_revoked
            and is_correct_root
            and is_not_banned
            and is_not_leaked
            and not special_serial_violation
        )

        if len(certificates) < 3:
            reasons.append("Certificate chain is shorter than 3 certificates")
        if not is_within_validity:
            reasons.append("At least one certificate is outside its validity period")
        if not chain_is_valid:
            reasons.append("Invalid certificate chain")
        if revoked_certificates:
            reasons.append("Serial number found in Google's revoked keybox list")
        if not is_correct_root:
            if certificate_type == "software":
                reasons.append("AOSP software root certificate is not accepted")
            elif any_certificate_expired:
                reasons.append("Unknown root certificate due to expiration of a certificate")
            else:
                reasons.append("Unknown root certificate")
        if has_banned_serial:
            reasons.append("Banned serial detected")
        if has_leaked_serial:
            reasons.append("Leaked serial detected")
        if special_serial_violation:
            reasons.append("Serial f92009e853b6b045 is only allowed on certificate 3 or 4")

        return ValidationResult(
            is_valid=is_valid_keychain,
            reasons=reasons,
            certificate_serials=certificate_serials,
            revoked_serials=revoked_certificates,
            certificate_type=certificate_type,
            has_banned_serial=has_banned_serial,
            has_leaked_serial=has_leaked_serial,
            special_serial_violation=special_serial_violation,
            nearest_expiration_date=nearest_expiration_date,
        )

    async def _load_revocation_status(self) -> dict:
        cache = self._revocation_cache
        now = time.time()
        if cache and (now - cache.fetched_at) < self.settings.cache_ttl_seconds:
            self._update_revocation_fingerprint(cache.data)
            return cache.data

        if cache:
            is_unchanged = await self._is_remote_unchanged(
                self.settings.revocation_url,
                cache,
            )
            if is_unchanged:
                cache.fetched_at = now
                self._update_revocation_fingerprint(cache.data)
                return cache.data

        headers = {
            "Cache-Control": "max-age=0, no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        }

        try:
            status_json, etag, last_modified = await self._request_json(
                self.settings.revocation_url,
                headers=headers,
            )
        except Exception:
            with open(self.settings.revocation_fallback_path, "r", encoding="utf-8") as handle:
                status_json = json.load(handle)
            etag = None
            last_modified = None

        if "entries" not in status_json or not isinstance(status_json["entries"], dict):
            raise ValueError("Invalid revocation status payload")

        self._update_revocation_fingerprint(status_json)

        self._revocation_cache = RemoteCache(
            fetched_at=now,
            data=status_json,
            etag=etag,
            last_modified=last_modified,
        )
        return status_json

    async def _fetch_banned_serials(self) -> list[str]:
        cache = self._banned_cache
        now = time.time()
        if cache and (now - cache.fetched_at) < self.settings.cache_ttl_seconds:
            return cache.data

        if cache:
            is_unchanged = await self._is_remote_unchanged(
                self.settings.banned_serials_url,
                cache,
            )
            if is_unchanged:
                cache.fetched_at = now
                return cache.data

        text, etag, last_modified = await self._request_text(self.settings.banned_serials_url)
        banned_serials = [line.strip().lower() for line in text.splitlines() if line.strip()]
        self._banned_cache = RemoteCache(
            fetched_at=now,
            data=banned_serials,
            etag=etag,
            last_modified=last_modified,
        )
        return banned_serials

    def _load_leaked_serials(self) -> set[str]:
        try:
            with open(self.settings.leaked_serials_path, "r", encoding="utf-8") as file_handle:
                return {
                    line.strip().lower()
                    for line in file_handle.readlines()
                    if line.strip()
                }
        except Exception as exc:
            logger.error("Failed to load leaked serials: {}", exc)
            return set()

    async def _request_text(self, url: str) -> tuple[str, str | None, str | None]:
        last_error: Exception | None = None

        for attempt in range(self.settings.network_retries + 1):
            try:
                async with aiohttp.ClientSession(timeout=self._timeout) as session:
                    async with session.get(url) as response:
                        if response.status != 200:
                            raise ValueError(f"Unexpected status {response.status} for {url}")
                        return (
                            await response.text(),
                            response.headers.get("ETag"),
                            response.headers.get("Last-Modified"),
                        )
            except Exception as exc:
                last_error = exc
                if attempt < self.settings.network_retries:
                    await asyncio.sleep(0.5 * (attempt + 1))

        raise RuntimeError(f"Request failed for {url}: {last_error}") from last_error

    async def _request_json(
        self,
        url: str,
        headers: dict | None = None,
        params: dict | None = None,
    ) -> tuple[dict, str | None, str | None]:
        last_error: Exception | None = None

        for attempt in range(self.settings.network_retries + 1):
            try:
                async with aiohttp.ClientSession(timeout=self._timeout) as session:
                    async with session.get(url, headers=headers, params=params) as response:
                        if response.status != 200:
                            raise ValueError(f"Unexpected status {response.status} for {url}")
                        return (
                            await response.json(),
                            response.headers.get("ETag"),
                            response.headers.get("Last-Modified"),
                        )
            except Exception as exc:
                last_error = exc
                if attempt < self.settings.network_retries:
                    await asyncio.sleep(0.5 * (attempt + 1))

        raise RuntimeError(f"Request failed for {url}: {last_error}") from last_error

    async def _request_head_metadata(
        self,
        url: str,
        headers: dict | None = None,
        params: dict | None = None,
    ) -> tuple[str | None, str | None] | None:
        last_error: Exception | None = None

        for attempt in range(self.settings.network_retries + 1):
            try:
                async with aiohttp.ClientSession(timeout=self._timeout) as session:
                    async with session.head(
                        url,
                        headers=headers,
                        params=params,
                        allow_redirects=True,
                    ) as response:
                        if response.status in {405, 501}:
                            return None
                        if response.status != 200:
                            raise ValueError(f"Unexpected HEAD status {response.status} for {url}")

                        etag = response.headers.get("ETag")
                        last_modified = response.headers.get("Last-Modified")
                        if etag is None and last_modified is None:
                            return None
                        return etag, last_modified
            except Exception as exc:
                last_error = exc
                if attempt < self.settings.network_retries:
                    await asyncio.sleep(0.5 * (attempt + 1))

        raise RuntimeError(f"HEAD request failed for {url}: {last_error}") from last_error

    async def _is_remote_unchanged(self, url: str, cache: RemoteCache[object]) -> bool:
        try:
            metadata = await self._request_head_metadata(url)
        except Exception as exc:
            logger.warning("HEAD metadata check failed for {}: {}", url, exc)
            return False

        if metadata is None:
            return False

        etag, last_modified = metadata
        return self._metadata_matches(cache, etag, last_modified)

    @staticmethod
    def _metadata_matches(
        cache: RemoteCache[object],
        etag: str | None,
        last_modified: str | None,
    ) -> bool:
        comparable = False

        if cache.etag is not None and etag is not None:
            comparable = True
            if cache.etag != etag:
                return False

        if cache.last_modified is not None and last_modified is not None:
            comparable = True
            if cache.last_modified != last_modified:
                return False

        return comparable

    @staticmethod
    def _parse_number_of_certificates(root: ET.Element) -> list[int]:
        certificates_counts = root.findall(".//NumberOfCertificates")
        if not certificates_counts:
            raise Exception("No NumberOfCertificates found.")

        counts = []
        for certificate in certificates_counts:
            if certificate.text is None:
                raise ValueError("Invalid NumberOfCertificates node")
            counts.append(int(certificate.text.strip()))
        return counts

    @staticmethod
    def _parse_certificates(root: ET.Element, pem_number: int) -> list[str]:
        pem_certificates: list[str] = []

        for keybox in root.findall(".//Keybox"):
            for key in keybox.findall("Key"):
                for certificate in key.findall('.//Certificate[@format="pem"]'):
                    if certificate.text is None:
                        continue
                    pem_certificates.append(
                        KeyboxValidator._sanitize_pem_certificate(certificate.text)
                    )
                    if len(pem_certificates) == pem_number:
                        break
                if len(pem_certificates) == pem_number:
                    break
            if len(pem_certificates) == pem_number:
                break

        if not pem_certificates:
            raise Exception("No Certificate found.")
        return pem_certificates

    @staticmethod
    def _sanitize_pem_certificate(raw: str) -> str:
        if not raw:
            raise ValueError("Empty certificate content")

        text = raw.replace("\r\n", "\n").replace("\r", "\n").strip()
        begin_idx = text.find(_PEM_BEGIN)
        if begin_idx != -1:
            end_idx = text.find(_PEM_END, begin_idx + len(_PEM_BEGIN))
            if end_idx != -1:
                text = text[begin_idx + len(_PEM_BEGIN):end_idx]

        runs: list[list[str]] = []
        current: list[str] = []
        for line in text.splitlines():
            stripped = _WS.sub("", line)
            if not stripped:
                # Ignore blank lines: some generators inject them into PEM content.
                continue

            if stripped.startswith("-----"):
                if current:
                    runs.append(current)
                    current = []
                continue

            if _B64_LINE.fullmatch(stripped):
                current.append(stripped)
            elif current:
                runs.append(current)
                current = []

        if current:
            runs.append(current)

        if not runs:
            raise ValueError("Certificate contains no recoverable base64 data")

        best = max(runs, key=lambda run: sum(len(segment) for segment in run))
        if len(best) > 1:
            modal_len, _ = Counter(len(segment) for segment in best).most_common(1)[0]
            body = [segment for segment in best if len(segment) == modal_len]
            last_full_index = max(
                index for index, segment in enumerate(best) if len(segment) == modal_len
            )
            if last_full_index + 1 < len(best) and len(best[last_full_index + 1]) < modal_len:
                body.append(best[last_full_index + 1])
            best = body

        payload = "".join(best)
        padding = (-len(payload)) % 4
        try:
            der = base64.b64decode(payload + "=" * padding, validate=False)
        except binascii.Error as exc:
            raise ValueError(f"Certificate base64 payload is not decodable: {exc}")

        payload = base64.b64encode(der).decode("ascii")
        wrapped = "\n".join(payload[index:index + 64] for index in range(0, len(payload), 64))
        return f"{_PEM_BEGIN}\n{wrapped}\n{_PEM_END}\n"

    @staticmethod
    def _subject_serial_number(certificate: x509.Certificate) -> str | None:
        for attr in certificate.subject:
            if attr.oid._name == "serialNumber":
                return attr.value.lower()
        return None

    @staticmethod
    def _verify_certificate_chain(certificates: list[x509.Certificate]) -> bool:
        for index in range(len(certificates) - 1):
            child = certificates[index]
            parent = certificates[index + 1]

            if child.issuer != parent.subject:
                return False

            signature = child.signature
            signature_algorithm = child.signature_algorithm_oid._name
            tbs_certificate = child.tbs_certificate_bytes
            public_key = parent.public_key()

            try:
                if signature_algorithm in {
                    "sha256WithRSAEncryption",
                    "sha1WithRSAEncryption",
                    "sha384WithRSAEncryption",
                    "sha512WithRSAEncryption",
                }:
                    hash_algorithm = {
                        "sha256WithRSAEncryption": hashes.SHA256(),
                        "sha1WithRSAEncryption": hashes.SHA1(),
                        "sha384WithRSAEncryption": hashes.SHA384(),
                        "sha512WithRSAEncryption": hashes.SHA512(),
                    }[signature_algorithm]
                    public_key.verify(
                        signature,
                        tbs_certificate,
                        padding.PKCS1v15(),
                        hash_algorithm,
                    )
                elif signature_algorithm in {
                    "ecdsa-with-SHA256",
                    "ecdsa-with-SHA1",
                    "ecdsa-with-SHA384",
                    "ecdsa-with-SHA512",
                }:
                    hash_algorithm = {
                        "ecdsa-with-SHA256": hashes.SHA256(),
                        "ecdsa-with-SHA1": hashes.SHA1(),
                        "ecdsa-with-SHA384": hashes.SHA384(),
                        "ecdsa-with-SHA512": hashes.SHA512(),
                    }[signature_algorithm]
                    public_key.verify(
                        signature,
                        tbs_certificate,
                        ec.ECDSA(hash_algorithm),
                    )
                else:
                    return False
            except Exception:
                return False

        return True

    @staticmethod
    def _has_special_serial_violation(certificates: list[x509.Certificate]) -> bool:
        special_serial = "f92009e853b6b045"
        cert_count = len(certificates)
        allowed_index = 2 if cert_count == 3 else 3 if cert_count > 3 else None

        for index, certificate in enumerate(certificates):
            cert_serial = hex(certificate.serial_number)[2:].lower()
            subject_serial = None
            for attr in certificate.subject:
                if attr.oid._name == "serialNumber":
                    subject_serial = attr.value.lower()
                    break

            if cert_serial == special_serial or subject_serial == special_serial:
                if allowed_index is None or index != allowed_index:
                    return True

        total_count = 0
        for certificate in certificates:
            cert_serial = hex(certificate.serial_number)[2:].lower()
            if cert_serial == special_serial:
                total_count += 1
                continue
            for attr in certificate.subject:
                if attr.oid._name == "serialNumber" and attr.value.lower() == special_serial:
                    total_count += 1
                    break

        return total_count > 1

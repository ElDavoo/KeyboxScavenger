from __future__ import annotations

import xml.etree.ElementTree as ET


class XmlNormalizationError(ValueError):
    pass


KEY_MATERIAL_TAGS = {"Certificate", "PrivateKey"}


def normalize_xml_payload(xml_payload: bytes) -> bytes:
    try:
        root = ET.fromstring(xml_payload)
    except ET.ParseError as exc:
        raise XmlNormalizationError(str(exc)) from exc

    _normalize_node(root)

    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _normalize_node(node: ET.Element) -> None:
    if node.attrib:
        ordered_attributes = {
            key: value
            for key, value in sorted(node.attrib.items())
            if key.lower() != "deviceid"
        }
        node.attrib.clear()
        node.attrib.update(ordered_attributes)

    if node.text is not None:
        node.text = _normalize_text(node.tag, node.text)

    for child in list(node):
        if child.tag is ET.Comment:
            node.remove(child)
            continue

        _normalize_node(child)

        if child.tail is not None:
            stripped_tail = child.tail.strip()
            child.tail = stripped_tail if stripped_tail else None


def _normalize_text(tag: str, text: str) -> str | None:
    if tag in KEY_MATERIAL_TAGS:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        return "\n".join(lines) if lines else None

    stripped_text = text.strip()
    return stripped_text if stripped_text else None

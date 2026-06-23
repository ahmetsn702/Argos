import xml.etree.ElementTree as ET
import io
import zipfile
from app.services.maltego.entity_map import get_entity_type

class MtgxBuilder:
    def build(self, graph: dict) -> bytes:
        root = ET.Element("MaltegoGraph", version="1.2")
        entities_el = ET.SubElement(root, "Entities")
        
        for f in graph.get("findings", []):
            fid = str(f.get("id", ""))
            ftype = str(f.get("type", ""))
            fval = str(f.get("value", ""))
            fconf = str(f.get("confidence", 0.0))
            
            entity_type = get_entity_type(ftype)
            
            # Entity with Type and id
            entity_el = ET.SubElement(entities_el, "Entity", Type=entity_type, id=fid)
            
            properties_el = ET.SubElement(entity_el, "Properties")
            prop_el = ET.SubElement(properties_el, "Property", Name="notes")
            prop_el.text = fconf
            
            display_el = ET.SubElement(entity_el, "DisplayInformation")
            label_el = ET.SubElement(display_el, "Label")
            label_el.text = fval
            
        links_el = ET.SubElement(root, "Links")
        for e in graph.get("edges", []):
            from_id = str(e.get("from_id", ""))
            to_id = str(e.get("to_id", ""))
            rel_type = str(e.get("rel_type", ""))
            weight = str(e.get("weight", 1.0))
            
            ET.SubElement(links_el, "Link", {
                "Source": from_id,
                "Target": to_id,
                "Relation": rel_type,
                "Weight": weight
            })
            
        try:
            ET.indent(root, space="  ")
        except Exception:
            pass
            
        xml_bytes = b'<?xml version="1.0" encoding="utf-8"?>\n' + ET.tostring(root, encoding="utf-8")
        
        bio = io.BytesIO()
        with zipfile.ZipFile(bio, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("Entities/", "")
            zf.writestr("graph.xml", xml_bytes)
            
        return bio.getvalue()

import io
import xml.etree.ElementTree as ET
import zipfile
import pytest
from datetime import datetime, timezone
from unittest.mock import patch
from fastapi.testclient import TestClient

from app.main import app
from app.models.confidence import (
    ConfidenceGraph, ConfidenceFinding, ConfidenceEdge, FindingType, EdgeType
)
from app.services.maltego.entity_map import get_entity_type
from app.services.maltego.mtgx_builder import MtgxBuilder
from app.services.confidence.cache import default_cache

client = TestClient(app)

# 1. Test get_entity_type with valid inputs
def test_entity_map_valid_types():
    assert get_entity_type("email") == "maltego.EmailAddress"
    assert get_entity_type("phone") == "maltego.PhoneNumber"
    assert get_entity_type("domain") == "maltego.Domain"
    assert get_entity_type("ip") == "maltego.IPv4Address"
    assert get_entity_type("username") == "maltego.Alias"
    assert get_entity_type("person") == "maltego.Person"
    assert get_entity_type("name") == "maltego.Person"
    assert get_entity_type("location") == "maltego.Location"
    # Test with enum
    assert get_entity_type(FindingType.EMAIL) == "maltego.EmailAddress"
    assert get_entity_type(FindingType.PHONE) == "maltego.PhoneNumber"
    # Test case sensitivity and whitespace
    assert get_entity_type(" EMAIL ") == "maltego.EmailAddress"

# 2. Test get_entity_type with invalid/unknown types
def test_entity_map_invalid_type():
    assert get_entity_type("unknown_type") == "maltego.Unknown"
    assert get_entity_type("") == "maltego.Unknown"
    assert get_entity_type(None) == "maltego.Unknown"

# 3. Test MtgxBuilder XML format
def test_mtgx_builder_xml_format():
    graph_data = {
        "findings": [
            {"id": "f1", "type": "email", "value": "test@example.com", "confidence": 0.85},
            {"id": "f2", "type": "phone", "value": "+12345", "confidence": 0.75}
        ],
        "edges": [
            {"from_id": "f1", "to_id": "f2", "rel_type": "same_as", "weight": 0.9}
        ]
    }
    builder = MtgxBuilder()
    mtgx_bytes = builder.build(graph_data)
    
    # Extract graph.xml from bytes
    bio = io.BytesIO(mtgx_bytes)
    with zipfile.ZipFile(bio, "r") as zf:
        xml_content = zf.read("graph.xml")
        
    root = ET.fromstring(xml_content)
    assert root.tag == "MaltegoGraph"
    assert root.attrib.get("version") == "1.2"
    
    entities = root.find("Entities")
    assert entities is not None
    entity_list = entities.findall("Entity")
    assert len(entity_list) == 2
    
    # Check first entity
    e1 = entity_list[0]
    assert e1.attrib.get("Type") == "maltego.EmailAddress"
    assert e1.attrib.get("id") == "f1"
    notes = e1.find("Properties").find("Property")
    assert notes.attrib.get("Name") == "notes"
    assert notes.text == "0.85"
    label = e1.find("DisplayInformation").find("Label")
    assert label.text == "test@example.com"
    
    links = root.find("Links")
    assert links is not None
    link_list = links.findall("Link")
    assert len(link_list) == 1
    l1 = link_list[0]
    assert l1.attrib.get("Source") == "f1"
    assert l1.attrib.get("Target") == "f2"
    assert l1.attrib.get("Relation") == "same_as"
    assert l1.attrib.get("Weight") == "0.9"

# 4. Test MtgxBuilder Zip Structure
def test_mtgx_builder_zip_structure():
    graph_data = {"findings": [], "edges": []}
    builder = MtgxBuilder()
    mtgx_bytes = builder.build(graph_data)
    
    bio = io.BytesIO(mtgx_bytes)
    with zipfile.ZipFile(bio, "r") as zf:
        namelist = zf.namelist()
        assert "graph.xml" in namelist
        assert "Entities/" in namelist

# 5. Test Router with MALTEGO_ENABLED=False
def test_router_maltego_disabled():
    with patch("app.routers.export.ff.MALTEGO_ENABLED", False):
        response = client.get("/export/maltego?seed_key=test_seed")
        assert response.status_code == 200
        assert response.json() == {"enabled": False}

# 6. Test Router Graph Not Found
def test_router_graph_not_found():
    with patch("app.routers.export.ff.MALTEGO_ENABLED", True):
        # Ensure the cache doesn't have this key
        default_cache.invalidate("nonexistent_seed")
        response = client.get("/export/maltego?seed_key=nonexistent_seed")
        assert response.status_code == 404
        assert response.json()["detail"] == "Graph not found"

# 7. Test Router Success Case
def test_router_export_success():
    with patch("app.routers.export.ff.MALTEGO_ENABLED", True):
        now = datetime.now(timezone.utc)
        graph = ConfidenceGraph(
            seed_key="success_seed",
            findings={
                "f1": ConfidenceFinding(
                    id="f1",
                    type=FindingType.EMAIL,
                    value="success@example.com",
                    raw_value="success@example.com",
                    sources=[],
                    confidence_score=0.95,
                    first_seen=now,
                    last_seen=now
                ),
                "f2": ConfidenceFinding(
                    id="f2",
                    type=FindingType.PHONE,
                    value="+987654321",
                    raw_value="+987654321",
                    sources=[],
                    confidence_score=0.85,
                    first_seen=now,
                    last_seen=now
                )
            },
            edges=[
                ConfidenceEdge(
                    source_id="f1",
                    target_id="f2",
                    edge_type=EdgeType.SAME_AS,
                    weight=0.95
                )
            ],
            computed_at=now
        )
        default_cache.put(graph)
        
        response = client.get("/export/maltego?seed_key=success_seed")
        assert response.status_code == 200
        assert response.headers.get("content-type") == "application/zip"
        assert "attachment; filename=argos_success_seed.mtgx" in response.headers.get("content-disposition", "")
        
        # Verify the ZIP and XML content from response bytes
        mtgx_bytes = response.content
        bio = io.BytesIO(mtgx_bytes)
        with zipfile.ZipFile(bio, "r") as zf:
            assert "graph.xml" in zf.namelist()
            assert "Entities/" in zf.namelist()
            xml_content = zf.read("graph.xml")
            
        root = ET.fromstring(xml_content)
        assert root.tag == "MaltegoGraph"
        
        entity_list = root.find("Entities").findall("Entity")
        assert len(entity_list) == 2
        assert entity_list[0].attrib.get("Type") == "maltego.EmailAddress"
        assert entity_list[1].attrib.get("Type") == "maltego.PhoneNumber"
        
        link_list = root.find("Links").findall("Link")
        assert len(link_list) == 1
        assert link_list[0].attrib.get("Source") == "f1"
        assert link_list[0].attrib.get("Target") == "f2"

# 8. Test E2E Empty Fields / Graceful Handling
def test_router_export_empty_fields_handling():
    with patch("app.routers.export.ff.MALTEGO_ENABLED", True):
        now = datetime.now(timezone.utc)
        graph = ConfidenceGraph(
            seed_key="empty_fields_seed",
            findings={},
            edges=[],
            computed_at=now
        )
        default_cache.put(graph)
        
        response = client.get("/export/maltego?seed_key=empty_fields_seed")
        assert response.status_code == 200
        assert response.headers.get("content-type") == "application/zip"
        
        # Verify empty structures do not crash the builder
        bio = io.BytesIO(response.content)
        with zipfile.ZipFile(bio, "r") as zf:
            xml_content = zf.read("graph.xml")
            
        root = ET.fromstring(xml_content)
        assert root.find("Entities") is not None
        assert len(root.find("Entities").findall("Entity")) == 0
        assert root.find("Links") is not None
        assert len(root.find("Links").findall("Link")) == 0

import os
import json
import pytest
from app.services.geo_service import analyze_visual_signals

def test_country_clues_file_integrity():
    """Verify that country_clues.json exists, is valid JSON, and has all 15 countries."""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    clues_path = os.path.abspath(os.path.join(current_dir, "..", "app", "data", "country_clues.json"))
    
    assert os.path.exists(clues_path), f"country_clues.json not found at {clues_path}"
    
    with open(clues_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    expected_countries = [
        "Turkey", "Germany", "France", "United Kingdom", "USA", "Japan", 
        "Brazil", "Australia", "Russia", "India", "Spain", "Italy", 
        "Netherlands", "Poland", "Greece"
    ]
    
    # Check that all expected countries are in the dataset
    for country in expected_countries:
        assert country in data, f"{country} missing from country_clues.json"
        clue = data[country]
        
        # Verify structure
        for field in ["driving_side", "road_center_line", "plate_format", "plate_colors", "language_script"]:
            assert field in clue, f"Field '{field}' missing for country '{country}'"
            
    # Spot check specific known clues
    assert data["Turkey"]["driving_side"] == "right"
    assert data["United Kingdom"]["driving_side"] == "left"
    assert data["Japan"]["driving_side"] == "left"
    assert data["USA"]["driving_side"] == "right"
    
    assert "yellow" in data["USA"]["road_center_line"]
    assert "white" in data["Germany"]["road_center_line"]
    assert "white" in data["Netherlands"]["road_center_line"]

@pytest.mark.anyio
async def test_analyze_visual_signals_compiles_prompt():
    """Verify that analyze_visual_signals attempts to generate a prompt and doesn't crash when clues file is read."""
    from unittest.mock import MagicMock, patch
    import base64
    
    mock_response = MagicMock()
    mock_response.text = '{"estimated_country": "Turkey", "confidence": 0.9}'
    
    # Pass a valid base64-encoded string
    valid_base64 = base64.b64encode(b"fake_image_bytes").decode("utf-8")
    
    with patch("google.genai.Client") as mock_client_cls:
        mock_client = mock_client_cls.return_value
        mock_client.models.generate_content = MagicMock(return_value=mock_response)
        
        result = await analyze_visual_signals(valid_base64)
        
        # Ensure it resolved and parse/generated content
        assert mock_client.models.generate_content.called
        call_args = mock_client.models.generate_content.call_args[1]
        contents = call_args["contents"]
        
        # First item in contents is our generated prompt
        prompt = contents[0]
        assert "VISUAL CLUES REFERENCE DATABASE" in prompt
        assert "Turkey" in prompt
        assert "United Kingdom" in prompt
        assert "right" in prompt
        
        assert result == {"estimated_country": "Turkey", "confidence": 0.9}

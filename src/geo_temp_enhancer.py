# geo_temp_enhancer.property
import json
import os
import time
from typing import Dict, List, Any, Optional, Tuple
import requests
import dateparser
from datetime import datetime

# Set the root directory for relative paths
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

class GeoTemporalEnhancer:
    """
    Enhances extracted entity data with:
    - Geospatial coordinates for locations
    - Standardized temporal information
    """
    
    def __init__(self):
        """
        Initialize the enhancer with optional API key for geocoding.
        """
        # Cache to avoid redundant geocoding requests
        self.geocoding_cache = {}
        # Cache to avoid redundant temporal parsing
        self.temporal_cache = {}
    
    def enhance_results(self, extraction_results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Enhance the extraction results with geospatial and temporal information
        using the unified entity ID system.
        
        Args:
            extraction_results: The original extraction results
            
        Returns:
            Enhanced results with additional geospatial and temporal data
        """
        enhanced_results = extraction_results.copy()
        
        if "entities" in enhanced_results:
            # Create empty lists for specialized attribute tables
            locations_data = []
            timeperiods_data = []
            
            # Process all entities
            enhanced_entities = []
            for entity in enhanced_results["entities"]:
                # Copy the original entity but keep only the basic fields
                enhanced_entity = {
                    "id": entity["id"],
                    "type": entity["type"],
                    "text": entity["text"],
                    "confidence": entity["confidence"]
                }
                
                # Keep the normalized field if it exists
                if "normalized" in entity:
                    enhanced_entity["normalized"] = entity["normalized"]
                
                entity_type = entity.get("type", "")

                # Process LOCATION entities
                if entity_type == "LOCATION":
                    # Get the normalized location name if available, otherwise use the text
                    location_name = entity.get("normalized", entity["text"])
                    
                    # Create basic location_attributes (basic info that will always be added)
                    location_attributes = {
                        "entity_id": entity["id"]
                    }
                    
                    # Check cache or geocode the location
                    if location_name in self.geocoding_cache:
                        geo_data = self.geocoding_cache[location_name]
                    else:
                        geo_data = self.geocode_location(location_name)
                        self.geocoding_cache[location_name] = geo_data
                    
                    # Add coordinate information if geocoding was successful
                    if geo_data:
                        # Add all geographic attributes to location_attributes
                        for key, value in geo_data.items():
                            location_attributes[key] = value
                    
                    # Always add to locations_data regardless of geocoding success
                    locations_data.append(location_attributes)
                    
                    # Sleep to respect API rate limits
                    time.sleep(0.1)
                
                # Process TIME entities
                elif entity_type == "TIME":
                    # Get the normalized date/time expression
                    normalized = entity.get("normalized", "")
                    
                    # Check cache or parse the temporal info
                    if normalized in self.temporal_cache:
                        temporal_enhancements = self.temporal_cache[normalized]
                    else:
                        temporal_enhancements = self.parse_temporal_info(
                            entity["text"], 
                            normalized
                        )
                        self.temporal_cache[normalized] = temporal_enhancements
                    
                    # Add time information only to timeperiods_data, not to enhanced_entity
                    time_attributes = {
                        "entity_id": entity["id"]
                    }
                    
                    # Add all temporal attributes to time_attributes
                    for key, value in temporal_enhancements.items():
                        time_attributes[key] = value
                    
                    timeperiods_data.append(time_attributes)
                
                enhanced_entities.append(enhanced_entity)
            
            # Update the entities list
            enhanced_results["entities"] = enhanced_entities
            
            # Add specialized attribute tables
            enhanced_results["locations"] = locations_data
            enhanced_results["timeperiods"] = timeperiods_data
        
        return enhanced_results
    
    def geocode_location(self, location_name: str) -> Dict[str, Any]:
        """
        Geocode a location to get its coordinates.
        
        This implementation uses Nominatim (OpenStreetMap), but could be
        replaced with Google Maps, Mapbox, or other geocoding services.
        
        Args:
            location_name: The name of the location to geocode
            
        Returns:
            Dictionary with geographic information
        """
        # Current implementation remains the same as before
        try:
            # Using Nominatim API (OpenStreetMap)
            headers = {'User-Agent': 'HistoricalEntityExtraction/1.0'}
            
            params = {
                'q': location_name,
                'format': 'json',
                'limit': 1
            }
            
            response = requests.get(
                'https://nominatim.openstreetmap.org/search',
                headers=headers,
                params=params
            )
            
            if response.status_code == 200:
                results = response.json()
                if results:
                    result = results[0]
                    flattened_data = {
                        "latitude": float(result["lat"]),
                        "longitude": float(result["lon"]),
                        "display_name": result["display_name"],
                        "location_type": result.get("type", ""),
                        "importance": result.get("importance", 0.0),
                        "osm_id": result.get("osm_id", "")
                    }
                    
                    if "boundingbox" in result:
                        flattened_data["bbox_south"] = float(result["boundingbox"][0])
                        flattened_data["bbox_north"] = float(result["boundingbox"][1])
                        flattened_data["bbox_west"] = float(result["boundingbox"][2])
                        flattened_data["bbox_east"] = float(result["boundingbox"][3])
                    
                    return flattened_data
            
            return {}
            
        except Exception as e:
            print(f"Error geocoding location '{location_name}': {e}")
            return {}
    
    def parse_temporal_info(self, text: str, normalized: str) -> Dict[str, Any]:
        """
        Parse temporal information to extract standardized dates and metadata.
        
        Args:
            text: The original temporal text
            normalized: The normalized temporal expression
            
        Returns:
            Enhanced temporal information
        """
        # Current implementation remains the same as before
        result = {
            "precision": "UNKNOWN",
            "type": "UNKNOWN",
            "date_reliability": 0.7
        }
        
        # First, try to use the normalized value if it exists
        if normalized:
            # Handle ISO-formatted dates (YYYY-MM-DD)
            if len(normalized) >= 10 and normalized[4] == '-' and normalized[7] == '-':
                result["start_date"] = normalized
                result["end_date"] = normalized
                result["precision"] = "DAY"
                result["type"] = "POINT"
                result["date_reliability"] = 0.9
                
            # Handle year-month format (YYYY-MM)
            elif len(normalized) >= 7 and normalized[4] == '-':
                year, month = normalized.split('-')
                result["start_date"] = f"{normalized}-01"
                
                # Calculate the last day of the month
                if month == '02':
                    # Simple leap year check
                    if int(year) % 4 == 0 and (int(year) % 100 != 0 or int(year) % 400 == 0):
                        result["end_date"] = f"{normalized}-29"
                    else:
                        result["end_date"] = f"{normalized}-28"
                elif month in ['04', '06', '09', '11']:
                    result["end_date"] = f"{normalized}-30"
                else:
                    result["end_date"] = f"{normalized}-31"
                
                result["precision"] = "MONTH"
                result["type"] = "PERIOD"
                result["date_reliability"] = 0.85
                
            # Handle year-only format (YYYY)
            elif len(normalized) == 4 and normalized.isdigit():
                result["start_date"] = f"{normalized}-01-01"
                result["end_date"] = f"{normalized}-12-31"
                result["precision"] = "YEAR"
                result["type"] = "PERIOD"
                result["date_reliability"] = 0.8
        
        # If normalized format wasn't recognized, try to parse the original text
        if result["precision"] == "UNKNOWN":
            try:
                # Use dateparser to handle natural language dates
                parsed_date = dateparser.parse(text)
                if parsed_date:
                    # Format as ISO
                    iso_date = parsed_date.strftime("%Y-%m-%d")
                    result["start_date"] = iso_date
                    result["end_date"] = iso_date
                    result["precision"] = "DAY"
                    result["type"] = "POINT"
                    result["date_reliability"] = 0.7
            except Exception as e:
                print(f"Error parsing date '{text}': {e}")
        
        # Look for specific temporal patterns in the text
        if "month" in text.lower():
            result["precision"] = "MONTH"
            result["type"] = "PERIOD"
        
        if "year" in text.lower():
            result["precision"] = "YEAR"
            result["type"] = "PERIOD"
        
        return result

def enhance_extraction_results():
    """
    Enhance extraction results with geospatial and temporal information.
    """
    # Create enhancer
    enhancer = GeoTemporalEnhancer()
    
    # Define input and output file paths
    input_file = os.path.join(ROOT_DIR, "extracted_results", "all_results_method2.json")
    output_dir = os.path.join(ROOT_DIR, "enhanced_results")
    os.makedirs(output_dir, exist_ok=True) 
    output_file = os.path.join(output_dir, "NZZ_19150405_method2.json")

    # Load input data
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Check if the structure is a dictionary of articles
    if isinstance(data, dict) and all(isinstance(value, dict) for value in data.values()):
        # Process each article
        enhanced_data = {}
        for article_id, article_data in data.items():
            enhanced_data[article_id] = enhancer.enhance_results(article_data)
    else:
        # Single article or different structure
        enhanced_data = enhancer.enhance_results(data)
    
    # Save enhanced data
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(enhanced_data, f, ensure_ascii=False, indent=2)
    
    print(f"Enhanced data saved to {output_file}")

if __name__ == "__main__":
    enhance_extraction_results()
# geo_temp_enhancer.py
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
        Handles various formats including date ranges, ISO timestamps, and invalid dates.
        
        Args:
            text: The original temporal text
            normalized: The normalized temporal expression
            
        Returns:
            Enhanced temporal information
        """
        result = {
            "precision": "UNKNOWN",
            "type": "UNKNOWN",
            "date_reliability": 0.7
        }
        
        def get_last_day_of_month(year, month):
            """Helper function to get the last day of a month"""
            if month == 2:
                if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0):
                    return 29
                else:
                    return 28
            elif month in [4, 6, 9, 11]:
                return 30
            else:
                return 31
        
        def fix_invalid_date(year, month, day):
            """Fix invalid dates by adjusting to valid values"""
            # Ensure month is valid
            month = max(1, min(12, month))
            
            # Ensure day is valid for the given month
            max_day = get_last_day_of_month(year, month)

            # Adjust day if it exceeds the maximum for the month
            if day > max_day:
                day = max_day 
            
            return year, month, day
        
        def extract_standard_date(date_str):
            """Extract a standard ISO date (YYYY-MM-DD)"""
            try:
                parts = date_str.split('-')
                year = int(parts[0])
                month = 1
                day = 1
                
                if len(parts) > 1 and parts[1].isdigit():
                    month = int(parts[1])
                
                if len(parts) > 2:
                    # Handle special T format for time (e.g., 05T13:00)
                    day_part = parts[2].split('T')[0]
                    if day_part.isdigit():
                        day = int(day_part)
                
                # Validate and fix date components
                year, month, day = fix_invalid_date(year, month, day)
                
                return {
                    "date": f"{year:04d}-{month:02d}-{day:02d}",
                    "year": year,
                    "month": month,
                    "day": day
                }
            except Exception as e:
                # print(f"Error extracting standard date from '{date_str}': {e}")
                return None
        
        # Main processing starts here
        if normalized:
            # Remove any leading text before actual dates
            if "approximately " in normalized:
                normalized = normalized.replace("approximately ", "")
            
            # Case 1: Handle date ranges with "to" or "and"
            for separator in [" to ", " and "]:
                if separator in normalized:
                    try:
                        start_part, end_part = normalized.split(separator)
                        
                        # Extract start date
                        start_date = extract_standard_date(start_part.strip())
                        if not start_date:
                            continue
                        
                        # Extract end date
                        end_date = extract_standard_date(end_part.strip())
                        if not end_date:
                            continue
                        
                        # Set date range
                        result["start_date"] = start_date["date"]
                        result["end_date"] = end_date["date"]
                        
                        # Determine precision
                        if len(start_part.split('-')) > 2 and len(end_part.split('-')) > 2:
                            result["precision"] = "DAY"
                        elif len(start_part.split('-')) > 1 and len(end_part.split('-')) > 1:
                            result["precision"] = "MONTH"
                        else:
                            result["precision"] = "YEAR"
                        
                        result["type"] = "PERIOD"
                        result["date_reliability"] = 0.85
                        return result
                    except Exception as e:
                        # This separator didn't work, try the next one
                        continue
            
            # Case 2: Handle ISO timestamps with T
            if 'T' in normalized:
                try:
                    date_part = normalized.split('T')[0]
                    time_part = normalized.split('T')[1]
                    
                    date_info = extract_standard_date(date_part)
                    if date_info:
                        result["start_date"] = date_info["date"]
                        result["end_date"] = date_info["date"]
                        result["precision"] = "DAY"
                        result["type"] = "POINT"
                        result["date_reliability"] = 0.9
                        return result
                except Exception as e:
                    # Continue to next case
                    pass
            
            # Case 3: Simple year range (YYYY-YYYY)
            if len(normalized) == 9 and normalized[4] == '-' and normalized[:4].isdigit() and normalized[5:].isdigit():
                try:
                    start_year = int(normalized[:4])
                    end_year = int(normalized[5:])
                    
                    result["start_date"] = f"{start_year:04d}-01-01"
                    result["end_date"] = f"{end_year:04d}-12-31"
                    result["precision"] = "YEAR"
                    result["type"] = "PERIOD"
                    result["date_reliability"] = 0.85
                    return result
                except Exception as e:
                    # Continue to next case
                    pass
            
            # Case 4: Standard ISO date (YYYY-MM-DD)
            if len(normalized) >= 10 and normalized[4] == '-' and normalized[7] == '-':
                date_info = extract_standard_date(normalized)
                if date_info:
                    result["start_date"] = date_info["date"]
                    result["end_date"] = date_info["date"]
                    result["precision"] = "DAY"
                    result["type"] = "POINT"
                    result["date_reliability"] = 0.9
                    return result
            
            # Case 5: Year-month (YYYY-MM)
            if len(normalized) == 7 and normalized[4] == '-' and normalized[:4].isdigit() and normalized[5:].isdigit():
                try:
                    year = int(normalized[:4])
                    month = int(normalized[5:])
                    
                    # Validate month
                    month = max(1, min(12, month))
                    
                    # Calculate last day of month
                    last_day = get_last_day_of_month(year, month)
                    
                    result["start_date"] = f"{year:04d}-{month:02d}-01"
                    result["end_date"] = f"{year:04d}-{month:02d}-{last_day:02d}"
                    result["precision"] = "MONTH"
                    result["type"] = "PERIOD"
                    result["date_reliability"] = 0.85
                    return result
                except Exception as e:
                    # Continue to next case
                    pass
            
            # Case 6: Year only (YYYY)
            if len(normalized) == 4 and normalized.isdigit():
                try:
                    year = int(normalized)
                    result["start_date"] = f"{year:04d}-01-01"
                    result["end_date"] = f"{year:04d}-12-31"
                    result["precision"] = "YEAR"
                    result["type"] = "PERIOD"
                    result["date_reliability"] = 0.8
                    return result
                except Exception as e:
                    # Continue to next case
                    pass
        
        # If none of the patterns matched, try dateparser on the original text
        try:
            parsed_date = dateparser.parse(text)
            if parsed_date:
                iso_date = parsed_date.strftime("%Y-%m-%d")
                result["start_date"] = iso_date
                result["end_date"] = iso_date
                result["precision"] = "DAY"
                result["type"] = "POINT"
                result["date_reliability"] = 0.7
        except Exception as e:
            # Fallback to text analysis
            pass
        
        # Analyze text content for additional clues
        if text:
            if "month" in text.lower() or "monthly" in text.lower():
                if "precision" not in result or result["precision"] == "UNKNOWN":
                    result["precision"] = "MONTH"
                    result["type"] = "PERIOD"
            
            if "year" in text.lower() or "annual" in text.lower() or "wartime" in text.lower():
                if "precision" not in result or result["precision"] == "UNKNOWN":
                    result["precision"] = "YEAR"
                    result["type"] = "PERIOD"
        
        return result

def enhance_extraction_results():
    """
    Enhance extraction results with geospatial and temporal information
    for all files in the extracted_results folder.
    """
    # Create enhancer
    enhancer = GeoTemporalEnhancer()
    
    # Define input and output directories
    input_dir = os.path.join(ROOT_DIR, "extracted_results")
    output_dir = os.path.join(ROOT_DIR, "enhanced_results")
    os.makedirs(output_dir, exist_ok=True)
    
    # Get all result files in the input directory that match the pattern "*_results_method*.json"
    result_files = [f for f in os.listdir(input_dir) if f.endswith('.json') and '_results_method' in f]
    
    if not result_files:
        print(f"No result files found in {input_dir}")
        return
    
    print(f"Found {len(result_files)} result files to process")
    
    # Process each result file
    for result_file in result_files:
        input_file_path = os.path.join(input_dir, result_file)
        
        # Extract base filename and method number
        # Example: "NZZ_19150405_results_method2.json" -> "NZZ_19150405" and "2"
        filename_parts = result_file.split('_results_method')
        base_filename = filename_parts[0]
        method_num = filename_parts[1].split('.')[0]
        
        # Create output filename
        output_filename = f"{base_filename}_method{method_num}.json"
        output_file_path = os.path.join(output_dir, output_filename)
        
        print(f"\n=== Processing file: {result_file} ===")
        
        # Load input data
        with open(input_file_path, 'r', encoding='utf-8') as f:
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
        with open(output_file_path, 'w', encoding='utf-8') as f:
            json.dump(enhanced_data, f, ensure_ascii=False, indent=2)
        
        print(f"Enhanced data saved to {output_filename}")
    
    print(f"\nAll files processed! Enhanced results saved in: {output_dir}")

if __name__ == "__main__":
    enhance_extraction_results()

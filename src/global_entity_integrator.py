# global_entity_integrator.py
import json
import os
import glob
from typing import Dict, List, Any, Tuple, Set
import hashlib
from difflib import SequenceMatcher
from math import radians, sin, cos, sqrt, atan2
import csv

# Set the root directory for relative paths
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

class GlobalEntityIntegrator:
    """
    Class for integrating entities extracted from multiple documents
    into a global ID system and merging duplicate entities
    """
    
    def __init__(self, debug_mode=False):
        self.global_entities = {}  # global_id -> entity
        self.global_relations = []
        self.id_mapping = {}  # (article_id, original_id) -> global_id
        self.debug_mode = debug_mode
        
    def create_global_entity_id(self, entity_type, normalized_text, attributes=None):
        """
        Create a unique ID based on entity characteristics
        """
        # For location objects, use coordinate-based ID
        if entity_type == "LOCATION" and attributes and "latitude" in attributes and "longitude" in attributes:
            geo_signature = f"{round(attributes['latitude'], 5)}_{round(attributes['longitude'], 5)}"
            base = f"LOC_{geo_signature}"
        # For time objects, use normalized date-based ID
        elif entity_type == "TIME" and attributes and "start_date" in attributes:
            base = f"TIME_{attributes['start_date']}"
        # For other objects, use normalized text-based ID
        else:
            base = f"{entity_type}_{normalized_text.lower().replace(' ', '_')}"
        
        # Create hash-based unique ID
        return hashlib.md5(base.encode()).hexdigest()[:12]
        
    def are_entities_similar(self, entity1, entity2, threshold=0.8):
        """Determine if two entities are semantically identical"""
        # If types are different, return False
        if entity1["type"] != entity2["type"]:
            return False
            
        # Compare based on entity type
        if entity1["type"] == "LOCATION":
            # Compare based on coordinates
            if all(k in entity1 and k in entity2 for k in ["latitude", "longitude"]):
                # Calculate distance using Haversine formula
                R = 6371  # Earth radius (km)
                lat1, lon1 = radians(entity1["latitude"]), radians(entity1["longitude"])
                lat2, lon2 = radians(entity2["latitude"]), radians(entity2["longitude"])
                
                dlat = lat2 - lat1
                dlon = lon2 - lon1
                
                a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
                c = 2 * atan2(sqrt(a), sqrt(1-a))
                distance = R * c
                
                # Consider as same location if within 1km
                return distance < 1
        
        elif entity1["type"] == "TIME":
            # Compare dates
            if "start_date" in entity1 and "start_date" in entity2:
                return entity1["start_date"] == entity2["start_date"]
            # Compare using normalized values
            if "normalized" in entity1 and "normalized" in entity2:
                return entity1["normalized"] == entity2["normalized"]
        
        # Compare text similarity
        normalized1 = entity1.get("normalized", entity1["text"]).lower()
        normalized2 = entity2.get("normalized", entity2["text"]).lower()
        
        similarity = SequenceMatcher(None, normalized1, normalized2).ratio()
        return similarity >= threshold
    
    def merge_location_attributes(self, entity, attributes, new_confidence=0):
        """
        Smartly merge location-related attributes
        
        Args:
            entity: Existing global entity
            attributes: New attribute data
            new_confidence: Confidence of the new entity (optional)
        """
        before_keys = set(entity.keys()) if self.debug_mode else set()
        
        # List of location attributes (coordinates, name, type, boundaries, etc.)
        location_attrs = [
            "latitude", "longitude", "display_name", "location_type",
            "importance", "osm_id", "bbox_south", "bbox_north", 
            "bbox_west", "bbox_east"
        ]
        
        # Attribute completeness priority - always add missing attributes
        for key in location_attrs:
            if key in attributes and (key not in entity or not entity[key]):
                entity[key] = attributes[key]
        
        # Update if there's a more detailed display_name
        if "display_name" in attributes and "display_name" in entity:
            if len(attributes["display_name"]) > len(entity["display_name"]):
                entity["display_name"] = attributes["display_name"]
        
        # Update if coordinates have higher precision (more decimal places)
        if all(k in attributes for k in ["latitude", "longitude"]) and all(k in entity for k in ["latitude", "longitude"]):
            current_lat_precision = len(str(entity["latitude"]).split('.')[-1]) if '.' in str(entity["latitude"]) else 0
            current_lon_precision = len(str(entity["longitude"]).split('.')[-1]) if '.' in str(entity["longitude"]) else 0
            
            new_lat_precision = len(str(attributes["latitude"]).split('.')[-1]) if '.' in str(attributes["latitude"]) else 0
            new_lon_precision = len(str(attributes["longitude"]).split('.')[-1]) if '.' in str(attributes["longitude"]) else 0
            
            if new_lat_precision > current_lat_precision or new_lon_precision > current_lon_precision:
                # Update all coordinate-related attributes
                for key in ["latitude", "longitude", "bbox_south", "bbox_north", "bbox_west", "bbox_east"]:
                    if key in attributes:
                        entity[key] = attributes[key]
        
        if self.debug_mode:
            after_keys = set(entity.keys())
            new_attrs = after_keys - before_keys
            if new_attrs:
                print(f"  Added location attributes: {', '.join(new_attrs)}")
    
    def merge_time_attributes(self, entity, attributes, new_confidence=0):
        """
        Smartly merge time-related attributes
        
        Args:
            entity: Existing global entity
            attributes: New attribute data
            new_confidence: Confidence of the new entity (optional)
        """
        before_keys = set(entity.keys()) if self.debug_mode else set()
        
        # List of time attributes
        time_attrs = ["precision", "type", "start_date", "end_date", "date_reliability"]
        
        # Attribute completeness priority - always add missing attributes (except type)
        for key in time_attrs:
            if key != "type" and key in attributes and (key not in entity or not entity[key]):
                entity[key] = attributes[key]
                
        # Update if there's more precise date information
        if "precision" in attributes and "precision" in entity:
            precision_rank = {"UNKNOWN": 0, "YEAR": 1, "MONTH": 2, "DAY": 3, "HOUR": 4, "MINUTE": 5}
            
            if precision_rank.get(attributes["precision"], 0) > precision_rank.get(entity["precision"], 0):
                # Update all time-related attributes with more precise date information
                for key in time_attrs:
                    if key in attributes:
                        entity[key] = attributes[key]
        
        if self.debug_mode:
            after_keys = set(entity.keys())
            new_attrs = after_keys - before_keys
            if new_attrs:
                print(f"  Added time attributes: {', '.join(new_attrs)}")
    
    def integrate_article(self, article_id, article_data):
        """
        Integrate data from a single article into the global entity system
        """
        if self.debug_mode:
            print(f"Integrating article: {article_id}")
            print(f"  Entities: {len(article_data.get('entities', []))}")
            print(f"  Relations: {len(article_data.get('relations', []))}")
            print(f"  Locations: {len(article_data.get('locations', []))}")
            print(f"  Timeperiods: {len(article_data.get('timeperiods', []))}")
        
        # 1. Process entities - first map location and time attributes to entities
        location_map = {}
        time_map = {}
        
        # Map location attributes - use entity_id only as key and store the rest of the fields as values
        for location in article_data.get("locations", []):
            entity_id = location["entity_id"]
            # Copy attribute information excluding the entity_id field
            location_attrs = {k: v for k, v in location.items() if k != "entity_id"}
            location_map[entity_id] = location_attrs
            
        # Map time attributes - similarly excluding entity_id
        for timeperiod in article_data.get("timeperiods", []):
            entity_id = timeperiod["entity_id"]
            time_attrs = {k: v for k, v in timeperiod.items() if k != "entity_id"}
            time_map[entity_id] = time_attrs
        
        # 2. Entity integration
        for entity in article_data.get("entities", []):
            local_id = entity["id"]
            entity_type = entity["type"]
            normalized_text = entity.get("normalized", entity["text"])
            
            # Get attributes
            attributes = None
            if entity_type == "LOCATION" and local_id in location_map:
                attributes = location_map[local_id]
            elif entity_type == "TIME" and local_id in time_map:
                attributes = time_map[local_id]
            
            # First check similarity with existing global entities
            matched_entity = None
            for global_id, global_entity in self.global_entities.items():
                if self.are_entities_similar(entity, global_entity):
                    matched_entity = global_entity
                    self.id_mapping[(article_id, local_id)] = global_id
                    
                    # Add source information
                    if "sources" not in global_entity:
                        global_entity["sources"] = []
                    if article_id not in global_entity["sources"]:
                        global_entity["sources"].append(article_id)
                    
                    # Update basic attributes if confidence is higher
                    if entity["confidence"] > global_entity["confidence"]:
                        global_entity["text"] = entity["text"]
                        global_entity["confidence"] = entity["confidence"]
                        if "normalized" in entity:
                            global_entity["normalized"] = entity["normalized"]
                    
                    # Smart merge of attribute information
                    if attributes:
                        if entity_type == "LOCATION":
                            self.merge_location_attributes(global_entity, attributes, entity["confidence"])
                        elif entity_type == "TIME":
                            self.merge_time_attributes(global_entity, attributes, entity["confidence"])
                    
                    if self.debug_mode:
                        print(f"  Matched entity: {entity['text']} ({entity_type}) with global ID {global_id}")
                    
                    break
            
            # Create new entity if no match found
            if not matched_entity:
                global_id = self.create_global_entity_id(entity_type, normalized_text, attributes)
                
                new_entity = {
                    "id": global_id,
                    "type": entity_type,
                    "text": entity["text"],
                    "confidence": entity["confidence"],
                    "sources": [article_id]
                }
                
                if "normalized" in entity:
                    new_entity["normalized"] = entity["normalized"]
                
                # Integrate attribute data
                if attributes:
                    if entity_type == "LOCATION":
                        for key in attributes:
                            if key != "type":  # Don't overwrite the type field
                                new_entity[key] = attributes[key]
                    elif entity_type == "TIME":
                        for key in attributes:
                            if key != "type":  # Don't overwrite the type field
                                new_entity[key] = attributes[key]
                
                self.global_entities[global_id] = new_entity
                self.id_mapping[(article_id, local_id)] = global_id
                
                if self.debug_mode:
                    print(f"  Created new entity: {entity['text']} ({entity_type}) with global ID {global_id}")
        
        # 3. Integrate relations
        relations_added = 0
        for relation in article_data.get("relations", []):
            # Map global IDs for the subject and object of the relation
            subject_key = (article_id, relation["subject"])
            object_key = (article_id, relation["object"])
            
            if subject_key not in self.id_mapping or object_key not in self.id_mapping:
                if self.debug_mode:
                    print(f"  Skipping relation: missing entity mapping for {subject_key} or {object_key}")
                continue  # Skip if mapping is missing
            
            subject_global = self.id_mapping[subject_key]
            object_global = self.id_mapping[object_key]
            
            # Map time and location context
            context_time_global = None
            if "context_time" in relation and (article_id, relation["context_time"]) in self.id_mapping:
                context_time_global = self.id_mapping[(article_id, relation["context_time"])]
                
            context_location_global = None
            if "context_location" in relation and (article_id, relation["context_location"]) in self.id_mapping:
                context_location_global = self.id_mapping[(article_id, relation["context_location"])]
            
            # Create relation signature (to prevent duplicates)
            signature = f"{subject_global}_{relation['predicate']}_{object_global}"
            if context_time_global:
                signature += f"_time_{context_time_global}"
            if context_location_global:
                signature += f"_loc_{context_location_global}"
            
            # Check for duplicate with existing relations
            is_duplicate = False
            for existing_relation in self.global_relations:
                existing_sig = f"{existing_relation['subject']}_{existing_relation['predicate']}_{existing_relation['object']}"
                if "context_time" in existing_relation:
                    existing_sig += f"_time_{existing_relation['context_time']}"
                if "context_location" in existing_relation:
                    existing_sig += f"_loc_{existing_relation['context_location']}"
                
                if signature == existing_sig:
                    is_duplicate = True
                    # Update if confidence is higher
                    if relation["confidence"] > existing_relation["confidence"]:
                        existing_relation["confidence"] = relation["confidence"]
                    
                    # Add source information
                    if "sources" not in existing_relation:
                        existing_relation["sources"] = []
                    if article_id not in existing_relation["sources"]:
                        existing_relation["sources"].append(article_id)
                    
                    if self.debug_mode:
                        print(f"  Found duplicate relation: {relation['predicate']}")
                    
                    break
            
            # Add new relation if not a duplicate
            if not is_duplicate:
                # Generate relation hash ID
                signature = f"{subject_global}_{relation['predicate']}_{object_global}"
                if context_time_global:
                    signature += f"_time_{context_time_global}"
                if context_location_global:
                    signature += f"_loc_{context_location_global}"
                relation_id = "R" + hashlib.md5(signature.encode()).hexdigest()[:11]
                
                new_relation = {
                    "id": relation_id,
                    "subject": subject_global,
                    "predicate": relation["predicate"],
                    "object": object_global,
                    "confidence": relation["confidence"],
                    "sources": [article_id]
                }
                
                if context_time_global:
                    new_relation["context_time"] = context_time_global
                if context_location_global:
                    new_relation["context_location"] = context_location_global
                
                self.global_relations.append(new_relation)
                relations_added += 1
        
        if self.debug_mode:
            print(f"  Added {relations_added} new relations")
    
    def integrate_multiple_articles(self, articles_data):
        """
        Process multiple article data in batch
        """
        for article_id, article_data in articles_data.items():
            self.integrate_article(article_id, article_data)
        
        return {
            "entities": list(self.global_entities.values()),
            "relations": self.global_relations
        }
    
    def validate_entity_mappings(self):
        """
        Validate entity integration results and provide statistics
        """
        # Statistics by entity type
        entity_types = {}
        location_with_coords = 0
        location_without_coords = 0
        time_with_dates = 0
        time_without_dates = 0
        
        for entity in self.global_entities.values():
            entity_type = entity["type"]
            entity_types[entity_type] = entity_types.get(entity_type, 0) + 1
            
            # Validate location entity attributes
            if entity_type == "LOCATION":
                if "latitude" in entity and "longitude" in entity and entity["latitude"] and entity["longitude"]:
                    location_with_coords += 1
                else:
                    location_without_coords += 1
            
            # Validate time entity attributes
            elif entity_type == "TIME":
                if "start_date" in entity and entity["start_date"]:
                    time_with_dates += 1
                else:
                    time_without_dates += 1
        
        # Relation statistics
        relations_with_time = sum(1 for r in self.global_relations if "context_time" in r and r["context_time"])
        relations_with_location = sum(1 for r in self.global_relations if "context_location" in r and r["context_location"])
        
        # Print results
        print("\n=== Entity Integration Validation ===")
        print(f"Total unique entities: {len(self.global_entities)}")
        print(f"Total relations: {len(self.global_relations)}")
        
        print("\nEntity types:")
        for entity_type, count in sorted(entity_types.items()):
            print(f"  {entity_type}: {count}")
        
        print("\nLocation entities:")
        total_locations = entity_types.get("LOCATION", 0)
        if total_locations > 0:
            print(f"  With coordinates: {location_with_coords} ({location_with_coords/total_locations*100:.1f}%)")
            print(f"  Without coordinates: {location_without_coords} ({location_without_coords/total_locations*100:.1f}%)")
        
        print("\nTime entities:")
        total_times = entity_types.get("TIME", 0)
        if total_times > 0:
            print(f"  With date information: {time_with_dates} ({time_with_dates/total_times*100:.1f}%)")
            print(f"  Without date information: {time_without_dates} ({time_without_dates/total_times*100:.1f}%)")
        
        print("\nRelation contexts:")
        if self.global_relations:
            print(f"  With time context: {relations_with_time} ({relations_with_time/len(self.global_relations)*100:.1f}%)")
            print(f"  With location context: {relations_with_location} ({relations_with_location/len(self.global_relations)*100:.1f}%)")
        
        return {
            "entities_by_type": entity_types,
            "location_with_coords": location_with_coords,
            "location_without_coords": location_without_coords,
            "time_with_dates": time_with_dates,
            "time_without_dates": time_without_dates,
            "relations_with_time": relations_with_time,
            "relations_with_location": relations_with_location
        }
    
    def write_to_json(self, output_file):
        """
        Save integrated data to a JSON file
        """
        output_data = {
            "entities": list(self.global_entities.values()),
            "relations": self.global_relations
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
            
        print(f"Integrated data saved to {output_file}")
    
    def write_to_csv_for_neo4j(self, output_dir):
        """
        Generate CSV files for Neo4j import
        """
        os.makedirs(output_dir, exist_ok=True)
        
        # 1. Entity basic information CSV - using proper CSV library
        with open(f"{output_dir}/entities.csv", 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
            # Header
            writer.writerow(["entity_id", "type", "text", "normalized", "confidence", "sources"])
            
            # Data
            for entity in self.global_entities.values():
                sources = "|".join(entity.get("sources", []))
                normalized = entity.get("normalized", "")
                writer.writerow([
                    entity['id'], 
                    entity['type'], 
                    entity['text'], 
                    normalized, 
                    entity['confidence'], 
                    sources
                ])
        
        # 2. Location entity attributes CSV
        with open(f"{output_dir}/locations.csv", 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
            # Header
            writer.writerow(["entity_id", "latitude", "longitude", "display_name", "location_type", 
                           "importance", "bbox_south", "bbox_north", "bbox_west", "bbox_east"])
            
            # Data - process all LOCATION entities
            location_count = 0
            for entity in self.global_entities.values():
                if entity["type"] == "LOCATION":
                    # Set default values
                    row = [
                        entity['id'],
                        entity.get("latitude", ""),
                        entity.get("longitude", ""),
                        entity.get("display_name", ""),
                        entity.get("location_type", ""),
                        entity.get("importance", ""),
                        entity.get("bbox_south", ""),
                        entity.get("bbox_north", ""),
                        entity.get("bbox_west", ""),
                        entity.get("bbox_east", "")
                    ]
                    writer.writerow(row)
                    location_count += 1
            
            print(f"Wrote {location_count} location entities to locations.csv")
        
        # 3. Time entity attributes CSV
        with open(f"{output_dir}/timeperiods.csv", 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
            # Header
            writer.writerow(["entity_id", "precision", "type", "start_date", "end_date", "date_reliability"])

            # Data - process all TIME entities
            time_count = 0
            for entity in self.global_entities.values():
                if entity["type"] == "TIME":
                    row = [
                        entity['id'],
                        entity.get("precision", "UNKNOWN"),
                        entity.get("type", "UNKNOWN"),
                        entity.get("start_date", ""),
                        entity.get("end_date", entity.get("start_date", "")),
                        entity.get("date_reliability", "")
                    ]
                    writer.writerow(row)
                    time_count += 1

            print(f"Wrote {time_count} time entities to timeperiods.csv")
        
        # 4. Relations CSV
        with open(f"{output_dir}/relations.csv", 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
            # Header
            writer.writerow([
                "relation_id", "subject_id", "predicate", "object_id", 
                "confidence", "context_time_id", "context_location_id", "sources"
            ])
            
            # Data
            for relation in self.global_relations:
                sources = "|".join(relation.get("sources", []))
                row = [
                    relation['id'],
                    relation['subject'],
                    relation['predicate'],
                    relation['object'],
                    relation['confidence'],
                    relation.get("context_time", ""),
                    relation.get("context_location", ""),
                    sources
                ]
                writer.writerow(row)
        
        print(f"CSV files for Neo4j import generated in {output_dir}")

# Main execution code
def main():
    # Input directory (output from geo_temp_enhancer.py)
    input_dir = os.path.join(ROOT_DIR, "enhanced_results")
    
    # Output file/directory
    output_dir = os.path.join(ROOT_DIR, "integrated_results")
    os.makedirs(output_dir, exist_ok=True)  # Create the directory if it doesn't exist
    output_json = os.path.join(output_dir, "integrated_knowledge_graph.json")
    output_csv_dir = os.path.join(ROOT_DIR, "neo4j_import")
    
    # Debug mode enabled or not
    debug_mode = True
    
    # Create global entity integrator
    integrator = GlobalEntityIntegrator(debug_mode=debug_mode)
    
    # Process each JSON file sequentially
    json_files = sorted(glob.glob(f"{input_dir}/*.json"))
    total_articles = 0
    
    for i, json_file in enumerate(json_files):
        print(f"[{i+1}/{len(json_files)}] Integrating {json_file}...")
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
                # Track number of articles processed in this file
                file_articles = 0
                
                # Handle either single document or multiple document format
                if isinstance(data, dict) and all(isinstance(value, dict) for value in data.values()) and "entities" not in data:
                    # Format containing multiple articles
                    for article_id, article_data in data.items():
                        unique_id = f"{os.path.basename(json_file).replace('.json', '')}_{article_id}"
                        integrator.integrate_article(unique_id, article_data)
                        file_articles += 1
                else:
                    # Single article format
                    article_id = f"{os.path.basename(json_file).replace('.json', '')}"
                    integrator.integrate_article(article_id, data)
                    file_articles += 1
                
                total_articles += file_articles
                print(f"  → {file_articles} articles processed from this file")
                print(f"  → Running total: {len(integrator.global_entities)} unique entities, {len(integrator.global_relations)} unique relations")
        except Exception as e:
            print(f"Error processing file {json_file}: {e}")
            print("Continuing with next file...")
    
    # Generate and save integrated results
    integrated_data = {
        "entities": list(integrator.global_entities.values()),
        "relations": integrator.global_relations
    }
    
    # Save to JSON in the integrated_results directory
    with open(output_json, 'w', encoding='utf-8') as f:
        json.dump(integrated_data, f, ensure_ascii=False, indent=2)
    
    # Validate integration results
    validation_results = integrator.validate_entity_mappings()
    
    # Generate CSV files for Neo4j
    integrator.write_to_csv_for_neo4j(output_csv_dir)
    
    # Print final statistics
    print(f"\nIntegration complete!")
    print(f"Processed {len(json_files)} files with {total_articles} total articles")
    print(f"Integrated {len(integrator.global_entities)} unique entities and {len(integrator.global_relations)} unique relations")
    
    # Warn about missing attribute information
    if validation_results["location_without_coords"] > 0:
        print(f"\nWARNING: {validation_results['location_without_coords']} location entities are missing coordinate information")
    
    if validation_results["time_without_dates"] > 0:
        print(f"\nWARNING: {validation_results['time_without_dates']} time entities are missing date information")

if __name__ == "__main__":
    main()